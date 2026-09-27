"""
AgenticOS - Process & Memory Adapters Unit Tests
Layer 10: System Services
Owner: Magesh (Linux/OS Lead)

Uses Python standard library `unittest` with mock /proc directories.
"""

import tempfile
import unittest
from pathlib import Path

from adapters.process_adapter import ProcessAdapter
from adapters.memory_adapter import MemoryAdapter


class TestProcessAdapter(unittest.TestCase):
    """Test suite for ProcessAdapter."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.proc_mock = Path(self.temp_dir.name) / "proc"
        self.proc_mock.mkdir(parents=True)
        self.adapter = ProcessAdapter(proc_path=str(self.proc_mock))

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_normal_process_parsing(self) -> None:
        """Verify parsing of PID, name, cmdline, state, memory RSS, and CPU ticks."""
        pid_dir = self.proc_mock / "42"
        pid_dir.mkdir()

        (pid_dir / "comm").write_text("agenticos-core\n", encoding="utf-8")
        (pid_dir / "cmdline").write_bytes(b"python3\x00-m\x00agenticos.core\x00--port\x008080\x00")
        sample_status = """Name:\tagenticos-core
State:\tS (sleeping)
PPid:\t1
Threads:\t4
VmRSS:\t16384 kB
VmSize:\t65536 kB
"""
        (pid_dir / "status").write_text(sample_status, encoding="utf-8")
        # Sample /proc/[pid]/stat: field 0=pid, field 1=(comm), field 2=state
        # utime is at post-paren field 11, stime at field 12
        sample_stat = "42 (agenticos-core) S 1 42 42 0 -1 4194304 100 0 0 0 150 75 0 0 20 0 4 0 12345 67108864 4096 ...\n"
        (pid_dir / "stat").write_text(sample_stat, encoding="utf-8")

        info = self.adapter.get_process_info(42)
        self.assertIsNotNone(info)
        self.assertEqual(info["pid"], 42)
        self.assertEqual(info["name"], "agenticos-core")
        self.assertEqual(info["state"], "S")
        self.assertEqual(info["ppid"], 1)
        self.assertEqual(info["threads"], 4)
        self.assertEqual(info["cmdline"], ["python3", "-m", "agenticos.core", "--port", "8080"])
        self.assertEqual(info["memory"]["vm_rss_bytes"], 16384 * 1024)
        self.assertEqual(info["memory"]["vm_size_bytes"], 65536 * 1024)
        self.assertEqual(info["cpu_ticks"]["utime"], 150)
        self.assertEqual(info["cpu_ticks"]["stime"], 75)
        self.assertEqual(info["starttime_ticks"], 12345)

    def test_multiple_process_discovery(self) -> None:
        """Verify listing and counting across multiple mock processes."""
        for pid in (10, 20, 30):
            p = self.proc_mock / str(pid)
            p.mkdir()
            (p / "comm").write_text(f"proc_{pid}\n", encoding="utf-8")
            (p / "status").write_text(f"Name:\tproc_{pid}\nState:\tS\n", encoding="utf-8")

        self.assertEqual(self.adapter.get_process_count(), 3)
        procs = self.adapter.list_processes()
        self.assertEqual(len(procs), 3)
        pids = [p["pid"] for p in procs]
        self.assertEqual(pids, [10, 20, 30])

        # Test limit
        procs_limited = self.adapter.list_processes(limit=2)
        self.assertEqual(len(procs_limited), 2)

    def test_process_disappearing_during_scan(self) -> None:
        """Verify that a process that vanishes mid-scan is skipped safely."""
        p = self.proc_mock / "99"
        p.mkdir()
        # Immediately query a non-existent PID
        info = self.adapter.get_process_info(9999)
        self.assertIsNone(info)

    def test_malformed_process_data_handling(self) -> None:
        """Ensure corrupted stat or status files do not crash the parser."""
        p = self.proc_mock / "88"
        p.mkdir()
        (p / "comm").write_text("corrupted\n", encoding="utf-8")
        (p / "status").write_text("GARBAGE_NO_COLONS\nVmRSS: not_a_number\n", encoding="utf-8")
        (p / "stat").write_text("NOT_EVEN_PARENS", encoding="utf-8")

        info = self.adapter.get_process_info(88)
        self.assertIsNotNone(info)
        self.assertEqual(info["pid"], 88)
        self.assertEqual(info["memory"]["vm_rss_bytes"], 0)
        self.assertEqual(info["cpu_ticks"]["utime"], 0)

    def test_prohibition_of_process_control_methods(self) -> None:
        """
        Security verification: verify that ProcessAdapter strictly lacks
        any process-control or modification methods.
        """
        forbidden_methods = [
            "kill",
            "terminate",
            "renice",
            "nice",
            "pause",
            "resume",
            "spawn",
            "execute",
            "send_signal",
        ]
        for method in forbidden_methods:
            self.assertFalse(
                hasattr(self.adapter, method),
                f"Security violation: ProcessAdapter must not implement '{method}'",
            )


class TestMemoryAdapter(unittest.TestCase):
    """Test suite for MemoryAdapter."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.proc_mock = Path(self.temp_dir.name) / "proc"
        self.proc_mock.mkdir(parents=True)
        self.adapter = MemoryAdapter(proc_path=str(self.proc_mock))

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_normal_memory_parsing(self) -> None:
        """Verify detailed memory metrics parsing including buffers and cache."""
        sample_meminfo = """MemTotal:       16000000 kB
MemFree:         4000000 kB
MemAvailable:   12000000 kB
Buffers:          500000 kB
Cached:          3000000 kB
SReclaimable:     200000 kB
SwapTotal:       4000000 kB
SwapFree:        3000000 kB
"""
        (self.proc_mock / "meminfo").write_text(sample_meminfo, encoding="utf-8")
        m = self.adapter.get_memory_metrics()

        self.assertEqual(m["status"], "available")
        self.assertEqual(m["total_bytes"], 16000000 * 1024)
        self.assertEqual(m["available_bytes"], 12000000 * 1024)
        # used = 16000000 - 12000000 = 4000000 kB = 25.0%
        self.assertEqual(m["used_bytes"], 4000000 * 1024)
        self.assertEqual(m["usage_percent"], 25.0)

        # Buffers and Cache
        self.assertEqual(m["buffers_bytes"], 500000 * 1024)
        self.assertEqual(m["cached_bytes"], 3000000 * 1024)
        self.assertEqual(m["slab_reclaimable_bytes"], 200000 * 1024)

        # Swap: 4M total, 3M free => 1M used = 25.0%
        self.assertEqual(m["swap_total_bytes"], 4000000 * 1024)
        self.assertEqual(m["swap_free_bytes"], 3000000 * 1024)
        self.assertEqual(m["swap_used_bytes"], 1000000 * 1024)
        self.assertEqual(m["swap_usage_percent"], 25.0)

    def test_missing_meminfo_handling(self) -> None:
        """Verify that missing /proc/meminfo returns 'unavailable' gracefully."""
        m = self.adapter.get_memory_metrics()
        self.assertEqual(m["status"], "unavailable")
        self.assertEqual(m["total_bytes"], 0)

    def test_malformed_meminfo_handling(self) -> None:
        """Verify that corrupted /proc/meminfo lines do not crash the parser."""
        corrupted = """NOT_A_LINE
MemTotal: invalid_number kB
MemFree: 2048 kB
Cached: non_numeric
"""
        (self.proc_mock / "meminfo").write_text(corrupted, encoding="utf-8")
        m = self.adapter.get_memory_metrics()
        self.assertEqual(m["status"], "available")
        self.assertEqual(m["total_bytes"], 0)
        self.assertEqual(m["free_bytes"], 2048 * 1024)

    def test_memory_summary_output(self) -> None:
        """Verify human-readable summary calculation."""
        sample_meminfo = """MemTotal:        1048576 kB
MemFree:          262144 kB
MemAvailable:     524288 kB
SwapTotal:             0 kB
SwapFree:              0 kB
"""
        (self.proc_mock / "meminfo").write_text(sample_meminfo, encoding="utf-8")
        summary = self.adapter.get_summary()

        self.assertEqual(summary["status"], "available")
        self.assertEqual(summary["total_mb"], 1024.0)
        self.assertEqual(summary["available_mb"], 512.0)
        self.assertEqual(summary["used_mb"], 512.0)
        self.assertEqual(summary["usage_percent"], 50.0)


if __name__ == "__main__":
    unittest.main()
