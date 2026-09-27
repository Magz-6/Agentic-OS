# AgenticOS v0.1 Alpha — Linux/OS Foundation & Phase 20 Integration Report

> **DOCUMENT TYPE:** Lead Integration & Handoff Report<br>
> **ENGINEERING LEAD:** Magesh (Linux / OS Lead — Layers 9, 10, 12, 13 & Packaging)<br>
> **TARGET MILESTONE:** 28 September 2026 (`AgenticOS-v0.1-Alpha.iso`)<br>
> **GIT BRANCH:** `magesh/linux-os-foundation`<br>
> **LATEST COMMIT:** `5f0bd90 feat(packaging): reproducible ISO build pipeline and QEMU boot validation`<br>
> **DATE:** 28 September 2026

---

## 1. Executive Summary

The Linux/OS foundation for AgenticOS v0.1 Alpha and the Phase 20 reproducible ISO packaging pipeline have been fully implemented, verified, and packaged on branch `magesh/linux-os-foundation`.

> **Integration Milestone Status:**<br>
> The Linux/OS foundation has been packaged into an AgenticOS v0.1 Alpha ISO and empirically boot-validated under QEMU BIOS and UEFI configurations.

*Note: In accordance with project governance, this milestone establishes virtualized boot and user-space foundation validation under QEMU; it does NOT claim bare-metal hardware compatibility, universal bootability, or production readiness.*

---

## 2. Magesh Scope & Ownership

In accordance with the project division of responsibilities, Magesh's technical domain encompasses:
* **Applications & Services Boundary:** Safe application launcher and desktop entry integration.
* **System Services (Layer 10):** Read-only adapters for processes, memory, and mounted filesystems.
* **Linux Integration & Health (Layer 12):** Service health inspection, status contracts, and systemd service templates.
* **Hardware Detection & Telemetry (Layers 11/13):** Dynamic CPU, memory, storage, and network telemetry collector and hardware detector.
* **Packaging & Virtual Machine Support (Phase 20):** Reproducible ISO generation, GRUB dual-bootloader configuration, and QEMU virtual machine validation.

*Ownership Boundary: AI agents, LLM runtime adapters, inter-agent message buses, and security policy engines belong to respective teammates (Krithikesh, Vishnu, Vivek, Vidhyuth, Lishanth) and are integrated as external consumers above this Linux foundation.*

---

## 3. Completed Components Summary

| Layer / Subsystem | Modules | Core Functionality | Verification Status |
| :--- | :--- | :--- | :---: |
| **Layer 9 (App Launcher)** | `adapters/app_launcher.py` | Shell-injection-safe application dispatch with strict allowlist enforcement | ✅ Unit tested |
| **Layer 10 (Process & Memory)** | `adapters/process_adapter.py`<br>`adapters/memory_adapter.py` | Read-only process enumeration, state extraction, and memory metric parsing via `/proc` | ✅ Unit tested |
| **Layer 10 (Filesystem Adapter)** | `adapters/filesystem_adapter.py` | Read-only mount table inspection (`/proc/mounts`) and disk space analysis | ✅ Unit tested |
| **Layer 11/13 (Hardware & Telemetry)** | `hardware/detector.py`<br>`telemetry/collector.py` | DMI/SMBIOS enumeration, CPU jiffies delta calculation, and live system telemetry | ✅ Unit tested |
| **Layer 12 (Service Health)** | `linux_integration/health.py` | Injection-safe service status inspection via `systemctl show --` | ✅ Unit tested |
| **Desktop Integration** | `packaging/desktop/` | FreeDesktop.org v1.5 compliant application specification | ✅ Validated |
| **Packaging & ISO Toolchain** | `packaging/scripts/build_iso.sh`<br>`packaging/scripts/verify_artifacts.sh`<br>`packaging/config/` | Unprivileged 7-stage ISO build pipeline using Candidate B (Ubuntu 24.04.5 LTS + Casper/OverlayFS) | ✅ Empirically Validated |

---

## 4. Validated ISO Artifact Metrics

The bootable ISO was assembled and empirically validated under QEMU:

* **Artifact Name:** `AgenticOS-v0.1-Alpha.iso`
* **Local Path:** `packaging/output/AgenticOS-v0.1-Alpha.iso`
* **File Size:** `246,796,288 bytes` (~246.8 MB / 235.36 MiB)
* **SHA256 Checksum:**
  ```text
  c64b9e1d1edd1760017a3647c6cdfebb87b43b47f9d9212411fdf503fdd69fc6
  ```
* **Git Tracking Policy:** Intentionally excluded from Git tracking via `.gitignore` to prevent multi-hundred-megabyte binary bloat in the repository.

---

## 5. Reproducible Build Instructions

The ISO build pipeline is 100% deterministic and runs completely unprivileged in standard Linux user space (zero `sudo` or root permissions required).

### Prerequisites
* Upstream base artifacts must already exist in `packaging/staging/`:
  - `vmlinuz` (Ubuntu 6.8.0-139-generic, 15,059,336 bytes)
  - `initrd` (Casper-enabled initrd, 78,777,934 bytes)
  - `ubuntu-server-minimal.squashfs` (SHA256: `bd1ce4815bb1988b171cc863b63ac367311af9a2f30c9b13a2ddddee7b89a5ea`)
* Standard packaging utilities: `xorriso`, `mksquashfs`, `unsquashfs`, `mtools`, `grub-mkimage`.

