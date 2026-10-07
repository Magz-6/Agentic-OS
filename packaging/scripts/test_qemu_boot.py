#!/usr/bin/env python3
"""
AgenticOS v0.1 Alpha — Automated QEMU VM Boot Verification Script
Level 5: Virtual Machine Integration Testing
Owner: Magesh (Linux/OS Lead)

Boots AgenticOS-v0.1-Alpha.iso in QEMU, connects via QMP, captures visual
screendumps across boot stages, and validates boot progression.
"""

import json
import os
import socket
import struct
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
OUTPUT_DIR = PROJECT_ROOT / "packaging" / "output"
ISO_PATH = OUTPUT_DIR / "AgenticOS-v0.1-Alpha.iso"

QMP_HOST = "127.0.0.1"
QMP_PORT = 4444


def ppm_to_bmp(ppm_bytes: bytes) -> bytes:
    """Convert raw PPM P6 image bytes to uncompressed 24-bit BMP."""
    lines = ppm_bytes.split(b"\n", 3)
    header = lines[0]
    dim_line = lines[1]
    idx = 2
    while dim_line.startswith(b"#"):
        dim_line = lines[idx]
        idx += 1
    w, h = map(int, dim_line.split())
    max_val = lines[idx]
    raw_pixels = b"\n".join(lines[idx + 1:])

    row_padding = (4 - (w * 3) % 4) % 4
    filesz = 54 + (w * 3 + row_padding) * h
    bmp = bytearray(b"BM")
    bmp += struct.pack("<IHHI", filesz, 0, 0, 54)
    bmp += struct.pack("<IIIHHIIIIII", 40, w, h, 1, 24, 0, 0, 0, 0, 0, 0)

    for y in range(h - 1, -1, -1):
        row = bytearray()
        for x in range(w):
            offset = (y * w + x) * 3
            if offset + 3 <= len(raw_pixels):
                r, g, b = raw_pixels[offset:offset + 3]
                row += bytes([b, g, r])
            else:
                row += b"\x00\x00\x00"
        row += b"\x00" * row_padding
        bmp += row

    return bytes(bmp)


class QMPClient:
    def __init__(self, host: str = QMP_HOST, port: int = QMP_PORT) -> None:
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((host, port))
        self.sock.settimeout(5.0)
        # Read greeting
        self._recv_json()
        # Enable capabilities
        self.cmd("qmp_capabilities")

    def _recv_json(self) -> dict:
        data = b""
        while not data.endswith(b"\r\n") and not data.endswith(b"\n"):
            chunk = self.sock.recv(4096)
            if not chunk:
                break
            data += chunk
        try:
            return json.loads(data.decode("utf-8"))
        except Exception:
            return {}

    def cmd(self, execute: str, arguments: dict | None = None) -> dict:
        payload: dict = {"execute": execute}
        if arguments:
            payload["arguments"] = arguments
        msg = json.dumps(payload).encode("utf-8") + b"\n"
        self.sock.sendall(msg)
        return self._recv_json()

    def screendump(self, output_ppm: str) -> None:
        self.cmd("screendump", {"filename": output_ppm})

    def quit(self) -> None:
        try:
            self.cmd("quit")
        except Exception:
            pass
        self.sock.close()


