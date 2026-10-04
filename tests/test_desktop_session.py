#!/usr/bin/env python3
"""
Unit tests for AgenticOS Desktop Session Service and Runner.
Layer 9: Applications & Desktop Integration Boundary
Layer 12: Linux Integration Boundary
Owner: Magesh (Linux/OS Lead)
"""

import configparser
import importlib.util
import os
import shutil
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_PATH = PROJECT_ROOT / "linux_integration" / "systemd" / "agenticos-desktop.service.template"
RUNNER_PATH = PROJECT_ROOT / "system-services" / "desktop" / "runner.py"

# Dynamically load runner module from hyphenated directory path
spec = importlib.util.spec_from_file_location("desktop_runner", str(RUNNER_PATH))
desktop_runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(desktop_runner)


class TestDesktopServiceTemplate(unittest.TestCase):
    """Test suite for agenticos-desktop.service.template."""

    def test_template_exists(self):
        self.assertTrue(TEMPLATE_PATH.is_file(), f"Missing {TEMPLATE_PATH}")

    def test_template_valid_ini(self):
        config = configparser.ConfigParser(interpolation=None)
        config.optionxform = str  # type: ignore
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        config.read_string(content)

        self.assertIn("Unit", config.sections())
        self.assertIn("Service", config.sections())
        self.assertIn("Install", config.sections())

    def test_unit_dependencies(self):
        config = configparser.ConfigParser(interpolation=None)
        config.optionxform = str  # type: ignore
        config.read_string(TEMPLATE_PATH.read_text(encoding="utf-8"))

        unit = config["Unit"]
        after = unit.get("After", "")
        self.assertIn("agenticos-firstboot.service", after)
        self.assertIn("agenticos-prompt-ui.service", after)

    def test_service_execstart(self):
        config = configparser.ConfigParser(interpolation=None)
        config.optionxform = str  # type: ignore
        config.read_string(TEMPLATE_PATH.read_text(encoding="utf-8"))

        service = config["Service"]
        exec_start = service.get("ExecStart", "")
        self.assertIn("/opt/agenticos/system-services/desktop/runner.py", exec_start)
        self.assertTrue(exec_start.startswith("/usr/bin/python3"))

    def test_install_wiring(self):
        config = configparser.ConfigParser(interpolation=None)
        config.optionxform = str  # type: ignore
        config.read_string(TEMPLATE_PATH.read_text(encoding="utf-8"))

        install = config["Install"]
        self.assertEqual(install.get("WantedBy"), "graphical.target")
        self.assertEqual(install.get("Alias"), "display-manager.service")

    def test_not_installed_on_host(self):
        host_unit = Path("/etc/systemd/system/agenticos-desktop.service")
        self.assertFalse(host_unit.exists(), "Service must not be installed on host system!")


class TestDesktopRunnerUserResolution(unittest.TestCase):
    """Test suite for desktop runner user resolution logic."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.marker_path = Path(self.temp_dir) / "firstboot-completed"
        self.passwd_path = Path(self.temp_dir) / "passwd"

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_resolve_user_empty(self):
        user = desktop_runner.resolve_user(marker_path=self.marker_path, passwd_path=self.passwd_path)
        self.assertIsNone(user)

    def test_resolve_user_from_marker(self):
        current_user = os.environ.get("USER", "root")
        self.marker_path.write_text(f"AGENTICOS_FIRSTBOOT_COMPLETED=true\nCREATED_USER={current_user}\n")
        user = desktop_runner.resolve_user(marker_path=self.marker_path, passwd_path=self.passwd_path)
        self.assertEqual(user, current_user)

    def test_constants(self):
        self.assertEqual(desktop_runner.DISPLAY_NUM, ":0")
        self.assertEqual(desktop_runner.VT_NUM, "vt7")
        self.assertEqual(desktop_runner.PROMPT_UI_URL, "http://127.0.0.1:8000")


class TestXorgFramebufferFallbackConfig(unittest.TestCase):
    """Test suite for Xorg framebuffer fallback configuration and package manifest."""

    def test_xorg_fallback_conf_exists(self):
        conf_path = PROJECT_ROOT / "linux_integration" / "xorg" / "10-framebuffer.conf"
        self.assertTrue(conf_path.is_file(), f"Missing {conf_path}")

    def test_xorg_fallback_conf_contents(self):
        conf_path = PROJECT_ROOT / "linux_integration" / "xorg" / "10-framebuffer.conf"
        content = conf_path.read_text(encoding="utf-8")
        self.assertIn('Section "Device"', content)
        self.assertIn('Driver      "fbdev"', content)
        self.assertIn('Option      "fbdev" "/dev/fb0"', content)
        self.assertIn('Section "Screen"', content)

    def test_gui_packages_manifest_includes_fbdev(self):
        manifest_path = PROJECT_ROOT / "packaging" / "config" / "gui-packages.conf"
        self.assertTrue(manifest_path.is_file(), f"Missing {manifest_path}")
        packages = [line.strip() for line in manifest_path.read_text(encoding="utf-8").splitlines() if line.strip() and not line.startswith("#")]
        self.assertIn("xserver-xorg-video-fbdev", packages)

class TestDesktopVTSwitch(unittest.TestCase):
    """Test suite for virtual terminal switching in desktop runner."""

    def test_switch_vt_callable(self):
        self.assertTrue(callable(getattr(desktop_runner, "switch_vt", None)))

    def test_switch_vt_with_mock_binary(self):
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".sh") as tmp:
            tmp.write("#!/bin/sh\nexit 0\n")
            tmp_path = tmp.name
        try:
            os.chmod(tmp_path, 0o755)
            res = desktop_runner.switch_vt(vt="vt7", chvt_path=tmp_path)
            self.assertTrue(res)
        finally:
            os.unlink(tmp_path)

    def test_switch_vt_missing_binary(self):
        res = desktop_runner.switch_vt(vt="vt7", chvt_path="/nonexistent/chvt")
        self.assertFalse(res)


if __name__ == "__main__":
    unittest.main()
