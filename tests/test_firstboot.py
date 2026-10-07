#!/usr/bin/env python3
"""
AgenticOS - First-Boot Account Setup Unit Tests
Layer 12: Agentic Microkernel / Linux Integration Boundary
Owner: Magesh (Linux/OS Lead)

Validates:
1. POSIX username validation, length constraints, and reserved username blocking.
2. Password validation (non-empty, min length, confirmation matching).
3. Setup completion detection (marker file and UID >= 1000 check).
4. Non-destructive dry-run account creation and marker generation.
5. Systemd first-boot service template syntax and security properties.
6. Safety assertion: service template is not installed on the host.
"""

import configparser
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from applications.firstboot.setup_wizard import (
    check_setup,
    create_local_user,
    is_setup_completed,
    main,
    validate_password,
    validate_username,
)


class TestFirstBootValidation(unittest.TestCase):
    """Test suite for first-boot credential and input validation."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.mock_passwd = os.path.join(self.temp_dir, "passwd")
        with open(self.mock_passwd, "w", encoding="utf-8") as f:
            f.write("root:x:0:0:root:/root:/bin/bash\n")
            f.write("daemon:x:1:1:daemon:/usr/sbin:/usr/sbin/nologin\n")
            f.write("nobody:x:65534:65534:nobody:/nonexistent:/usr/sbin/nologin\n")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_valid_usernames(self):
        valid_names = ["alice", "dev_user", "agent-01", "john_doe", "user123", "a"]
        for name in valid_names:
            valid, msg = validate_username(name, self.mock_passwd)
            self.assertTrue(valid, f"Expected '{name}' to be valid, got: {msg}")

    def test_invalid_usernames_empty_or_length(self):
        # Empty
        valid, msg = validate_username("", self.mock_passwd)
        self.assertFalse(valid)
        self.assertIn("empty", msg.lower())

        # Too long (> 32 chars)
        long_name = "a" * 33
        valid, msg = validate_username(long_name, self.mock_passwd)
        self.assertFalse(valid)
        self.assertIn("32", msg)

    def test_invalid_usernames_characters(self):
        invalid_names = [
            "Alice",  # uppercase
            "123user",  # starts with digit
            "-user",  # starts with hyphen
            "user name",  # space
            "user@name",  # special char
            "user!",  # special char
        ]
        for name in invalid_names:
            valid, msg = validate_username(name, self.mock_passwd)
            self.assertFalse(valid, f"Expected '{name}' to be invalid")

    def test_reserved_usernames_rejected(self):
        reserved = ["root", "daemon", "bin", "sys", "nobody", "sshd", "_apt"]
        for name in reserved:
            valid, msg = validate_username(name, self.mock_passwd)
            self.assertFalse(valid, f"Expected reserved name '{name}' to be rejected")
            self.assertIn("reserved", msg.lower())

    def test_existing_username_rejected(self):
        # Add existing custom user to mock passwd
        with open(self.mock_passwd, "a", encoding="utf-8") as f:
            f.write("existinguser:x:1001:1001::/home/existinguser:/bin/bash\n")

        valid, msg = validate_username("existinguser", self.mock_passwd)
        self.assertFalse(valid)
        self.assertIn("already exists", msg.lower())

    def test_password_validation(self):
        # Empty
        valid, msg = validate_password("", "")
        self.assertFalse(valid)
        self.assertIn("empty", msg.lower())

        # Too short (< 4)
        valid, msg = validate_password("abc", "abc")
        self.assertFalse(valid)
        self.assertIn("at least 4", msg.lower())

        # Mismatch
        valid, msg = validate_password("password123", "password456")
        self.assertFalse(valid)
        self.assertIn("do not match", msg.lower())

        # Valid
        valid, msg = validate_password("securepassword", "securepassword")
        self.assertTrue(valid)
        self.assertEqual(msg, "")


class TestFirstBootDetectionAndCreation(unittest.TestCase):
    """Test suite for setup completion detection and dry-run creation."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.marker_path = os.path.join(self.temp_dir, "firstboot-completed")
        self.mock_passwd = os.path.join(self.temp_dir, "passwd")
        # System only accounts (no UID >= 1000)
        with open(self.mock_passwd, "w", encoding="utf-8") as f:
            f.write("root:x:0:0:root:/root:/bin/bash\n")
            f.write("daemon:x:1:1:daemon:/usr/sbin:/usr/sbin/nologin\n")
            f.write("nobody:x:65534:65534:nobody:/nonexistent:/usr/sbin/nologin\n")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_setup_not_completed_initially(self):
        completed = is_setup_completed(self.marker_path, self.mock_passwd)
        self.assertFalse(completed)

    def test_setup_completed_by_marker_file(self):
        with open(self.marker_path, "w", encoding="utf-8") as f:
            f.write("AGENTICOS_FIRSTBOOT_COMPLETED=true\n")
        completed = is_setup_completed(self.marker_path, self.mock_passwd)
        self.assertTrue(completed)

    def test_setup_not_completed_by_existing_uid1000(self):
        with open(self.mock_passwd, "a", encoding="utf-8") as f:
            f.write("operator:x:1000:1000::/home/operator:/bin/bash\n")
        completed = is_setup_completed(self.marker_path, self.mock_passwd)
        self.assertFalse(completed)

    def test_dry_run_user_creation(self):
        res = create_local_user(
            "testuser",
            "testpass123",
            dry_run=True,
            marker_path=self.marker_path,
        )
        self.assertTrue(res)
        self.assertTrue(os.path.exists(self.marker_path))
        with open(self.marker_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("AGENTICOS_FIRSTBOOT_COMPLETED=true", content)
        self.assertIn("CREATED_USER=testuser", content)
        self.assertIn("MODE=dry_run", content)

    def test_check_setup_return_codes(self):
        # Initial: required -> exit code 1 (must be int, not bool)
        code_req = check_setup(self.marker_path, self.mock_passwd)
        self.assertEqual(code_req, 1)
        self.assertIs(type(code_req), int)

        # After marker: completed -> exit code 0 (must be int, not bool)
        with open(self.marker_path, "w", encoding="utf-8") as f:
            f.write("AGENTICOS_FIRSTBOOT_COMPLETED=true\n")
        code_comp = check_setup(self.marker_path, self.mock_passwd)
        self.assertEqual(code_comp, 0)
        self.assertIs(type(code_comp), int)

    def test_main_cli_check_flag(self):
        # Initial: required -> main returns 1
        ret_req = main(["--check", "--marker-path", self.marker_path, "--passwd-path", self.mock_passwd])
        self.assertEqual(ret_req, 1)
        self.assertIs(type(ret_req), int)

        # Completed: main returns 0
        with open(self.marker_path, "w", encoding="utf-8") as f:
            f.write("AGENTICOS_FIRSTBOOT_COMPLETED=true\n")
        ret_comp = main(["--check", "--marker-path", self.marker_path, "--passwd-path", self.mock_passwd])
        self.assertEqual(ret_comp, 0)
        self.assertIs(type(ret_comp), int)

    def test_subprocess_cli_check_exit_code(self):
        script_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "applications", "firstboot", "setup_wizard.py")
        )
        # Required state -> exit code 1
        proc_req = subprocess.run(
            [sys.executable, script_path, "--check", "--marker-path", self.marker_path, "--passwd-path", self.mock_passwd],
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc_req.returncode, 1)
        self.assertIn("REQUIRED", proc_req.stdout)

        # Completed state -> exit code 0
        with open(self.marker_path, "w", encoding="utf-8") as f:
            f.write("AGENTICOS_FIRSTBOOT_COMPLETED=true\n")
        proc_comp = subprocess.run(
            [sys.executable, script_path, "--check", "--marker-path", self.marker_path, "--passwd-path", self.mock_passwd],
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc_comp.returncode, 0)
        self.assertIn("COMPLETED", proc_comp.stdout)


