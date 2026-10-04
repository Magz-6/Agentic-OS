# AgenticOS — Plymouth Boot Splash Integration

## Overview
- **Owner**: Magesh (Linux Integration & System Services Lead)
- **Status**: Implemented (Phase 11)
- **Engine**: `ubuntu-text` (built into base Ubuntu Server Minimal distribution)
- **Theme Name**: `agenticos`

---

## 1. Engine & Design Rationale
The `agenticos` Plymouth theme leverages the built-in `ubuntu-text` rendering module:
- **Zero Graphical Overhead**: Does not require Xorg, Wayland, or heavy desktop graphics libraries.
- **Universal Compatibility**: Renders reliably across standard Linux framebuffers (DRM/KMS) and text consoles in VirtualBox and bare-metal environments.
- **Branding**:
  - `title`: `AgenticOS` (replaces `Ubuntu 24.04`)
  - `black`: `0x0a0e14` (deep midnight background)
  - `white`: `0xffffff` (crisp white title text)
  - `brown`: `0x00bcd4` (bright cyan active progress dots)
  - `blue`: `0x0097a7` (muted teal inactive progress dots)

---

## 2. File Layout
Inside the target root filesystem:
```
/usr/share/plymouth/themes/agenticos/agenticos.plymouth
/etc/plymouth/plymouthd.conf
/usr/share/plymouth/themes/default.plymouth -> /usr/share/plymouth/themes/agenticos/agenticos.plymouth
/etc/alternatives/text.plymouth -> /usr/share/plymouth/themes/agenticos/agenticos.plymouth
```

---

## 3. Kernel Command Line
Configured in GRUB (`/boot/grub/grub.cfg`):
```grub
linux /casper/vmlinuz boot=casper layerfs-path=ubuntu-server-minimal.squashfs quiet splash plymouth.theme=agenticos ---
```
This forces Plymouth to select `agenticos` at the earliest stage of user-space initialization.
