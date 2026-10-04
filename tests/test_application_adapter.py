"""Tests for ApplicationAdapter.

Validates:
- Allowlisted application behavior (browser, terminal, text_editor, file_manager)
- Unavailable application / binary resolution
- Unknown application / action rejection
- Arbitrary command / file path rejection
- Shell metacharacter rejection in arguments
- Dry-run execution
"""

import unittest
from unittest.mock import patch

from adapters.application_adapter import ApplicationAdapter
from adapters.result import AdapterStatus


class TestApplicationAdapter(unittest.TestCase):
    """Test suite for ApplicationAdapter."""

    def setUp(self):
        self.adapter = ApplicationAdapter()

    def test_adapter_metadata(self):
        """Verify adapter metadata and supported actions."""
        self.assertEqual(self.adapter.name, "application")
        self.assertIn("launch_application", self.adapter.supported_actions)
        self.assertIn("check_availability", self.adapter.supported_actions)
        self.assertIn("list_applications", self.adapter.supported_actions)
        self.assertIn("resolve_binary", self.adapter.supported_actions)

    def test_list_applications(self):
        """Verify listing allowlisted applications."""
        result = self.adapter.run("list_applications")
        self.assertTrue(result.success)
        self.assertEqual(result.status, AdapterStatus.SUCCESS)
        self.assertIn("applications", result.data)
        apps = result.data["applications"]
        self.assertIn("browser", apps)
        self.assertIn("terminal", apps)
        self.assertIn("text_editor", apps)
        self.assertIn("file_manager", apps)

    def test_check_availability_unknown_app(self):
        """Verify checking availability of an unallowlisted app fails validation."""
        result = self.adapter.run("check_availability", {"app_name": "malicious_tool"})
        self.assertFalse(result.success)
        self.assertEqual(result.status, AdapterStatus.VALIDATION_ERROR)
        self.assertIn("Unknown or disallowed application", str(result.error))

    def test_check_availability_allowlisted(self):
        """Verify checking availability for an allowlisted app."""
        result = self.adapter.run("check_availability", {"app_name": "browser"})
        self.assertTrue(result.success)
        self.assertEqual(result.status, AdapterStatus.SUCCESS)
        self.assertIn("available", result.data)
        self.assertIn("app_name", result.data)
        self.assertEqual(result.data["app_name"], "browser")

    def test_resolve_binary_found(self):
        """Verify resolve_binary returns path when found."""
        with patch("shutil.which", return_value="/usr/bin/nano"):
            result = self.adapter.run("resolve_binary", {"app_name": "text_editor"})
            self.assertTrue(result.success)
            self.assertEqual(result.data["binary_path"], "/usr/bin/nano")

    def test_resolve_binary_not_found(self):
        """Verify resolve_binary returns None when no candidate binary exists."""
        with patch("shutil.which", return_value=None):
            result = self.adapter.run("resolve_binary", {"app_name": "browser"})
            self.assertTrue(result.success)
            self.assertIsNone(result.data["binary_path"])

    def test_launch_application_dry_run(self):
        """Verify dry run launch succeeds without actually spawning processes."""
        result = self.adapter.run("launch_application", {"app_name": "text_editor", "dry_run": True})
        self.assertTrue(result.success)
        self.assertTrue(result.data["dry_run"])
        self.assertEqual(result.data["app_name"], "text_editor")

    def test_launch_application_dry_run_with_valid_args(self):
        """Verify dry run with valid arguments."""
        result = self.adapter.run(
            "launch_application",
            {"app_name": "text_editor", "args": ["/tmp/test.txt", "--line", "10"], "dry_run": True}
        )
        self.assertTrue(result.success)
        self.assertTrue(result.data["dry_run"])
        self.assertEqual(result.data["args"], ["/tmp/test.txt", "--line", "10"])

    def test_reject_unallowlisted_application(self):
        """Verify rejection of non-allowlisted application."""
        result = self.adapter.run("launch_application", {"app_name": "bash"})
        self.assertFalse(result.success)
        self.assertEqual(result.status, AdapterStatus.VALIDATION_ERROR)
        self.assertIn("Unknown or disallowed application", str(result.error))

    def test_reject_arbitrary_path_launch(self):
        """Verify arbitrary file paths cannot be passed as app_name."""
        for bad_app in ["/bin/sh", "/usr/bin/python3", "curl", "rm", "sudo"]:
            result = self.adapter.run("launch_application", {"app_name": bad_app})
            self.assertFalse(result.success)
            self.assertEqual(result.status, AdapterStatus.VALIDATION_ERROR)

    def test_reject_shell_metacharacters_in_args(self):
        """Verify shell metacharacters in arguments are blocked."""
        dangerous_args = [
            ["foo; rm -rf /"],
            ["foo && ls"],
            ["foo | grep bar"],
            ["`whoami`"],
            ["$(id)"],
            ["test > /tmp/out"],
            ["test < /tmp/in"],
            ["var=$VAL"],
            ["item\ncommand"],
        ]
        for args in dangerous_args:
            result = self.adapter.run(
                "launch_application",
                {"app_name": "text_editor", "args": args, "dry_run": True}
            )
            self.assertFalse(result.success, f"Should have failed on args: {args}")
            self.assertEqual(result.status, AdapterStatus.VALIDATION_ERROR)
            self.assertIn("forbidden", str(result.error))

    def test_reject_non_list_args(self):
        """Verify args must be a list of strings."""
        result = self.adapter.run(
            "launch_application",
            {"app_name": "text_editor", "args": "not a list", "dry_run": True}
        )
        self.assertFalse(result.success)
        self.assertEqual(result.status, AdapterStatus.VALIDATION_ERROR)
        self.assertIn("must be a list", str(result.error))

    def test_reject_missing_app_name(self):
        """Verify validation fails if app_name is missing."""
        result = self.adapter.run("launch_application", {})
        self.assertFalse(result.success)
        self.assertEqual(result.status, AdapterStatus.VALIDATION_ERROR)
        self.assertIn("Missing required parameter", str(result.error))

    def test_unsupported_action(self):
        """Verify unsupported action is rejected."""
        result = self.adapter.run("execute_command", {"command": "ls"})
        self.assertFalse(result.success)
        self.assertEqual(result.status, AdapterStatus.UNSUPPORTED_ACTION)


if __name__ == "__main__":
    unittest.main()
