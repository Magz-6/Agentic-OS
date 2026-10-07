#!/usr/bin/env python3
"""
Unit tests for AgenticOS Native Desktop Shell Backend & Interfaces.
Layer 9: Applications & Native Desktop
Layer 12: Linux Integration Boundary
Owner: Magesh (Linux/OS Lead)
"""

import os
import shutil
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
import sys
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import importlib.util

SHELL_MAIN_PATH = PROJECT_ROOT / "applications" / "agenticos-shell" / "main.py"
spec = importlib.util.spec_from_file_location("agenticos_shell_main", str(SHELL_MAIN_PATH))
shell_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(shell_module)

AgenticOSShellBackend = shell_module.AgenticOSShellBackend
main = shell_module.main


class TestAgenticOSShellBackend(unittest.TestCase):
    """Test suite for AgenticOS native shell backend and safe interfaces."""

    def setUp(self):
        self.backend = AgenticOSShellBackend()
        self.temp_dir = tempfile.mkdtemp()
        self.base_dir = Path(self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_backend_system_summary(self):
        """Verify get_system_summary returns structured metadata with OS name."""
        summary = self.backend.get_system_summary()
        self.assertEqual(summary["os_name"], "AgenticOS v0.1 Alpha")
        self.assertIn("kernel", summary)
        self.assertIn("machine", summary)
        self.assertIn("hostname", summary)
        self.assertIn("user", summary)
        self.assertIn("mem_total_mb", summary)
        self.assertIn("cpu_cores", summary)

    def test_services_status_structure(self):
        """Verify get_services_status queries AgenticOS services."""
        status_map = self.backend.get_services_status()
        self.assertIn("agenticos-desktop.service", status_map)
        self.assertIn("agenticos-firstboot.service", status_map)
        self.assertIn("agenticos-telemetry.service", status_map)
        self.assertIn("agenticos-goal-runtime.service", status_map)
        for s, state in status_map.items():
            self.assertIsInstance(state, str)

    def test_create_project_folder_valid(self):
        """Verify safe project directory creation."""
        res = self.backend.create_project_folder("MyAlphaProject", base_dir=self.base_dir)
        self.assertTrue(res["success"])
        expected_path = self.base_dir / "MyAlphaProject"
        self.assertTrue(expected_path.is_dir())
        self.assertIn("created", res["message"].lower())

    def test_create_project_folder_traversal_rejected(self):
        """Verify path traversal characters are rejected in folder name."""
        res = self.backend.create_project_folder("../escape_folder", base_dir=self.base_dir)
        self.assertFalse(res["success"])
        self.assertIn("Invalid folder name", res["message"])

    def test_create_project_folder_empty_rejected(self):
        """Verify empty folder name is rejected."""
        res = self.backend.create_project_folder("", base_dir=self.base_dir)
        self.assertFalse(res["success"])
        self.assertIn("empty", res["message"].lower())

    def test_safe_power_action_allowlist(self):
        """Verify power actions only accept reboot and poweroff."""
        res = self.backend.execute_safe_power_action("rm -rf /")
        self.assertFalse(res["success"])
        self.assertIn("Unsupported power action", res["message"])

        res_sh = self.backend.execute_safe_power_action("bash -c 'echo pwned'")
        self.assertFalse(res_sh["success"])
        self.assertIn("Unsupported power action", res_sh["message"])

    def test_cli_check_argument(self):
        """Verify --check argument exits with 0."""
        import sys
        old_argv = sys.argv
        try:
            sys.argv = ["main.py", "--check"]
            code = main()
            self.assertEqual(code, 0)
        finally:
            sys.argv = old_argv


if __name__ == "__main__":
    unittest.main()
