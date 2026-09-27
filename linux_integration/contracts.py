"""
AgenticOS - Linux Integration Contracts
Layer 12: Agentic Microkernel / Linux Integration Boundary
Owner: Magesh (Linux/OS Lead)

TEMPORARY LOCAL INTERFACE — REQUIRES TEAM API APPROVAL

This module defines typed data structures for service health inspection
and system integration status.
"""

import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ServiceStatus:
    """
    Structured status of an individual system service.
    """
    name: str
    active_state: str = "unknown"       # e.g., active, inactive, failed, unknown
    substate: str = "unknown"           # e.g., running, dead, exited
    main_pid: Optional[int] = None
    healthy: bool = False
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class HealthReport:
    """
    Consolidated system health snapshot.
    """
    schema_version: str = "0.1.0"
    layer: str = "Layer 12: Linux Integration & Health"
    timestamp: float = field(default_factory=time.time)
    systemd_available: bool = False
    system_state: str = "unknown"       # e.g., running, degraded, unavailable
    services: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
