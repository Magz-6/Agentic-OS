"""AgenticOS Core Foundation Package.

Contains fundamental primitives:
- Context and distributed tracing (`TraceContext`, `RequestContext`)
- Lifecycle status enums (`GoalStatus`, `WorkflowStatus`, `StepStatus`, `AgentStatus`)
- Structured errors (`AgenticOSError`, `ValidationError`, `PolicyViolationError`, etc.)
- Results and verification (`ExecutionResult`, `VerificationReport`)
- Provisional schema validation (`DraftSchemaValidator`)
"""

from .context import TraceContext, RequestContext, generate_id, current_utc_timestamp
from .status import (
    GoalStatus,
    WorkflowStatus,
    StepStatus,
    AgentStatus,
    RequestStatus,
    VALID_REQUEST_TRANSITIONS,
    VALID_GOAL_TRANSITIONS,
)
from .errors import (
    AgenticOSError,
    ValidationError,
    PolicyViolationError,
    TimeoutError,
    NotFoundError,
    ResourceExhaustedError,
)
from .results import ExecutionResult, VerificationCheck, VerificationReport
from .validation import DraftSchemaValidator
from .request_lifecycle import (
    RequestLifecycle,
    RequestLifecycleResult,
    StateTransitionRecord,
)

__all__ = [
    "TraceContext",
    "RequestContext",
    "generate_id",
    "current_utc_timestamp",
    "GoalStatus",
    "WorkflowStatus",
    "StepStatus",
    "AgentStatus",
    "RequestStatus",
    "VALID_REQUEST_TRANSITIONS",
    "VALID_GOAL_TRANSITIONS",
    "AgenticOSError",
    "ValidationError",
    "PolicyViolationError",
    "TimeoutError",
    "NotFoundError",
    "ResourceExhaustedError",
    "ExecutionResult",
    "VerificationCheck",
    "VerificationReport",
    "DraftSchemaValidator",
    "RequestLifecycle",
    "RequestLifecycleResult",
    "StateTransitionRecord",
]


