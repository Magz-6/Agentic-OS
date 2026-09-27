"""
AgenticOS - Desktop Integration Unit Tests
Layer 9: Applications & Desktop Integration Boundary
Owner: Magesh (Linux/OS Lead)

Validates the FreeDesktop .desktop entry template, action definitions,
and asserts that no unauthorized shortcuts were installed on the host.
"""

import configparser
import os
import unittest
from pathlib import Path


class TestDesktopIntegration(unittest.TestCase):
    """Test suite for desktop integration template."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.repo_root = Path(__file__).resolve().parent.parent
        cls.template_path = (
            cls.repo_root / "desktop" / "agenticos.desktop.template"
        )

    def test_template_file_exists(self) -> None:
        """Verify that the desktop entry template exists in the repository."""
        self.assertTrue(
            self.template_path.is_file(),
            f"Expected template at {self.template_path}",
        )

    def test_desktop_entry_syntax(self) -> None:
        """Verify standard FreeDesktop .desktop entry keys and sections."""
        config = configparser.ConfigParser(interpolation=None)
        config.optionxform = str  # type: ignore
        config.read_string(self.template_path.read_text(encoding="utf-8"))

        self.assertIn("Desktop Entry", config.sections())
        entry = config["Desktop Entry"]
        self.assertEqual(entry.get("Type"), "Application")
        self.assertEqual(entry.get("Name"), "AgenticOS")
        self.assertEqual(entry.get("Terminal", "").lower(), "true")
        self.assertIn("Exec", entry)

    def test_desktop_actions_configured(self) -> None:
        """Verify all 4 desktop actions are defined with valid sections."""
        config = configparser.ConfigParser(interpolation=None)
        config.optionxform = str  # type: ignore
        config.read_string(self.template_path.read_text(encoding="utf-8"))

        actions_str = config["Desktop Entry"].get("Actions", "")
        actions = [a.strip() for a in actions_str.split(";") if a.strip()]

        expected_actions = ["SystemInfo", "HealthCheck", "LaunchTerminal", "LaunchBrowser"]
        for expected in expected_actions:
            self.assertIn(expected, actions)
            section_name = f"Desktop Action {expected}"
            self.assertIn(section_name, config.sections())
            self.assertIn("Exec", config[section_name])

    def test_no_shell_wrapper_in_exec(self) -> None:
        """Verify that Exec lines do not use arbitrary shell wrappers."""
        config = configparser.ConfigParser(interpolation=None)
        config.optionxform = str  # type: ignore
        config.read_string(self.template_path.read_text(encoding="utf-8"))

        for sec in config.sections():
            if "Exec" in config[sec]:
                exec_cmd = config[sec]["Exec"]
                self.assertNotIn("sh -c", exec_cmd)
                self.assertNotIn("bash -c", exec_cmd)

    def test_desktop_entry_strictly_uninstalled(self) -> None:
        """
        Safety assertion: verify that the desktop entry has NOT been installed
        into user or system application directories.
        """
        user_apps = Path.home() / ".local" / "share" / "applications" / "agenticos.desktop"
        self.assertFalse(
            user_apps.exists(),
            "CRITICAL: agenticos.desktop must not be installed in ~/.local/share/applications!",
        )

        sys_apps = Path("/usr/share/applications/agenticos.desktop")
        self.assertFalse(
            sys_apps.exists(),
            "CRITICAL: agenticos.desktop must not be installed in /usr/share/applications!",
        )


if __name__ == "__main__":
    unittest.main()
