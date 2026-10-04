"""Workflow Runtime Interface — AgenticOS v0.1 Alpha.

Defines the abstract contract for Layer 4 (Workflow Runtime).
Responsible for:
- Decomposing Goals into Directed Acyclic Graph (DAG) plans
- Step dependency tracking and progress observation
- Workflow execution dispatch and replanning hooks

Note:
Full business logic will be implemented in the 01 Oct milestone.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from src.core.context import TraceContext


class WorkflowRuntimeInterface(ABC):
    """Abstract interface defining the Workflow Runtime service contract."""

    @abstractmethod
    def create_workflow(
        self,
        goal_definition: Dict[str, Any],
        trace_context: TraceContext
    ) -> Dict[str, Any]:
        """Compile a GoalDefinition into an executable DAG WorkflowPlan.
        
        Args:
            goal_definition: Dict conforming to provisional GoalDefinition schema.
            trace_context: Distributed tracing context.
            
        Returns:
            Workflow record dict conforming to provisional WorkflowPlan schema.
        """
        pass

    @abstractmethod
    def get_workflow(
        self,
        workflow_id: str,
        trace_context: TraceContext
    ) -> Dict[str, Any]:
        """Retrieve current state, steps, and execution status of a Workflow.
        
        Args:
            workflow_id: Canonical workflow identifier.
            trace_context: Distributed tracing context.
            
        Returns:
            Workflow record dict.
            
        Raises:
            NotFoundError: If workflow_id does not exist.
        """
        pass

    @abstractmethod
    def dispatch_workflow(
        self,
        workflow_id: str,
        trace_context: TraceContext
    ) -> Dict[str, Any]:
        """Dispatch ready steps in the workflow to Global Agent Manager for execution.
        
        Args:
            workflow_id: Target workflow identifier.
            trace_context: Distributed tracing context.
            
        Returns:
            Execution status dictionary (e.g. status='EXECUTING').
        """
        pass

    @abstractmethod
    def replan_workflow(
        self,
        workflow_id: str,
        failed_step_id: str,
        failure_reason: str,
        trace_context: TraceContext
    ) -> Dict[str, Any]:
        """Re-plan remaining steps in DAG when an unrecoverable step failure occurs.
        
        Args:
            workflow_id: Target workflow identifier.
            failed_step_id: Identifier of the step that failed.
            failure_reason: Explanation of the failure condition.
            trace_context: Distributed tracing context.
            
        Returns:
            Updated workflow record with revised DAG steps.
        """
        pass
