"""
AgenticOS - Filesystem Service Adapter
Layer 10: System Services (Filesystem Management Boundary)
Owner: Magesh (Linux/OS Lead)

TEMPORARY LOCAL INTERFACE — REQUIRES TEAM API APPROVAL

This module provides safe, strictly read-only filesystem inspection using
standard POSIX interfaces (os.stat, os.statvfs, os.scandir) and /proc/mounts.

CRITICAL SECURITY CONSTRAINT:
This adapter contains ZERO file modification, creation, deletion, renaming,
permission changes, or mount capabilities. It cannot execute files.
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from .base import BaseAdapter
from .result import AdapterResult, AdapterStatus


class FilesystemAdapter(BaseAdapter):
    """
    Read-only adapter for inspecting Linux files, directories, and mounts.
    Implements BaseAdapter framework contract while preserving direct method interfaces.
    """

    SUPPORTED_ACTIONS: Set[str] = {
        "inspect_path",
        "check_existence",
        "list_directory",
        "get_metadata",
        "get_usage",
        "get_mounts",
    }

    def __init__(self, mounts_path: str = "/proc/mounts", allowed_roots: Optional[List[str]] = None) -> None:
        self.mounts_path = Path(mounts_path)
        self.allowed_roots = [Path(r).resolve() for r in allowed_roots] if allowed_roots else None

    @property
    def name(self) -> str:
        return "filesystem"

    @property
    def supported_actions(self) -> Set[str]:
        return set(self.SUPPORTED_ACTIONS)

    def inspect_path(self, target_path: Union[str, Path]) -> Dict[str, Any]:
        """
        Safely inspect a filesystem path.
        Distinguishes regular files, directories, symlinks, and broken symlinks.
        Never throws exceptions on inaccessible or missing paths.
        """
        p = Path(target_path)
        info: Dict[str, Any] = {
            "path": str(p),
            "exists": False,
            "is_file": False,
            "is_dir": False,
            "is_symlink": False,
            "is_broken_symlink": False,
            "size_bytes": 0,
            "mtime": 0.0,
            "permissions_octal": None,
            "symlink_target": None,
            "status": "not_found",
        }

        try:
            # First check lstat to detect symlinks before dereferencing
            lstat_res = p.lstat()
            info["is_symlink"] = p.is_symlink()

            if info["is_symlink"]:
                try:
                    info["symlink_target"] = str(p.readlink())
                except OSError:
                    pass

                # Check if symlink target exists
                try:
                    stat_res = p.stat()
                    info["exists"] = True
                    info["is_file"] = p.is_file()
                    info["is_dir"] = p.is_dir()
                    info["size_bytes"] = stat_res.st_size
                    info["mtime"] = stat_res.st_mtime
                    info["permissions_octal"] = oct(stat_res.st_mode & 0o777)
                    info["status"] = "ok"
                except (FileNotFoundError, OSError):
                    # Target missing => broken symlink
                    info["exists"] = False
                    info["is_broken_symlink"] = True
                    info["size_bytes"] = lstat_res.st_size
                    info["mtime"] = lstat_res.st_mtime
                    info["permissions_octal"] = oct(lstat_res.st_mode & 0o777)
                    info["status"] = "broken_symlink"
            else:
                # Regular file or directory
                info["exists"] = True
                info["is_file"] = p.is_file()
                info["is_dir"] = p.is_dir()
                info["size_bytes"] = lstat_res.st_size
                info["mtime"] = lstat_res.st_mtime
                info["permissions_octal"] = oct(lstat_res.st_mode & 0o777)
                info["status"] = "ok"

        except FileNotFoundError:
            info["status"] = "not_found"
        except PermissionError:
            info["status"] = "permission_denied"
        except OSError:
            info["status"] = "error"

        return info

    def list_directory(
        self, target_path: Union[str, Path], limit: Optional[int] = 100
    ) -> Dict[str, Any]:
        """
        List the entries of an accessible directory.
        Returns entry summaries and skips unreadable entries gracefully.
        """
        p = Path(target_path)
        result: Dict[str, Any] = {
            "path": str(p),
            "status": "ok",
            "total_entries": 0,
            "entries": [],
        }

        if not p.exists():
            result["status"] = "not_found"
            return result

        if not p.is_dir():
            result["status"] = "not_a_directory"
            return result

        entries: List[Dict[str, Any]] = []
        try:
            with os.scandir(p) as it:
                for entry in it:
                    result["total_entries"] += 1
                    if limit and len(entries) >= limit:
                        continue

                    entry_info: Dict[str, Any] = {
                        "name": entry.name,
                        "is_file": False,
                        "is_dir": False,
                        "is_symlink": False,
                        "size_bytes": 0,
                    }
                    try:
                        entry_info["is_symlink"] = entry.is_symlink()
                        entry_info["is_file"] = entry.is_file()
                        entry_info["is_dir"] = entry.is_dir()
                        if entry_info["is_file"]:
                            entry_info["size_bytes"] = entry.stat().st_size
                    except (PermissionError, OSError):
                        pass

                    entries.append(entry_info)
        except PermissionError:
            result["status"] = "permission_denied"
            return result
        except OSError:
            result["status"] = "error"
            return result

        result["entries"] = entries
        return result

    def get_usage(self, target_path: Union[str, Path] = "/") -> Dict[str, Any]:
        """
        Query storage capacity, free space, and usage percentage for the
        filesystem containing target_path using POSIX os.statvfs.
        """
        p = str(target_path)
        usage: Dict[str, Any] = {
            "path": p,
            "status": "available",
            "total_bytes": 0,
            "free_bytes": 0,
            "available_bytes": 0,
            "used_bytes": 0,
            "usage_percent": 0.0,
        }

        try:
            if hasattr(os, "statvfs"):
                st = os.statvfs(p)
                total = st.f_blocks * st.f_frsize
                free = st.f_bfree * st.f_frsize
                avail = st.f_bavail * st.f_frsize
                used = max(0, total - free)
            else:
                import shutil
                du = shutil.disk_usage(p)
                total = du.total
                free = du.free
                avail = du.free
                used = du.used

            usage["total_bytes"] = total
            usage["free_bytes"] = free
            usage["available_bytes"] = avail
            usage["used_bytes"] = used
            if total > 0:
                usage["usage_percent"] = round((used / total) * 100.0, 2)
        except (FileNotFoundError, OSError):
            usage["status"] = "unavailable"

        return usage

    def get_mounts(self) -> List[Dict[str, Any]]:
        """
        Parse mounted filesystems from Linux /proc/mounts.
        """
        mounts: List[Dict[str, Any]] = []
        if not self.mounts_path.is_file():
            return mounts

        try:
            content = self.mounts_path.read_text(encoding="utf-8", errors="replace")
            for line in content.splitlines():
                parts = line.strip().split()
                if len(parts) >= 4:
                    device = parts[0]
                    mountpoint = parts[1]
                    fstype = parts[2]
                    options = parts[3].split(",")

                    mounts.append({
                        "device": device,
                        "mountpoint": mountpoint,
                        "fstype": fstype,
                        "options": options,
                        "is_read_only": ("ro" in options),
                    })
        except (PermissionError, OSError):
            pass

        return mounts

    def _resolve_target_path(self, parameters: Dict[str, Any], default: Optional[str] = None) -> Optional[str]:
        """Helper to extract 'path' or 'target_path' from parameters."""
        return parameters.get("path", parameters.get("target_path", default))

    def validate(self, action: str, parameters: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Validate filesystem action and parameters against safety boundaries."""
        if action not in self.SUPPORTED_ACTIONS:
            return False, f"Action '{action}' is not supported by {self.name}"

        # Safe parameter type checking
        if not isinstance(parameters, dict):
            return False, "Parameters must be a dictionary"

        # Actions requiring a target path
        if action in ("inspect_path", "check_existence", "get_metadata", "list_directory"):
            target = self._resolve_target_path(parameters)
            if target is None:
                return False, f"Missing required parameter 'path' or 'target_path' for action '{action}'"
            if not isinstance(target, (str, Path)) or str(target).strip() == "":
                return False, "Parameter 'path' must be a non-empty string"
            if "\0" in str(target):
                return False, "Parameter 'path' contains illegal null byte"

            # Check sandbox traversal if allowed_roots is enforced
            if self.allowed_roots:
                resolved = Path(target).resolve()
                if not any(resolved == root or root in resolved.parents for root in self.allowed_roots):
                    return False, f"Path traversal violation: '{target}' resolves outside allowed workspace"

            if action == "list_directory" and "limit" in parameters:
                limit = parameters["limit"]
                if not isinstance(limit, int) or isinstance(limit, bool) or limit < 0:
                    return False, "Parameter 'limit' must be a non-negative integer"

        elif action == "get_usage":
            target = self._resolve_target_path(parameters, default="/")
            if not isinstance(target, (str, Path)):
                return False, "Parameter 'path' must be a string or Path"
            if "\0" in str(target):
                return False, "Parameter 'path' contains illegal null byte"

        return True, None

    def execute(self, action: str, parameters: Dict[str, Any]) -> AdapterResult:
        """Execute validated filesystem action and return AdapterResult."""
        if action in ("inspect_path", "get_metadata"):
            target = self._resolve_target_path(parameters)
            info = self.inspect_path(target)  # type: ignore
            return AdapterResult.success_result(
                adapter=self.name,
                action=action,
                message=f"Path inspection status: {info['status']}",
                data=info,
            )

        elif action == "check_existence":
            target = self._resolve_target_path(parameters)
            info = self.inspect_path(target)  # type: ignore
            return AdapterResult.success_result(
                adapter=self.name,
                action=action,
                message=f"Path exists: {info['exists']}",
                data={"path": info["path"], "exists": info["exists"], "status": info["status"]},
            )

        elif action == "list_directory":
            target = self._resolve_target_path(parameters)
            limit = parameters.get("limit", 100)
            listing = self.list_directory(target, limit=limit)  # type: ignore
            if listing.get("status") == "ok":
                return AdapterResult.success_result(
                    adapter=self.name,
                    action=action,
                    message=f"Directory listed successfully ({listing['total_entries']} entries found)",
                    data=listing,
                )
            else:
                return AdapterResult.execution_error(
                    adapter=self.name,
                    action=action,
                    message=f"Failed to list directory: {listing['status']}",
                    details=listing,
                )

        elif action == "get_usage":
            target = self._resolve_target_path(parameters, default="/")
            usage = self.get_usage(target)  # type: ignore
            return AdapterResult.success_result(
                adapter=self.name,
                action=action,
                message=f"Filesystem capacity queried for {usage['path']}",
                data=usage,
            )

        elif action == "get_mounts":
            mounts = self.get_mounts()
            return AdapterResult.success_result(
                adapter=self.name,
                action=action,
                message=f"Retrieved {len(mounts)} mount points",
                data={"mounts": mounts, "count": len(mounts)},
            )

        return AdapterResult.unsupported_action(
            adapter=self.name,
            action=action,
            supported_actions=self.supported_actions,
        )


if __name__ == "__main__":
    import json
    adapter = FilesystemAdapter()
    print("Filesystem usage at root (/):")
    print(json.dumps(adapter.get_usage("/"), indent=2))
    print("\nRoot directory listing sample:")
    print(json.dumps(adapter.list_directory("/", limit=5), indent=2))
    print("\nAdapter execution via run():")
    res = adapter.run("inspect_path", {"path": "/etc"})
    print(json.dumps(res.to_dict(), indent=2))
