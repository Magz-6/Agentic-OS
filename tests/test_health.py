"""
AgenticOS - Service Health Inspector Unit Tests
Layer 12: Agentic Microkernel / Linux Integration Boundary
Owner: Magesh (Linux/OS Lead)

Uses Python standard library `unittest` and `unittest.mock`.
"""

import subprocess
import unittest
from unittest.mock import MagicMock, patch

from linux_integration.contracts import HealthReport, ServiceStatus
from linux_integration.health import ServiceHealthInspector


class TestServiceHealthInspector(unittest.TestCase):
    """Test suite for ServiceHealthInspector."""

    def setUp(self) -> None:
        self.inspector = ServiceHealthInspector(systemctl_bin="/mock/bin/systemctl")

    @patch("subprocess.run")
    def test_systemd_available_healthy(self, mock_run: MagicMock) -> None:
        """Verify is_systemd_available returns True when output is 'running'."""
        mock_run.return_value = MagicMock(stdout="running\n", returncode=0)
        self.assertTrue(self.inspector.is_systemd_available())

    @patch("subprocess.run")
    def test_systemd_available_degraded(self, mock_run: MagicMock) -> None:
        """Verify is_systemd_available returns True when output is 'degraded'."""
        mock_run.return_value = MagicMock(stdout="degraded\n", returncode=1)
        self.assertTrue(self.inspector.is_systemd_available())

    @patch("subprocess.run")
    def test_systemd_unavailable_error(self, mock_run: MagicMock) -> None:
        """Verify is_systemd_available returns False when subprocess raises an error."""
        mock_run.side_effect = OSError("Connection refused")
        self.assertFalse(self.inspector.is_systemd_available())

    def test_missing_systemctl_binary(self) -> None:
        """Verify graceful error reporting when systemctl binary does not exist."""
        no_systemd = ServiceHealthInspector(systemctl_bin=None)
        self.assertFalse(no_systemd.is_systemd_available())

        status = no_systemd.inspect_service("test.service")
        self.assertFalse(status.healthy)
        self.assertEqual(status.active_state, "unavailable")
        self.assertEqual(status.error, "systemctl_not_found")

    @patch("subprocess.run")
    def test_inspect_service_active_healthy(self, mock_run: MagicMock) -> None:
        """Verify active, running service is marked healthy with MainPID."""
        mock_stdout = """ActiveState=active
SubState=running
MainPID=4321
Result=success
"""
        mock_run.return_value = MagicMock(stdout=mock_stdout, returncode=0)
        st = self.inspector.inspect_service("agenticos-telemetry.service")

        self.assertTrue(st.healthy)
        self.assertEqual(st.active_state, "active")
        self.assertEqual(st.substate, "running")
        self.assertEqual(st.main_pid, 4321)
        self.assertIsNone(st.error)

    @patch("subprocess.run")
    def test_inspect_service_failed(self, mock_run: MagicMock) -> None:
        """Verify failed service is marked unhealthy with result details."""
        mock_stdout = """ActiveState=failed
SubState=failed
MainPID=0
Result=exit-code
"""
        mock_run.return_value = MagicMock(stdout=mock_stdout, returncode=0)
        st = self.inspector.inspect_service("agenticos-failing.service")

        self.assertFalse(st.healthy)
        self.assertEqual(st.active_state, "failed")
        self.assertEqual(st.substate, "failed")
        self.assertIsNone(st.main_pid)
        self.assertIn("service_failed", st.error or "")

    @patch("subprocess.run")
    def test_inspect_service_inactive(self, mock_run: MagicMock) -> None:
        """Verify inactive/dead service is marked unhealthy."""
        mock_stdout = """ActiveState=inactive
SubState=dead
MainPID=0
Result=success
"""
        mock_run.return_value = MagicMock(stdout=mock_stdout, returncode=0)
        st = self.inspector.inspect_service("agenticos-stopped.service")

        self.assertFalse(st.healthy)
        self.assertEqual(st.active_state, "inactive")
        self.assertEqual(st.substate, "dead")

    @patch("subprocess.run")
    def test_inspect_service_timeout(self, mock_run: MagicMock) -> None:
        """Verify timeout during inspection is handled safely."""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd=["systemctl"], timeout=3)
        st = self.inspector.inspect_service("agenticos-hung.service")

        self.assertFalse(st.healthy)
        self.assertEqual(st.active_state, "timeout")
        self.assertEqual(st.error, "systemctl_timeout")

    @patch("subprocess.run")
    def test_inspect_system_health_aggregation(self, mock_run: MagicMock) -> None:
        """Verify aggregated health report across multiple services."""
        # 1st call for is_systemd_available, 2nd for system_state, 3rd for service inspection
        mock_run.side_effect = [
            MagicMock(stdout="running\n", returncode=0),
            MagicMock(stdout="running\n", returncode=0),
            MagicMock(stdout="ActiveState=active\nSubState=running\nMainPID=100\nResult=success\n"),
        ]
        report = self.inspector.inspect_system_health(["agenticos-telemetry.service"])

        self.assertTrue(report.systemd_available)
        self.assertEqual(report.system_state, "running")
        self.assertIn("agenticos-telemetry.service", report.services)
        self.assertEqual(report.errors, [])

    def test_prohibition_of_service_control_methods(self) -> None:
        """
        Security verification: verify that ServiceHealthInspector strictly lacks
        any service lifecycle modification methods.
        """
        forbidden_methods = [
            "start",
            "stop",
            "restart",
            "enable",
            "disable",
            "mask",
            "unmask",
            "reload",
            "kill",
            "reset_failed",
        ]
        for method in forbidden_methods:
            self.assertFalse(
                hasattr(self.inspector, method),
                f"Security violation: ServiceHealthInspector must not implement '{method}'",
            )

    @patch("subprocess.run")
    def test_inspect_service_rejects_option_names(self, mock_run: MagicMock) -> None:
        """Security test: verify that option-like or dangerous unit names are rejected without calling systemctl."""
        invalid_names = [
            "--version",
            "-t",
            "--help",
            "service;rm -rf /",
            "service && echo 1",
            "service\nname",
            "",
            "-bad.service",
        ]
        for name in invalid_names:
            st = self.inspector.inspect_service(name)
            self.assertFalse(st.healthy)
            self.assertEqual(st.active_state, "rejected")
            self.assertEqual(st.error, "invalid_service_name")
        mock_run.assert_not_called()

    @patch("subprocess.run")
    def test_inspect_service_uses_double_dash_separator(self, mock_run: MagicMock) -> None:
        """Security test: verify that systemctl show uses -- before the service name."""
        mock_run.return_value = MagicMock(stdout="ActiveState=inactive\nSubState=dead\n", returncode=0)
        self.inspector.inspect_service("valid-service.service")
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        self.assertIn("--", cmd)
        dash_idx = cmd.index("--")
        svc_idx = cmd.index("valid-service.service")
        self.assertEqual(svc_idx, dash_idx + 1, "-- must immediately precede service_name")


if __name__ == "__main__":
    unittest.main()
