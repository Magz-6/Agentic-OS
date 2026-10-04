"""Structured Result and Verification Primitives for AgenticOS.

All execution layers return structured result envelopes that include
status flags, output payloads, metrics, and verification reports.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from .context import TraceContext, current_utc_timestamp


@dataclass
class ExecutionResult:
    """Standard execution result returned by workflow steps and capabilities.
    
    Fields:
        success: True if the execution completed without unrecoverable errors.
        data: Arbitrary structured output produced by the execution.
        trace_context: Distributed tracing context.
        error: Detailed error dictionary if success is False, else None.
        metrics: Performance measurements (duration_ms, memory_used, retries).
        timestamp: UTC completion timestamp.
    """
    success: bool
    trace_context: TraceContext
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[Dict[str, Any]] = None
    metrics: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=current_utc_timestamp)

    def to_dict(self) -> Dict[str, Any]:
        """Convert execution result into serializable dictionary."""
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "metrics": self.metrics,
            "timestamp": self.timestamp,
            "trace_context": self.trace_context.to_dict(),
        }

    @classmethod
    def successful(
        cls,
        trace_context: TraceContext,
        data: Optional[Dict[str, Any]] = None,
        metrics: Optional[Dict[str, Any]] = None
    ) -> ExecutionResult:
        """Convenience factory for a successful execution result."""
        return cls(
            success=True,
            trace_context=trace_context,
            data=data or {},
            metrics=metrics or {}
        )

    @classmethod
    def failed(
        cls,
        trace_context: TraceContext,
        error_message: str,
        error_code: str = "EXECUTION_FAILURE",
        details: Optional[Dict[str, Any]] = None
    ) -> ExecutionResult:
        """Convenience factory for a failed execution result."""
        return cls(
            success=False,
            trace_context=trace_context,
            error={
                "error_code": error_code,
                "message": error_message,
                "details": details or {}
            }
        )


@dataclass
class VerificationCheck:
    """Individual assertion check in a VerificationReport."""
    check_name: str
    passed: bool
    details: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "check_name": self.check_name,
            "passed": self.passed,
            "details": self.details
        }


@dataclass
class VerificationReport:
    """Post-execution verification report conforming to docs/api-draft.md.
    
    Fields:
        goal_id: Identifier of the goal being verified.
        verified: True if all post-conditions passed.
        status: Outcome status ('SUCCESS', 'FAILED_VERIFICATION', 'SYSTEM_ERROR').
        user_message: Human-friendly explanation of the outcome.
        checks: List of individual assertions evaluated.
        trace_context: Tracing context.
    """
    goal_id: str
    verified: bool
    status: str
    user_message: str
    trace_context: TraceContext
    checks: List[VerificationCheck] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert report to dictionary format."""
        return {
            "goal_id": self.goal_id,
            "verified": self.verified,
            "status": self.status,
            "user_message": self.user_message,
            "checks": [c.to_dict() for c in self.checks],
            "trace_context": self.trace_context.to_dict(),
        }
