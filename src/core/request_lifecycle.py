"""Request Lifecycle Coordinator for AgenticOS v0.1 Alpha.

This module coordinates the lifecycle of incoming requests as they enter
the Agentic Core, linking:
  Incoming Request
  → Request Context & Trace Context
  → Intent Validation & Ambiguity Detection
  → Goal Runtime Boundary (IF-01 Handoff)
  → Structured Result / Error

Complies with Vivek's 29 September milestone requirements.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict, Any, Optional, List
from .context import TraceContext, RequestContext, current_utc_timestamp
from .status import RequestStatus, VALID_REQUEST_TRANSITIONS, StateTransitionRecord
from .errors import (
    AgenticOSError,
    ValidationError,
    PolicyViolationError,
)
from .validation import DraftSchemaValidator

if TYPE_CHECKING:
    from src.goal_runtime.interface import GoalRuntimeInterface



@dataclass
class RequestLifecycleResult:
    """Structured outcome of request lifecycle execution."""
    request_id: str
    trace_id: str
    status: RequestStatus
    success: bool
    trace_context: TraceContext
    goal_record: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None
    clarification_required: bool = False
    clarification_prompt: Optional[str] = None
    history: List[StateTransitionRecord] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert the result into a clean serializable dictionary."""
        return {
            "request_id": self.request_id,
            "trace_id": self.trace_id,
            "status": self.status.value,
            "success": self.success,
            "goal_record": self.goal_record,
            "error": self.error,
            "clarification_required": self.clarification_required,
            "clarification_prompt": self.clarification_prompt,
            "trace_context": self.trace_context.to_dict(),
            "history": [h.to_dict() for h in self.history],
        }


