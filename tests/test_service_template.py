"""
AgenticOS - Service Template & Configuration Unit Tests
Layer 12: Agentic Microkernel / Linux Integration Boundary
Owner: Magesh (Linux/OS Lead)

Validates the declarative systemd unit template, security constraints,
and verifies that no unauthorized services were installed on the host.
"""

import configparser
import os
import unittest
from pathlib import Path


class TestServiceTemplate(unittest.TestCase):
    """Test suite for systemd service template verification."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.repo_root = Path(__file__).resolve().parent.parent
        cls.template_path = (
            cls.repo_root
            / "linux_integration"
            / "systemd"
            / "agenticos-telemetry.service.template"
        )

    def test_template_file_exists(self) -> None:
        """Verify that the template file exists in the repository."""
        self.assertTrue(
            self.template_path.is_file(),
            f"Expected template at {self.template_path}",
        )

    def test_template_valid_systemd_ini_syntax(self) -> None:
        """Verify that the template parses cleanly as a standard INI configuration."""
        config = configparser.ConfigParser(interpolation=None)
        # Preserve case sensitivity for systemd keys
        config.optionxform = str  # type: ignore

        content = self.template_path.read_text(encoding="utf-8")
        config.read_string(content)

        # Must have [Unit], [Service], and [Install] sections
        self.assertIn("Unit", config.sections())
        self.assertIn("Service", config.sections())
        self.assertIn("Install", config.sections())

    def test_execstart_no_shell_wrapper(self) -> None:
        """Verify that ExecStart invokes python directly and does not use sh -c."""
        config = configparser.ConfigParser(interpolation=None)
        config.optionxform = str  # type: ignore
        config.read_string(self.template_path.read_text(encoding="utf-8"))

        exec_start = config["Service"].get("ExecStart", "")
        self.assertTrue(exec_start.startswith("/usr/bin/python3 -m"))
        self.assertNotIn("sh -c", exec_start)
        self.assertNotIn("bash -c", exec_start)
        self.assertNotIn(";", exec_start)
        self.assertNotIn("&", exec_start)

    def test_security_constraints_no_root(self) -> None:
        """Verify that no root privileges or elevated capabilities are specified."""
        config = configparser.ConfigParser(interpolation=None)
        config.optionxform = str  # type: ignore
        config.read_string(self.template_path.read_text(encoding="utf-8"))

        service = config["Service"]
        # Must not request root user or group
        self.assertNotEqual(service.get("User", ""), "root")
        self.assertNotEqual(service.get("Group", ""), "root")

        # Must have NoNewPrivileges
        self.assertEqual(service.get("NoNewPrivileges", "").lower(), "true")

    def test_restart_policy_configured(self) -> None:
        """Verify that a safe restart policy is configured."""
        config = configparser.ConfigParser(interpolation=None)
        config.optionxform = str  # type: ignore
        config.read_string(self.template_path.read_text(encoding="utf-8"))

        service = config["Service"]
        self.assertEqual(service.get("Restart", ""), "on-failure")
        self.assertIn("5", service.get("RestartSec", ""))

    def test_service_strictly_uninstalled(self) -> None:
        """
        Safety assertion: verify that the service template has NOT been installed
        into system or user service directories.
        """
        system_unit = Path("/etc/systemd/system/agenticos-telemetry.service")
        self.assertFalse(
            system_unit.exists(),
            "CRITICAL: agenticos-telemetry.service must not be installed in /etc/systemd/system!",
        )

        user_home = Path.home()
        user_unit = user_home / ".config" / "systemd" / "user" / "agenticos-telemetry.service"
        self.assertFalse(
            user_unit.exists(),
            "CRITICAL: agenticos-telemetry.service must not be installed in user systemd directory!",
        )


if __name__ == "__main__":
    unittest.main()
