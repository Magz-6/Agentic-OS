"""Global Agent Manager (GAM) Interface — AgenticOS v0.1 Alpha.

Defines the abstract contract for Layer 5 (Global Agent Manager).
Responsible for:
- Agent registry management
- Capability-based matchmaking
- Task allocation and scheduling
- Agent lifecycle and health heartbeat observation

Note:
Full business logic will be implemented in the 02 Oct milestone.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from src.core.context import TraceContext


class GlobalAgentManagerInterface(ABC):
    """Abstract interface defining the Global Agent Manager service contract."""

    @abstractmethod
    def register_agent(
        self,
        agent_descriptor: Dict[str, Any],
        trace_context: TraceContext
    ) -> Dict[str, Any]:
        """Register a new or restarted agent worker with the global registry.
        
        Args:
            agent_descriptor: Agent metadata (agent_id, capabilities, max_concurrency).
            trace_context: Distributed tracing context.
            
        Returns:
            Registration confirmation dict with status 'REGISTERED'.
        """
        pass

    @abstractmethod
    def discover_agents(
        self,
        capability: str,
        trace_context: TraceContext
    ) -> List[Dict[str, Any]]:
        """Query registry for agents certified with a specific capability.
        
        Args:
            capability: Required capability string (e.g. 'filesystem.compress').
            trace_context: Distributed tracing context.
            
        Returns:
            List of matching agent descriptor dictionaries.
        """
        pass

    @abstractmethod
    def allocate_agent(
        self,
        step_requirement: Dict[str, Any],
        trace_context: TraceContext
    ) -> Dict[str, Any]:
        """Match and allocate a capable, available agent for a workflow task.
        
        Args:
            step_requirement: Dict containing step_id, required_capabilities, priority.
            trace_context: Distributed tracing context.
            
        Returns:
            AgentTaskAssignment dict conforming to provisional schema.
        """
        pass

    @abstractmethod
    def release_agent(
        self,
        assignment_id: str,
        final_status: str,
        trace_context: TraceContext
    ) -> Dict[str, Any]:
        """Release an allocated agent back to the available pool upon task completion.
        
        Args:
            assignment_id: Identifier of the completed assignment.
            final_status: Completion outcome ('COMPLETED', 'FAILED', 'TIMEOUT').
            trace_context: Distributed tracing context.
            
        Returns:
            Release confirmation dict.
        """
        pass

    @abstractmethod
    def update_agent_health(
        self,
        agent_id: str,
        status: str,
        trace_context: TraceContext
    ) -> Dict[str, Any]:
        """Record heartbeat or update health status of an agent instance.
        
        Args:
            agent_id: Canonical agent identifier.
            status: Health status ('IDLE', 'BUSY', 'UNHEALTHY', 'OFFLINE').
            trace_context: Distributed tracing context.
            
        Returns:
            Health acknowledgement dict.
        """
        pass
