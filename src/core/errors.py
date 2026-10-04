"""Structured Error and Failure Representation for AgenticOS.

All errors in AgenticOS are structured, typed, and serializable so that
failures can be tracked, audited, and propagated back to the user or caller
without crashing the runtime.
"""

from __future__ import annotations
from typing import Optional, Dict, Any
from .context import TraceContext, current_utc_timestamp


class AgenticOSError(Exception):
    """Base exception for all AgenticOS operational and system errors.
    
    Attributes:
        message: Human-readable explanation of what failed.
        error_code: Machine-readable uppercase identifier (e.g. 'VALIDATION_ERROR').
        trace_context: Distributed tracing context at time of failure.
        details: Optional dictionary containing error metadata.
        timestamp: UTC ISO-8601 timestamp when error occurred.
    """
    def __init__(
        self,
        message: str,
        error_code: str = "GENERIC_ERROR",
        trace_context: Optional[TraceContext] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.trace_context = trace_context
        self.details = details or {}
        self.timestamp = current_utc_timestamp()

    def to_dict(self) -> Dict[str, Any]:
        """Convert structured error into a serializable dictionary."""
        return {
            "error": True,
            "error_code": self.error_code,
            "message": self.message,
            "timestamp": self.timestamp,
            "details": self.details,
            "trace_context": self.trace_context.to_dict() if self.trace_context else None,
        }


class ValidationError(AgenticOSError):
    """Raised when a data contract or payload fails schema validation."""
    def __init__(
        self,
        message: str,
        trace_context: Optional[TraceContext] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            trace_context=trace_context,
            details=details
        )


class PolicyViolationError(AgenticOSError):
    """Raised when an operation is blocked by security or governance policies."""
    def __init__(
        self,
        message: str,
        trace_context: Optional[TraceContext] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        super().__init__(
            message=message,
            error_code="SECURITY_POLICY_VIOLATION",
            trace_context=trace_context,
            details=details
        )


class TimeoutError(AgenticOSError):
    """Raised when an agent or workflow step exceeds its SLA deadline."""
    def __init__(
        self,
        message: str,
        trace_context: Optional[TraceContext] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        super().__init__(
            message=message,
            error_code="DEADLINE_EXCEEDED",
            trace_context=trace_context,
            details=details
        )


class NotFoundError(AgenticOSError):
    """Raised when an entity (Goal, Workflow, Agent) cannot be located."""
    def __init__(
        self,
        message: str,
        trace_context: Optional[TraceContext] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        super().__init__(
            message=message,
            error_code="ENTITY_NOT_FOUND",
            trace_context=trace_context,
            details=details
        )


class ResourceExhaustedError(AgenticOSError):
    """Raised when concurrency limits or resource quotas are exhausted."""
    def __init__(
        self,
        message: str,
        trace_context: Optional[TraceContext] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        super().__init__(
            message=message,
            error_code="RESOURCE_EXHAUSTED",
            trace_context=trace_context,
            details=details
        )
