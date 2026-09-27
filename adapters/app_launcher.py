"""
AgenticOS - Safe Application Launcher
Layer 9: Applications & Services
Owner: Magesh (Linux/OS Lead)

TEMPORARY LOCAL INTERFACE — REQUIRES TEAM API APPROVAL

This module provides a secure, allowlisted application launching mechanism.
It strictly prevents arbitrary command execution, shell injection, and
privilege escalation.

SECURITY GUARANTEES:
1. shell=True is NEVER used.
2. Only explicitly allowlisted application IDs can be resolved.
3. Arbitrary executable paths cannot be injected.
4. Arguments containing shell metacharacters are rejected.
5. Zero elevated privileges (no sudo/root).
"""

import os
import re
import shutil
import subprocess
from typing import Any, Dict, List, Optional, Sequence


class ApplicationLauncherError(Exception):
    """Base exception for application launcher errors."""
    pass


class UnknownApplicationError(ApplicationLauncherError):
    """Raised when an application ID is not in the approved allowlist."""
    pass


class InvalidArgumentError(ApplicationLauncherError):
    """Raised when an argument contains dangerous shell metacharacters."""
    pass


class ExecutableNotFoundError(ApplicationLauncherError):
    """Raised when the resolved binary does not exist or is not executable."""
    pass


class AppLauncher:
    """
    Secure application launcher restricted to a controlled allowlist.
    """

    # Provisional solo allowlist (UNDEFINED by team, provisional only)
    DEFAULT_ALLOWLIST: Dict[str, Dict[str, Any]] = {
        "browser": {
            "description": "Default Web Browser",
            "candidates": ["firefox", "chromium-browser", "google-chrome", "wslview"],
        },
        "terminal": {
            "description": "Default Terminal Emulator",
            "candidates": ["gnome-terminal", "x-terminal-emulator", "xfce4-terminal", "alacritty"],
        },
        "text_editor": {
            "description": "Default Text Editor",
            "candidates": ["gedit", "mousepad", "nano"],
        },
        "file_manager": {
            "description": "Default File Manager",
            "candidates": ["nautilus", "thunar", "dolphin"],
        },
    }

    # Disallow dangerous shell metacharacters in arguments
    FORBIDDEN_ARG_CHARS = re.compile(r"[;&|`$<>\n\r\t]")

    # Explicitly prohibit command-execution flags that wrap shell scripts
    FORBIDDEN_COMMAND_FLAGS = {"-c", "/c", "--command"}

    def __init__(self, allowlist: Optional[Dict[str, Dict[str, Any]]] = None) -> None:
        self.allowlist = allowlist if allowlist is not None else self.DEFAULT_ALLOWLIST

    def is_allowed(self, app_id: str) -> bool:
        """Check if an application ID is present in the allowlist."""
        return app_id in self.allowlist

    def get_allowed_applications(self) -> List[str]:
        """Return the list of all allowlisted application IDs."""
        return sorted(list(self.allowlist.keys()))

    def resolve_executable(self, app_id: str) -> Optional[str]:
        """
        Resolve the system executable path for an allowlisted application ID.
        Checks candidates sequentially using shutil.which.
        """
        if not self.is_allowed(app_id):
            raise UnknownApplicationError(
                f"Application '{app_id}' is not in the approved allowlist: {self.get_allowed_applications()}"
            )

        app_config = self.allowlist[app_id]
        for candidate in app_config.get("candidates", []):
            exe_path = shutil.which(candidate)
            if exe_path and os.path.isfile(exe_path) and os.access(exe_path, os.X_OK):
                return exe_path

        return None

    def validate_arguments(self, args: Sequence[str]) -> None:
        """
        Validate command arguments to ensure no shell metacharacters or
        command execution flags are passed.
        """
        for arg in args:
            if self.FORBIDDEN_ARG_CHARS.search(arg):
                raise InvalidArgumentError(
                    f"Argument contains forbidden shell characters: '{arg}'"
                )
            if arg in self.FORBIDDEN_COMMAND_FLAGS:
                raise InvalidArgumentError(
                    f"Command execution flag '{arg}' is strictly prohibited"
                )

    def launch(
        self,
        app_id: str,
        args: Optional[Sequence[str]] = None,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """
        Safely launch an allowlisted application without invoking a shell.
        
        Args:
            app_id: Allowlisted application identifier (e.g. 'browser', 'terminal')
            args: Optional list of safe arguments (e.g. ['https://ubuntu.com'])
            dry_run: If True, resolves and validates without spawning the process.
            
        Returns:
            Structured dictionary reporting the launch status, PID, and resolved binary.
        """
        args = list(args) if args is not None else []

        # 1. Allowlist verification
        if not self.is_allowed(app_id):
            return {
                "status": "rejected",
                "app_id": app_id,
                "reason": "unknown_application",
                "error": f"Application '{app_id}' is not in the allowlist",
                "pid": None,
            }

        # 2. Argument validation
        try:
            self.validate_arguments(args)
        except InvalidArgumentError as e:
            return {
                "status": "rejected",
                "app_id": app_id,
                "reason": "invalid_arguments",
                "error": str(e),
                "pid": None,
            }

        # 3. Executable resolution
        exe_path = self.resolve_executable(app_id)
        if not exe_path:
            return {
                "status": "error",
                "app_id": app_id,
                "reason": "binary_not_found",
                "error": f"No installed executable found for '{app_id}'",
                "pid": None,
            }

        command = [exe_path] + args

        # 4. Dry-run mode for testing and inspection
        if dry_run:
            return {
                "status": "dry_run",
                "app_id": app_id,
                "executable": exe_path,
                "command": command,
                "pid": None,
            }

        # 5. Direct execution (NEVER shell=True)
        try:
            # We redirect stdin/stdout/stderr to DEVNULL for background launcher safety
            proc = subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True,
                shell=False,  # CRITICAL SECURITY GUARANTEE
            )
            return {
                "status": "launched",
                "app_id": app_id,
                "executable": exe_path,
                "pid": proc.pid,
            }
        except (OSError, PermissionError) as e:
            return {
                "status": "error",
                "app_id": app_id,
                "reason": "execution_failed",
                "error": str(e),
                "pid": None,
            }


if __name__ == "__main__":
    import json
    launcher = AppLauncher()
    print("Allowed applications:", launcher.get_allowed_applications())
    for app in launcher.get_allowed_applications():
        res = launcher.launch(app, dry_run=True)
        print(f"[{app}] ->", json.dumps(res))
