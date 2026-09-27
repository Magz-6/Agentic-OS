"""
AgenticOS - Hardware Information Collector
Layer 13: Hardware Detection and Reporting
Owner: Magesh (Linux/OS Lead)

TEMPORARY LOCAL INTERFACE — REQUIRES TEAM API APPROVAL

This module provides safe, read-only hardware inspection using Linux user-space
pseudo-filesystems (/proc and /sys) and the Python standard library.
"""

import os
import platform
from pathlib import Path
from typing import Any, Dict, List, Optional


class HardwareDetector:
    """
    Read-only hardware detector for Linux systems.
    
    Extracts hardware and platform metadata from /proc and /sys.
    Allows injecting custom root paths for safe unit testing without root access.
    """

    def __init__(self, proc_path: str = "/proc", sys_path: str = "/sys") -> None:
        self.proc_path = Path(proc_path)
        self.sys_path = Path(sys_path)

    def _read_file_safe(self, path: Path) -> Optional[str]:
        """Safely read text from a path, returning None if unreadable or absent."""
        try:
            if path.is_file():
                return path.read_text(encoding="utf-8", errors="replace").strip()
        except (PermissionError, OSError, UnicodeDecodeError):
            pass
        return None

    def get_cpu_info(self) -> Dict[str, Any]:
        """
        Parse CPU model, logical core count, and architecture from /proc/cpuinfo.
        """
        cpu_info: Dict[str, Any] = {
            "model_name": "unknown",
            "logical_cores": 0,
            "architecture": platform.machine() or "unknown",
            "mhz": None,
            "flags": [],
        }

        cpuinfo_path = self.proc_path / "cpuinfo"
        content = self._read_file_safe(cpuinfo_path)
        if not content:
            # Fallback for core count when /proc/cpuinfo is inaccessible
            cpu_info["logical_cores"] = os.cpu_count() or 0
            return cpu_info

        core_count = 0
        for line in content.splitlines():
            line = line.strip()
            if not line or ":" not in line:
                continue
            key, val = [part.strip() for part in line.split(":", 1)]

            if key == "processor":
                core_count += 1
            elif key == "model name" and cpu_info["model_name"] == "unknown":
                cpu_info["model_name"] = val
            elif key in ("cpu MHz", "clock") and cpu_info["mhz"] is None:
                try:
                    cpu_info["mhz"] = float(val)
                except ValueError:
                    pass
            elif key in ("flags", "Features") and not cpu_info["flags"]:
                cpu_info["flags"] = val.split()

        cpu_info["logical_cores"] = core_count if core_count > 0 else (os.cpu_count() or 0)
        return cpu_info

    def get_memory_info(self) -> Dict[str, Any]:
        """
        Parse memory capacity from /proc/meminfo.
        Values are returned in bytes for consistency.
        """
        mem_info: Dict[str, Any] = {
            "total_bytes": 0,
            "available_bytes": 0,
            "free_bytes": 0,
            "swap_total_bytes": 0,
            "swap_free_bytes": 0,
            "status": "available",
        }

        meminfo_path = self.proc_path / "meminfo"
        content = self._read_file_safe(meminfo_path)
        if not content:
            mem_info["status"] = "unavailable"
            return mem_info

        fields_kb: Dict[str, int] = {}
        for line in content.splitlines():
            parts = line.split(":")
            if len(parts) == 2:
                key = parts[0].strip()
                val_parts = parts[1].strip().split()
                if val_parts:
                    try:
                        fields_kb[key] = int(val_parts[0])
                    except ValueError:
                        continue

        # Convert kB (1024 bytes) to bytes
        mem_info["total_bytes"] = fields_kb.get("MemTotal", 0) * 1024
        mem_info["free_bytes"] = fields_kb.get("MemFree", 0) * 1024
        mem_info["available_bytes"] = fields_kb.get("MemAvailable", fields_kb.get("MemFree", 0)) * 1024
        mem_info["swap_total_bytes"] = fields_kb.get("SwapTotal", 0) * 1024
        mem_info["swap_free_bytes"] = fields_kb.get("SwapFree", 0) * 1024
        return mem_info

    def get_platform_info(self) -> Dict[str, Any]:
        """
        Collect OS distribution, kernel version, and virtualization markers.
        """
        return {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "python_version": platform.python_version(),
            "node": platform.node(),
            "is_virtualized_environment": self._detect_virtualization(),
        }

    def _detect_virtualization(self) -> bool:
        """Heuristic check for virtual machine / container / WSL2 environment."""
        release = platform.release().lower()
        if "wsl" in release or "microsoft" in release:
            return True

        # Check /sys/class/dmi/id/product_name or sys_vendor
        sys_vendor = self._read_file_safe(self.sys_path / "class" / "dmi" / "id" / "sys_vendor")
        if sys_vendor:
            vendor = sys_vendor.lower()
            if any(v in vendor for v in ("qemu", "kvm", "vmware", "virtualbox", "microsoft", "xen")):
                return True

        return False

    def get_dmi_info(self) -> Dict[str, str]:
        """
        Read DMI (Desktop Management Interface) hardware data from /sys/class/dmi/id.
        In WSL2 or restricted containers, these are often unavailable without root.
        """
        dmi_path = self.sys_path / "class" / "dmi" / "id"
        keys = ["sys_vendor", "product_name", "product_version", "bios_vendor", "bios_version"]
        dmi: Dict[str, str] = {}
        for key in keys:
            val = self._read_file_safe(dmi_path / key)
            dmi[key] = val if val is not None else "unavailable"
        return dmi

    def get_block_devices(self) -> List[Dict[str, Any]]:
        """
        Query block devices (disks, partitions) from /sys/block.
        """
        devices: List[Dict[str, Any]] = []
        block_dir = self.sys_path / "class" / "block"
        if not block_dir.is_dir():
            block_dir = self.sys_path / "block"

        if not block_dir.is_dir():
            return devices

        try:
            for entry in sorted(block_dir.iterdir()):
                dev_name = entry.name
                # Filter out loop and ram devices for cleaner hardware summary
                if dev_name.startswith(("loop", "ram")):
                    continue

                size_sectors_str = self._read_file_safe(entry / "size")
                size_bytes = 0
                if size_sectors_str:
                    try:
                        # Linux sectors are typically 512 bytes
                        size_bytes = int(size_sectors_str) * 512
                    except ValueError:
                        pass

                removable_str = self._read_file_safe(entry / "removable")
                ro_str = self._read_file_safe(entry / "ro")

                devices.append({
                    "name": dev_name,
                    "size_bytes": size_bytes,
                    "removable": (removable_str == "1"),
                    "read_only": (ro_str == "1"),
                })
        except (PermissionError, OSError):
            pass

        return devices

    def get_network_interfaces(self) -> List[Dict[str, Any]]:
        """
        Query network interface names and operational states from /sys/class/net.
        """
        interfaces: List[Dict[str, Any]] = []
        net_dir = self.sys_path / "class" / "net"
        if not net_dir.is_dir():
            return interfaces

        try:
            for iface_entry in sorted(net_dir.iterdir()):
                name = iface_entry.name
                operstate = self._read_file_safe(iface_entry / "operstate") or "unknown"
                mtu_str = self._read_file_safe(iface_entry / "mtu")
                mtu = int(mtu_str) if mtu_str and mtu_str.isdigit() else None
                address = self._read_file_safe(iface_entry / "address") or "unavailable"

                interfaces.append({
                    "interface": name,
                    "operstate": operstate,
                    "mtu": mtu,
                    "mac_address": address,
                })
        except (PermissionError, OSError):
            pass

        return interfaces

    def collect_all(self) -> Dict[str, Any]:
        """
        Aggregate all hardware and platform detection into a structured report.
        """
        return {
            "schema_version": "0.1.0",
            "layer": "Layer 13: Hardware",
            "platform": self.get_platform_info(),
            "cpu": self.get_cpu_info(),
            "memory": self.get_memory_info(),
            "dmi": self.get_dmi_info(),
            "block_devices": self.get_block_devices(),
            "network_interfaces": self.get_network_interfaces(),
        }


if __name__ == "__main__":
    import json
    detector = HardwareDetector()
    report = detector.collect_all()
    print(json.dumps(report, indent=2))
