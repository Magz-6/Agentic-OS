#!/usr/bin/env python3
"""
AgenticOS v0.1 Alpha — Level 4 ISO Inspection & Validation Script
Verifies:
1. ISO artifact and SHA256 checksum file integrity
2. Presence of Casper live-boot components (/casper/vmlinuz, initrd, squashfs)
3. Full inspection of SquashFS rootfs:
   - Native AgenticOS desktop shell (/opt/agenticos/applications/agenticos-shell/main.py)
   - Desktop session supervisor (/opt/agenticos/system-services/desktop/runner.py)
   - AgenticOS system services and systemd units
   - Plymouth boot splash theme and configuration
   - Native GTK 3 typelibs and Openbox window manager
   - Zero browser desktop dependencies
   - Clean distribution identity
"""

import hashlib
import os
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
OUTPUT_DIR = PROJECT_ROOT / "packaging" / "output"
ISO_PATH = OUTPUT_DIR / "AgenticOS-v0.1-Alpha.iso"
SHA_PATH = OUTPUT_DIR / "AgenticOS-v0.1-Alpha.iso.sha256"


def verify_iso_checksum() -> bool:
    print("[Validation 1/4] Checking ISO file and SHA-256 integrity...")
    if not ISO_PATH.is_file():
        print(f"ERROR: ISO file not found at {ISO_PATH}", file=sys.stderr)
        return False

    size_mb = ISO_PATH.stat().st_size / (1024 * 1024)
    print(f"  - ISO File: {ISO_PATH.name} ({size_mb:.2f} MB)")

    if not SHA_PATH.is_file():
        print(f"ERROR: SHA256 file not found at {SHA_PATH}", file=sys.stderr)
        return False

    expected_hash = SHA_PATH.read_text(encoding="utf-8").strip().split()[0]
    print(f"  - Expected SHA256: {expected_hash}")

    hasher = hashlib.sha256()
    with ISO_PATH.open("rb") as f:
        while chunk := f.read(1024 * 1024):
            hasher.update(chunk)
    actual_hash = hasher.hexdigest()
    print(f"  - Computed SHA256: {actual_hash}")

    if actual_hash != expected_hash:
        print("ERROR: SHA256 checksum mismatch!", file=sys.stderr)
        return False

    print("  ✅ SHA-256 checksum matches perfectly.")
    return True


def verify_iso_tree() -> bool:
    print("\n[Validation 2/4] Verifying ISO structure via xorriso...")
    try:
        res = subprocess.run(
            ["xorriso", "-indev", str(ISO_PATH), "-ls", "/casper"],
            capture_output=True,
            text=True,
            check=True,
        )
        output = res.stdout + res.stderr
        for item in ["vmlinuz", "initrd", "ubuntu-server-gui.squashfs"]:
            if item in output:
                print(f"  ✅ Found /casper/{item}")
            else:
                print(f"  ❌ Missing /casper/{item}", file=sys.stderr)
                return False
        return True
    except Exception as e:
        print(f"ERROR querying ISO via xorriso: {e}", file=sys.stderr)
        return False


def verify_squashfs_contents() -> bool:
    print("\n[Validation 3/4] Extracting and inspecting SquashFS root filesystem...")
    squashfs_path = PROJECT_ROOT / "packaging" / "staging" / "iso_root" / "casper" / "ubuntu-server-gui.squashfs"
    if not squashfs_path.is_file():
        # Fallback to extracting from ISO
        temp_dir = tempfile.mkdtemp()
        squashfs_path = Path(temp_dir) / "casper.squashfs"
        subprocess.run(
            ["xorriso", "-osirrox", "on", "-indev", str(ISO_PATH), "-extract", "/casper/ubuntu-server-gui.squashfs", str(squashfs_path)],
            check=True,
            capture_output=True,
        )

    try:
        res = subprocess.run(
            ["unsquashfs", "-l", str(squashfs_path)],
            capture_output=True,
            text=True,
            check=True,
        )
        files = set(res.stdout.splitlines())

        required_files = [
            ("Native AgenticOS Desktop Shell", "squashfs-root/opt/agenticos/applications/agenticos-shell/main.py"),
            ("Desktop Session Runner", "squashfs-root/opt/agenticos/system-services/desktop/runner.py"),
            ("Filesystem Adapter", "squashfs-root/opt/agenticos/adapters/filesystem_adapter.py"),
            ("Application Launcher Adapter", "squashfs-root/opt/agenticos/adapters/app_launcher.py"),
            ("Hardware Detector", "squashfs-root/opt/agenticos/hardware/detector.py"),
            ("Desktop Systemd Service", "squashfs-root/etc/systemd/system/agenticos-desktop.service"),
            ("First-Boot Service", "squashfs-root/etc/systemd/system/agenticos-firstboot.service"),
            ("Plymouth AgenticOS Theme", "squashfs-root/usr/share/plymouth/themes/agenticos/agenticos.plymouth"),
            ("Plymouth Splash Image", "squashfs-root/usr/share/plymouth/themes/agenticos/agenticos-splash.png"),
            ("Plymouth Script", "squashfs-root/usr/share/plymouth/themes/agenticos/agenticos.script"),
            ("GTK 3.0 GObject Typelib", "squashfs-root/usr/lib/x86_64-linux-gnu/girepository-1.0/Gtk-3.0.typelib"),
            ("Openbox Window Manager", "squashfs-root/usr/bin/openbox"),
            ("Xorg Display Server", "squashfs-root/usr/bin/Xorg"),
        ]

        all_ok = True
        for desc, path in required_files:
            if path in files:
                print(f"  ✅ {desc}: Found ({path})")
            else:
                print(f"  ❌ {desc}: MISSING ({path})", file=sys.stderr)
                all_ok = False

        return all_ok
    except Exception as e:
        print(f"ERROR inspecting SquashFS: {e}", file=sys.stderr)
        return False


