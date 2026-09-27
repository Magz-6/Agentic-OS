# AgenticOS — Virtual Machine & Packaging Specification

> **DOCUMENT STATUS:** ISO boot validated under QEMU; reproducible build codification in progress.<br>
> **MAINTAINER:** Magesh (Linux / OS Lead)<br>
> **MILESTONE TARGET:** 28 September 2026 (`AgenticOS-v0.1-Alpha.iso`)<br>
> **DATE:** 28 September 2026

---

## 1. Executive Summary & Core Architectural Question

> ### Core Architectural Question:
> **What exactly must the final AgenticOS bootable/installable artifact contain, and what is the approved build path?**

In the master architecture plan (`AgenticOS_Architecture_Target_Employee_Daily_Plan_27Sep_15Oct.docx`), the milestone target for 28 September 2026 specifies:
* **Deliverable:** "first branded bootable ISO + systemd services".
* **Verification Criterion:** "Clean ISO boots; core services start; telemetry returns valid data. Fresh VM boot/install + vertical E2E + smoke suite PASS."

This document establishes the virtual machine hardware profiles, QEMU configuration, verified packaging pathway (Candidate B), firmware requirements, Casper live-boot requirements, and empirical boot validation results.

> ### ⚠️ MANDATORY DEPLOYMENT BOUNDARY:
> **ISO boot validation has been achieved under QEMU virtualization; physical bare-metal hardware compatibility and bare-metal disk installation remain UNTESTED.**<br>
> Current Phase 20 deliverables provide the **Layer 10/12 Linux user-space foundation, virtual machine specifications, reproducible ISO packaging toolchain, and QEMU boot validation**. Service units remain uninstalled into `/etc/systemd/system` (`INSTALL_SYSTEMD_SERVICE=0`, `ENABLE_SYSTEMD_SERVICE=0`).

---

## 2. Target Virtual Machine Hardware Profile

To evaluate the integrated AgenticOS stack in a clean, reproducible virtualized environment (such as QEMU, VirtualBox, or UTM), the following baseline hardware profile is specified:

| Hardware Resource | Minimum Specification | Recommended Specification | Virtual Emulation Model |
| :--- | :--- | :--- | :--- |
| **Architecture** | `x86_64` (AMD64) | `x86_64` (AMD64) | Standard x86_64 Q35 chipset |
| **Processor (vCPUs)**| 2 vCPUs | 4 vCPUs | Host pass-through (`-cpu host`) or QEMU `max` |
| **System Memory (RAM)**| 2048 MB (2 GB) | 4096 MB (4 GB) | VirtIO balloon driver support |
| **Virtual Storage** | 20 GB dynamic disk | 40 GB dynamic disk | VirtIO Block (`virtio-blk-pci`) or NVMe |
| **Firmware** | Legacy BIOS (SeaBIOS) | UEFI (OVMF x86_64) | OVMF with standard UEFI NVRAM |
| **Network Interface**| User-mode NAT | User-mode NAT with port forwarding | `virtio-net-pci` or Intel `e1000` |
| **Graphics / Display**| Standard VGA (1024x768) | VirtIO-GPU with 3D acceleration | `virtio-vga` or `virtio-gpu-pci` |

---

## 3. QEMU Execution Reference (Empirically Verified Commands)

QEMU 8.2.2 is available within the Ubuntu WSL2 runtime (`/usr/bin/qemu-system-x86_64`), and QEMU 8.x is installed on the Windows host (`C:\Program Files\qemu`). 

The assembled `AgenticOS-v0.1-Alpha.iso` was verified using the following standardized, unprivileged QEMU invocations:

```bash
# BIOS (El Torito / i386-pc) Boot Validation:
qemu-system-x86_64 \
  -m 2048 \
  -cdrom packaging/output/AgenticOS-v0.1-Alpha.iso \
  -boot d \
  -nographic \
  -serial mon:stdio

# UEFI (x86_64-efi via OVMF) Boot Validation:
qemu-system-x86_64 \
  -m 2048 \
  -bios /usr/share/OVMF/OVMF_CODE.fd \
  -cdrom packaging/output/AgenticOS-v0.1-Alpha.iso \
  -boot d \
  -nographic \
  -serial mon:stdio
```

---

## 4. Target Artifact Requirements (from Master Plan)

According to the master architecture document, the final bootable release artifact satisfies:

1. **Artifact Filename:** `AgenticOS-v0.1-Alpha.iso`.
2. **Format:** Hybrid ISO 9660 / UDF image bootable directly from USB flash drives or VM optical drives with dual UEFI and legacy BIOS El Torito support.
3. **Core Operating System Runtime:**
   * Standard Linux LTS kernel (Ubuntu stock `6.8.0-139-generic`).
   * Systemd init system functioning as PID 1 (`systemd 255.4`).
   * Standard POSIX libraries (glibc) and Python 3.12+ runtime environment.
