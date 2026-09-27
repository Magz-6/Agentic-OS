"""
AgenticOS - Hardware Detector Unit Tests
Layer 13: Hardware Detection and Reporting
Owner: Magesh (Linux/OS Lead)

Uses Python standard library `unittest` with mock file systems to guarantee
safe, repeatable testing without root privileges or hardware dependencies.
"""

import tempfile
import unittest
from pathlib import Path

from hardware.detector import HardwareDetector


class TestHardwareDetector(unittest.TestCase):
    """Test suite for HardwareDetector."""

    def setUp(self) -> None:
        """Create a temporary sandbox directory to simulate /proc and /sys."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.proc_mock = self.root / "proc"
        self.sys_mock = self.root / "sys"
        self.proc_mock.mkdir(parents=True)
        self.sys_mock.mkdir(parents=True)
        self.detector = HardwareDetector(
            proc_path=str(self.proc_mock),
            sys_path=str(self.sys_mock),
        )

    def tearDown(self) -> None:
        """Clean up temporary sandbox."""
        self.temp_dir.cleanup()

    def test_normal_cpu_info_parsing(self) -> None:
        """Verify normal CPU model name, logical cores, and flags parsing."""
        sample_cpuinfo = """processor\t: 0
vendor_id\t: GenuineIntel
cpu family\t: 6
model\t\t: 183
model name\t: Intel(R) Core(TM) i7-13645HX
stepping\t: 1
cpu MHz\t\t: 2600.000
flags\t\t: fpu vme de pse tsc msr pae mce cx8
processor\t: 1
vendor_id\t: GenuineIntel
cpu family\t: 6
model\t\t: 183
model name\t: Intel(R) Core(TM) i7-13645HX
stepping\t: 1
cpu MHz\t\t: 2600.000
flags\t\t: fpu vme de pse tsc msr pae mce cx8
"""
        (self.proc_mock / "cpuinfo").write_text(sample_cpuinfo, encoding="utf-8")
        cpu_info = self.detector.get_cpu_info()

        self.assertEqual(cpu_info["model_name"], "Intel(R) Core(TM) i7-13645HX")
        self.assertEqual(cpu_info["logical_cores"], 2)
        self.assertEqual(cpu_info["mhz"], 2600.0)
        self.assertIn("fpu", cpu_info["flags"])
        self.assertIn("vme", cpu_info["flags"])

    def test_normal_memory_info_parsing(self) -> None:
        """Verify conversion of /proc/meminfo kB values to bytes."""
        sample_meminfo = """MemTotal:        8017408 kB
MemFree:         4194304 kB
MemAvailable:    6291456 kB
Buffers:          102400 kB
Cached:          1048576 kB
SwapTotal:       2097152 kB
SwapFree:        2097152 kB
"""
        (self.proc_mock / "meminfo").write_text(sample_meminfo, encoding="utf-8")
        mem_info = self.detector.get_memory_info()

        self.assertEqual(mem_info["status"], "available")
        self.assertEqual(mem_info["total_bytes"], 8017408 * 1024)
        self.assertEqual(mem_info["free_bytes"], 4194304 * 1024)
        self.assertEqual(mem_info["available_bytes"], 6291456 * 1024)
        self.assertEqual(mem_info["swap_total_bytes"], 2097152 * 1024)

    def test_missing_proc_entries_handling(self) -> None:
        """Ensure missing /proc/cpuinfo or /proc/meminfo fall back gracefully."""
        # /proc is empty
        cpu_info = self.detector.get_cpu_info()
        self.assertEqual(cpu_info["model_name"], "unknown")
        self.assertGreaterEqual(cpu_info["logical_cores"], 0)

        mem_info = self.detector.get_memory_info()
        self.assertEqual(mem_info["status"], "unavailable")
        self.assertEqual(mem_info["total_bytes"], 0)

    def test_missing_sys_entries_handling(self) -> None:
        """Ensure missing /sys subdirectories return empty lists instead of raising exceptions."""
        blocks = self.detector.get_block_devices()
        self.assertEqual(blocks, [])

        nets = self.detector.get_network_interfaces()
        self.assertEqual(nets, [])

        dmi = self.detector.get_dmi_info()
        self.assertEqual(dmi["product_name"], "unavailable")

    def test_malformed_input_handling(self) -> None:
        """Ensure garbage input or corrupt formatting does not crash the parser."""
        corrupted_meminfo = """NOT_A_KEY
MemTotal: invalid_number kB
MemFree: 1024
Random Corrupted Bytes: ###@@!
"""
        (self.proc_mock / "meminfo").write_text(corrupted_meminfo, encoding="utf-8")
        mem_info = self.detector.get_memory_info()

        # Should parse what it can, set 0 for invalid, and not crash
        self.assertEqual(mem_info["total_bytes"], 0)
        self.assertEqual(mem_info["free_bytes"], 1024 * 1024)

    def test_block_devices_parsing(self) -> None:
        """Verify block device parsing from mock /sys/block."""
        sdd_dir = self.sys_mock / "class" / "block" / "sdd"
        sdd_dir.mkdir(parents=True)
        (sdd_dir / "size").write_text("2097152\n", encoding="utf-8")  # 2M sectors = 1GB
        (sdd_dir / "removable").write_text("0\n", encoding="utf-8")
        (sdd_dir / "ro").write_text("0\n", encoding="utf-8")

        devices = self.detector.get_block_devices()
        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0]["name"], "sdd")
        self.assertEqual(devices[0]["size_bytes"], 2097152 * 512)
        self.assertFalse(devices[0]["removable"])
        self.assertFalse(devices[0]["read_only"])

    def test_network_interfaces_parsing(self) -> None:
        """Verify network interface state parsing from mock /sys/class/net."""
        eth0_dir = self.sys_mock / "class" / "net" / "eth0"
        eth0_dir.mkdir(parents=True)
        (eth0_dir / "operstate").write_text("up\n", encoding="utf-8")
        (eth0_dir / "mtu").write_text("1500\n", encoding="utf-8")
        (eth0_dir / "address").write_text("00:15:5d:be:63:51\n", encoding="utf-8")

        interfaces = self.detector.get_network_interfaces()
        self.assertEqual(len(interfaces), 1)
        self.assertEqual(interfaces[0]["interface"], "eth0")
        self.assertEqual(interfaces[0]["operstate"], "up")
        self.assertEqual(interfaces[0]["mtu"], 1500)
        self.assertEqual(interfaces[0]["mac_address"], "00:15:5d:be:63:51")

    def test_structured_output_format(self) -> None:
        """Verify that collect_all() returns all required schema keys."""
        report = self.detector.collect_all()
        required_keys = ["schema_version", "layer", "platform", "cpu", "memory", "dmi", "block_devices", "network_interfaces"]
        for key in required_keys:
            self.assertIn(key, report)
        self.assertEqual(report["schema_version"], "0.1.0")
        self.assertEqual(report["layer"], "Layer 13: Hardware")


if __name__ == "__main__":
    unittest.main()
