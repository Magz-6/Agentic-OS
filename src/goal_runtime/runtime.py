"""Concrete Goal Runtime Implementation — AgenticOS Layer 3.

Implements GoalRuntimeInterface to manage declarative Goal lifecycles:
- Goal creation from IntentPayload (G01)
- Goal parameter and constraint updates (G02)
- Graceful Goal cancellation (G03)
- Dynamic Goal replanning triggers (G04)
- Goal prioritization and constraint validation
- Goal decomposition/refinement hierarchy
"""

from __future__ import annotations
from typing import Dict, Any, List, Optional
from src.core.context import TraceContext, generate_id, current_utc_timestamp
from src.core.status import GoalStatus
from src.core.errors import (
    NotFoundError,
    ValidationError,
    AgenticOSError,
)
from .interface import GoalRuntimeInterface
from .models import Goal


class GoalRuntime(GoalRuntimeInterface):
    """Concrete implementation of Goal Runtime service for AgenticOS."""

    def __init__(
        self,
        default_priority: int = 5,
        default_timeout_seconds: int = 120
    ) -> None:
        self.default_priority = default_priority
        self.default_timeout_seconds = default_timeout_seconds
        self._goals: Dict[str, Goal] = {}

    def _validate_priority(self, priority: Any) -> int:
        """Validate and return integer priority in range 1..10."""
        if not isinstance(priority, int) or isinstance(priority, bool) or not (1 <= priority <= 10):
            raise ValidationError(
                message=f"Field 'priority' must be an integer between 1 and 10, got {priority}",
                details={"priority": priority}
            )
        return priority

    def _validate_constraints(self, constraints: Any) -> Dict[str, Any]:
        """Validate operational constraints dictionary."""
        if not isinstance(constraints, dict):
            raise ValidationError(
                message=f"Field 'constraints' must be a dictionary, got {type(constraints).__name__}",
                details={"constraints": constraints}
            )
        validated = dict(constraints)

        # Check timeout_seconds if provided
        if "timeout_seconds" in validated:
            timeout = validated["timeout_seconds"]
            if not isinstance(timeout, int) or isinstance(timeout, bool) or timeout <= 0:
                raise ValidationError(
                    message=f"Constraint 'timeout_seconds' must be a positive integer, got {timeout}",
                    details={"timeout_seconds": timeout}
                )

        # Check max_retries if provided
        if "max_retries" in validated:
            retries = validated["max_retries"]
            if not isinstance(retries, int) or isinstance(retries, bool) or retries < 0:
                raise ValidationError(
                    message=f"Constraint 'max_retries' must be a non-negative integer, got {retries}",
                    details={"max_retries": retries}
                )

        return validated

    def create_goal(
        self,
        intent_payload: Dict[str, Any],
        trace_context: TraceContext
    ) -> Dict[str, Any]:
        """Create and register a new Goal from an IntentPayload (G01).
        
        Args:
            intent_payload: Dict conforming to provisional IntentPayload schema.
            trace_context: Distributed tracing context.
            
        Returns:
            Goal record dict conforming to provisional GoalDefinition schema.
            
        Raises:
            ValidationError: If required fields, priority, or constraints are invalid.
        """
        if not isinstance(intent_payload, dict):
            raise ValidationError("Expected intent_payload to be a dictionary")

        intent_id = intent_payload.get("intent_id", generate_id("int-"))
        action_name = intent_payload.get("action_name")
        if not action_name or not isinstance(action_name, str):
            raise ValidationError("Intent payload missing valid 'action_name'")

        user_id = intent_payload.get("user_id", "unknown_user")
        parameters = intent_payload.get("parameters", {})
        if not isinstance(parameters, dict):
            raise ValidationError("Field 'parameters' must be a dictionary")

        # Validate priority
        raw_priority = intent_payload.get("priority", self.default_priority)
        priority = self._validate_priority(raw_priority)

        # Validate constraints
        raw_constraints = intent_payload.get("constraints", {})
        constraints = self._validate_constraints(raw_constraints)
        if "timeout_seconds" not in constraints:
            constraints["timeout_seconds"] = self.default_timeout_seconds

        goal_id = generate_id("goal-")
        child_trace = trace_context.child_span()

        goal = Goal(
            goal_id=goal_id,
            intent_id=intent_id,
            user_id=user_id,
            action_name=action_name,
            state=GoalStatus.SUBMITTED,
            priority=priority,
            constraints=constraints,
            parameters=dict(parameters),
            trace_context=child_trace
        )

        # Transition from SUBMITTED to ACTIVE for execution readiness
        goal.transition_to(GoalStatus.ACTIVE, detail="Goal validated and activated")
        self._goals[goal_id] = goal

        return goal.to_dict()

    def get_goal(
        self,
        goal_id: str,
        trace_context: TraceContext
    ) -> Dict[str, Any]:
        """Retrieve the current state of an existing Goal by its ID.
        
        Args:
            goal_id: Canonical goal identifier.
            trace_context: Distributed tracing context.
            
        Returns:
            Goal record dict.
            
        Raises:
            NotFoundError: If goal_id does not exist.
        """
        if goal_id not in self._goals:
            raise NotFoundError(
                message=f"Goal '{goal_id}' not found in registry",
                trace_context=trace_context,
                details={"goal_id": goal_id}
            )
        return self._goals[goal_id].to_dict()

    def update_goal(
        self,
        goal_id: str,
        updates: Dict[str, Any],
        trace_context: TraceContext
    ) -> Dict[str, Any]:
        """Update constraints, priority, or parameters of an active Goal (G02).
        
        Args:
            goal_id: Target goal identifier.
            updates: Dictionary of fields to update.
            trace_context: Distributed tracing context.
            
        Returns:
            Updated goal record dict.
            
        Raises:
            NotFoundError: If goal does not exist.
            AgenticOSError: If goal is in a terminal state.
            ValidationError: If updates attempt to alter immutable fields or invalid data.
        """
        if goal_id not in self._goals:
            raise NotFoundError(
                message=f"Goal '{goal_id}' not found",
                trace_context=trace_context,
                details={"goal_id": goal_id}
            )

        goal = self._goals[goal_id]

        # Prevent updates to terminal goals
        if goal.state in (GoalStatus.COMPLETED, GoalStatus.FAILED, GoalStatus.CANCELLED):
            raise AgenticOSError(
                message=f"Cannot update goal '{goal_id}' in terminal state '{goal.state.value}'",
                error_code="GOAL_TERMINAL_STATE",
                trace_context=trace_context,
                details={"goal_id": goal_id, "state": goal.state.value}
            )

        # Disallow changing goal_id
        if "goal_id" in updates and updates["goal_id"] != goal_id:
            raise ValidationError(
                message="Cannot modify immutable field 'goal_id'",
                details={"original": goal_id, "attempted": updates["goal_id"]}
            )

        # Update priority if present
        if "priority" in updates:
            goal.priority = self._validate_priority(updates["priority"])

        # Update parameters if present
        if "parameters" in updates:
            if not isinstance(updates["parameters"], dict):
                raise ValidationError("Field 'parameters' must be a dictionary")
            goal.parameters.update(updates["parameters"])

        # Update constraints if present
        if "constraints" in updates:
            validated_c = self._validate_constraints(updates["constraints"])
            goal.constraints.update(validated_c)

        # Update action_name if present
        if "action_name" in updates:
            if not isinstance(updates["action_name"], str) or not updates["action_name"]:
                raise ValidationError("Field 'action_name' must be a non-empty string")
            goal.action_name = updates["action_name"]

        # Update refinement metadata if present
        if "refinement_metadata" in updates:
            if not isinstance(updates["refinement_metadata"], dict):
                raise ValidationError("Field 'refinement_metadata' must be a dictionary")
            goal.refinement_metadata.update(updates["refinement_metadata"])

        goal.updated_at = current_utc_timestamp()
        return goal.to_dict()

    def cancel_goal(
        self,
        goal_id: str,
        reason: str,
        trace_context: TraceContext
    ) -> Dict[str, Any]:
        """Abort an active Goal and signal downstream workflows to halt (G03).
        
        Args:
            goal_id: Target goal identifier.
            reason: Human or policy reason for cancellation.
            trace_context: Distributed tracing context.
            
        Returns:
            Cancelled goal record dict with status 'CANCELLED'.
            
        Raises:
            NotFoundError: If goal does not exist.
            AgenticOSError: If goal is already in a non-cancellable terminal state.
        """
        if goal_id not in self._goals:
            raise NotFoundError(
                message=f"Goal '{goal_id}' not found",
                trace_context=trace_context,
                details={"goal_id": goal_id}
            )

        goal = self._goals[goal_id]

        if goal.state == GoalStatus.CANCELLED:
            # Idempotent return if already cancelled
            return goal.to_dict()

        if goal.state in (GoalStatus.COMPLETED, GoalStatus.FAILED):
            raise AgenticOSError(
                message=f"Cannot cancel goal '{goal_id}' in terminal state '{goal.state.value}'",
                error_code="INVALID_STATE_TRANSITION",
                trace_context=trace_context,
                details={"goal_id": goal_id, "state": goal.state.value}
            )

        goal.transition_to(GoalStatus.CANCELLED, detail=f"Cancellation reason: {reason}")
        goal.cancellation_reason = reason
        return goal.to_dict()

    def replan_goal(
        self,
        goal_id: str,
        trigger_reason: str,
        trace_context: TraceContext
    ) -> Dict[str, Any]:
        """Trigger dynamic re-planning for a goal following step failure (G04).
        
        Args:
            goal_id: Target goal identifier.
            trigger_reason: Description of the failure or condition triggering replan.
            trace_context: Distributed tracing context.
            
        Returns:
            Goal record transitioned to 'REPLANNING' status.
            
        Raises:
            NotFoundError: If goal does not exist.
            AgenticOSError: If goal is in a terminal state.
        """
        if goal_id not in self._goals:
            raise NotFoundError(
                message=f"Goal '{goal_id}' not found",
                trace_context=trace_context,
                details={"goal_id": goal_id}
            )

        goal = self._goals[goal_id]

        if goal.state in (GoalStatus.COMPLETED, GoalStatus.FAILED, GoalStatus.CANCELLED):
            raise AgenticOSError(
                message=f"Cannot replan goal '{goal_id}' in terminal state '{goal.state.value}'",
                error_code="INVALID_STATE_TRANSITION",
                trace_context=trace_context,
                details={"goal_id": goal_id, "state": goal.state.value}
            )

        goal.transition_to(GoalStatus.REPLANNING, detail=f"Replanning triggered: {trigger_reason}")
        goal.replan_reason = trigger_reason
        return goal.to_dict()

    def decompose_goal(
        self,
        parent_goal_id: str,
        sub_goals_data: List[Dict[str, Any]],
        trace_context: TraceContext
    ) -> List[Dict[str, Any]]:
        """Decompose a parent goal into refined child sub-goals.
        
        Args:
            parent_goal_id: Identifier of the parent goal being decomposed.
            sub_goals_data: List of intent/action dictionaries defining the sub-goals.
            trace_context: Distributed tracing context.
            
        Returns:
            List of created sub-goal record dictionaries.
            
        Raises:
            NotFoundError: If parent goal does not exist.
            AgenticOSError: If parent goal is in a terminal state.
        """
        if parent_goal_id not in self._goals:
            raise NotFoundError(
                message=f"Parent goal '{parent_goal_id}' not found",
                trace_context=trace_context,
                details={"parent_goal_id": parent_goal_id}
            )

        parent_goal = self._goals[parent_goal_id]
        if parent_goal.state in (GoalStatus.COMPLETED, GoalStatus.FAILED, GoalStatus.CANCELLED):
            raise AgenticOSError(
                message=f"Cannot decompose goal '{parent_goal_id}' in terminal state '{parent_goal.state.value}'",
                error_code="GOAL_TERMINAL_STATE",
                trace_context=trace_context
            )

        created_sub_goals = []
        for idx, sub_data in enumerate(sub_goals_data):
            sub_trace = trace_context.child_span()
            sub_payload = dict(sub_data)
            sub_payload.setdefault("user_id", parent_goal.user_id)
            sub_payload.setdefault("priority", parent_goal.priority)

            # Create the sub-goal
            sub_record = self.create_goal(sub_payload, sub_trace)
            sub_goal_obj = self._goals[sub_record["goal_id"]]
            sub_goal_obj.parent_goal_id = parent_goal_id

            # Register child in parent
            parent_goal.sub_goal_ids.append(sub_record["goal_id"])
            created_sub_goals.append(sub_goal_obj.to_dict())

        parent_goal.updated_at = current_utc_timestamp()
        return created_sub_goals

    def get_sub_goals(
        self,
        parent_goal_id: str,
        trace_context: TraceContext
    ) -> List[Dict[str, Any]]:
        """Retrieve all refined sub-goals belonging to a parent goal."""
        if parent_goal_id not in self._goals:
            raise NotFoundError(
                message=f"Parent goal '{parent_goal_id}' not found",
                trace_context=trace_context,
                details={"parent_goal_id": parent_goal_id}
            )
        parent_goal = self._goals[parent_goal_id]
        return [self._goals[sid].to_dict() for sid in parent_goal.sub_goal_ids if sid in self._goals]

    def list_goals(self, status: Optional[GoalStatus] = None) -> List[Dict[str, Any]]:
        """List all goals in registry, optionally filtered by status."""
        if status is not None:
            return [g.to_dict() for g in self._goals.values() if g.state == status]
        return [g.to_dict() for g in self._goals.values()]
