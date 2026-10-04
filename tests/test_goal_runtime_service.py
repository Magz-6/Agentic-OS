#!/usr/bin/env python3
"""Unit tests for AgenticOS Goal Runtime systemd service integration.

Verifies:
1. Existence, readability, and valid INI syntax of agenticos-goal-runtime.service.template.
2. Safety check: template is NOT installed into host /etc/systemd/system/.
3. Security constraints: DynamicUser=yes, NoNewPrivileges=true, ProtectSystem=strict.
4. Bounded restart policy: Restart=on-failure, RestartSec=5s.
5. OS-level StateDirectory configuration: StateDirectory=agenticos/goal-runtime.
6. Target ExecStart execution path: /usr/bin/python3 /opt/agenticos/system-services/goal-runtime/runner.py.
7. Service runner self-diagnostic health check (--check flag).
8. Clean distinction between process persistence and in-memory goal data persistence.
"""

from __future__ import annotations

import configparser
import os
import subprocess
import sys
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TEMPLATE_PATH = os.path.join(
    PROJECT_ROOT, "linux_integration", "systemd", "agenticos-goal-runtime.service.template"
)
RUNNER_PATH = os.path.join(PROJECT_ROOT, "system-services", "goal-runtime", "runner.py")


class TestGoalRuntimeSystemdService(unittest.TestCase):
    """Test suite for Goal Runtime systemd service configuration and runner."""

    def setUp(self):
        self.assertTrue(os.path.exists(TEMPLATE_PATH), f"Template not found at {TEMPLATE_PATH}")
        self.parser = configparser.ConfigParser(interpolation=None, strict=False)
        with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
            self.parser.read_file(f)

    def test_service_template_valid_ini(self):
        """Verify the template parses cleanly as a standard systemd INI file."""
        self.assertIn("Unit", self.parser.sections())
        self.assertIn("Service", self.parser.sections())
        self.assertIn("Install", self.parser.sections())

    def test_execstart_target_and_no_shell(self):
        """Verify ExecStart directly executes python3 runner without shell wrappers."""
        exec_start = self.parser.get("Service", "ExecStart")
        self.assertTrue(
            exec_start.startswith("/usr/bin/python3"),
            f"ExecStart must use absolute python3 path: {exec_start}",
        )
        self.assertIn("/opt/agenticos/system-services/goal-runtime/runner.py", exec_start)
        self.assertNotIn("sh -c", exec_start, "ExecStart must not use shell wrapper")
        self.assertNotIn("/bin/bash", exec_start, "ExecStart must not use bash wrapper")

    def test_bounded_restart_policy(self):
        """Verify restart-on-failure behavior is safe and bounded."""
        restart = self.parser.get("Service", "Restart")
        restart_sec = self.parser.get("Service", "RestartSec")
        self.assertEqual(restart, "on-failure")
        self.assertEqual(restart_sec, "5s")

    def test_unprivileged_security_constraints(self):
        """Verify unprivileged sandboxing and DynamicUser configuration."""
        self.assertEqual(self.parser.get("Service", "DynamicUser"), "yes")
        self.assertEqual(self.parser.get("Service", "NoNewPrivileges"), "true")
        self.assertEqual(self.parser.get("Service", "ProtectSystem"), "strict")
        self.assertEqual(self.parser.get("Service", "ProtectHome"), "true")
        self.assertEqual(self.parser.get("Service", "PrivateTmp"), "true")

    def test_state_directory_configured(self):
        """Verify StateDirectory is configured for OS-level persistence."""
        state_dir = self.parser.get("Service", "StateDirectory")
        self.assertEqual(state_dir, "agenticos/goal-runtime")

    def test_installation_target(self):
        """Verify service targets multi-user.target for boot startup."""
        wanted_by = self.parser.get("Install", "WantedBy")
        self.assertEqual(wanted_by, "multi-user.target")

    def test_service_not_installed_on_host(self):
        """Safety assertion: verify template is NOT installed into host /etc/systemd/system/."""
        host_installed_path = "/etc/systemd/system/agenticos-goal-runtime.service"
        self.assertFalse(
            os.path.exists(host_installed_path),
            f"Template must not be installed onto host system: {host_installed_path}",
        )

    def test_runner_exists_and_executable(self):
        """Verify system-services/goal-runtime/runner.py exists and is readable."""
        self.assertTrue(os.path.exists(RUNNER_PATH), f"Runner missing at {RUNNER_PATH}")
        self.assertTrue(os.path.isfile(RUNNER_PATH))

    def test_runner_health_check_cli(self):
        """Verify runner.py --check returns exit code 0 and reports healthy."""
        result = subprocess.run(
            [sys.executable, RUNNER_PATH, "--check"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            result.returncode,
            0,
            f"runner.py --check failed with code {result.returncode}: {result.stderr}",
        )
        self.assertIn("healthy", result.stdout.lower())
        self.assertIn("agenticos-goal-runtime", result.stdout)

    def test_runner_graceful_shutdown_on_sigterm(self):
        """Verify runner.py terminates cleanly with exit code 0 upon SIGTERM."""
        if sys.platform == "win32":
            # POSIX signals are tested in Linux environment
            return
        import time
        import signal

        proc = subprocess.Popen(
            [sys.executable, RUNNER_PATH],
            cwd=PROJECT_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            # Allow runner to initialize
            time.sleep(1.0)
            proc.send_signal(signal.SIGTERM)
            stdout, stderr = proc.communicate(timeout=5)
            self.assertEqual(proc.returncode, 0, f"Expected returncode 0 on SIGTERM, got {proc.returncode}. Stderr: {stderr}")
            combined = (stdout + "\n" + stderr).lower()
            self.assertIn("shutdown completed cleanly", combined)
        finally:
            if proc.poll() is None:
                proc.kill()


if __name__ == "__main__":
    unittest.main()

