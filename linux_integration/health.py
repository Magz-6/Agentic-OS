"""
AgenticOS - Service Health Inspector
Layer 12: Agentic Microkernel / Linux Integration Boundary
Owner: Magesh (Linux/OS Lead)

TEMPORARY LOCAL INTERFACE — REQUIRES TEAM API APPROVAL

This module provides safe, read-only systemd user-service status and health
inspection. It never modifies, starts, stops, or restarts services.
"""

import re
import shutil
import subprocess
from typing import Any, Dict, List, Optional

try:
    from .contracts import HealthReport, ServiceStatus
except (ImportError, ValueError):
    from contracts import HealthReport, ServiceStatus


_DEFAULT_SYSTEMCTL = object()
SAFE_UNIT_NAME_REGEX = re.compile(r"^[a-zA-Z0-9_@\.-]+$")


class ServiceHealthInspector:
    """
    Read-only service health inspector for Linux systemd user sessions.
    """

    def __init__(self, systemctl_bin: Any = _DEFAULT_SYSTEMCTL) -> None:
        if systemctl_bin is _DEFAULT_SYSTEMCTL:
            self.systemctl_bin = shutil.which("systemctl")
        else:
            self.systemctl_bin = systemctl_bin

    def is_systemd_available(self) -> bool:
        """
        Check if systemctl is available and responsive for user sessions.
        """
        if not self.systemctl_bin:
            return False

        try:
            res = subprocess.run(
                [self.systemctl_bin, "--user", "is-system-running"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=3,
                check=False,
            )
            # Valid states: running, degraded, initializing, starting, etc.
            output = res.stdout.strip().lower()
            return output in ("running", "degraded", "initializing", "starting")
        except (subprocess.SubprocessError, OSError):
            return False

    def inspect_service(self, service_name: str) -> ServiceStatus:
        """
        Query the read-only operational state of a user service.
        Uses `systemctl --user show` to parse state, substate, PID, and result.
        """
        if not service_name or service_name.startswith("-") or not SAFE_UNIT_NAME_REGEX.match(service_name):
            return ServiceStatus(
                name=service_name,
                active_state="rejected",
                substate="rejected",
                healthy=False,
                error="invalid_service_name",
            )

        if not self.systemctl_bin:
            return ServiceStatus(
                name=service_name,
                active_state="unavailable",
                substate="unavailable",
                healthy=False,
                error="systemctl_not_found",
            )

        try:
            res = subprocess.run(
                [
                    self.systemctl_bin,
                    "--user",
                    "show",
                    "--",
                    service_name,
                    "--property=ActiveState,SubState,MainPID,Result",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=3,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return ServiceStatus(
                name=service_name,
                active_state="timeout",
                healthy=False,
                error="systemctl_timeout",
            )
        except (subprocess.SubprocessError, OSError) as e:
            return ServiceStatus(
                name=service_name,
                active_state="error",
                healthy=False,
                error=str(e),
            )

        props: Dict[str, str] = {}
        for line in res.stdout.splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                props[k.strip()] = v.strip()

        active_state = props.get("ActiveState", "unknown")
        substate = props.get("SubState", "unknown")
        result = props.get("Result", "unknown")
        main_pid_str = props.get("MainPID", "0")

        main_pid: Optional[int] = None
        if main_pid_str.isdigit():
            val = int(main_pid_str)
            main_pid = val if val > 0 else None

        # Healthy if active and running
        is_healthy = (active_state == "active" and substate == "running")
        err = None
        if active_state == "failed":
            err = f"service_failed (result: {result})"
        elif active_state not in ("active", "activating"):
            err = f"service_{active_state}"

        return ServiceStatus(
            name=service_name,
            active_state=active_state,
            substate=substate,
            main_pid=main_pid,
            healthy=is_healthy,
            error=err,
        )

    def inspect_system_health(
        self, service_names: Optional[List[str]] = None
    ) -> HealthReport:
        """
        Generate a consolidated health report for systemd and specified services.
        """
        systemd_ok = self.is_systemd_available()
        system_state = "unavailable"

        if systemd_ok and self.systemctl_bin:
            try:
                res = subprocess.run(
                    [self.systemctl_bin, "--user", "is-system-running"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=3,
                    check=False,
                )
                system_state = res.stdout.strip() or "unknown"
            except (subprocess.SubprocessError, OSError):
                system_state = "error"

        services_dict: Dict[str, Dict[str, Any]] = {}
        errors: List[str] = []

        if service_names:
            for s_name in service_names:
                st = self.inspect_service(s_name)
                services_dict[s_name] = st.to_dict()
                if not st.healthy:
                    errors.append(f"{s_name}: {st.error or 'unhealthy'}")

        return HealthReport(
            systemd_available=systemd_ok,
            system_state=system_state,
            services=services_dict,
            errors=errors,
        )


if __name__ == "__main__":
    import json
    inspector = ServiceHealthInspector()
    print("systemd user session available:", inspector.is_systemd_available())
    report = inspector.inspect_system_health(["agenticos-telemetry.service", "dbus.service"])
    print(json.dumps(report.to_dict(), indent=2))