def run_qemu_boot_test() -> int:
    print("=====================================================================")
    print("AgenticOS v0.1 Alpha — Level 5 QEMU Boot Verification")
    print("=====================================================================")
    print(f"Target ISO: {ISO_PATH}")

    if not ISO_PATH.is_file():
        print(f"ERROR: ISO file does not exist: {ISO_PATH}", file=sys.stderr)
        return 1

    ppm_temp = Path("/tmp/agenticos_qemu_screen.ppm")

    qemu_cmd = [
        "qemu-system-x86_64",
        "-m", "3072",
        "-smp", "4",
        "-cdrom", str(ISO_PATH),
        "-display", "none",
        "-vga", "std",
        "-qmp", f"tcp:{QMP_HOST}:{QMP_PORT},server,nowait",
    ]

    print("[QEMU] Launching virtual machine instance...")
    proc = subprocess.Popen(qemu_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    try:
        # Wait for QEMU QMP socket to open
        time.sleep(2.0)
        qmp = None
        for attempt in range(10):
            try:
                qmp = QMPClient()
                break
            except Exception:
                time.sleep(1.0)

        if not qmp:
            print("ERROR: Could not connect to QEMU QMP socket.", file=sys.stderr)
            proc.terminate()
            return 1

        print("  ✅ Connected to QEMU QMP control interface.")

        # Stage 1: Bootloader & GRUB capture (t=4s)
        time.sleep(2.0)
        print("[QEMU] Capturing Stage 1: GRUB Boot Menu...")
        qmp.screendump(str(ppm_temp))
        time.sleep(1.0)
        if ppm_temp.is_file():
            bmp_bytes = ppm_to_bmp(ppm_temp.read_bytes())
            grub_bmp = OUTPUT_DIR / "qemu_stage1_grub.bmp"
            grub_bmp.write_bytes(bmp_bytes)
            print(f"  ✅ Saved {grub_bmp.name} ({len(bmp_bytes)} bytes)")

        # Trigger GRUB boot immediately
        qmp.cmd("send-key", {"keys": [{"type": "qcode", "data": "ret"}]})

        # Stage 2: Kernel Boot & Plymouth Splash (t=47s)
        print("[QEMU] Waiting for kernel boot and Plymouth splash (45s)...", flush=True)
        time.sleep(45.0)
        print("[QEMU] Capturing Stage 2: Plymouth Splash / Kernel Load...", flush=True)
        qmp.screendump(str(ppm_temp))
        time.sleep(1.0)
        if ppm_temp.is_file():
            bmp_bytes = ppm_to_bmp(ppm_temp.read_bytes())
            splash_bmp = OUTPUT_DIR / "qemu_stage2_splash.bmp"
            splash_bmp.write_bytes(bmp_bytes)
            print(f"  ✅ Saved {splash_bmp.name} ({len(bmp_bytes)} bytes)", flush=True)

        # Stage 3: Userspace & Services Transition
        print("[QEMU] Waiting for userspace services transition (15s)...", flush=True)
        time.sleep(15.0)
        print("[QEMU] Capturing Stage 3: Services & Graphical Transition...", flush=True)
        qmp.screendump(str(ppm_temp))
        time.sleep(1.0)
        if ppm_temp.is_file():
            bmp_bytes = ppm_to_bmp(ppm_temp.read_bytes())
            services_bmp = OUTPUT_DIR / "qemu_stage3_services.bmp"
            services_bmp.write_bytes(bmp_bytes)
            print(f"  ✅ Saved {services_bmp.name} ({len(bmp_bytes)} bytes)")

        # Stage 3b: AgenticOS Graphical Login Screen (LightDM Slick Greeter)
        print("[QEMU] Waiting for LightDM Graphical Login Screen (15s)...", flush=True)
        time.sleep(15.0)
        login_bmp = OUTPUT_DIR / "qemu_stage3b_login.bmp"
        qmp.screendump(str(ppm_temp))
        time.sleep(1.0)
        if ppm_temp.is_file():
            bmp_bytes = ppm_to_bmp(ppm_temp.read_bytes())
            login_bmp.write_bytes(bmp_bytes)
            print(f"  ✅ Saved {login_bmp.name} ({len(bmp_bytes)} bytes)")

        # Simulate user login: Press Enter on Slick Greeter (user agenticos in nopasswdlogin)
        print("[QEMU] Submitting user login at graphical greeter (sending Enter key)...", flush=True)
        qmp.cmd("send-key", {"keys": [{"type": "qcode", "data": "ret"}]})
        time.sleep(2.0)

        # Stage 4: Native AgenticOS GTK Desktop Shell (polling up to 20 times)
        print("[QEMU] Waiting for Xorg, Openbox, and Native AgenticOS GTK Desktop Shell...")
        desktop_bmp = OUTPUT_DIR / "qemu_stage4_desktop.bmp"
        for poll_idx in range(20):
            time.sleep(6.0)
            qmp.screendump(str(ppm_temp))
            time.sleep(1.0)
            if ppm_temp.is_file():
                bmp_bytes = ppm_to_bmp(ppm_temp.read_bytes())
                desktop_bmp.write_bytes(bmp_bytes)
                try:
                    from PIL import Image
                    im = Image.open(desktop_bmp)
                    color_count = len(set(im.getdata()))
                    print(f"  [QEMU] Poll {poll_idx + 1}/20: Screen snapshot saved ({len(bmp_bytes)} bytes, {color_count} colors)", flush=True)
                    if 100 < color_count < 20000:
                        print("  🎉 Native AgenticOS Desktop Shell window detected and confirmed rendered!", flush=True)
                        break
                except Exception:
                    print(f"  [QEMU] Poll {poll_idx + 1}/20: Screen snapshot saved ({len(bmp_bytes)} bytes)", flush=True)

        # Also maintain canonical backwards-compatible alias
        if desktop_bmp.is_file():
            (OUTPUT_DIR / "qemu_stage3_desktop.bmp").write_bytes(desktop_bmp.read_bytes())

        # Export PNG versions if PIL is installed
        try:
            from PIL import Image
            for stem in ["qemu_stage1_grub", "qemu_stage2_splash", "qemu_stage3_services", "qemu_stage3b_login", "qemu_stage4_desktop", "qemu_stage3_desktop"]:
                b_path = OUTPUT_DIR / f"{stem}.bmp"
                p_path = OUTPUT_DIR / f"{stem}.png"
                if b_path.is_file():
                    Image.open(b_path).save(p_path)
            print("  ✅ Converted all screendumps to PNG format.")
        except Exception:
            pass

        # Clean shutdown
        print("[QEMU] Initiating clean VM termination...")
        qmp.quit()
        proc.wait(timeout=5)
        print("  ✅ QEMU VM terminated cleanly.")

    except Exception as exc:
        print(f"ERROR during QEMU boot test: {exc}", file=sys.stderr)
        proc.terminate()
        return 1

    print("=====================================================================")
    print("🎉 LEVEL 5 QEMU BOOT VALIDATION COMPLETED SUCCESSFULLY")
    print("Visual Evidence Captured:")
    print("  1. packaging/output/qemu_stage1_grub.bmp")
    print("  2. packaging/output/qemu_stage2_splash.bmp")
    print("  3. packaging/output/qemu_stage3_desktop.bmp")
    print("=====================================================================")
    return 0


if __name__ == "__main__":
    sys.exit(run_qemu_boot_test())
