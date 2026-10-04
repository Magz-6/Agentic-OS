"""AgenticOS - Adapter Registry.

Layer 10: System Services / Application Adapters Boundary.
Owner: Magesh (Linux Integration & System Services Lead).

Provides a safe, local registration and discovery mechanism for AgenticOS adapters.
Strictly disallows remote registration or loading arbitrary code paths.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from .base import BaseAdapter


class DuplicateAdapterError(ValueError):
    """Raised when registering an adapter with a name that is already registered."""
    pass


class InvalidAdapterError(TypeError):
    """Raised when attempting to register an object that does not inherit from BaseAdapter."""
    pass


class AdapterRegistry:
    """Local, in-process registry for discovering and dispatching AgenticOS adapters."""

    def __init__(self) -> None:
        self._adapters: Dict[str, BaseAdapter] = {}

    def register(self, adapter: BaseAdapter, allow_override: bool = False) -> None:
        """Register an adapter instance.

        Args:
            adapter: Instance of BaseAdapter.
            allow_override: If True, permits replacing an existing registration.

        Raises:
            InvalidAdapterError: If adapter does not inherit from BaseAdapter.
            DuplicateAdapterError: If an adapter with the same name already exists and allow_override is False.
        """
        if not isinstance(adapter, BaseAdapter):
            raise InvalidAdapterError(
                f"Expected instance of BaseAdapter, got: {type(adapter).__name__}"
            )

        name = adapter.name
        if not name or not isinstance(name, str):
            raise ValueError(f"Adapter has invalid or empty name: {name!r}")

        if name in self._adapters and not allow_override:
            raise DuplicateAdapterError(
                f"Adapter '{name}' is already registered in registry. Use allow_override=True to replace."
            )

        self._adapters[name] = adapter

    def get(self, name: str) -> Optional[BaseAdapter]:
        """Retrieve an adapter by its canonical name."""
        return self._adapters.get(name)

    def has(self, name: str) -> bool:
        """Check whether an adapter is registered by name."""
        return name in self._adapters

    def list_adapters(self) -> List[str]:
        """Return a sorted list of all registered adapter names."""
        return sorted(list(self._adapters.keys()))

    def unregister(self, name: str) -> bool:
        """Remove an adapter by name. Returns True if removed, False if not found."""
        if name in self._adapters:
            del self._adapters[name]
            return True
        return False

    def clear(self) -> None:
        """Clear all registered adapters."""
        self._adapters.clear()


# Default global registry instance for convenience
default_registry = AdapterRegistry()
