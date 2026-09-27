#!/usr/bin/env python3
"""
Unit tests for AgenticOS Packaging and Virtual Machine specification.

Verifies:
1. Existence and readability of packaging documentation.
2. Explicit documentation answering:
   "What exactly must the final AgenticOS bootable/installable artifact contain,
    and what is the approved build path?"
3. Clear status declaration that standalone ISO creation is NOT YET IMPLEMENTED / BLOCKED.
4. Completeness of VM profile recommendations (CPU, RAM, Disk, QEMU parameters).
5. Safety check: no destructive automation scripts or partition format commands present.
"""

import os
import unittest

PACKAGE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "packaging"))
README_FILE = os.path.join(PACKAGE_DIR, "README.md")


class TestPackagingSpecification(unittest.TestCase):
    """Test suite for packaging and VM proposal documentation."""

    def test_packaging_readme_exists(self):
        """Verify that packaging/README.md exists and is readable."""
        self.assertTrue(os.path.exists(README_FILE), f"Missing {README_FILE}")
        self.assertTrue(os.path.isfile(README_FILE), f"{README_FILE} is not a regular file")
        with open(README_FILE, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertGreater(len(content), 200, "packaging/README.md is unexpectedly empty or short")

    def test_core_architectural_question_addressed(self):
        """Verify that the core architectural question is explicitly addressed."""
        with open(README_FILE, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("What exactly must the final AgenticOS bootable/installable artifact contain", content)
        self.assertIn("what is the approved build path?", content)

    def test_status_marked_not_yet_implemented(self):
        """Safety assertion: verify ISO generation is marked as NOT YET IMPLEMENTED / BLOCKED."""
        with open(README_FILE, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("NOT YET IMPLEMENTED", content)
        self.assertIn("UNDEFINED / BLOCKED", content)

    def test_artifact_and_vm_specifications_present(self):
        """Verify artifact name, candidate options, and VM specs are thoroughly detailed."""
        with open(README_FILE, "r", encoding="utf-8") as f:
            content = f.read()
        # Artifact details
        self.assertIn("AgenticOS-v0.1-Alpha.iso", content)
        self.assertIn("systemd", content)
        self.assertIn("agenticos-telemetry.service", content)

        # Candidate build options
        self.assertIn("Option A", content)
        self.assertIn("Option B", content)

        # VM specifications
        self.assertIn("vCPUs", content)
        self.assertIn("RAM", content)
        self.assertIn("qemu-system-x86_64", content)

    def test_prohibition_of_destructive_packaging_scripts(self):
        """Safety check: ensure no raw destructive scripts exist in the packaging directory."""
        dangerous_terms = [b"mkfs", b"dd if=", b"fdisk", b"parted", b"rm -rf /"]
        for entry in os.listdir(PACKAGE_DIR):
            entry_path = os.path.join(PACKAGE_DIR, entry)
            if os.path.isfile(entry_path) and not entry.endswith(".md"):
                # If non-markdown files are created, check for dangerous commands
                with open(entry_path, "rb") as f:
                    file_bytes = f.read()
                for term in dangerous_terms:
                    self.assertNotIn(term, file_bytes, f"Dangerous command found in {entry_path}: {term}")


if __name__ == "__main__":
    unittest.main()
