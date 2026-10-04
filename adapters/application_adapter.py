"""AgenticOS - Application Adapter.

Layer 9: Applications & Services Boundary.
Owner: Magesh (Linux Integration & System Services Lead).

Provides a secure, allowlist-controlled application execution adapter.
Strictly prevents arbitrary command execution, shell invocation, and path injection.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from .base import BaseAdapter
from .app_launcher import AppLauncher, InvalidArgumentError, UnknownApplicationError
from .result import AdapterResult, AdapterStatus


class ApplicationAdapter(BaseAdapter):
    """Controlled application adapter for launching allowlisted Linux applications.

    Enforces strict execution boundaries:
    - Never uses shell=True.
    - Only permits application IDs registered in an explicit allowlist.
    - Rejects shell metacharacters and script-execution flags in parameters.
    - Reports clear error status when desktop/GUI applications (like browsers)
      are unavailable in headless environments.
    """

    SUPPORTED_ACTIONS: Set[str] = {
        "launch_application",
        "check_availability",
        "is_allowed",
        "list_applications",
        "list_allowed_applications",
        "resolve_binary",
        "resolve_executable",
    }

    def __init__(self, launcher: Optional[AppLauncher] = None) -> None:
        self.launcher = launcher if launcher is not None else AppLauncher()

    @property
    def name(self) -> str:
        return "application"

    @property
    def supported_actions(self) -> Set[str]:
        return set(self.SUPPORTED_ACTIONS)

    def _extract_app_id(self, parameters: Dict[str, Any]) -> Optional[str]:
        """Extract app identifier from app_id or app_name."""
        return parameters.get("app_id") or parameters.get("app_name")

    def validate(
        self, action: str, parameters: Dict[str, Any]
    ) -> Tuple[bool, Optional[str]]:
        """Validate application action and parameters against security allowlist."""
        if action not in self.SUPPORTED_ACTIONS:
            return False, f"Action '{action}' is not supported by {self.name}"

        if not isinstance(parameters, dict):
            return False, "Parameters must be a dictionary"

        # Actions requiring an allowlisted app_id / app_name
        if action in (
            "launch_application",
            "is_allowed",
            "check_availability",
            "resolve_binary",
            "resolve_executable",
        ):
            app_id = self._extract_app_id(parameters)
            if not app_id:
                return False, f"Missing required parameter: 'app_name' or 'app_id'"
            if not isinstance(app_id, str) or str(app_id).strip() == "":
                return False, "Parameter must be a non-empty string"
            if "\0" in app_id:
                return False, "Parameter contains illegal null byte"

            # Strict prohibition on arbitrary paths or shell injection in app_id
            if "/" in app_id or "\\" in app_id:
                return False, "Parameter must be an allowlist ID, not a file path"

            # For launch and resolve, must be in the approved allowlist
            if not self.launcher.is_allowed(app_id):
                return (
                    False,
                    f"Unknown or disallowed application '{app_id}'. Approved: {self.launcher.get_allowed_applications()}",
                )

            # Argument validation for launch_application
            if action == "launch_application" and "args" in parameters:
                args = parameters["args"]
                if not isinstance(args, (list, tuple)):
                    return False, "Parameter 'args' must be a list or tuple of strings"
                for arg in args:
                    if not isinstance(arg, str):
                        return False, f"All arguments must be strings, got: {type(arg).__name__}"
                try:
                    self.launcher.validate_arguments(args)
                except InvalidArgumentError as err:
                    return False, str(err)

            # Dry-run type validation
            if action == "launch_application" and "dry_run" in parameters:
                if not isinstance(parameters["dry_run"], bool):
                    return False, "Parameter 'dry_run' must be a boolean"

        return True, None

    def execute(self, action: str, parameters: Dict[str, Any]) -> AdapterResult:
        """Execute validated application action and return structured AdapterResult."""
        if action in ("list_applications", "list_allowed_applications"):
            apps = self.launcher.get_allowed_applications()
            return AdapterResult.success_result(
                adapter=self.name,
                action=action,
                message=f"Retrieved {len(apps)} allowlisted applications",
                data={"applications": apps, "allowed_applications": apps, "count": len(apps)},
            )

        elif action in ("check_availability", "is_allowed"):
            app_id = self._extract_app_id(parameters) or ""
            allowed = self.launcher.is_allowed(app_id)
            available = allowed and (self.launcher.resolve_executable(app_id) is not None)
            return AdapterResult.success_result(
                adapter=self.name,
                action=action,
                message=f"Application '{app_id}' available: {available}",
                data={"app_name": app_id, "app_id": app_id, "is_allowed": allowed, "available": available},
            )

        elif action in ("resolve_binary", "resolve_executable"):
            app_id = self._extract_app_id(parameters) or ""
            exe_path = self.launcher.resolve_executable(app_id)
            return AdapterResult.success_result(
                adapter=self.name,
                action=action,
                message=f"Resolved binary path for '{app_id}'" if exe_path else f"No binary found for '{app_id}'",
                data={"app_name": app_id, "app_id": app_id, "binary_path": exe_path, "executable": exe_path, "found": bool(exe_path)},
            )

        elif action == "launch_application":
            app_id = self._extract_app_id(parameters) or ""
            args = parameters.get("args", [])
            dry_run = parameters.get("dry_run", False)

            if dry_run:
                exe_path = self.launcher.resolve_executable(app_id) or f"/usr/bin/{app_id}"
                return AdapterResult.success_result(
                    adapter=self.name,
                    action=action,
                    message=f"Dry run launch for '{app_id}' simulated successfully",
                    data={
                        "app_name": app_id,
                        "app_id": app_id,
                        "dry_run": True,
                        "executable": exe_path,
                        "command": [exe_path] + list(args),
                        "args": list(args),
                    },
                )

            # Check if binary is installed
            exe_path = self.launcher.resolve_executable(app_id)
            if not exe_path:
                return AdapterResult.execution_error(
                    adapter=self.name,
                    action=action,
                    message=(
                        f"Cannot launch '{app_id}': No installed candidate binary found. "
                        "If running in a headless environment without desktop/GUI, this capability is unavailable."
                    ),
                    details={
                        "app_name": app_id,
                        "app_id": app_id,
                        "reason": "binary_not_found",
                        "candidates": self.launcher.allowlist[app_id].get("candidates", []),
                        "desktop_available": False,
                    },
                )

            launch_res = self.launcher.launch(app_id, args=args, dry_run=dry_run)
            status_val = launch_res.get("status")

            if status_val in ("launched", "dry_run"):
                return AdapterResult.success_result(
                    adapter=self.name,
                    action=action,
                    message=f"Application '{app_id}' launch status: {status_val}",
                    data=launch_res,
                )
            else:
                return AdapterResult.execution_error(
                    adapter=self.name,
                    action=action,
                    message=f"Failed to launch '{app_id}': {launch_res.get('error', 'unknown error')}",
                    details=launch_res,
                )

        return AdapterResult.unsupported_action(
            adapter=self.name,
            action=action,
            supported_actions=self.supported_actions,
        )

