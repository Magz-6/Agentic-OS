"""
AgenticOS - Process Service Adapter
Layer 10: System Services (Process Management Boundary)
Owner: Magesh (Linux/OS Lead)

TEMPORARY LOCAL INTERFACE — REQUIRES TEAM API APPROVAL

This module provides safe, read-only process inspection using Linux /proc/[pid]
interfaces and the Python standard library.

CRITICAL SECURITY CONSTRAINT:
This adapter contains ZERO process modification capabilities. It CANNOT kill,
pause, resume, reprioritize, or execute processes.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional


class ProcessAdapter:
    """
    Read-only adapter for inspecting Linux processes.
    
    Extracts process metadata (PID, executable name, command-line arguments,
    state, memory RSS, and CPU ticks) directly from /proc/[pid]/.
    """

    def __init__(self, proc_path: str = "/proc") -> None:
        self.proc_path = Path(proc_path)

    def _read_file_safe(self, path: Path) -> Optional[str]:
        """Safely read text from a path, returning None if unreadable or absent."""
        try:
            if path.is_file():
                return path.read_text(encoding="utf-8", errors="replace").strip()
        except (PermissionError, OSError, UnicodeDecodeError):
            pass
        return None

    def _read_bytes_safe(self, path: Path) -> Optional[bytes]:
        """Safely read binary data (e.g. null-separated cmdline) from a path."""
        try:
            if path.is_file():
                return path.read_bytes()
        except (PermissionError, OSError):
            pass
        return None

    def get_process_info(self, pid: int) -> Optional[Dict[str, Any]]:
        """
        Inspect an individual process by PID.
        Returns a structured dictionary, or None if the process does not exist
        or terminated during inspection.
        """
        pid_dir = self.proc_path / str(pid)
        if not pid_dir.is_dir():
            return None

        # 1. Process Name (from /proc/[pid]/comm or status)
        name = self._read_file_safe(pid_dir / "comm") or "unknown"

        # 2. Command Line (null-separated arguments from /proc/[pid]/cmdline)
        cmdline_bytes = self._read_bytes_safe(pid_dir / "cmdline")
        cmdline: List[str] = []
        if cmdline_bytes:
            cmdline = [
                arg.decode("utf-8", errors="replace")
                for arg in cmdline_bytes.split(b"\x00")
                if arg
            ]

        # 3. Status metadata (/proc/[pid]/status)
        status_content = self._read_file_safe(pid_dir / "status")
        state = "unknown"
        ppid = None
        threads = 1
        vm_rss_bytes = 0
        vm_size_bytes = 0

        if status_content:
            for line in status_content.splitlines():
                if ":" not in line:
                    continue
                k, v = [part.strip() for part in line.split(":", 1)]
                if k == "State":
                    state = v.split()[0] if v else "unknown"
                elif k == "PPid":
                    try:
                        ppid = int(v)
                    except ValueError:
                        pass
                elif k == "Threads":
                    try:
                        threads = int(v)
                    except ValueError:
                        pass
                elif k == "VmRSS":
                    try:
                        # VmRSS is in kB
                        vm_rss_bytes = int(v.split()[0]) * 1024
                    except (ValueError, IndexError):
                        pass
                elif k == "VmSize":
                    try:
                        vm_size_bytes = int(v.split()[0]) * 1024
                    except (ValueError, IndexError):
                        pass
                elif k == "Name" and name == "unknown":
                    name = v

        # 4. CPU ticks from /proc/[pid]/stat
        utime_jiffies = 0
        stime_jiffies = 0
        starttime_ticks = 0

        stat_content = self._read_file_safe(pid_dir / "stat")
        if stat_content:
            rparen_idx = stat_content.rfind(")")
            if rparen_idx != -1 and len(stat_content) > rparen_idx + 2:
                fields = stat_content[rparen_idx + 2:].split()
                # fields are 0-indexed relative to post-paren:
                # field 0 = state (overall index 3)
                # field 11 = utime (overall index 14)
                # field 12 = stime (overall index 15)
                # field 19 = starttime (overall index 22)
                try:
                    if len(fields) > 11:
                        utime_jiffies = int(fields[11])
                    if len(fields) > 12:
                        stime_jiffies = int(fields[12])
                    if len(fields) > 19:
                        starttime_ticks = int(fields[19])
                except (ValueError, IndexError):
                    pass

        return {
            "pid": pid,
            "name": name,
            "state": state,
            "ppid": ppid,
            "threads": threads,
            "cmdline": cmdline,
            "memory": {
                "vm_rss_bytes": vm_rss_bytes,
                "vm_size_bytes": vm_size_bytes,
            },
            "cpu_ticks": {
                "utime": utime_jiffies,
                "stime": stime_jiffies,
            },
            "starttime_ticks": starttime_ticks,
        }

    def list_processes(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        List all accessible running processes.
        Gracefully skips processes that terminate during the scan.
        """
        processes: List[Dict[str, Any]] = []
        if not self.proc_path.is_dir():
            return processes

        try:
            entries = sorted(
                [int(e.name) for e in self.proc_path.iterdir() if e.name.isdigit()]
            )
        except (PermissionError, OSError):
            return processes

        for pid in entries:
            info = self.get_process_info(pid)
            if info is not None:
                processes.append(info)
                if limit and len(processes) >= limit:
                    break

        return processes

    def get_process_count(self) -> int:
        """Return the number of accessible active processes."""
        if not self.proc_path.is_dir():
            return 0
        try:
            return sum(1 for e in self.proc_path.iterdir() if e.name.isdigit())
        except (PermissionError, OSError):
            return 0


if __name__ == "__main__":
    import json
    adapter = ProcessAdapter()
    print("Process count:", adapter.get_process_count())
    sample = adapter.list_processes(limit=5)
    print(json.dumps(sample, indent=2))
