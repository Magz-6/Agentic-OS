"""
AgenticOS - Prompt UI Integration Unit Tests
Layer 9: Applications & Desktop Integration Boundary
Owner: Magesh (Linux/OS Lead)

Validates the Prompt UI files, launcher interface, desktop entry template,
and verifies strict adherence to the mock backend boundary.
"""

import configparser
import json
import subprocess
import sys
import unittest
from pathlib import Path


class TestPromptUIIntegration(unittest.TestCase):
    """Test suite for Prompt UI integration."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.repo_root = Path(__file__).resolve().parent.parent
        cls.app_dir = cls.repo_root / "applications" / "prompt-ui"
        cls.template_path = cls.app_dir / "agenticos-prompt-ui.desktop.template"
        cls.launcher_path = cls.app_dir / "launch.py"

    def test_all_ui_assets_present(self) -> None:
        """Verify all 6 core UI prototype files and integration scripts exist."""
        expected_files = [
            "index.html",
            "styles.css",
            "app.js",
            "request-handler.js",
            "server.py",
            "README.md",
            "launch.py",
            "agenticos-prompt-ui.desktop.template",
        ]
        for fname in expected_files:
            target = self.app_dir / fname
            self.assertTrue(target.is_file(), f"Missing required UI file: {fname}")
            self.assertGreater(target.stat().st_size, 0, f"File is empty: {fname}")

    def test_desktop_template_syntax(self) -> None:
        """Verify FreeDesktop .desktop entry syntax and action definitions."""
        config = configparser.ConfigParser(interpolation=None)
        config.optionxform = str  # type: ignore
        config.read_string(self.template_path.read_text(encoding="utf-8"))

        self.assertIn("Desktop Entry", config.sections())
        entry = config["Desktop Entry"]
        self.assertEqual(entry.get("Type"), "Application")
        self.assertEqual(entry.get("Name"), "AgenticOS Prompt UI")
        self.assertIn("Exec", entry)

        # Check all actions are present
        actions = [a.strip() for a in entry.get("Actions", "").split(";") if a.strip()]
        expected_actions = ["LaunchBrowserOnly", "StartServerOnly", "StopServer"]
        for expected in expected_actions:
            self.assertIn(expected, actions)
            section = f"Desktop Action {expected}"
            self.assertIn(section, config.sections())
            self.assertIn("Exec", config[section])

    def test_no_shell_wrappers_in_exec(self) -> None:
        """Verify that Exec lines do not use arbitrary shell wrappers."""
        config = configparser.ConfigParser(interpolation=None)
        config.optionxform = str  # type: ignore
        config.read_string(self.template_path.read_text(encoding="utf-8"))

        for section in config.sections():
            if "Exec" in config[section]:
                cmd = config[section]["Exec"]
                self.assertNotIn("sh -c", cmd)
                self.assertNotIn("bash -c", cmd)

    def test_desktop_template_strictly_uninstalled(self) -> None:
        """Safety assertion: verify template is not installed into system directories."""
        user_apps = Path.home() / ".local" / "share" / "applications" / "agenticos-prompt-ui.desktop"
        self.assertFalse(user_apps.exists(), "Must not be installed in ~/.local/share/applications!")

        sys_apps = Path("/usr/share/applications/agenticos-prompt-ui.desktop")
        self.assertFalse(sys_apps.exists(), "Must not be installed in /usr/share/applications!")

    def test_launcher_dry_run(self) -> None:
        """Verify that launch.py executes dry-run without errors."""
        res = subprocess.run(
            [sys.executable, str(self.launcher_path), "--dry-run", "--json"],
            capture_output=True,
            text=True,
            check=True,
        )
        data = json.loads(res.stdout)
        self.assertEqual(data.get("status"), "dry_run")
        self.assertEqual(data.get("url"), "http://127.0.0.1:8000")

    def test_mock_backend_boundary_preserved(self) -> None:
        """Verify that request-handler.js retains its mock execution engine."""
        handler_text = (self.app_dir / "request-handler.js").read_text(encoding="utf-8")
        self.assertIn("class MockAgenticEngine", handler_text)
        self.assertIn("classifyRisk", handler_text)
        self.assertIn("AWAITING_CONFIRMATION", handler_text)
        # Ensure it has not been replaced with live network calls
        self.assertNotIn("http://localhost:5000/api", handler_text)
        self.assertNotIn("wss://", handler_text)


class TestPromptUISystemdService(unittest.TestCase):
    """Test suite for Prompt UI systemd service template verification."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.repo_root = Path(__file__).resolve().parent.parent
        cls.template_path = (
            cls.repo_root
            / "linux_integration"
            / "systemd"
            / "agenticos-prompt-ui.service.template"
        )

    def test_service_template_exists(self) -> None:
        self.assertTrue(self.template_path.is_file(), f"Missing {self.template_path}")

    def test_service_template_valid_ini(self) -> None:
        config = configparser.ConfigParser(interpolation=None)
        config.optionxform = str  # type: ignore
        content = self.template_path.read_text(encoding="utf-8")
        config.read_string(content)

        self.assertIn("Unit", config.sections())
        self.assertIn("Service", config.sections())
        self.assertIn("Install", config.sections())

    def test_execstart_target_and_no_shell(self) -> None:
        config = configparser.ConfigParser(interpolation=None)
        config.optionxform = str  # type: ignore
        config.read_string(self.template_path.read_text(encoding="utf-8"))

        exec_start = config["Service"].get("ExecStart", "")
        self.assertEqual(
            exec_start,
            "/usr/bin/python3 /opt/agenticos/applications/prompt-ui/server.py",
        )
        self.assertNotIn("sh -c", exec_start)
        self.assertNotIn("bash -c", exec_start)

    def test_unprivileged_security_constraints(self) -> None:
        config = configparser.ConfigParser(interpolation=None)
        config.optionxform = str  # type: ignore
        config.read_string(self.template_path.read_text(encoding="utf-8"))

        service = config["Service"]
        self.assertNotEqual(service.get("User", ""), "root")
        self.assertEqual(service.get("DynamicUser", "").lower(), "yes")
        self.assertEqual(service.get("NoNewPrivileges", "").lower(), "true")

    def test_bounded_restart_policy(self) -> None:
        config = configparser.ConfigParser(interpolation=None)
        config.optionxform = str  # type: ignore
        config.read_string(self.template_path.read_text(encoding="utf-8"))

        service = config["Service"]
        self.assertEqual(service.get("Restart", ""), "on-failure")
        self.assertIn("5", service.get("RestartSec", ""))

    def test_service_not_installed_on_host(self) -> None:
        host_unit = Path("/etc/systemd/system/agenticos-prompt-ui.service")
        self.assertFalse(
            host_unit.exists(),
            "CRITICAL: agenticos-prompt-ui.service must not be installed on host /etc/systemd/system!",
        )


if __name__ == "__main__":
    unittest.main()
