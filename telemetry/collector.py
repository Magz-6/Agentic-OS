"""
AgenticOS - System Telemetry Collector
Layer 11/13: System Telemetry & Metrics
Owner: Magesh (Linux/OS Lead)

TEMPORARY LOCAL INTERFACE — REQUIRES TEAM API APPROVAL

This module provides safe, read-only system telemetry collection using Linux
user-space pseudo-filesystems (/proc and /sys) and the Python standard library.
It never modifies process state, cgroups, or kernel parameters.
"""

import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class SystemTelemetryCollector:
    """
    Read-only collector for dynamic system metrics on Linux.
    
    Parses CPU counters, memory utilization, system load, uptime, network I/O,
    and process summaries directly from /proc without elevated privileges.
    """

    def __init__(self, proc_path: str = "/proc", sys_path: str = "/sys") -> None:
        self.proc_path = Path(proc_path)
        self.sys_path = Path(sys_path)
        self._last_cpu_sample: Optional[Dict[str, int]] = None

    def _read_file_safe(self, path: Path) -> Optional[str]:
        """Safely read text from a path, returning None if unreadable or absent."""
        try:
            if path.is_file():
                return path.read_text(encoding="utf-8", errors="replace").strip()
        except (PermissionError, OSError, UnicodeDecodeError):
            pass
        return None

    def get_cpu_times(self) -> Optional[Dict[str, int]]:
        """
        Parse raw cumulative CPU jiffies from the first line of /proc/stat.
        Format: cpu user nice system idle iowait irq softirq steal guest guest_nice
        """
        stat_path = self.proc_path / "stat"
        content = self._read_file_safe(stat_path)
        if not content:
            return None

        for line in content.splitlines():
            parts = line.strip().split()
            if parts and parts[0] == "cpu":
                try:
                    fields = [int(p) for p in parts[1:]]
                    user = fields[0] if len(fields) > 0 else 0
                    nice = fields[1] if len(fields) > 1 else 0
                    system = fields[2] if len(fields) > 2 else 0
                    idle = fields[3] if len(fields) > 3 else 0
                    iowait = fields[4] if len(fields) > 4 else 0
                    irq = fields[5] if len(fields) > 5 else 0
                    softirq = fields[6] if len(fields) > 6 else 0
                    steal = fields[7] if len(fields) > 7 else 0

                    idle_total = idle + iowait
                    non_idle = user + nice + system + irq + softirq + steal
                    total = idle_total + non_idle

                    return {
                        "user": user,
                        "nice": nice,
                        "system": system,
                        "idle": idle,
                        "iowait": iowait,
                        "irq": irq,
                        "softirq": softirq,
                        "steal": steal,
                        "idle_total": idle_total,
                        "total": total,
                    }
                except (ValueError, IndexError):
                    return None
        return None

    @staticmethod
    def calculate_cpu_percent(sample1: Dict[str, int], sample2: Dict[str, int]) -> float:
        """
        Calculate the CPU utilization percentage between two /proc/stat samples.
        """
        total_delta = sample2["total"] - sample1["total"]
        idle_delta = sample2["idle_total"] - sample1["idle_total"]

        if total_delta <= 0:
            return 0.0

        busy_delta = total_delta - idle_delta
        percent = (busy_delta / total_delta) * 100.0
        return max(0.0, min(100.0, round(percent, 2)))

    def get_cpu_telemetry(self, sample_interval: float = 0.05) -> Dict[str, Any]:
        """
        Gather CPU telemetry including calculated utilization percentage.
        If an earlier sample is stored and interval is 0, uses the stored sample.
        Otherwise takes two samples separated by sample_interval.
        """
        logical_cores = os.cpu_count() or 0
        s1 = self.get_cpu_times()

        if s1 is None:
            return {
                "usage_percent": 0.0,
                "logical_cores": logical_cores,
                "status": "unavailable",
            }

        usage_pct = 0.0
        if sample_interval > 0:
            time.sleep(sample_interval)
            s2 = self.get_cpu_times()
            if s2:
                usage_pct = self.calculate_cpu_percent(s1, s2)
        elif self._last_cpu_sample:
            usage_pct = self.calculate_cpu_percent(self._last_cpu_sample, s1)

        self._last_cpu_sample = s1

        return {
            "usage_percent": usage_pct,
            "logical_cores": logical_cores,
            "status": "available",
            "jiffies": s1,
        }

    def get_memory_telemetry(self) -> Dict[str, Any]:
        """
        Parse memory usage and swap statistics from /proc/meminfo.
        Converts kB to bytes and calculates usage percentage.
        """
        mem_info: Dict[str, Any] = {
            "total_bytes": 0,
            "available_bytes": 0,
            "used_bytes": 0,
            "free_bytes": 0,
            "usage_percent": 0.0,
            "swap_total_bytes": 0,
            "swap_free_bytes": 0,
            "swap_used_bytes": 0,
            "swap_usage_percent": 0.0,
            "status": "available",
        }

        content = self._read_file_safe(self.proc_path / "meminfo")
        if not content:
            mem_info["status"] = "unavailable"
            return mem_info

        fields: Dict[str, int] = {}
        for line in content.splitlines():
            parts = line.split(":")
            if len(parts) == 2:
                key = parts[0].strip()
                val_parts = parts[1].strip().split()
                if val_parts:
                    try:
                        fields[key] = int(val_parts[0]) * 1024  # kB to bytes
                    except ValueError:
                        continue

        total = fields.get("MemTotal", 0)
        free = fields.get("MemFree", 0)
        available = fields.get("MemAvailable", free)
        used = max(0, total - available)

        mem_info["total_bytes"] = total
        mem_info["free_bytes"] = free
        mem_info["available_bytes"] = available
        mem_info["used_bytes"] = used
        if total > 0:
            mem_info["usage_percent"] = round((used / total) * 100.0, 2)

        swap_total = fields.get("SwapTotal", 0)
        swap_free = fields.get("SwapFree", 0)
        swap_used = max(0, swap_total - swap_free)

        mem_info["swap_total_bytes"] = swap_total
        mem_info["swap_free_bytes"] = swap_free
        mem_info["swap_used_bytes"] = swap_used
        if swap_total > 0:
            mem_info["swap_usage_percent"] = round((swap_used / swap_total) * 100.0, 2)

        return mem_info

    def get_load_average(self) -> Dict[str, Any]:
        """
        Parse 1-minute, 5-minute, and 15-minute load averages from /proc/loadavg.
        """
        load_info: Dict[str, Any] = {
            "load_1m": 0.0,
            "load_5m": 0.0,
            "load_15m": 0.0,
            "status": "available",
        }

        content = self._read_file_safe(self.proc_path / "loadavg")
        if not content:
            load_info["status"] = "unavailable"
            return load_info

        parts = content.split()
        if len(parts) >= 3:
            try:
                load_info["load_1m"] = float(parts[0])
                load_info["load_5m"] = float(parts[1])
                load_info["load_15m"] = float(parts[2])
            except ValueError:
                load_info["status"] = "malformed"
        else:
            load_info["status"] = "malformed"

        return load_info

    def get_uptime(self) -> Dict[str, Any]:
        """
        Parse system uptime and idle time in seconds from /proc/uptime.
        """
        uptime_info: Dict[str, Any] = {
            "uptime_seconds": 0.0,
            "idle_seconds": 0.0,
            "status": "available",
        }

        content = self._read_file_safe(self.proc_path / "uptime")
        if not content:
            uptime_info["status"] = "unavailable"
            return uptime_info

        parts = content.split()
        if len(parts) >= 1:
            try:
                uptime_info["uptime_seconds"] = float(parts[0])
                if len(parts) >= 2:
                    uptime_info["idle_seconds"] = float(parts[1])
            except ValueError:
                uptime_info["status"] = "malformed"

        return uptime_info

    def get_network_telemetry(self) -> List[Dict[str, Any]]:
        """
        Parse interface network traffic counters from /proc/net/dev.
        """
        interfaces: List[Dict[str, Any]] = []
        content = self._read_file_safe(self.proc_path / "net" / "dev")
        if not content:
            return interfaces

        lines = content.splitlines()
        # First two lines are headers
        for line in lines[2:]:
            if ":" not in line:
                continue
            iface_name, rest = line.split(":", 1)
            iface_name = iface_name.strip()
            cols = rest.strip().split()
            if len(cols) >= 16:
                try:
                    rx_bytes = int(cols[0])
                    rx_packets = int(cols[1])
                    tx_bytes = int(cols[8])
                    tx_packets = int(cols[9])

                    # Safely check operstate from sysfs if accessible
                    operstate = "unknown"
                    state_file = self.sys_path / "class" / "net" / iface_name / "operstate"
                    if state_file.is_file():
                        operstate = self._read_file_safe(state_file) or "unknown"

                    interfaces.append({
                        "interface": iface_name,
                        "rx_bytes": rx_bytes,
                        "tx_bytes": tx_bytes,
                        "rx_packets": rx_packets,
                        "tx_packets": tx_packets,
                        "operstate": operstate,
                    })
                except (ValueError, IndexError):
                    continue

        return interfaces

    def get_process_summary(self) -> Dict[str, Any]:
        """
        Read total process count and currently running processes from /proc/[pid]/stat.
        Gracefully ignores processes that terminate during the scan.
        """
        summary = {
            "total_processes": 0,
            "running_processes": 0,
            "status": "available",
        }

        if not self.proc_path.is_dir():
            summary["status"] = "unavailable"
            return summary

        total = 0
        running = 0

        try:
            for entry in self.proc_path.iterdir():
                if entry.name.isdigit():
                    total += 1
                    stat_file = entry / "stat"
                    # Read process state safely
                    try:
                        content = self._read_file_safe(stat_file)
                        if content:
                            # State is character right after closing parenthesis of comm
                            rparen_idx = content.rfind(")")
                            if rparen_idx != -1 and len(content) > rparen_idx + 2:
                                state = content[rparen_idx + 2]
                                if state == "R":
                                    running += 1
                    except (PermissionError, OSError):
                        pass
        except (PermissionError, OSError):
            summary["status"] = "partial"

        summary["total_processes"] = total
        summary["running_processes"] = running
        return summary

    def collect_all(self, sample_interval: float = 0.05) -> Dict[str, Any]:
        """
        Collect complete dynamic telemetry snapshot.
        """
        return {
            "schema_version": "0.1.0",
            "layer": "Layer 11/13: System Telemetry",
            "timestamp": time.time(),
            "cpu": self.get_cpu_telemetry(sample_interval=sample_interval),
            "memory": self.get_memory_telemetry(),
            "load_average": self.get_load_average(),
            "uptime": self.get_uptime(),
            "network": self.get_network_telemetry(),
            "process_summary": self.get_process_summary(),
        }


if __name__ == "__main__":
    import json
    collector = SystemTelemetryCollector()
    snapshot = collector.collect_all()
    print(json.dumps(snapshot, indent=2))
