"""Unit tests for AgenticOS graphical Plymouth boot splash theme and integration."""

import configparser
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestPlymouthTheme(unittest.TestCase):
    """Test suite validating AgenticOS graphical Plymouth theme structure and packaging."""

    def setUp(self):
        self.theme_dir = (
            PROJECT_ROOT
            / "linux_integration"
            / "plymouth"
            / "agenticos"
        )
        self.theme_file = self.theme_dir / "agenticos.plymouth"
        self.script_file = self.theme_dir / "agenticos.script"
        self.image_file = self.theme_dir / "agenticos-splash.png"
        self.grub_cfg = PROJECT_ROOT / "packaging" / "config" / "grub.cfg"
        self.build_script = PROJECT_ROOT / "packaging" / "scripts" / "build_iso.sh"

    def test_theme_file_exists(self):
        """Verify the agenticos.plymouth theme file exists."""
        self.assertTrue(
            self.theme_file.is_file(),
            f"Missing theme file: {self.theme_file}",
        )

    def test_script_file_exists(self):
        """Verify the graphical Plymouth script exists."""
        self.assertTrue(
            self.script_file.is_file(),
            f"Missing Plymouth script: {self.script_file}",
        )

    def test_splash_image_exists(self):
        """Verify the AgenticOS splash image exists."""
        self.assertTrue(
            self.image_file.is_file(),
            f"Missing splash image: {self.image_file}",
        )

    def test_theme_file_structure(self):
        """Verify theme file uses the Plymouth script engine."""
        config = configparser.ConfigParser()
        config.read(self.theme_file)

        self.assertIn("Plymouth Theme", config.sections())
        self.assertIn("script", config.sections())

        theme_sec = config["Plymouth Theme"]
        self.assertEqual(theme_sec.get("Name"), "AgenticOS")
        self.assertEqual(theme_sec.get("ModuleName"), "script")

        script_sec = config["script"]
        self.assertEqual(
            script_sec.get("ImageDir"),
            "/usr/share/plymouth/themes/agenticos",
        )
        self.assertEqual(
            script_sec.get("ScriptFile"),
            "/usr/share/plymouth/themes/agenticos/agenticos.script",
        )

    def test_script_content(self):
        """Verify the script loads and centers the AgenticOS splash image."""
        content = self.script_file.read_text(encoding="utf-8")

        self.assertIn('Image("agenticos-splash.png")', content)
        self.assertIn("Window.GetWidth()", content)
        self.assertIn("Window.GetHeight()", content)
        self.assertIn("Sprite(wallpaper)", content)
        self.assertIn("sprite.SetPosition(x, y, 0)", content)

    def test_grub_configuration(self):
        """Verify grub.cfg enables Plymouth and selects the AgenticOS theme."""
        self.assertTrue(self.grub_cfg.is_file())
        content = self.grub_cfg.read_text(encoding="utf-8")

        self.assertIn("plymouth.theme=agenticos", content)
        self.assertIn("quiet splash", content)

    def test_build_script_stages_graphical_theme(self):
        """Verify build_iso.sh stages all graphical Plymouth assets."""
        self.assertTrue(self.build_script.is_file())
        content = self.build_script.read_text(encoding="utf-8")

        self.assertIn("agenticos.plymouth", content)
        self.assertIn("agenticos.script", content)
        self.assertIn("agenticos-splash.png", content)
        self.assertIn("plymouthd.conf", content)
        self.assertIn("Theme=agenticos", content)

    def test_splash_image_format(self):
        """Verify the splash image has the expected PNG signature."""
        with self.image_file.open("rb") as image:
            signature = image.read(8)

        self.assertEqual(
            signature,
            b"\x89PNG\r\n\x1a\n",
            "AgenticOS splash image must be a valid PNG file.",
        )


if __name__ == "__main__":
    unittest.main()
