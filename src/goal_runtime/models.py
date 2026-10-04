"""Goal Definition Models and Primitives — AgenticOS Layer 3.

Provides the internal representation of a declarative Goal, its constraints,
lifecycle state tracking, and refinement/decomposition hierarchy.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from src.core.context import TraceContext, current_utc_timestamp
from src.core.status import GoalStatus, VALID_GOAL_TRANSITIONS, StateTransitionRecord
from src.core.errors import AgenticOSError



@dataclass
class Goal:
    """Internal domain model of a Goal in the Goal Runtime.
    
    Fields:
        goal_id: Unique canonical goal identifier (e.g. 'goal-uuid').
        intent_id: Associated intent identifier from Intent Intelligence.
        user_id: Owner / authenticated user requesting the goal.
        action_name: Classified action verb/name (e.g. 'backup_directory').
        state: Current lifecycle state (GoalStatus enum).
        priority: Priority integer between 1 (lowest) and 10 (critical). Default: 5.
        constraints: Dict of operational constraints (timeout_seconds, max_retries, etc.).
        parameters: Execution parameters passed from Intent Intelligence.
        trace_context: Distributed tracing context linked to originating request.
        parent_goal_id: Identifier of parent goal if this is a refined sub-goal.
        sub_goal_ids: List of child goal IDs created via decomposition.
        refinement_metadata: Metadata describing decomposition/refinement details.
        cancellation_reason: Reason string if goal was cancelled.
        replan_reason: Reason string if goal was replanned.
        created_at: ISO-8601 UTC timestamp of goal creation.
        updated_at: ISO-8601 UTC timestamp of last update.
        history: Sequential audit log of lifecycle state transitions.
    """
    goal_id: str
    intent_id: str
    user_id: str
    action_name: str
    state: GoalStatus
    priority: int
    constraints: Dict[str, Any]
    parameters: Dict[str, Any]
    trace_context: TraceContext
    parent_goal_id: Optional[str] = None
    sub_goal_ids: List[str] = field(default_factory=list)
    refinement_metadata: Dict[str, Any] = field(default_factory=dict)
    cancellation_reason: Optional[str] = None
    replan_reason: Optional[str] = None
    created_at: str = field(default_factory=current_utc_timestamp)
    updated_at: str = field(default_factory=current_utc_timestamp)
    history: List[StateTransitionRecord] = field(default_factory=list)

    def transition_to(self, new_state: GoalStatus, detail: str = "") -> None:
        """Safely transition goal state or raise structured AgenticOSError.
        
        Args:
            new_state: Target GoalStatus enum.
            detail: Optional reason or context for the transition.
            
        Raises:
            AgenticOSError: If requested transition is forbidden by state machine.
        """
        allowed = VALID_GOAL_TRANSITIONS.get(self.state, set())
        if new_state not in allowed:
            raise AgenticOSError(
                message=f"Illegal goal state transition from {self.state.value} to {new_state.value}",
                error_code="INVALID_STATE_TRANSITION",
                details={
                    "goal_id": self.goal_id,
                    "current_state": self.state.value,
                    "target_state": new_state.value,
                    "allowed_transitions": [s.value for s in allowed]
                }
            )
        record = StateTransitionRecord(
            from_state=self.state, # type: ignore
            to_state=new_state,    # type: ignore
            timestamp=current_utc_timestamp(),
            detail=detail
        )
        self.history.append(record)
        self.state = new_state
        self.updated_at = current_utc_timestamp()

    def to_dict(self) -> Dict[str, Any]:
        """Convert goal model to dictionary conforming to docs/api-draft.md."""
        return {
            "goal_id": self.goal_id,
            "intent_id": self.intent_id,
            "user_id": self.user_id,
            "action_name": self.action_name,
            "state": self.state.value,
            "priority": self.priority,
            "constraints": dict(self.constraints),
            "parameters": dict(self.parameters),
            "parent_goal_id": self.parent_goal_id,
            "sub_goal_ids": list(self.sub_goal_ids),
            "refinement_metadata": dict(self.refinement_metadata),
            "cancellation_reason": self.cancellation_reason,
            "replan_reason": self.replan_reason,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "trace_context": self.trace_context.to_dict(),
            "history": [h.to_dict() for h in self.history],
        }
