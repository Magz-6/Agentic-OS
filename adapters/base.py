"""AgenticOS - Base Adapter Interface.

Layer 10: System Services / Application Adapters Boundary.
Owner: Magesh (Linux Integration & System Services Lead).

Defines the contract-neutral BaseAdapter abstract interface that all AgenticOS
adapters must implement.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Set, Tuple

from .result import AdapterResult, AdapterStatus


class BaseAdapter(ABC):
    """Abstract base class for all AgenticOS application and system adapters.

    Provides a contract-neutral boundary that accepts an action verb and
    parameter dictionary, validates inputs safely, and produces an AdapterResult.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique canonical identifier of the adapter (e.g. 'filesystem', 'application')."""
        pass

    @property
    @abstractmethod
    def supported_actions(self) -> Set[str]:
        """Set of action names explicitly supported by this adapter."""
        pass

    @abstractmethod
    def validate(
        self, action: str, parameters: Dict[str, Any]
    ) -> Tuple[bool, Optional[str]]:
        """Validate whether the requested action and parameters are well-formed and permissible.

        Args:
            action: Name of the action to execute.
            parameters: Dictionary of action arguments.

        Returns:
            Tuple of (is_valid, error_message). If valid, error_message is None.
        """
        pass

    @abstractmethod
    def execute(self, action: str, parameters: Dict[str, Any]) -> AdapterResult:
        """Execute a validated action and return an AdapterResult.

        Args:
            action: Name of the action to execute.
            parameters: Dictionary of validated action arguments.

        Returns:
            Structured AdapterResult envelope.
        """
        pass

    def is_retry_safe(
        self, action: str, parameters: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Return whether an interrupted action may be safely executed again.

        Adapters must explicitly opt in to retry safety. The conservative
        default is False so side-effecting operations are never repeated
        automatically after a crash.
        """
        return False

    def run(
        self, action: str, parameters: Optional[Dict[str, Any]] = None
    ) -> AdapterResult:
        """Entry point for executing an adapter action with validation and safety guards.

        Args:
            action: Name of the action.
            parameters: Optional dictionary of action arguments.

        Returns:
            AdapterResult reflecting execution or validation outcome.
        """
        params = dict(parameters) if parameters is not None else {}

        # 1. Action support check
        if action not in self.supported_actions:
            return AdapterResult.unsupported_action(
                adapter=self.name,
                action=action,
                supported_actions=self.supported_actions,
            )

        # 2. Parameter validation
        is_valid, error_msg = self.validate(action, params)
        if not is_valid:
            return AdapterResult.validation_error(
                adapter=self.name,
                action=action,
                message=error_msg or "Invalid parameters provided",
            )

        # 3. Execution with exception containment
        try:
            return self.execute(action, params)
        except Exception as exc:
            return AdapterResult.execution_error(
                adapter=self.name,
                action=action,
                message=f"Unhandled exception during adapter execution: {str(exc)}",
                details={"exception_type": type(exc).__name__, "error": str(exc)},
            )
