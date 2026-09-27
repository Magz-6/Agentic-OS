"""
AgenticOS - System Telemetry Collector Unit Tests
Layer 11/13: System Telemetry & Metrics
Owner: Magesh (Linux/OS Lead)

Uses Python standard library `unittest` with mock pseudo-filesystems to guarantee
safe, repeatable testing without root privileges or hardware dependencies.
"""

import tempfile
import unittest
from pathlib import Path

from telemetry.collector import SystemTelemetryCollector


class TestSystemTelemetryCollector(unittest.TestCase):
    """Test suite for SystemTelemetryCollector."""

    def setUp(self) -> None:
        """Create a temporary sandbox directory to simulate /proc and /sys."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.proc_mock = self.root / "proc"
        self.sys_mock = self.root / "sys"
        self.proc_mock.mkdir(parents=True)
        self.sys_mock.mkdir(parents=True)
        self.collector = SystemTelemetryCollector(
            proc_path=str(self.proc_mock),
            sys_path=str(self.sys_mock),
        )

    def tearDown(self) -> None:
        """Clean up temporary sandbox."""
        self.temp_dir.cleanup()

    def test_cpu_counter_parsing(self) -> None:
        """Verify parsing of cumulative CPU jiffies from /proc/stat."""
        sample_stat = """cpu  2255 34 2290 22625 24 10 30 1 0 0
cpu0 1132 17 1145 11310 12 5 15 0 0 0
cpu1 1123 17 1145 11315 12 5 15 1 0 0
intr 1149305 0 0 0 0
"""
        (self.proc_mock / "stat").write_text(sample_stat, encoding="utf-8")
        cpu_times = self.collector.get_cpu_times()

        self.assertIsNotNone(cpu_times)
        self.assertEqual(cpu_times["user"], 2255)
        self.assertEqual(cpu_times["nice"], 34)
        self.assertEqual(cpu_times["system"], 2290)
        self.assertEqual(cpu_times["idle"], 22625)
        self.assertEqual(cpu_times["iowait"], 24)
        self.assertEqual(cpu_times["idle_total"], 22625 + 24)
        self.assertEqual(cpu_times["total"], (2255 + 34 + 2290 + 10 + 30 + 1) + (22625 + 24))

    def test_cpu_percent_calculation(self) -> None:
        """Verify delta-based CPU percentage calculation logic."""
        sample1 = {"idle_total": 8000, "total": 10000}
        # In sample2, total increased by 1000, idle increased by 750 (250 busy => 25.0%)
        sample2 = {"idle_total": 8750, "total": 11000}

        pct = SystemTelemetryCollector.calculate_cpu_percent(sample1, sample2)
        self.assertEqual(pct, 25.0)

        # 100% idle delta => 0.0% busy
        sample_idle = {"idle_total": 9000, "total": 11000}
        self.assertEqual(SystemTelemetryCollector.calculate_cpu_percent(sample1, sample_idle), 0.0)

        # 0 delta total => 0.0%
        self.assertEqual(SystemTelemetryCollector.calculate_cpu_percent(sample1, sample1), 0.0)

    def test_memory_and_swap_parsing(self) -> None:
        """Verify memory and swap byte calculations and percentage math."""
        sample_meminfo = """MemTotal:       1000000 kB
MemFree:         400000 kB
MemAvailable:    800000 kB
SwapTotal:       500000 kB
SwapFree:        250000 kB
"""
        (self.proc_mock / "meminfo").write_text(sample_meminfo, encoding="utf-8")
        mem = self.collector.get_memory_telemetry()

        self.assertEqual(mem["status"], "available")
        self.assertEqual(mem["total_bytes"], 1000000 * 1024)
        self.assertEqual(mem["available_bytes"], 800000 * 1024)
        # used = total - available = 200,000 kB = 20.0%
        self.assertEqual(mem["used_bytes"], 200000 * 1024)
        self.assertEqual(mem["usage_percent"], 20.0)

        # Swap: 500,000 total, 250,000 free => 250,000 used = 50.0%
        self.assertEqual(mem["swap_total_bytes"], 500000 * 1024)
        self.assertEqual(mem["swap_free_bytes"], 250000 * 1024)
        self.assertEqual(mem["swap_used_bytes"], 250000 * 1024)
        self.assertEqual(mem["swap_usage_percent"], 50.0)

    def test_load_average_parsing(self) -> None:
        """Verify parsing of 1m, 5m, 15m load averages from /proc/loadavg."""
        sample_load = "0.15 0.25 0.10 2/350 48123\n"
        (self.proc_mock / "loadavg").write_text(sample_load, encoding="utf-8")
        load = self.collector.get_load_average()

        self.assertEqual(load["status"], "available")
        self.assertEqual(load["load_1m"], 0.15)
        self.assertEqual(load["load_5m"], 0.25)
        self.assertEqual(load["load_15m"], 0.10)

    def test_uptime_parsing(self) -> None:
        """Verify parsing of system uptime and idle seconds."""
        sample_uptime = "12345.67 98765.43\n"
        (self.proc_mock / "uptime").write_text(sample_uptime, encoding="utf-8")
        uptime = self.collector.get_uptime()

        self.assertEqual(uptime["status"], "available")
        self.assertEqual(uptime["uptime_seconds"], 12345.67)
        self.assertEqual(uptime["idle_seconds"], 98765.43)

    def test_network_byte_parsing(self) -> None:
        """Verify parsing of interface traffic counters from /proc/net/dev."""
        net_dir = self.proc_mock / "net"
        net_dir.mkdir(parents=True)
        sample_dev = """Inter-|   Receive                                                |  Transmit
 face |bytes    packets errs drop fifo frame compressed multicast|bytes    packets errs drop fifo colls carrier compressed
    lo: 1024000     500    0    0    0     0          0         0  1024000     500    0    0    0     0       0          0
  eth0: 5242880    2000    0    0    0     0          0         0  2621440    1000    0    0    0     0       0          0
