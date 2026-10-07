# AgenticOS v0.1 Alpha — Release Architecture & Linux OS Foundation

**Owner:** Magesh (Linux OS / ISO / Applications / System Services / Linux Integration Lead)  
**Distribution:** AgenticOS v0.1 Alpha  
**Base System:** Ubuntu 24.04.5 LTS (Noble Numbat)  
**Kernel:** Linux 6.8.0-139-generic x86_64  
**Date:** October 2026  

---

## 1. Operating System Declaration

> **Architectural Mandate:**  
> **"AgenticOS v0.1 Alpha is a Linux-based operating system distribution with a native graphical desktop and AgenticOS services."**

AgenticOS is **NOT** a browser-based application, localhost web page, or web wrapper. The graphical desktop is a **native Linux GUI application** written in GTK 3 (`applications/agenticos-shell/main.py`) running directly on top of the Xorg display server and Openbox window manager.

The prototype browser Prompt UI (`applications/prompt-ui/`) remains available strictly as a decoupled developer and prototype service, but **is NOT the operating system desktop**. Falkon, Chromium, and other web browsers have been removed from the primary desktop execution path.

---

## 2. System Architecture

```
                                USER
                                 │
                     NATIVE AGENTICOS DESKTOP
                                 │
         ┌───────────────────────┴───────────────────────┐
         │                                               │
   Linux Kernel                                 AgenticOS Services
         │                                               │
    Ubuntu Base                                  Agent Runtime*
         │                                       System Services
         │                                       Hardware Layer
         │                                       Native UI Shell
         │                                       Applications
         │                                               │
         └───────────────────────┬───────────────────────┘
                                 ↓
                     SYSTEM EXECUTION & HARDWARE
```
*\*External teammate dependencies adhere to defined integration boundaries.*

---

## 3. Native Graphical Desktop Stack

| Layer | Component | Implementation / Package | Ownership |
|---|---|---|---|
| **Display Server** | Xorg Display Server | `xorg`, `xserver-xorg-video-fbdev` | Magesh |
| **Window Manager** | Openbox | `/usr/bin/openbox-session`, `/usr/bin/openbox` | Magesh |
| **Native Shell** | AgenticOS Shell | `/opt/agenticos/applications/agenticos-shell/main.py` (GTK 3) | Magesh |
| **Session Runner** | Desktop Runner | `/opt/agenticos/system-services/desktop/runner.py` | Magesh |
| **System Service** | Desktop Service | `/etc/systemd/system/agenticos-desktop.service` | Magesh |
| **Theme / Styling** | AgenticOS Dark Theme | Custom CSS Provider (Slate/Cyan palette) | Magesh |

### Native Shell Capabilities (`applications/agenticos-shell/main.py`)
1. **AgenticOS Branding**: Persistent header with version badge, active regular user badge, and live system clock.
2. **Application Launcher**: Allowlisted application launcher cards for Terminal, File Manager, Text Editor, AI Goal Runtime, and System Inspector.
3. **Live Telemetry & Status**: Hostname, Kernel, Uptime, CPU core count and model, live RAM usage progress bar, and status of `agenticos-*` systemd services.
4. **Filesystem Workspace**: Integrated directory browser and safe "Create Project Folder" action for project workspaces.
5. **Controlled Power Management**: Safe confirmation dialogs triggering `systemctl reboot` and `systemctl poweroff` without arbitrary shell execution.
6. **Least Privilege**: Strictly executes as the unprivileged regular non-root user.

---

## 4. Boot Process & Plymouth Boot Splash

```
Firmware (BIOS / UEFI)
       ↓
    GRUB 2 (Hybrid El Torito / EFI ESP)
       ↓
  Linux Kernel (vmlinuz 6.8.0-139-generic)
       ↓
  Casper Live Environment (OverlayFS)
       ↓
AgenticOS Plymouth Splash (`Theme=agenticos`)
       ↓
   systemd (multi-user.target)
       ↓
AgenticOS First-Boot Service (`agenticos-firstboot.service`)
       ↓
   graphical.target
       ↓
AgenticOS Desktop Service (`agenticos-desktop.service`)
       ↓
   Xorg (:0, vt7)
       ↓
  Openbox Window Manager
       ↓
NATIVE AGENTICOS DESKTOP SHELL
```

### Plymouth Theme Configuration
- **Location**: `/usr/share/plymouth/themes/agenticos/`
- **Definition File**: `agenticos.plymouth` (`ModuleName=script`)
- **Splash Script**: `agenticos.script` (loads and centers splash image across screen resolutions)
- **Splash Image**: `agenticos-splash.png` (official AgenticOS branding)
- **Daemon Configuration**: `/etc/plymouth/plymouthd.conf` (`Theme=agenticos`, `ShowDelay=0`)
- **GRUB Integration**: Kernel parameter `plymouth.theme=agenticos quiet splash`

---

## 5. Magesh Adapter Framework

