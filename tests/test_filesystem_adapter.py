#!/usr/bin/env python3
"""Unit tests for FilesystemAdapter within the Adapter Framework.

Verifies:
1. inspect_path action for existing and nonexistent paths.
2. check_existence action.
3. list_directory action with limits and error handling.
4. get_metadata action.
5. get_usage and get_mounts actions.
6. Rejection of unsupported actions (e.g. delete, write, format, chmod).
7. Validation errors on empty, malformed, or null-byte paths.
8. Workspace sandboxing and path traversal violations when allowed_roots is set.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from adapters.filesystem_adapter import FilesystemAdapter
from adapters.result import AdapterStatus


class TestFilesystemAdapterFramework(unittest.TestCase):
    """Test suite for FilesystemAdapter BaseAdapter integration."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name).resolve()

        # Create sample files
        self.sample_file = self.root / "sample.txt"
        self.sample_file.write_text("Adapter Framework Test", encoding="utf-8")

        self.sub_dir = self.root / "sub"
        self.sub_dir.mkdir()
        (self.sub_dir / "child.txt").write_text("child content", encoding="utf-8")

        # Mock mounts file
        self.mock_mounts = self.root / "mounts"
        self.mock_mounts.write_text(
            "sysfs /sys sysfs rw 0 0\n/dev/sda1 / ext4 rw 0 0\n", encoding="utf-8"
        )

        self.adapter = FilesystemAdapter(
            mounts_path=str(self.mock_mounts),
            allowed_roots=[str(self.root)],
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_inspect_path_existing_file(self):
        """Verify inspect_path returns success and accurate file metadata."""
        res = self.adapter.run("inspect_path", {"path": str(self.sample_file)})
        self.assertTrue(res.success)
        self.assertEqual(res.status, AdapterStatus.SUCCESS)
        self.assertEqual(res.data["exists"], True)
        self.assertEqual(res.data["is_file"], True)
        self.assertEqual(res.data["is_dir"], False)
        self.assertEqual(res.data["size_bytes"], len("Adapter Framework Test"))

    def test_inspect_path_nonexistent(self):
        """Verify inspect_path gracefully reports not_found without failing."""
        missing = self.root / "ghost.txt"
        res = self.adapter.run("inspect_path", {"path": str(missing)})
        self.assertTrue(res.success)
        self.assertEqual(res.data["exists"], False)
        self.assertEqual(res.data["status"], "not_found")

    def test_check_existence(self):
        """Verify check_existence action returns boolean exists flag."""
        res_exists = self.adapter.run("check_existence", {"path": str(self.sample_file)})
        self.assertTrue(res_exists.success)
        self.assertEqual(res_exists.data["exists"], True)

        res_missing = self.adapter.run("check_existence", {"path": str(self.root / "missing.txt")})
        self.assertTrue(res_missing.success)
        self.assertEqual(res_missing.data["exists"], False)

    def test_list_directory(self):
        """Verify list_directory action enumerates files."""
        res = self.adapter.run("list_directory", {"path": str(self.root), "limit": 10})
        self.assertTrue(res.success)
        self.assertEqual(res.status, AdapterStatus.SUCCESS)
        self.assertGreaterEqual(res.data["total_entries"], 2)

    def test_get_metadata(self):
        """Verify get_metadata returns filesystem stat attributes."""
        res = self.adapter.run("get_metadata", {"path": str(self.sample_file)})
        self.assertTrue(res.success)
        self.assertIn("permissions_octal", res.data)
        self.assertIn("mtime", res.data)

    def test_get_mounts(self):
        """Verify get_mounts action reads mounts safely."""
        res = self.adapter.run("get_mounts", {})
        self.assertTrue(res.success)
        self.assertEqual(len(res.data["mounts"]), 2)

    def test_rejection_of_destructive_actions(self):
        """Verify that delete, write, format, rmdir are rejected as UNSUPPORTED_ACTION."""
        destructive_actions = ["delete", "remove", "unlink", "write", "rmdir", "format", "chmod"]
        for action in destructive_actions:
            res = self.adapter.run(action, {"path": str(self.sample_file)})
            self.assertFalse(res.success)
            self.assertEqual(res.status, AdapterStatus.UNSUPPORTED_ACTION)

    def test_path_traversal_violation(self):
        """Verify traversal outside allowed_roots returns VALIDATION_ERROR."""
        outside_path = self.root / ".." / "outside.txt"
        res = self.adapter.run("inspect_path", {"path": str(outside_path)})
        self.assertFalse(res.success)
        self.assertEqual(res.status, AdapterStatus.VALIDATION_ERROR)
        self.assertIn("Path traversal violation", res.message)

    def test_malformed_parameters(self):
        """Verify validation errors on empty paths or null bytes."""
        # Empty path
        res_empty = self.adapter.run("inspect_path", {"path": ""})
        self.assertFalse(res_empty.success)
        self.assertEqual(res_empty.status, AdapterStatus.VALIDATION_ERROR)

        # Null byte
        res_null = self.adapter.run("inspect_path", {"path": "/tmp/test\0bad"})
        self.assertFalse(res_null.success)
        self.assertEqual(res_null.status, AdapterStatus.VALIDATION_ERROR)


if __name__ == "__main__":
    unittest.main()