4. **AgenticOS Stack Components:**
   * Pre-configured systemd service (`agenticos-telemetry.service`).
   * Hardware detection (`hardware/detector.py`) and telemetry (`telemetry/collector.py`).
   * Safe user-space adapters (`adapters/`).
   * Service health inspector (`linux_integration/health.py`).
   * Agentic Core, Runtime, LLM adapter, and UI shell (Layers 1–8, 11).
5. **Session Policy:**
   * Automatic boot to a designated unprivileged system user (`agenticos`).
   * Live ephemeral session with RAM copy-on-write overlay, preventing unintentional modification to physical host storage.

---

## 5. Candidate Build Pathways Evaluation & Selection

| Candidate Build Pathway | Mechanism | Advantages | Constraints & Blockers | Evaluation Status |
| :--- | :--- | :--- | :--- | :--- |
| **Option A: Ubuntu Live Build (`live-build` / `casper`)** | Generates an ephemeral live squashfs filesystem with Ubuntu packages and casper boot scripts. | Standardized live-boot workflow; ephemeral RAM overlay; ideal for demonstration. | Requires root (`sudo`), host kernel loop devices (`/dev/loop*`), and heavy package downloads. May encounter WSL2-specific limitations. | Evaluated; unselected. |
| **Option B: Live Server Remaster (`xorriso` + custom GRUB)** | Extracts official Ubuntu 24.04.5 Live Server kernel, initrd, and minimal rootfs; packages custom GRUB and OverlayFS. | 100% reproducible; unprivileged user-space build (zero `sudo`); compact footprint (~235 MiB); dual BIOS/UEFI boot. | Requires explicit Casper layer redirection and UUID matching. | **SELECTED & IMPLEMENTED (Candidate B)** |
| **Option C: Debootstrap + Custom GRUB** | Bootstraps a minimal Debian/Ubuntu rootfs, creates squashfs, and manually configures GRUB bootloader. | Minimal image size (< 400 MB); zero extraneous packages. | Extremely high maintenance; complex manual EFI/initramfs assembly. | Evaluated; unselected. |
| **Option D: Pre-Built VM Disk Image (`.qcow2` / `.vhdx`)** | Builds a direct virtual disk image using `qemu-img` or Packer. | Boots in seconds in QEMU; bypasses complex ISO installer squashing. | Does not satisfy the strict `.iso` delivery format specified in the 28 September milestone. | Supplemental developer artifact only. |

---

## 6. Verified Upstream Components & Casper Requirements

### Verified Upstream Release Components
* **Ubuntu Release:** Ubuntu 24.04.5 LTS (Noble Numbat) Live Server media (`ubuntu-24.04.5-live-server-amd64.iso`, SHA256: `97f3d7ffb032c3eb3b23d2c8be9cc76e60c2c1f2c0146ba5ba9fe01cafae0fd8`).
* **Kernel:** Ubuntu generic kernel `6.8.0-139-generic` (`vmlinuz`, 15,059,336 bytes).
* **Initramfs:** Casper-enabled `initrd` (78,777,934 bytes, zstd-compressed cpio containing 50 Casper hook scripts).
* **Base SquashFS:** `ubuntu-server-minimal.squashfs` (166,932,480 bytes, SHA256: `bd1ce4815bb1988b171cc863b63ac367311af9a2f30c9b13a2ddddee7b89a5ea`).

### Empirically Discovered Casper Requirements
1. **Casper Medium Discovery & UUID Matching:**
   * The Ubuntu Live Server initrd embeds `/conf/uuid.conf` with UUID `50c98eb4-4c0f-4c1a-82d2-4234cf187d50`.
   * Casper's `/scripts/casper` function `matches_uuid()` scans candidate block devices (`/dev/sr0`) checking for `/.disk/casper-uuid-generic`.
   * Without this file, Casper fails with `Unable to find a medium containing a live file system`.
   * The build pipeline automatically writes `/.disk/casper-uuid-generic` and `/.disk/info`.
2. **Live Server Layer Selection (`layerfs-path`):**
   * Live Server initrd defaults to multi-layer installer squashfs trees (`conf/conf.d/default-layer.conf`).
   * Because AgenticOS uses the clean standalone `ubuntu-server-minimal.squashfs`, the kernel command line must specify:
     ```text
     layerfs-path=ubuntu-server-minimal.squashfs
     ```
   * This parameter instructs Casper to mount `ubuntu-server-minimal.squashfs` directly as the OverlayFS base on `tmpfs`.

---

## 7. Empirical QEMU Boot Validation & Runtime Telemetry

The assembled ISO was empirically boot-tested under QEMU 8.2.2 across both BIOS and UEFI boot paths:

### Verified Runtime Boot Chain
```text
Linux kernel (6.8.0-139-generic)
    ↓
initrd (Casper hooks)
    ↓
Casper media discovery (/.disk/casper-uuid-generic)
    ↓
live optical medium (/dev/sr0)
    ↓
SquashFS (casper/ubuntu-server-minimal.squashfs)
    ↓
OverlayFS (tmpfs copy-on-write overlay)
    ↓
systemd (v255.4 PID 1)
    ↓
Ubuntu 24.04.5 LTS userspace
```

