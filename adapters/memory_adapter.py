"""
AgenticOS - Memory Service Adapter
Layer 10: System Services (Memory Management Boundary)
Owner: Magesh (Linux/OS Lead)

TEMPORARY LOCAL INTERFACE — REQUIRES TEAM API APPROVAL

This module provides safe, read-only memory and swap inspection using Linux
/proc/meminfo and the Python standard library.

CRITICAL SECURITY CONSTRAINT:
This adapter contains ZERO memory allocation or cgroup modification logic.
It does not alter kernel memory limits or process memory spaces.
"""

from pathlib import Path
from typing import Any, Dict, Optional


class MemoryAdapter:
    """
    Read-only adapter for inspecting Linux system memory.
    
    Parses detailed kernel memory counters including total, available, free,
    used, page cache, buffers, and swap from /proc/meminfo.
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

    def get_memory_metrics(self) -> Dict[str, Any]:
        """
        Parse comprehensive memory and swap metrics from /proc/meminfo.
        All byte quantities are returned in standard bytes (integers).
        """
        metrics: Dict[str, Any] = {
            "status": "available",
            "total_bytes": 0,
            "available_bytes": 0,
            "free_bytes": 0,
            "used_bytes": 0,
            "usage_percent": 0.0,
            "buffers_bytes": 0,
            "cached_bytes": 0,
            "slab_reclaimable_bytes": 0,
            "swap_total_bytes": 0,
            "swap_free_bytes": 0,
            "swap_used_bytes": 0,
            "swap_usage_percent": 0.0,
        }

        content = self._read_file_safe(self.proc_path / "meminfo")
        if not content:
            metrics["status"] = "unavailable"
            return metrics

        fields_kb: Dict[str, int] = {}
        for line in content.splitlines():
            if ":" not in line:
                continue
            k, v = [part.strip() for part in line.split(":", 1)]
            val_parts = v.split()
            if val_parts:
                try:
                    fields_kb[k] = int(val_parts[0])
                except ValueError:
                    continue

        total = fields_kb.get("MemTotal", 0) * 1024
        free = fields_kb.get("MemFree", 0) * 1024
        available = fields_kb.get("MemAvailable", fields_kb.get("MemFree", 0)) * 1024
        used = max(0, total - available)

        metrics["total_bytes"] = total
        metrics["free_bytes"] = free
        metrics["available_bytes"] = available
        metrics["used_bytes"] = used
        if total > 0:
            metrics["usage_percent"] = round((used / total) * 100.0, 2)

        metrics["buffers_bytes"] = fields_kb.get("Buffers", 0) * 1024
        metrics["cached_bytes"] = fields_kb.get("Cached", 0) * 1024
        metrics["slab_reclaimable_bytes"] = fields_kb.get("SReclaimable", 0) * 1024

        swap_total = fields_kb.get("SwapTotal", 0) * 1024
        swap_free = fields_kb.get("SwapFree", 0) * 1024
        swap_used = max(0, swap_total - swap_free)

        metrics["swap_total_bytes"] = swap_total
        metrics["swap_free_bytes"] = swap_free
        metrics["swap_used_bytes"] = swap_used
        if swap_total > 0:
            metrics["swap_usage_percent"] = round((swap_used / swap_total) * 100.0, 2)

        return metrics

    def get_summary(self) -> Dict[str, Any]:
        """
        Return high-level human-readable memory summary alongside raw metrics.
        """
        m = self.get_memory_metrics()
        return {
            "status": m["status"],
            "total_mb": round(m["total_bytes"] / (1024 * 1024), 2),
            "available_mb": round(m["available_bytes"] / (1024 * 1024), 2),
            "used_mb": round(m["used_bytes"] / (1024 * 1024), 2),
            "usage_percent": m["usage_percent"],
            "swap_used_mb": round(m["swap_used_bytes"] / (1024 * 1024), 2),
            "swap_usage_percent": m["swap_usage_percent"],
            "raw": m,
        }


if __name__ == "__main__":
    import json
    adapter = MemoryAdapter()
    print(json.dumps(adapter.get_summary(), indent=2))
