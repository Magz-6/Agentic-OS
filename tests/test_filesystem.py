"""
AgenticOS - Filesystem Adapter Unit Tests
Layer 10: System Services (Filesystem Management Boundary)
Owner: Magesh (Linux/OS Lead)

Uses Python standard library `unittest` with temporary sandboxes to guarantee
safe, repeatable testing without root privileges or system modifications.
"""

import os
import tempfile
import unittest
from pathlib import Path

import adapters.filesystem_adapter


class TestFilesystemAdapter(unittest.TestCase):
    """Test suite for FilesystemAdapter."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.mounts_mock = self.root / "mock_mounts"
        self.adapter = adapters.filesystem_adapter.FilesystemAdapter(mounts_path=str(self.mounts_mock))

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_inspect_regular_file(self) -> None:
        """Verify inspection of a normal file (existence, size, mtime, permissions)."""
        test_file = self.root / "sample.txt"
        test_file.write_text("Hello AgenticOS", encoding="utf-8")

        info = self.adapter.inspect_path(test_file)
        self.assertTrue(info["exists"])
        self.assertTrue(info["is_file"])
        self.assertFalse(info["is_dir"])
        self.assertFalse(info["is_symlink"])
        self.assertEqual(info["size_bytes"], len("Hello AgenticOS"))
        self.assertIsNotNone(info["permissions_octal"])
        self.assertEqual(info["status"], "ok")

    def test_inspect_directory_and_nested_structure(self) -> None:
        """Verify inspection of directory paths and nested subdirectories."""
        nested = self.root / "a" / "b" / "c"
        nested.mkdir(parents=True)

        info = self.adapter.inspect_path(nested)
        self.assertTrue(info["exists"])
        self.assertFalse(info["is_file"])
        self.assertTrue(info["is_dir"])
        self.assertFalse(info["is_symlink"])
        self.assertEqual(info["status"], "ok")

    def test_inspect_missing_path(self) -> None:
        """Ensure non-existent paths return status 'not_found' gracefully."""
        missing = self.root / "does_not_exist.txt"
        info = self.adapter.inspect_path(missing)

        self.assertFalse(info["exists"])
        self.assertFalse(info["is_file"])
        self.assertFalse(info["is_dir"])
        self.assertEqual(info["status"], "not_found")

    def test_inspect_valid_symlink(self) -> None:
        """Verify detection of valid symlinks and resolution to target."""
        target_file = self.root / "target.txt"
        target_file.write_text("Target Data", encoding="utf-8")
        link = self.root / "link_to_target.txt"

        try:
            link.symlink_to(target_file)
        except OSError:
            # If symlink creation is not permitted on host, skip test
            self.skipTest("Symlinks not permitted on this host environment")

        info = self.adapter.inspect_path(link)
        self.assertTrue(info["exists"])
        self.assertTrue(info["is_symlink"])
        self.assertFalse(info["is_broken_symlink"])
        self.assertEqual(info["status"], "ok")
        self.assertIsNotNone(info["symlink_target"])

    def test_inspect_broken_symlink(self) -> None:
        """Verify safe handling of broken symlinks without crashing."""
        nonexistent_target = self.root / "ghost_file.txt"
        broken_link = self.root / "broken_link.txt"

        try:
            broken_link.symlink_to(nonexistent_target)
        except OSError:
            self.skipTest("Symlinks not permitted on this host environment")

        info = self.adapter.inspect_path(broken_link)
        self.assertFalse(info["exists"])
        self.assertTrue(info["is_symlink"])
        self.assertTrue(info["is_broken_symlink"])
        self.assertEqual(info["status"], "broken_symlink")

    def test_list_directory_normal_and_empty(self) -> None:
        """Verify listing entries in populated and empty directories."""
        empty_dir = self.root / "empty"
        empty_dir.mkdir()
        res_empty = self.adapter.list_directory(empty_dir)
        self.assertEqual(res_empty["status"], "ok")
        self.assertEqual(res_empty["total_entries"], 0)
        self.assertEqual(res_empty["entries"], [])

        # Populated directory
        (empty_dir / "f1.txt").write_text("1", encoding="utf-8")
        (empty_dir / "f2.txt").write_text("22", encoding="utf-8")
        (empty_dir / "sub").mkdir()

        res_populated = self.adapter.list_directory(empty_dir)
        self.assertEqual(res_populated["status"], "ok")
        self.assertEqual(res_populated["total_entries"], 3)
        names = {e["name"] for e in res_populated["entries"]}
        self.assertEqual(names, {"f1.txt", "f2.txt", "sub"})

    def test_list_directory_errors(self) -> None:
        """Verify handling of missing directory or calling list on a file."""
        res_missing = self.adapter.list_directory(self.root / "absent")
        self.assertEqual(res_missing["status"], "not_found")

        a_file = self.root / "a_file.txt"
        a_file.write_text("data", encoding="utf-8")
        res_file = self.adapter.list_directory(a_file)
        self.assertEqual(res_file["status"], "not_a_directory")

    def test_get_usage_valid_and_invalid(self) -> None:
        """Verify storage capacity and usage query via statvfs."""
        usage = self.adapter.get_usage(str(self.root))
        # Should return available with non-zero storage capacity
        self.assertIn(usage["status"], ("available", "unavailable"))
        if usage["status"] == "available":
            self.assertGreater(usage["total_bytes"], 0)
            self.assertGreaterEqual(usage["free_bytes"], 0)
            self.assertGreaterEqual(usage["usage_percent"], 0.0)

        # Invalid path
        usage_bad = self.adapter.get_usage("/non/existent/path/for/sure/12345")
        self.assertEqual(usage_bad["status"], "unavailable")

    def test_get_mounts_parsing(self) -> None:
        """Verify parsing of Linux /proc/mounts format."""
        mock_content = """sysfs /sys sysfs rw,nosuid,nodev,noexec,relatime 0 0
proc /proc proc rw,nosuid,nodev,noexec,relatime 0 0
/dev/sdd / ext4 rw,relatime,discard,errors=remount-ro,data=ordered 0 0
/dev/sda /mnt/c 9p ro,noatime,dirsync,aname=drvfs;path=C: 0 0
"""
        self.mounts_mock.write_text(mock_content, encoding="utf-8")
        mounts = self.adapter.get_mounts()

        self.assertEqual(len(mounts), 4)
        root_mount = next(m for m in mounts if m["mountpoint"] == "/")
        self.assertEqual(root_mount["device"], "/dev/sdd")
        self.assertEqual(root_mount["fstype"], "ext4")
        self.assertFalse(root_mount["is_read_only"])

        c_mount = next(m for m in mounts if m["mountpoint"] == "/mnt/c")
        self.assertTrue(c_mount["is_read_only"])

    def test_prohibition_of_destructive_filesystem_methods(self) -> None:
        """
        Security verification: verify that FilesystemAdapter strictly lacks
        any file creation, modification, deletion, formatting, or execution methods.
        """
        forbidden_methods = [
            "delete",
            "remove",
            "unlink",
            "rmdir",
            "write",
            "create",
            "touch",
            "chmod",
            "chown",
            "mkdir",
            "move",
            "rename",
            "copy",
            "truncate",
            "mount",
            "umount",
            "format",
            "mkfs",
            "dd",
            "execute_file",
        ]
        for method in forbidden_methods:
            self.assertFalse(
                hasattr(self.adapter, method),
                f"Security violation: FilesystemAdapter must not implement '{method}'",
            )


if __name__ == "__main__":
    unittest.main()
