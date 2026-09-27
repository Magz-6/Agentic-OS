"""
AgenticOS - Application Launcher Unit Tests
Layer 9: Applications & Services
Owner: Magesh (Linux/OS Lead)

Uses Python standard library `unittest` and `unittest.mock`.
CRITICAL SAFETY RULE: Real processes are NEVER launched during tests.
"""

import unittest
from unittest.mock import MagicMock, patch

from adapters.app_launcher import (
    AppLauncher,
    InvalidArgumentError,
    UnknownApplicationError,
)


class TestAppLauncher(unittest.TestCase):
    """Test suite for AppLauncher."""

    def setUp(self) -> None:
        self.mock_allowlist = {
            "browser": {
                "description": "Mock Browser",
                "candidates": ["mock_browser_bin"],
            },
            "terminal": {
                "description": "Mock Terminal",
                "candidates": ["mock_term_bin"],
            },
        }
        self.launcher = AppLauncher(allowlist=self.mock_allowlist)

    def test_allowlist_membership(self) -> None:
        """Verify checking for allowlisted applications."""
        self.assertTrue(self.launcher.is_allowed("browser"))
        self.assertTrue(self.launcher.is_allowed("terminal"))
        self.assertFalse(self.launcher.is_allowed("malicious_app"))
        self.assertFalse(self.launcher.is_allowed("/bin/sh"))

    def test_rejection_of_unknown_application(self) -> None:
        """Verify that unknown application IDs are rejected with a structured error."""
        res = self.launcher.launch("unauthorized_app")
        self.assertEqual(res["status"], "rejected")
        self.assertEqual(res["reason"], "unknown_application")
        self.assertIsNone(res["pid"])

    def test_rejection_of_arbitrary_executable_paths(self) -> None:
        """Verify that passing an arbitrary path as app_id is rejected."""
        dangerous_paths = [
            "/bin/bash",
            "/usr/bin/python3",
            "../../bin/sh",
            "sudo rm -rf /",
        ]
        for path in dangerous_paths:
            res = self.launcher.launch(path)
            self.assertEqual(res["status"], "rejected")
            self.assertEqual(res["reason"], "unknown_application")

    def test_rejection_of_shell_metacharacters(self) -> None:
        """Verify that arguments containing shell injection vectors are rejected."""
        injection_payloads = [
            ["https://safe.org; rm -rf /"],
            ["https://safe.org && echo pwned"],
            ["https://safe.org | cat /etc/passwd"],
            ["`id`"],
            ["$(whoami)"],
            ["https://safe.org > /tmp/evil"],
            ["arg\nwith\nnewlines"],
        ]
        for payload in injection_payloads:
            res = self.launcher.launch("browser", args=payload)
            self.assertEqual(res["status"], "rejected")
            self.assertEqual(res["reason"], "invalid_arguments")
            self.assertIn("forbidden shell characters", res["error"])

    def test_rejection_of_command_execution_flags(self) -> None:
        """Security test: verify that -c, /c, and --command are strictly rejected."""
        dangerous_flags = [["-c", "id"], ["/c", "dir"], ["--command", "echo"]]
        for flags in dangerous_flags:
            res = self.launcher.launch("terminal", args=flags)
            self.assertEqual(res["status"], "rejected")
            self.assertEqual(res["reason"], "invalid_arguments")
            self.assertIn("strictly prohibited", res["error"])

    def test_default_terminal_candidates_exclude_raw_shells(self) -> None:
        """Security assertion: ensure raw shells are not in the terminal candidates."""
        default_launcher = AppLauncher()
        term_candidates = default_launcher.DEFAULT_ALLOWLIST["terminal"]["candidates"]
        prohibited_shells = {"bash", "sh", "zsh", "dash", "csh", "tcsh", "ksh"}
        for shell in prohibited_shells:
            self.assertNotIn(
                shell,
                term_candidates,
                f"Raw shell '{shell}' must not be a terminal emulator candidate",
            )

    @patch("shutil.which")
    @patch("os.path.isfile")
    @patch("os.access")
    def test_allowlisted_application_resolution(
        self, mock_access: MagicMock, mock_isfile: MagicMock, mock_which: MagicMock
    ) -> None:
        """Verify executable resolution when a candidate binary exists."""
        mock_which.return_value = "/usr/bin/mock_browser_bin"
        mock_isfile.return_value = True
        mock_access.return_value = True

        resolved = self.launcher.resolve_executable("browser")
        self.assertEqual(resolved, "/usr/bin/mock_browser_bin")

    @patch("shutil.which")
    def test_missing_executable_handling(self, mock_which: MagicMock) -> None:
        """Verify graceful error reporting when candidate executable is not installed."""
        mock_which.return_value = None

        res = self.launcher.launch("browser")
        self.assertEqual(res["status"], "error")
        self.assertEqual(res["reason"], "binary_not_found")
        self.assertIsNone(res["pid"])

    @patch("shutil.which")
    @patch("os.path.isfile")
    @patch("os.access")
    def test_dry_run_mode(
        self, mock_access: MagicMock, mock_isfile: MagicMock, mock_which: MagicMock
    ) -> None:
        """Verify dry-run mode returns resolved command without spawning a process."""
        mock_which.return_value = "/usr/bin/mock_term_bin"
        mock_isfile.return_value = True
        mock_access.return_value = True

        res = self.launcher.launch("terminal", args=["--profile", "default"], dry_run=True)
        self.assertEqual(res["status"], "dry_run")
        self.assertEqual(res["executable"], "/usr/bin/mock_term_bin")
        self.assertEqual(res["command"], ["/usr/bin/mock_term_bin", "--profile", "default"])
        self.assertIsNone(res["pid"])

    @patch("subprocess.Popen")
    @patch("shutil.which")
    @patch("os.path.isfile")
    @patch("os.access")
    def test_mocked_launch_success_and_shell_false(
        self,
        mock_access: MagicMock,
        mock_isfile: MagicMock,
        mock_which: MagicMock,
        mock_popen: MagicMock,
    ) -> None:
        """
        Verify successful launch using mocks and explicitly assert shell=False.
        """
        mock_which.return_value = "/usr/bin/mock_browser_bin"
        mock_isfile.return_value = True
        mock_access.return_value = True

        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_popen.return_value = mock_process

        res = self.launcher.launch("browser", args=["https://ubuntu.com"])
        self.assertEqual(res["status"], "launched")
        self.assertEqual(res["pid"], 12345)

        # SECURITY ASSERTION: Verify subprocess.Popen was called with shell=False
        mock_popen.assert_called_once()
        _, kwargs = mock_popen.call_args
        self.assertFalse(kwargs.get("shell", True), "CRITICAL: shell must be False")


if __name__ == "__main__":
    unittest.main()
