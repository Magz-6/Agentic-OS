"""AgenticOS - System Adapter.

Layer 10: System Services Boundary.
Owner: Magesh (Linux Integration & System Services Lead).

Provides safe, conservative, strictly read-only inspection of system state.
Exposes host, kernel, uptime, memory, and service status without permitting
reboots, shutdowns, package installations, or arbitrary execution.
"""

from __future__ import annotations

import os
import platform
import re
import socket
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional, Set, Tuple

from .base import BaseAdapter
from .memory_adapter import MemoryAdapter
from .result import AdapterResult, AdapterStatus


class SystemAdapter(BaseAdapter):
    """Safe, read-only system adapter for querying AgenticOS system status."""

    SUPPORTED_ACTIONS: Set[str] = {
        "get_system_info",
        "get_hostname",
        "get_kernel_info",
        "get_uptime",
        "get_memory_info",
        "get_service_status",
    }

    # Strict service name whitelist pattern: letters, numbers, hyphens, underscores, dots
    SAFE_SERVICE_NAME = re.compile(r"^[a-zA-Z0-9_\-\.]+$")

    def __init__(
        self,
        memory_adapter: Optional[MemoryAdapter] = None,
        proc_path: str = "/proc",
    ) -> None:
        self.memory_adapter = (
            memory_adapter if memory_adapter is not None else MemoryAdapter(proc_path=proc_path)
        )
        self.proc_path = Path(proc_path)

    @property
    def name(self) -> str:
        return "system"

    @property
    def supported_actions(self) -> Set[str]:
        return set(self.SUPPORTED_ACTIONS)

    def validate(
        self, action: str, parameters: Dict[str, Any]
    ) -> Tuple[bool, Optional[str]]:
        """Validate system action and parameters against non-destructive boundaries."""
        if action not in self.SUPPORTED_ACTIONS:
            return False, f"Action '{action}' is not supported by {self.name}"

        if not isinstance(parameters, dict):
            return False, "Parameters must be a dictionary"

        if action == "get_service_status":
            service_name = parameters.get("service_name")
            if not service_name:
                return False, "Missing required parameter 'service_name'"
            if not isinstance(service_name, str) or str(service_name).strip() == "":
                return False, "Parameter 'service_name' must be a non-empty string"
            if len(service_name) > 128:
                return False, f"service_name is too long (max 128 characters)"
            if not self.SAFE_SERVICE_NAME.match(service_name):
                return False, f"Invalid service_name '{service_name}': contains illegal characters"

        return True, None

    def is_retry_safe(
        self, action: str, parameters: Optional[Dict[str, Any]] = None
    ) -> bool:
        """SystemAdapter operations are read-only and safe to repeat."""
        return action in self.SUPPORTED_ACTIONS

    def execute(self, action: str, parameters: Dict[str, Any]) -> AdapterResult:
        """Execute validated non-destructive system query."""
        if action == "get_hostname":
            hostname = socket.gethostname()
            return AdapterResult.success_result(
                adapter=self.name,
                action=action,
                message=f"Current hostname: {hostname}",
                data={"hostname": hostname},
            )

        elif action == "get_system_info":
            os_name = "AgenticOS"
            os_pretty = "AgenticOS v0.1 Alpha"
            os_release_file = Path("/etc/os-release")
            if os_release_file.is_file():
                try:
                    for line in os_release_file.read_text(encoding="utf-8", errors="replace").splitlines():
                        if line.startswith("PRETTY_NAME="):
                            os_pretty = line.split("=", 1)[1].strip('"\'')
                        elif line.startswith("NAME="):
                            os_name = line.split("=", 1)[1].strip('"\'')
                except Exception:
                    pass

            info: Dict[str, Any] = {
                "os_name": os_name,
                "os_pretty_name": os_pretty,
                "system": platform.system(),
                "release": platform.release(),
                "kernel": platform.release(),
                "machine": platform.machine(),
                "architecture": platform.machine(),
                "hostname": socket.gethostname(),
                "python_version": platform.python_version(),
            }
            return AdapterResult.success_result(
                adapter=self.name,
                action=action,
                message=f"System info: {info['os_pretty_name']} on {info['machine']}",
                data=info,
            )

        elif action == "get_kernel_info":
            kernel_version = platform.release()
            version_file = self.proc_path / "version"
            full_version = None
            if version_file.is_file():
                try:
                    full_version = version_file.read_text(encoding="utf-8", errors="replace").strip()
                except Exception:
                    pass

            return AdapterResult.success_result(
                adapter=self.name,
                action=action,
                message=f"Kernel release: {kernel_version}",
                data={
                    "kernel_release": kernel_version,
                    "release": kernel_version,
                    "version": kernel_version,
                    "kernel_string": full_version or kernel_version,
                    "architecture": platform.machine(),
                    "machine": platform.machine(),
                },
            )

        elif action == "get_uptime":
            uptime_file = self.proc_path / "uptime"
            if uptime_file.is_file():
                try:
                    parts = uptime_file.read_text(encoding="utf-8", errors="replace").strip().split()
                    uptime_secs = float(parts[0])
                    idle_secs = float(parts[1]) if len(parts) > 1 else 0.0
                    return AdapterResult.success_result(
                        adapter=self.name,
                        action=action,
                        message=f"System uptime: {int(uptime_secs)} seconds",
                        data={"uptime_seconds": uptime_secs, "idle_seconds": idle_secs},
                    )
                except Exception as exc:
                    return AdapterResult.execution_error(
                        adapter=self.name,
                        action=action,
                        message=f"Failed to read /proc/uptime: {str(exc)}",
                    )
            return AdapterResult.execution_error(
                adapter=self.name,
                action=action,
                message="/proc/uptime is unavailable on this platform",
            )

        elif action == "get_memory_info":
            mem_data = self.memory_adapter.get_memory_metrics()
            return AdapterResult.success_result(
                adapter=self.name,
                action=action,
                message="Retrieved memory metrics from /proc/meminfo",
                data=mem_data,
            )

        elif action == "get_service_status":
            service_name = parameters["service_name"]
            # Ensure service name ends with .service if not specified
            unit_name = service_name if service_name.endswith(".service") else f"{service_name}.service"

            try:
                res = subprocess.run(
                    ["systemctl", "is-active", unit_name],
                    capture_output=True,
                    text=True,
                    timeout=3,
                    shell=False,  # CRITICAL SECURITY GUARANTEE
                )
                state = res.stdout.strip() or res.stderr.strip() or "unknown"
                is_active = (res.returncode == 0 and state == "active")
                return AdapterResult.success_result(
                    adapter=self.name,
                    action=action,
                    message=f"Service '{unit_name}' status: {state}",
                    data={
                        "service_name": service_name,
                        "unit_name": unit_name,
                        "state": state,
                        "active_state": state,
                        "is_active": is_active,
                    },
                )
            except FileNotFoundError:
                return AdapterResult.execution_error(
                    adapter=self.name,
                    action=action,
                    message="systemctl binary not found in PATH",
                    details={"service_name": unit_name, "systemd_available": False},
                )
            except subprocess.TimeoutExpired:
                return AdapterResult.execution_error(
                    adapter=self.name,
                    action=action,
                    message=f"Timed out querying service '{unit_name}'",
                    details={"service_name": unit_name},
                )
            except Exception as exc:
                return AdapterResult.execution_error(
                    adapter=self.name,
                    action=action,
                    message=f"Failed to query service status: {str(exc)}",
                    details={"service_name": unit_name, "error": str(exc)},
                )

        return AdapterResult.unsupported_action(
            adapter=self.name,
            action=action,
            supported_actions=self.supported_actions,
        )