The AgenticOS adapter framework strictly rejects arbitrary command execution, `shell=True`, and path traversal.

```
                  BaseAdapter
                       │
       ┌───────────────┼───────────────┐
       ↓               ↓               ↓
ApplicationAdapter SystemAdapter FilesystemAdapter
       │               │               │
  AppLauncher     HardwareDetector Memory/Process
```

- **`BaseAdapter`**: Abstract adapter contract defining `name`, `supported_actions`, `validate()`, `is_retry_safe()`, and `execute()`.
- **`AdapterResult`**: Structured execution result with status codes (`SUCCESS`, `VALIDATION_ERROR`, `EXECUTION_ERROR`, `UNSUPPORTED_ACTION`), message, and payload data.
- **`AdapterRegistry` / `default_registry`**: Central registry for all adapter instances.
- **`ApplicationAdapter`**: Validates against an explicit allowlist (`browser`, `file_manager`, `terminal`, `text_editor`), inspects availability, resolves binaries, and launches approved Linux applications.
- **`SystemAdapter`**: Read-only queries for hostname, OS info, kernel release, uptime, and systemctl service status.
- **`FilesystemAdapter`**: Safe path inspection, directory enumeration, capacity queries, mount queries, and safe project directory creation. Blocks destructive actions (`delete`, `remove`, `unlink`, `format`, `rmdir`, `chmod`).

---

## 6. System Services Integration

All system services are installed via systemd templates during ISO packaging:
- **`agenticos-desktop.service`**: Supervised by `system-services/desktop/runner.py`, enabled at `graphical.target`, aliased to `display-manager.service`.
- **`agenticos-firstboot.service`**: Account provisioning wizard on initial boot.
- **`agenticos-telemetry.service`**: Background hardware and system metrics collector.
- **`agenticos-goal-runtime.service`**: Background runner for goal lifecycle orchestration.

---

## 7. ISO Build Pipeline & Packaging

- **Build Script**: `packaging/scripts/build_iso.sh`
- **Execution Mode**: Unprivileged user execution under `fakeroot`.
- **Target Selection**: `BUILD_TARGET=gui`
- **Staging Pipeline**:
  - Stage 1: Clean staging trees
  - Stage 2: Stage kernel (`vmlinuz`), initrd, and `ubuntu-server-gui.squashfs`
  - Stage 3: Unpack SquashFS, stage AgenticOS components to `/opt/agenticos`, integrate GTK 3 typelib packages, configure OS identity and systemd services, install Plymouth theme
  - Stage 4: Repack compressed SquashFS (`mksquashfs -comp xz`)
  - Stage 5: Assemble BIOS & UEFI hybrid GRUB bootloaders
  - Stage 6: Master hybrid ISO via `xorriso`
  - Stage 7: Generate SHA-256 integrity checksum

### Final ISO Release Artifacts
- **File Name**: `AgenticOS-v0.1-Alpha.iso`
- **File Size**: `693,319,680 bytes` (661.20 MiB / approximately 662 MB)
- **SHA-256 Checksum**: `c5be925ec8412fefebd620a32971d64b94017e19c369b0df8ea0be631d3ab86a`
- **Checksum File**: `AgenticOS-v0.1-Alpha.iso.sha256`

---

## 8. Verification & Test Results

The release satisfies all 6 validation levels:
- **Level 1 (Syntax)**: `python3 -m compileall` across all modules: **0 errors**.
- **Level 2 (Unit Tests)**: Full repository unit test discovery: **243 passed, 0 failures, 0 errors**.
- **Level 3 (Packaging)**: Clean staging directories verified.
- **Level 4 (ISO Inspection)**: `packaging/scripts/validate_iso.py` mounted and verified all required files in the SquashFS rootfs: **PASS**.
- **Level 5 (QEMU Boot)**: `packaging/scripts/test_qemu_boot.py` booted the ISO in QEMU, captured GRUB, Plymouth splash, and desktop states via QMP: **PASS**.
- **Level 6 (Regression)**: Full repository regression run: **243 passed, 0 regressions**.

---

## 9. Team Integration Boundaries

Components owned by teammates are maintained with clean, decoupled integration boundaries:
- **Vivek (Architecture & Goal/Workflow Runtime)**: Systemd service template `agenticos-goal-runtime.service` and runner in place.
- **Vishnu (AI/LLM & Intent Intelligence)**: Intent adapter boundaries exposed via `src/core/`.
- **Krithikesh (Agent Runtime, Bus & Capability)**: Capability adapter boundaries exposed via `adapters/`.
- **Vidhyuth (Kernel Intelligence & Adaptive Policy)**: Telemetry data stream provided via `hardware/detector.py` and `telemetry/collector.py`.
- **Lishanth (Governance, Security, QA)**: Security allowlists, least-privilege non-root execution, and read-only adapter contracts enforced across all Magesh modules.

Missing teammate runtime implementations remain designated:
`UNDEFINED / BLOCKED — external dependency`