class TestFirstBootServiceTemplate(unittest.TestCase):
    """Test suite for systemd service template verification."""

    @classmethod
    def setUpClass(cls):
        cls.repo_root = Path(__file__).resolve().parent.parent
        cls.template_path = (
            cls.repo_root
            / "linux_integration"
            / "systemd"
            / "agenticos-firstboot.service.template"
        )

    def test_template_file_exists(self):
        self.assertTrue(self.template_path.is_file(), f"Missing {self.template_path}")

    def test_template_valid_systemd_ini_syntax(self):
        config = configparser.ConfigParser(interpolation=None)
        config.optionxform = str  # type: ignore
        content = self.template_path.read_text(encoding="utf-8")
        config.read_string(content)

        self.assertIn("Unit", config.sections())
        self.assertIn("Service", config.sections())
        self.assertIn("Install", config.sections())

    def test_unit_ordering_and_condition(self):
        config = configparser.ConfigParser(interpolation=None)
        config.optionxform = str  # type: ignore
        config.read_string(self.template_path.read_text(encoding="utf-8"))

        unit = config["Unit"]
        self.assertEqual(unit.get("Before"), "getty@tty1.service")
        self.assertEqual(
            unit.get("ConditionPathExists"),
            "!/var/lib/agenticos/firstboot-completed",
        )

    def test_service_console_configuration(self):
        config = configparser.ConfigParser(interpolation=None)
        config.optionxform = str  # type: ignore
        config.read_string(self.template_path.read_text(encoding="utf-8"))

        service = config["Service"]
        self.assertEqual(service.get("StandardInput"), "tty")
        self.assertEqual(service.get("StandardOutput"), "tty")
        self.assertEqual(service.get("TTYPath"), "/dev/tty1")
        self.assertIn("/setup_wizard.py", service.get("ExecStart", ""))

    def test_service_not_installed_on_host(self):
        host_system_unit = Path("/etc/systemd/system/agenticos-firstboot.service")
        self.assertFalse(
            host_system_unit.exists(),
            "CRITICAL: agenticos-firstboot.service must not be installed on host /etc/systemd/system!",
        )


if __name__ == "__main__":
    unittest.main()
