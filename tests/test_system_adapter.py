"""Tests for SystemAdapter.

Validates:
- Allowed informational queries:
  get_system_info, get_hostname, get_kernel_info, get_uptime,
  get_memory_info, get_service_status
- Rejection of unknown actions and destructive actions:
  reboot, shutdown, sudo, kill, etc.
- Parameter validation for service_name (safe alphanumeric pattern, length limit)
- Proper envelope results (AdapterResult, AdapterStatus)
"""

import unittest
from unittest.mock import patch, MagicMock

from adapters.system_adapter import SystemAdapter
from adapters.result import AdapterStatus


class TestSystemAdapter(unittest.TestCase):
    """Test suite for SystemAdapter."""

    def setUp(self):
        self.adapter = SystemAdapter()

    def test_adapter_metadata(self):
        """Verify adapter name and supported actions."""
        self.assertEqual(self.adapter.name, "system")
        expected_actions = {
            "get_system_info",
            "get_hostname",
            "get_kernel_info",
            "get_uptime",
            "get_memory_info",
            "get_service_status",
        }
        self.assertEqual(self.adapter.supported_actions, expected_actions)

    def test_get_system_info(self):
        """Verify get_system_info returns aggregate OS metadata."""
        result = self.adapter.run("get_system_info")
        self.assertTrue(result.success)
        self.assertEqual(result.status, AdapterStatus.SUCCESS)
        self.assertIn("system", result.data)
        self.assertIn("hostname", result.data)
        self.assertIn("kernel", result.data)
        self.assertIn("architecture", result.data)

    def test_get_hostname(self):
        """Verify get_hostname returns hostname."""
        result = self.adapter.run("get_hostname")
        self.assertTrue(result.success)
        self.assertEqual(result.status, AdapterStatus.SUCCESS)
        self.assertIn("hostname", result.data)
        self.assertIsInstance(result.data["hostname"], str)

    def test_get_kernel_info(self):
        """Verify get_kernel_info returns kernel details."""
        result = self.adapter.run("get_kernel_info")
        self.assertTrue(result.success)
        self.assertEqual(result.status, AdapterStatus.SUCCESS)
        self.assertIn("release", result.data)
        self.assertIn("version", result.data)
        self.assertIn("machine", result.data)

    def test_get_uptime(self):
        """Verify get_uptime returns uptime or fallback gracefully."""
        result = self.adapter.run("get_uptime")
        self.assertTrue(result.success)
        self.assertEqual(result.status, AdapterStatus.SUCCESS)
        self.assertIn("uptime_seconds", result.data)

    def test_get_memory_info(self):
        """Verify get_memory_info returns memory statistics or fallback."""
        result = self.adapter.run("get_memory_info")
        self.assertTrue(result.success)
        self.assertEqual(result.status, AdapterStatus.SUCCESS)
        self.assertIsInstance(result.data, dict)

    def test_get_service_status_valid(self):
        """Verify get_service_status runs with a valid service name."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="active\n", stderr="")
            result = self.adapter.run("get_service_status", {"service_name": "agenticos-prompt-ui"})
            self.assertTrue(result.success)
            self.assertEqual(result.status, AdapterStatus.SUCCESS)
            self.assertEqual(result.data["service_name"], "agenticos-prompt-ui")
            self.assertEqual(result.data["active_state"], "active")

    def test_get_service_status_missing_param(self):
        """Verify get_service_status fails validation when service_name is missing."""
        result = self.adapter.run("get_service_status", {})
        self.assertFalse(result.success)
        self.assertEqual(result.status, AdapterStatus.VALIDATION_ERROR)
        self.assertIn("Missing required parameter", str(result.error))

    def test_get_service_status_invalid_name_chars(self):
        """Verify get_service_status rejects service names with special characters."""
        invalid_names = [
            "service; rm -rf /",
            "service && ls",
            "service`whoami`",
            "service$(id)",
            "service|grep foo",
            "service name",
            "/bin/service",
            "../service",
        ]
        for name in invalid_names:
            result = self.adapter.run("get_service_status", {"service_name": name})
            self.assertFalse(result.success, f"Should reject: {name}")
            self.assertEqual(result.status, AdapterStatus.VALIDATION_ERROR)
            self.assertIn("Invalid service_name", str(result.error))

    def test_get_service_status_too_long(self):
        """Verify get_service_status rejects excessively long service names."""
        long_name = "a" * 129
        result = self.adapter.run("get_service_status", {"service_name": long_name})
        self.assertFalse(result.success)
        self.assertEqual(result.status, AdapterStatus.VALIDATION_ERROR)

    def test_reject_destructive_actions(self):
        """Verify destructive actions are strictly rejected."""
        destructive_actions = [
            "reboot",
            "shutdown",
            "poweroff",
            "kill",
            "kill_process",
            "sudo",
            "rm",
            "exec",
            "shell",
        ]
        for action in destructive_actions:
            result = self.adapter.run(action)
            self.assertFalse(result.success, f"Should reject action: {action}")
            self.assertEqual(result.status, AdapterStatus.UNSUPPORTED_ACTION)

    def test_unsupported_action(self):
        """Verify arbitrary unknown action is rejected."""
        result = self.adapter.run("arbitrary_action")
        self.assertFalse(result.success)
        self.assertEqual(result.status, AdapterStatus.UNSUPPORTED_ACTION)


if __name__ == "__main__":
    unittest.main()
