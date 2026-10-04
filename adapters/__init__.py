"""AgenticOS - Adapters Framework Package.

Layer 9 & 10: System Services & Application Adapters.
Owner: Magesh (Linux Integration & System Services Lead).

Provides contract-neutral application and system adapters with standardized
validation and structured results.
"""

from .base import BaseAdapter
from .result import AdapterResult, AdapterStatus
from .registry import (
    AdapterRegistry,
    DuplicateAdapterError,
    InvalidAdapterError,
    default_registry,
)
from .filesystem_adapter import FilesystemAdapter
from .application_adapter import ApplicationAdapter
from .system_adapter import SystemAdapter
from .app_launcher import AppLauncher
from .memory_adapter import MemoryAdapter
from .process_adapter import ProcessAdapter

__all__ = [
    "BaseAdapter",
    "AdapterResult",
    "AdapterStatus",
    "AdapterRegistry",
    "DuplicateAdapterError",
    "InvalidAdapterError",
    "default_registry",
    "FilesystemAdapter",
    "ApplicationAdapter",
    "SystemAdapter",
    "AppLauncher",
    "MemoryAdapter",
    "ProcessAdapter",
]
