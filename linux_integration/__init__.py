"""
AgenticOS - Linux Integration Package
Layer 12: Agentic Microkernel / Linux Integration Boundary
Owner: Magesh (Linux/OS Lead)

TEMPORARY LOCAL INTERFACE — REQUIRES TEAM API APPROVAL
"""

from .contracts import ServiceStatus, HealthReport
from .health import ServiceHealthInspector

__all__ = ["ServiceStatus", "HealthReport", "ServiceHealthInspector"]
