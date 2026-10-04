"""Lifecycle and Status Primitives for AgenticOS Core Runtimes.

This module provides standard enumerations representing the state machines
of Goals, Workflows, Steps, and Agents.
"""

from enum import Enum


class GoalStatus(str, Enum):
    """Lifecycle states of a declarative Goal in the Goal Runtime."""
    SUBMITTED = "SUBMITTED"      # Received from Intent Intelligence, pending validation
    ACTIVE = "ACTIVE"            # Validated, prioritized, handed to Workflow Runtime
    BLOCKED = "BLOCKED"          # Waiting on user confirmation (HITL) or external resource
    REPLANNING = "REPLANNING"    # Step failure or environment change triggered new plan
    COMPLETED = "COMPLETED"      # Success criteria satisfied and verified
    FAILED = "FAILED"            # Unrecoverable error encountered; rollback completed
    CANCELLED = "CANCELLED"      # Aborted by user or security policy


class WorkflowStatus(str, Enum):
    """Execution states of a Workflow Directed Acyclic Graph (DAG)."""
    PLANNED = "PLANNED"          # DAG compiled, steps sequenced, ready for dispatch
    EXECUTING = "EXECUTING"      # Active steps are currently running
    PAUSED = "PAUSED"            # Paused for policy check or manual intervention
    COMPLETED = "COMPLETED"      # All steps finished successfully
    FAILED = "FAILED"            # One or more critical steps failed unrecoverably
    CANCELLED = "CANCELLED"      # Workflow halted due to goal cancellation


class StepStatus(str, Enum):
    """States of an individual task node within a workflow DAG."""
    PENDING = "PENDING"          # Waiting for predecessor steps to complete
    READY = "READY"              # All dependencies met, awaiting agent allocation
    RUNNING = "RUNNING"          # Assigned to an agent and actively executing
    COMPLETED = "COMPLETED"      # Execution succeeded and output validated
    FAILED = "FAILED"            # Execution failed or timed out
    SKIPPED = "SKIPPED"          # Bypassed due to conditional branch logic


class AgentStatus(str, Enum):
    """Operational health and capacity states of a registered agent in GAM."""
    IDLE = "IDLE"                # Online, healthy, ready to accept tasks
    ALLOCATED = "ALLOCATED"      # Assigned a task, awaiting execution acknowledgement
    BUSY = "BUSY"                # Actively executing at full concurrency limit
    UNHEALTHY = "UNHEALTHY"      # Missed heartbeats or failed health probes
    OFFLINE = "OFFLINE"          # Gracefully deregistered or disconnected


class RequestStatus(str, Enum):
    """Lifecycle states of an incoming request traversing the Agentic Core."""
    RECEIVED = "RECEIVED"        # Request accepted at boundary, context established
    VALIDATING = "VALIDATING"    # Request and intent payload undergoing validation
    VALIDATED = "VALIDATED"      # Intent schema, parameters, and confidence verified
    REJECTED = "REJECTED"        # Request rejected (malformed, ambiguous, or policy denial)
    PROCESSING = "PROCESSING"    # Handed off to Goal Runtime boundary
    COMPLETED = "COMPLETED"      # Downstream execution succeeded
    FAILED = "FAILED"            # Downstream execution or system failure


# Valid state transitions for RequestStatus
VALID_REQUEST_TRANSITIONS = {
    RequestStatus.RECEIVED: {RequestStatus.VALIDATING, RequestStatus.REJECTED, RequestStatus.FAILED},
    RequestStatus.VALIDATING: {RequestStatus.VALIDATED, RequestStatus.REJECTED, RequestStatus.FAILED},
    RequestStatus.VALIDATED: {RequestStatus.PROCESSING, RequestStatus.REJECTED, RequestStatus.FAILED},
    RequestStatus.PROCESSING: {RequestStatus.COMPLETED, RequestStatus.FAILED},
    RequestStatus.REJECTED: set(),
    RequestStatus.COMPLETED: set(),
    RequestStatus.FAILED: set(),
}


# Valid state transitions for GoalStatus
VALID_GOAL_TRANSITIONS = {
    GoalStatus.SUBMITTED: {GoalStatus.ACTIVE, GoalStatus.FAILED, GoalStatus.CANCELLED},
    GoalStatus.ACTIVE: {GoalStatus.BLOCKED, GoalStatus.REPLANNING, GoalStatus.COMPLETED, GoalStatus.FAILED, GoalStatus.CANCELLED},
    GoalStatus.BLOCKED: {GoalStatus.ACTIVE, GoalStatus.REPLANNING, GoalStatus.CANCELLED, GoalStatus.FAILED},
    GoalStatus.REPLANNING: {GoalStatus.ACTIVE, GoalStatus.FAILED, GoalStatus.CANCELLED},
    GoalStatus.COMPLETED: set(),
    GoalStatus.FAILED: set(),
    GoalStatus.CANCELLED: set(),
}


from dataclasses import dataclass, field
from typing import Any, Dict
from .context import current_utc_timestamp


@dataclass
class StateTransitionRecord:
    """Historical audit record of a state transition in AgenticOS."""
    from_state: Any
    to_state: Any
    timestamp: str = field(default_factory=current_utc_timestamp)
    detail: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "from_state": self.from_state.value if hasattr(self.from_state, "value") else str(self.from_state),
            "to_state": self.to_state.value if hasattr(self.to_state, "value") else str(self.to_state),
            "timestamp": self.timestamp,
            "detail": self.detail,
        }