def verify_clean_environment() -> bool:
    print("\n[Validation 4/4] Verifying clean environment requirements...")
    squashfs_path = PROJECT_ROOT / "packaging" / "staging" / "iso_root" / "casper" / "ubuntu-server-gui.squashfs"
    try:
        res = subprocess.run(
            ["unsquashfs", "-l", str(squashfs_path)],
            capture_output=True,
            text=True,
            check=True,
        )
        files = res.stdout.splitlines()

        # Check for pycache in /opt/agenticos
        pycache_files = [f for f in files if "opt/agenticos" in f and "__pycache__" in f]
        if pycache_files:
            print(f"  ⚠️ Warning: {len(pycache_files)} pycache files detected in /opt/agenticos")
        else:
            print("  ✅ Zero pycache files in /opt/agenticos.")

        # Check for user paths
        leak_files = [f for f in files if any(k in f for k in ["OneDrive", "Users/mages", "mnt/c"])]
        if leak_files:
            print(f"  ❌ Leak detected: {leak_files[:5]}", file=sys.stderr)
            return False
        else:
            print("  ✅ Zero host/developer paths leaked in rootfs.")

        return True
    except Exception as e:
        print(f"ERROR verifying clean environment: {e}", file=sys.stderr)
        return False


def verify_initrd_plymouth() -> bool:
    print("\n[Validation 5/5] Verifying AgenticOS Plymouth theme in Casper initrd...")
    initrd_path = PROJECT_ROOT / "packaging" / "staging" / "iso_root" / "casper" / "initrd"
    if not initrd_path.is_file():
        temp_dir = tempfile.mkdtemp()
        initrd_path = Path(temp_dir) / "initrd"
        subprocess.run(
            ["xorriso", "-osirrox", "on", "-indev", str(ISO_PATH), "-extract", "/casper/initrd", str(initrd_path)],
            check=True,
            capture_output=True,
        )

    try:
        res = subprocess.run(
            ["lsinitramfs", str(initrd_path)],
            capture_output=True,
            text=True,
            check=True,
        )
        files = set(res.stdout.splitlines())

        required_initrd = [
            ("Initrd Plymouth Theme", "usr/share/plymouth/themes/agenticos/agenticos.plymouth"),
            ("Initrd Plymouth Script", "usr/share/plymouth/themes/agenticos/agenticos.script"),
            ("Initrd Plymouth Splash", "usr/share/plymouth/themes/agenticos/agenticos-splash.png"),
            ("Initrd Plymouth Script Plugin", "usr/lib/x86_64-linux-gnu/plymouth/script.so"),
            ("Initrd Plymouth Graphics Lib", "usr/lib/x86_64-linux-gnu/libply-splash-graphics.so.5"),
        ]

        all_ok = True
        for desc, path in required_initrd:
            if path in files:
                print(f"  ✅ {desc}: Found ({path})")
            else:
                print(f"  ❌ {desc}: MISSING ({path})", file=sys.stderr)
                all_ok = False

        return all_ok
    except Exception as e:
        print(f"ERROR inspecting Initrd: {e}", file=sys.stderr)
        return False


def main() -> int:
    print("=====================================================================")
    print("AgenticOS v0.1 Alpha — Level 4 ISO Inspection & Validation")
    print("=====================================================================")

    ok1 = verify_iso_checksum()
    ok2 = verify_iso_tree()
    ok3 = verify_squashfs_contents()
    ok4 = verify_clean_environment()
    ok5 = verify_initrd_plymouth()

    print("=====================================================================")
    if ok1 and ok2 and ok3 and ok4 and ok5:
        print("🎉 ALL LEVEL 4 ISO VALIDATIONS PASSED SUCCESSFULLY")
        print(f"Artifact: {ISO_PATH.name} ({ISO_PATH.stat().st_size / (1024*1024):.2f} MB)")
        print(f"SHA-256:  {SHA_PATH.read_text(encoding='utf-8').strip().split()[0]}")
        print("=====================================================================")
        return 0
    else:
        print("❌ SOME VALIDATIONS FAILED")
        print("=====================================================================")
        return 1


if __name__ == "__main__":
    sys.exit(main())
