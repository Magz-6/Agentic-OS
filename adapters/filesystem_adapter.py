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
from typing import Any, Dict, List, Optional, Union


class FilesystemAdapter:
    """
    Read-only adapter for inspecting Linux files, directories, and mounts.
    """

    def __init__(self, mounts_path: str = "/proc/mounts") -> None:
        self.mounts_path = Path(mounts_path)

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


if __name__ == "__main__":
    import json
    adapter = FilesystemAdapter()
    print("Filesystem usage at root (/):")
    print(json.dumps(adapter.get_usage("/"), indent=2))
    print("\nRoot directory listing sample:")
    print(json.dumps(adapter.list_directory("/", limit=5), indent=2))
