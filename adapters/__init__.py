"""
AgenticOS - Adapters Package
Layer 9 & 10: System Services & Application Adapters
Owner: Magesh (Linux/OS Lead)

TEMPORARY LOCAL INTERFACE — REQUIRES TEAM API APPROVAL
"""

from .process_adapter import ProcessAdapter
from .memory_adapter import MemoryAdapter
from .filesystem_adapter import FilesystemAdapter
from .app_launcher import AppLauncher

__all__ = [
    "ProcessAdapter",
    "MemoryAdapter",
    "FilesystemAdapter",
    "AppLauncher",
]