class RequestLifecycle:
    """Stateful coordinator for managing an individual request's journey.
    
    Attributes:
        goal_runtime: Optional GoalRuntimeInterface instance for downstream handoff.
        confidence_threshold: Minimum confidence score below which intent is considered ambiguous.
    """

    def __init__(
        self,
        goal_runtime: Optional[GoalRuntimeInterface] = None,
        confidence_threshold: float = 0.70
    ) -> None:
        self.goal_runtime = goal_runtime
        self.confidence_threshold = confidence_threshold
        self._current_state = RequestStatus.RECEIVED
        self._history: List[StateTransitionRecord] = []

    @property
    def current_state(self) -> RequestStatus:
        """Current lifecycle state."""
        return self._current_state

    def transition_to(self, new_state: RequestStatus, detail: str = "") -> None:
        """Safely transition to a new state or raise a structured error.
        
        Args:
            new_state: Target RequestStatus.
            detail: Optional descriptive reason for the transition.
            
        Raises:
            AgenticOSError: If the requested transition is illegal.
        """
        allowed = VALID_REQUEST_TRANSITIONS.get(self._current_state, set())
        if new_state not in allowed:
            raise AgenticOSError(
                message=f"Illegal state transition from {self._current_state.value} to {new_state.value}",
                error_code="INVALID_STATE_TRANSITION",
                details={
                    "current_state": self._current_state.value,
                    "target_state": new_state.value,
                    "allowed_transitions": [s.value for s in allowed],
                }
            )
        record = StateTransitionRecord(
            from_state=self._current_state,
            to_state=new_state,
            detail=detail
        )
        self._history.append(record)
        self._current_state = new_state

    def execute(
        self,
        raw_request: Any,
        request_context: Optional[RequestContext] = None
    ) -> RequestLifecycleResult:
        """Process an incoming request through the canonical lifecycle stages.
        
        Args:
            raw_request: Incoming request payload (dict representing request or IntentPayload).
            request_context: Optional existing RequestContext from upstream caller.
            
        Returns:
            RequestLifecycleResult with final state, goal record, or structured error.
        """
        # --- Stage 1: Context & Identity Establishment ---
        trace: TraceContext
        user_id = "unknown_user"
        request_id: Optional[str] = None

        # Check if raw_request is malformed (must be dict)
        if not isinstance(raw_request, dict):
            # Fallback trace context for reporting
            trace = TraceContext.new_root()
            self.transition_to(RequestStatus.REJECTED, detail="Malformed request: not a dict")
            return RequestLifecycleResult(
                request_id=trace.request_id,
                trace_id=trace.trace_id,
                status=self._current_state,
                success=False,
                trace_context=trace,
                error={
                    "error_code": "MALFORMED_REQUEST",
                    "message": f"Expected request payload to be a dictionary, got {type(raw_request).__name__}",
                },
                history=list(self._history)
            )

        # Extract or establish RequestContext / TraceContext
        if request_context is not None:
            user_id = request_context.user_id
            trace = request_context.trace.child_span()
            request_id = request_context.trace.request_id
        elif "trace_context" in raw_request and isinstance(raw_request["trace_context"], dict):
            try:
                trace = TraceContext.from_dict(raw_request["trace_context"]).child_span()
                request_id = trace.request_id
            except Exception as e:
                trace = TraceContext.new_root()
                self.transition_to(RequestStatus.REJECTED, detail="Invalid trace context")
                return RequestLifecycleResult(
                    request_id=trace.request_id,
                    trace_id=trace.trace_id,
                    status=self._current_state,
                    success=False,
                    trace_context=trace,
                    error={
                        "error_code": "INVALID_TRACE_CONTEXT",
                        "message": f"Malformed trace_context in request: {str(e)}",
                    },
                    history=list(self._history)
                )
        else:
            request_id = raw_request.get("request_id")
            trace = TraceContext.new_root(request_id=request_id)

        user_id = raw_request.get("user_id", user_id)
        if not user_id or user_id == "unknown_user":
            # Missing user context
            self.transition_to(RequestStatus.REJECTED, detail="Missing user_id identity")
            return RequestLifecycleResult(
                request_id=trace.request_id,
                trace_id=trace.trace_id,
                status=self._current_state,
                success=False,
                trace_context=trace,
                error={
                    "error_code": "MISSING_USER_CONTEXT",
                    "message": "Incoming request lacks required 'user_id' identity.",
                },
                history=list(self._history)
            )

        # --- Stage 2: Intent Validation & Ambiguity Inspection ---
        try:
            self.transition_to(RequestStatus.VALIDATING, detail="Validating intent payload")
        except AgenticOSError as err:
            return self._build_transition_error_result(trace, err)

        # Extract intent payload: could be inside raw_request["intent"] or raw_request itself
        intent_payload: Dict[str, Any]
        if "intent" in raw_request and isinstance(raw_request["intent"], dict):
            intent_payload = dict(raw_request["intent"])
        else:
            intent_payload = dict(raw_request)

        # Ensure user_id and trace_context are embedded in intent_payload
        intent_payload.setdefault("user_id", user_id)
        intent_payload["trace_context"] = trace.to_dict()

        # Check required fields
        required_fields = ["intent_id", "user_id", "action_name", "parameters", "confidence_score"]
        missing = [f for f in required_fields if f not in intent_payload]
        if missing:
            self.transition_to(RequestStatus.REJECTED, detail=f"Missing fields: {missing}")
            return RequestLifecycleResult(
                request_id=trace.request_id,
                trace_id=trace.trace_id,
                status=self._current_state,
                success=False,
                trace_context=trace,
                error={
                    "error_code": "VALIDATION_ERROR",
                    "message": f"Intent payload missing required fields: {missing}",
                    "details": {"missing_fields": missing},
                },
                history=list(self._history)
            )

        # Validate confidence score type and range
        confidence = intent_payload.get("confidence_score")
        if not isinstance(confidence, (int, float)) or not (0.0 <= confidence <= 1.0):
            self.transition_to(RequestStatus.REJECTED, detail="Invalid confidence score")
            return RequestLifecycleResult(
                request_id=trace.request_id,
                trace_id=trace.trace_id,
                status=self._current_state,
                success=False,
                trace_context=trace,
                error={
                    "error_code": "INVALID_CONFIDENCE_SCORE",
                    "message": f"Confidence score must be a number between 0.0 and 1.0, got {confidence}",
                },
                history=list(self._history)
            )

        # Check Ambiguity / Confidence Threshold (Task 5 requirement)
        if confidence < self.confidence_threshold:
            action_name = intent_payload.get("action_name", "unknown")
            clarification_msg = (
                f"Intent '{action_name}' is ambiguous (confidence {confidence:.2f} < "
                f"threshold {self.confidence_threshold:.2f}). Please clarify your goal."
            )
            self.transition_to(RequestStatus.REJECTED, detail="Intent confidence below threshold")
            return RequestLifecycleResult(
                request_id=trace.request_id,
                trace_id=trace.trace_id,
                status=self._current_state,
                success=False,
                trace_context=trace,
                clarification_required=True,
                clarification_prompt=clarification_msg,
                error={
                    "error_code": "AMBIGUOUS_INTENT",
                    "message": clarification_msg,
                    "confidence": confidence,
                    "threshold": self.confidence_threshold,
                },
                history=list(self._history)
            )

        # Run draft schema validation
        try:
            DraftSchemaValidator.validate_intent_payload(intent_payload)
        except ValidationError as val_err:
            self.transition_to(RequestStatus.REJECTED, detail=f"Schema violation: {val_err.message}")
            return RequestLifecycleResult(
                request_id=trace.request_id,
                trace_id=trace.trace_id,
                status=self._current_state,
                success=False,
                trace_context=trace,
                error=val_err.to_dict(),
                history=list(self._history)
            )

        # Successfully validated
        self.transition_to(RequestStatus.VALIDATED, detail="Intent schema and confidence verified")

        # --- Stage 3: Goal Runtime Boundary Handoff (IF-01) ---
        if self.goal_runtime is None:
            # Standalone validation mode (no goal runtime attached)
            self.transition_to(RequestStatus.PROCESSING, detail="No GoalRuntime attached (standalone mode)")
            self.transition_to(RequestStatus.COMPLETED, detail="Lifecycle completed at validation boundary")
            return RequestLifecycleResult(
                request_id=trace.request_id,
                trace_id=trace.trace_id,
                status=self._current_state,
                success=True,
                trace_context=trace,
                goal_record={"status": "VALIDATED_NO_GOAL_RUNTIME_ATTACHED"},
                history=list(self._history)
            )

        # Transition to PROCESSING for Goal Runtime execution
        self.transition_to(RequestStatus.PROCESSING, detail="Dispatching intent to GoalRuntimeInterface")
        goal_span = trace.child_span()

        try:
            goal_record = self.goal_runtime.create_goal(intent_payload, goal_span)
            self.transition_to(RequestStatus.COMPLETED, detail="Goal created successfully")
            return RequestLifecycleResult(
                request_id=trace.request_id,
                trace_id=trace.trace_id,
                status=self._current_state,
                success=True,
                trace_context=goal_span,
                goal_record=goal_record,
                history=list(self._history)
            )
        except AgenticOSError as os_err:
            self.transition_to(RequestStatus.FAILED, detail=f"GoalRuntime error: {os_err.message}")
            return RequestLifecycleResult(
                request_id=trace.request_id,
                trace_id=trace.trace_id,
                status=self._current_state,
                success=False,
                trace_context=goal_span,
                error=os_err.to_dict(),
                history=list(self._history)
            )
        except Exception as unhandled_err:
            self.transition_to(RequestStatus.FAILED, detail=f"Unhandled failure: {str(unhandled_err)}")
            return RequestLifecycleResult(
                request_id=trace.request_id,
                trace_id=trace.trace_id,
                status=self._current_state,
                success=False,
                trace_context=goal_span,
                error={
                    "error_code": "GOAL_RUNTIME_INVOCATION_ERROR",
                    "message": str(unhandled_err),
                    "type": type(unhandled_err).__name__,
                },
                history=list(self._history)
            )

    def _build_transition_error_result(
        self,
        trace: TraceContext,
        err: AgenticOSError
    ) -> RequestLifecycleResult:
        """Helper to build a structured result when an internal state transition fails."""
        return RequestLifecycleResult(
            request_id=trace.request_id,
            trace_id=trace.trace_id,
            status=self._current_state,
            success=False,
            trace_context=trace,
            error=err.to_dict(),
            history=list(self._history)
        )
