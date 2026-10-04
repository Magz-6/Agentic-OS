"""Context and Tracing Primitives for AgenticOS.

Every operation in AgenticOS must carry distributed tracing context so that
requests can be tracked from User Input down to the Linux kernel and back.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
import uuid
from typing import Optional, Dict, Any


def generate_id(prefix: str = "") -> str:
    """Generate a unique UUIDv4 string with an optional descriptive prefix."""
    unique_part = str(uuid.uuid4())
    return f"{prefix}{unique_part}" if prefix else unique_part


def current_utc_timestamp() -> str:
    """Generate an ISO-8601 compliant UTC timestamp string."""
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class TraceContext:
    """Distributed tracing context following W3C / AgenticOS conventions.
    
    Fields:
        request_id: Canonical UUID identifying the original user prompt.
        trace_id: Distributed trace identifier crossing all layer boundaries.
        span_id: Identifier for the current layer operation span.
        parent_span_id: Identifier of the invoking layer's span (None for root).
        timestamp: UTC creation timestamp in ISO-8601 format.
    """
    request_id: str
    trace_id: str
    span_id: str
    parent_span_id: Optional[str] = None
    timestamp: str = field(default_factory=current_utc_timestamp)

    @classmethod
    def new_root(cls, request_id: Optional[str] = None) -> TraceContext:
        """Create a new root trace context for an incoming user request."""
        req_id = request_id or generate_id("req-")
        trace_id = generate_id("tr-")
        span_id = generate_id("span-")
        return cls(
            request_id=req_id,
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=None,
            timestamp=current_utc_timestamp()
        )

    def child_span(self) -> TraceContext:
        """Spawn a child span for a downstream layer boundary call."""
        return TraceContext(
            request_id=self.request_id,
            trace_id=self.trace_id,
            span_id=generate_id("span-"),
            parent_span_id=self.span_id,
            timestamp=current_utc_timestamp()
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert the trace context to a plain dictionary for serialization."""
        return {
            "request_id": self.request_id,
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TraceContext:
        """Reconstruct a TraceContext from a dictionary payload."""
        return cls(
            request_id=str(data["request_id"]),
            trace_id=str(data["trace_id"]),
            span_id=str(data["span_id"]),
            parent_span_id=data.get("parent_span_id"),
            timestamp=str(data.get("timestamp", current_utc_timestamp()))
        )


@dataclass(frozen=True)
class RequestContext:
    """Security and identity context for an authenticated user request.
    
    Fields:
        user_id: Identity of the user issuing the request.
        trace: Distributed tracing context for the request.
        session_id: Optional terminal / UI session identifier.
        privilege_level: Operating privilege level ('standard_user', 'admin').
    """
    user_id: str
    trace: TraceContext
    session_id: Optional[str] = None
    privilege_level: str = "standard_user"

    @classmethod
    def create(
        cls,
        user_id: str,
        session_id: Optional[str] = None,
        privilege_level: str = "standard_user",
        request_id: Optional[str] = None
    ) -> RequestContext:
        """Create a fresh RequestContext with a new root TraceContext."""
        return cls(
            user_id=user_id,
            trace=TraceContext.new_root(request_id=request_id),
            session_id=session_id,
            privilege_level=privilege_level
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize request context to dictionary format."""
        return {
            "user_id": self.user_id,
            "session_id": self.session_id,
            "privilege_level": self.privilege_level,
            "trace_context": self.trace.to_dict(),
        }