### Build Command
```bash
cd AgenticOS

# Optional pre-flight check of staged components:
bash packaging/scripts/verify_artifacts.sh

# Execute reproducible ISO assembly:
bash packaging/scripts/build_iso.sh
```

---

## 6. QEMU BIOS Boot Validation

The fresh ISO was boot-validated in BIOS mode under QEMU 8.2.2.

### Execution Command
```bash
qemu-system-x86_64 \
  -m 2048 \
  -cdrom packaging/output/AgenticOS-v0.1-Alpha.iso \
  -boot d \
  -nographic \
  -serial mon:stdio
```

### Captured Empirical Validation Telemetry
* **Kernel Initialization:** `Linux version 6.8.0-139-generic (buildd@lcy02-amd64-036) ... SMP PREEMPT_DYNAMIC`
* **Optical Medium Detection:** Casper matched optical drive `/dev/sr0` via `/.disk/casper-uuid-generic` matching `/conf/uuid.conf` (`50c98eb4-4c0f-4c1a-82d2-4234cf187d50`).
* **SquashFS Attachment:** `loop1: detected capacity change from 0 to 289568`
* **OverlayFS Activation:** `overlayfs: "xino" feature enabled using 3 upper inode bits.`
* **Userspace Initialization:** `systemd 255.4-1ubuntu8.17 running in system mode`
* **Hypervisor Detection:** `Detected virtualization qemu.`
* **System Banner:**
  ```text
  Welcome to Ubuntu 24.04.5 LTS!
  Hostname set to <agenticos>.
  ```
* **Payload Verification:** `/opt/agenticos` present inside live SquashFS (`adapters`, `hardware`, `telemetry`, `linux_integration`).

---

## 7. QEMU UEFI Boot Validation

The same fresh ISO was boot-validated under UEFI firmware using standard OVMF firmware (`/usr/share/ovmf/OVMF.fd` or `/usr/share/OVMF/OVMF_CODE.fd`).

### Execution Command
```bash
qemu-system-x86_64 \
  -m 2048 \
  -bios /usr/share/OVMF/OVMF_CODE.fd \
  -cdrom packaging/output/AgenticOS-v0.1-Alpha.iso \
  -boot d \
  -nographic \
  -serial mon:stdio
```

### Observed Evidence
* FAT ESP image (`/boot/grub/efi.img`) recognized by OVMF.
* GRUB EFI loader (`BOOTX64.EFI`) executed cleanly.
* Identical kernel, Casper medium matching, OverlayFS mounting, and `systemd 255.4` userspace boot state reached.
* **Status:** **UEFI boot validated under QEMU.**

---

## 8. Test Suite Verification Baseline

Executed strictly using standard library `unittest` (zero third-party dependencies required):

* **Linux Runtime (Ubuntu 24.04 LTS):**
  `75 / 75 passed (0.112s)` — Zero failures, zero errors.
* **Windows 11 Host:**
  `73 passed, 2 skipped (0.103s)` — The 2 intentional skips guard Linux-specific POSIX filesystem interfaces (`os.statvfs` error codes) when executed outside Linux.

---

## 9. Architecture & Safety Boundaries

Throughout development and packaging, strict governance boundaries were enforced:
1. **User-Space Operation:** 100% user-space design; zero custom kernel compilation, zero kernel patching, zero out-of-tree drivers.
2. **Least Privilege:** All adapters, build scripts, and inspection tools run unprivileged (zero `sudo`).
3. **Read-Only Inspection:** Adapters inspect `/proc` and `/sys` without system mutation.
4. **Service Governance Safeguards:** Systemd service templates exist as unlinked reference files under `/opt/agenticos/systemd/`. Automatic installation into `/etc/systemd/system/` is disabled by contract:
   ```bash
   INSTALL_SYSTEMD_SERVICE=0
   ENABLE_SYSTEMD_SERVICE=0
   ```

---

## 10. Known Limitations & Deferred Items

To maintain technical precision and avoid overclaiming:
* **Bare-Metal Hardware:** Bootability has been validated under QEMU virtualization; physical bare-metal hardware compatibility has **not** been tested.
* **Cross-Layer IPC/API Contracts:** Dataclasses currently provide internal representations; final serialization contracts await project-wide schema freeze.
* **Application Allowlist:** The launcher enforces a default development allowlist (`python3`, `bash`, `ls`, etc.); production allowlist configuration is deferred to the security lead.
* **Host Service Enablement:** System-wide daemon auto-start remains intentionally disabled pending lead review.

---

## 11. Team Handoff & Next Steps

Team members integrating with Magesh's Linux foundation should follow these steps:

1. **Checkout Branch:**
   ```bash
   git checkout magesh/linux-os-foundation
   ```
2. **Inspect Commit History:**
   Review commit `5f0bd90` for packaging and `344d64f` for user-space foundation.
3. **Run Unit Tests:**
   ```bash
   python3 -m unittest discover -s tests -v
   ```
4. **Build & Verify ISO:**
   Follow instructions in [Section 5](#5-reproducible-build-instructions) and [Section 6](#6-qemu-bios-boot-validation) to assemble and test the ISO.
5. **Consume User-Space Modules:**
   Import `telemetry.collector.SystemTelemetryCollector`, `hardware.detector.HardwareDetector`, and `adapters.process_adapter.ProcessAdapter` into higher-level agent runtime pipelines.
