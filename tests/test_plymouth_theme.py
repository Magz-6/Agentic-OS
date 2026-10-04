"""Unit tests for AgenticOS Plymouth boot splash theme and integration."""

import configparser
import re
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestPlymouthTheme(unittest.TestCase):
    """Test suite validating AgenticOS Plymouth theme structure and packaging."""

    def setUp(self):
        self.theme_file = PROJECT_ROOT / "linux_integration" / "plymouth" / "agenticos" / "agenticos.plymouth"
        self.grub_cfg = PROJECT_ROOT / "packaging" / "config" / "grub.cfg"
        self.build_script = PROJECT_ROOT / "packaging" / "scripts" / "build_iso.sh"

    def test_theme_file_exists(self):
        """Verify the agenticos.plymouth theme file exists."""
        self.assertTrue(self.theme_file.is_file(), f"Missing theme file: {self.theme_file}")

    def test_theme_file_structure(self):
        """Verify theme file parses as INI and has required sections and keys."""
        config = configparser.ConfigParser()
        config.read(self.theme_file)

        self.assertIn("Plymouth Theme", config.sections())
        self.assertIn("ubuntu-text", config.sections())

        # Check [Plymouth Theme]
        theme_sec = config["Plymouth Theme"]
        self.assertEqual(theme_sec.get("Name"), "AgenticOS")
        self.assertEqual(theme_sec.get("ModuleName"), "ubuntu-text")

        # Check [ubuntu-text]
        text_sec = config["ubuntu-text"]
        self.assertEqual(text_sec.get("title"), "AgenticOS")

        # Check colors are valid hex integers
        color_keys = ["black", "white", "brown", "blue"]
        for key in color_keys:
            self.assertIn(key, text_sec)
            val = text_sec.get(key)
            self.assertTrue(val.startswith("0x"), f"Color '{key}' should start with 0x: {val}")
            int(val, 16)  # Ensure valid hex int

    def test_grub_configuration(self):
        """Verify grub.cfg sets plymouth.theme=agenticos on kernel command line."""
        self.assertTrue(self.grub_cfg.is_file())
        content = self.grub_cfg.read_text(encoding="utf-8")
        self.assertIn("plymouth.theme=agenticos", content)
        self.assertIn("quiet splash", content)

    def test_build_script_stages_theme(self):
        """Verify build_iso.sh includes theme and daemon config staging."""
        self.assertTrue(self.build_script.is_file())
        content = self.build_script.read_text(encoding="utf-8")
        self.assertIn("agenticos.plymouth", content)
        self.assertIn("plymouthd.conf", content)
        self.assertIn("Theme=agenticos", content)


if __name__ == "__main__":
    unittest.main()