"""
        (net_dir / "dev").write_text(sample_dev, encoding="utf-8")

        # Mock operstate for eth0
        eth0_sys = self.sys_mock / "class" / "net" / "eth0"
        eth0_sys.mkdir(parents=True)
        (eth0_sys / "operstate").write_text("up\n", encoding="utf-8")

        interfaces = self.collector.get_network_telemetry()
        self.assertEqual(len(interfaces), 2)

        eth0 = next(iface for iface in interfaces if iface["interface"] == "eth0")
        self.assertEqual(eth0["rx_bytes"], 5242880)
        self.assertEqual(eth0["tx_bytes"], 2621440)
        self.assertEqual(eth0["rx_packets"], 2000)
        self.assertEqual(eth0["tx_packets"], 1000)
        self.assertEqual(eth0["operstate"], "up")

    def test_process_counting(self) -> None:
        """Verify total and running process counting from /proc/[pid]/stat."""
        # Create PID 1 (Sleeping 'S')
        p1 = self.proc_mock / "1"
        p1.mkdir()
        (p1 / "stat").write_text("1 (systemd) S 0 1 1 0 -1 ...\n", encoding="utf-8")

        # Create PID 100 (Running 'R')
        p100 = self.proc_mock / "100"
        p100.mkdir()
        (p100 / "stat").write_text("100 (python3) R 1 100 100 0 -1 ...\n", encoding="utf-8")

        # Create PID 200 (Running 'R')
        p200 = self.proc_mock / "200"
        p200.mkdir()
        (p200 / "stat").write_text("200 (agenticos) R 1 200 200 0 -1 ...\n", encoding="utf-8")

        # Create non-pid folder (e.g. /proc/sys)
        (self.proc_mock / "sys_dir").mkdir()

        summary = self.collector.get_process_summary()
        self.assertEqual(summary["total_processes"], 3)
        self.assertEqual(summary["running_processes"], 2)

    def test_missing_proc_files_handling(self) -> None:
        """Ensure missing /proc files result in safe 'unavailable' responses without exceptions."""
        # /proc is empty
        mem = self.collector.get_memory_telemetry()
        self.assertEqual(mem["status"], "unavailable")

        load = self.collector.get_load_average()
        self.assertEqual(load["status"], "unavailable")

        uptime = self.collector.get_uptime()
        self.assertEqual(uptime["status"], "unavailable")

        net = self.collector.get_network_telemetry()
        self.assertEqual(net, [])

        cpu = self.collector.get_cpu_telemetry(sample_interval=0.0)
        self.assertEqual(cpu["status"], "unavailable")

    def test_malformed_values_handling(self) -> None:
        """Ensure corrupted /proc files are handled gracefully."""
        (self.proc_mock / "loadavg").write_text("corrupted_text\n", encoding="utf-8")
        load = self.collector.get_load_average()
        self.assertIn(load["status"], ("malformed", "unavailable"))

        (self.proc_mock / "uptime").write_text("non_numeric\n", encoding="utf-8")
        uptime = self.collector.get_uptime()
        self.assertEqual(uptime["status"], "malformed")

    def test_structured_output_format(self) -> None:
        """Verify collect_all() output schema and timestamps."""
        snapshot = self.collector.collect_all(sample_interval=0.0)
        required_keys = ["schema_version", "layer", "timestamp", "cpu", "memory", "load_average", "uptime", "network", "process_summary"]
        for key in required_keys:
            self.assertIn(key, snapshot)
        self.assertEqual(snapshot["schema_version"], "0.1.0")
        self.assertEqual(snapshot["layer"], "Layer 11/13: System Telemetry")


if __name__ == "__main__":
    unittest.main()
