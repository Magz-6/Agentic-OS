"""AgenticOS - Adapter Execution Result.

Layer 10: System Services / Application Adapters Boundary.
Owner: Magesh (Linux Integration & System Services Lead).

Defines the contract-neutral structured result representation returned by all
AgenticOS adapters.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class AdapterStatus(str, Enum):
    """Standardized outcome status for adapter action executions."""

    SUCCESS = "SUCCESS"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    UNSUPPORTED_ACTION = "UNSUPPORTED_ACTION"
    EXECUTION_ERROR = "EXECUTION_ERROR"


@dataclass
class AdapterResult:
    """Contract-neutral result envelope returned by all AgenticOS adapters.

    Fields:
        success: Boolean flag indicating if action succeeded.
        status: Standardized AdapterStatus enum.
        adapter: Name of the originating adapter.
        action: Name of the requested action.
        message: Human-readable status or diagnostic explanation.
        data: Optional dictionary containing safe result payload.
        error: Optional dictionary containing structured error details.
    """

    success: bool
    status: AdapterStatus
    adapter: str
    action: str
    message: str
    data: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None

    @classmethod
    def success_result(
        cls,
        adapter: str,
        action: str,
        message: str = "Action completed successfully",
        data: Optional[Dict[str, Any]] = None,
    ) -> AdapterResult:
        """Create a standard SUCCESS result envelope."""
        return cls(
            success=True,
            status=AdapterStatus.SUCCESS,
            adapter=adapter,
            action=action,
            message=message,
            data=data if data is not None else {},
            error=None,
        )

    @classmethod
    def validation_error(
        cls,
        adapter: str,
        action: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> AdapterResult:
        """Create a VALIDATION_ERROR result envelope."""
        return cls(
            success=False,
            status=AdapterStatus.VALIDATION_ERROR,
            adapter=adapter,
            action=action,
            message=message,
            data=None,
            error=details if details is not None else {"reason": message},
        )

    @classmethod
    def unsupported_action(
        cls,
        adapter: str,
        action: str,
        message: Optional[str] = None,
        supported_actions: Optional[Sequence[str]] = None,
    ) -> AdapterResult:
        """Create an UNSUPPORTED_ACTION result envelope."""
        msg = message or f"Action '{action}' is not supported by adapter '{adapter}'"
        err_details: Dict[str, Any] = {"unsupported_action": action}
        if supported_actions is not None:
            err_details["supported_actions"] = sorted(list(supported_actions))
        return cls(
            success=False,
            status=AdapterStatus.UNSUPPORTED_ACTION,
            adapter=adapter,
            action=action,
            message=msg,
            data=None,
            error=err_details,
        )

    @classmethod
    def execution_error(
        cls,
        adapter: str,
        action: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> AdapterResult:
        """Create an EXECUTION_ERROR result envelope."""
        return cls(
            success=False,
            status=AdapterStatus.EXECUTION_ERROR,
            adapter=adapter,
            action=action,
            message=message,
            data=None,
            error=details if details is not None else {"reason": message},
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to a standard dictionary representation."""
        res: Dict[str, Any] = {
            "success": self.success,
            "status": self.status.value if isinstance(self.status, AdapterStatus) else str(self.status),
            "adapter": self.adapter,
            "action": self.action,
            "message": self.message,
        }
        if self.data is not None:
            res["data"] = self.data
        if self.error is not None:
            res["error"] = self.error
        return res
