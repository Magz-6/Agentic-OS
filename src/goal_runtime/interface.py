"""Goal Runtime Interface — AgenticOS v0.1 Alpha.

Defines the abstract contract for Layer 3 (Goal Runtime).
Responsible for:
- Translating structured intent into prioritized Goal objects
- Goal lifecycle state management
- Goal cancellation and replanning hooks

Note:
Full business logic will be implemented in the 30 Sep milestone.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from src.core.context import TraceContext


class GoalRuntimeInterface(ABC):
    """Abstract interface defining the Goal Runtime service contract."""

    @abstractmethod
    def create_goal(
        self,
        intent_payload: Dict[str, Any],
        trace_context: TraceContext
    ) -> Dict[str, Any]:
        """Create and register a new Goal from an IntentPayload.
        
        Args:
            intent_payload: Dict conforming to provisional IntentPayload schema.
            trace_context: Distributed tracing context.
            
        Returns:
            Goal record dict conforming to provisional GoalDefinition schema.
        """
        pass

    @abstractmethod
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
        pass

    @abstractmethod
    def update_goal(
        self,
        goal_id: str,
        updates: Dict[str, Any],
        trace_context: TraceContext
    ) -> Dict[str, Any]:
        """Update constraints, priority, or parameters of an active Goal.
        
        Args:
            goal_id: Target goal identifier.
            updates: Dictionary of fields to update.
            trace_context: Distributed tracing context.
            
        Returns:
            Updated goal record dict.
        """
        pass

    @abstractmethod
    def cancel_goal(
        self,
        goal_id: str,
        reason: str,
        trace_context: TraceContext
    ) -> Dict[str, Any]:
        """Abort an active Goal and signal downstream workflows to halt.
        
        Args:
            goal_id: Target goal identifier.
            reason: Human or policy reason for cancellation.
            trace_context: Distributed tracing context.
            
        Returns:
            Cancelled goal record dict with status 'CANCELLED'.
        """
        pass

    @abstractmethod
    def replan_goal(
        self,
        goal_id: str,
        trigger_reason: str,
        trace_context: TraceContext
    ) -> Dict[str, Any]:
        """Trigger dynamic re-planning for a goal following step failure.
        
        Args:
            goal_id: Target goal identifier.
            trigger_reason: Description of the failure or condition triggering replan.
            trace_context: Distributed tracing context.
            
        Returns:
            Goal record transitioned to 'REPLANNING' status.
        """
        pass