### Historical Step 20.10 Test Artifact Metrics
*(Historical test artifact generated and verified during Step 20.10 boot validation; distinguished from subsequent clean rebuild artifacts):*
* **ISO Output Path:** `packaging/output/AgenticOS-v0.1-Alpha.iso`
* **File Size:** `246,796,288 bytes` (~246.8 MB / 235.36 MiB)
* **SHA256:** `54790d1f5ccff2736fa16a1b7b1cf4035580fe23e97a7028ca0d22232c07e77e`
* **Live Guest Console Output:**
  ```text
  [   31.494612] loop1: detected capacity change from 0 to 289568
  [   31.591290] overlayfs: "xino" feature enabled using 3 upper inode bits.
  systemd 255.4-1ubuntu8.17 running in system mode
  Detected virtualization qemu.
  Detected architecture x86-64.

  Welcome to Ubuntu 24.04.5 LTS!
  Hostname set to <agenticos>.
  Initializing machine ID from random generator.
  ```

---

## 8. Three-Tier Runtime Differentiation

To avoid overclaiming, technical verification across AgenticOS environments is explicitly separated into three distinct tiers:

```
+-------------------------------------------------------------------------+
|                  Three-Tier Runtime Verification Matrix                 |
+-------------------------------------------------------------------------+
|  Tier 1: WSL2 (Ubuntu 24.04)   -> VERIFIED (75 unit tests passing)     |
|  Tier 2: Real Virtual Machine  -> BOOT VALIDATED under QEMU (BIOS/UEFI)|
|  Tier 3: Bare-Metal Hardware   -> UNTESTED (No physical boot performed)|
+-------------------------------------------------------------------------+
```

1. **Tier 1: WSL2 Linux Runtime (Current Workspace):**
   * Verified: All 75 automated unit tests pass; real `/proc` and `/sys` interfaces read cleanly; systemd user session query verified.
   * Limitation: Hardware is virtualized by Hyper-V; loop devices and raw partition formatting are restricted.
2. **Tier 2: Real Virtual Machine (QEMU 8.2.2):**
   * Status: **BOOT VALIDATED**. Assembled `AgenticOS-v0.1-Alpha.iso` booted successfully in QEMU under both BIOS (El Torito) and UEFI (OVMF). Kernel, Casper, OverlayFS, and systemd userspace initialization empirically verified.
   * Limitation: Virtualized hardware (Q35 / VirtIO); does not establish physical hardware compatibility.
3. **Tier 3: Bare-Metal Physical PC Hardware:**
   * Status: **UNTESTED**. The prototype has never been booted directly on bare-metal motherboard hardware. Physical thermal, battery, and PCI controller behavior remains unverified.

---

## 9. Current Host Packaging Tooling Audit

An audit of installed packaging software in the current environment confirmed:
* **Installed & Verified:** Python 3.12, GCC 13.3, GNU Make 4.3, QEMU 8.2.2, `xorriso 1.5.6`, `mksquashfs 4.6.1`, `unsquashfs 4.6.1`, `grub-mkimage 2.12`, `mtools 4.0.43`.
* **Governance Compliance:** All tools operate 100% in unprivileged user space; **no root commands (`sudo`) or host kernel modifications have been executed**.

---

## 10. Operational Boundaries & Implementation Status

### Prohibited Claims & Boundary Declarations
The QEMU result establishes virtualized boot validation, **not universal hardware compatibility**.
We do **NOT** claim:
* production-ready
* installation-ready
* hardware compatibility validated
* physical-machine boot validated
* universal UEFI/BIOS compatibility

### Implementation Status Matrix

| Subsystem / Deliverable | Current Status | Test Evidence | Classification |
| :--- | :---: | :---: | :--- |
| **VM Hardware Specifications** | **DOCUMENTED** | `test_artifact_and_vm_specifications_present` | Approved Reference |
| **QEMU Invocation Parameters** | **VERIFIED** | Empirical QEMU Execution (BIOS & UEFI) | Approved Reference |
| **Build Pathways Evaluation** | **CANDIDATE B SELECTED** | `packaging/scripts/build_iso.sh` | **IMPLEMENTED** |
| **Prohibition of Destructive Scripts** | **VERIFIED** | `test_prohibition_of_destructive_packaging_scripts` | Security Invariant |
| **Casper Boot Metadata Codification** | **VERIFIED** | `packaging/config/grub.cfg`, `build_iso.sh` | **IMPLEMENTED** |
| **QEMU Virtual Machine Boot** | **BOOT VALIDATED** | Console Telemetry (`systemd 255.4`) | **VALIDATED** |
| **System-Wide Service Auto-Install** | **NOT YET IMPLEMENTED** | `INSTALL_SYSTEMD_SERVICE=0` | **UNDEFINED / BLOCKED** |
| **Physical Bare-Metal Disk Install** | **NOT YET IMPLEMENTED** | N/A | **UNDEFINED / BLOCKED** |
| **Bare-Metal Hardware Compatibility**| **NOT TESTED** | N/A | **Target Requirement** |
