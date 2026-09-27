# AgenticOS — Virtual Machine & Packaging Specification

> **DOCUMENT STATUS:** AUDIT & PROPOSAL DOCUMENTATION  
> **MAINTAINER:** Magesh (Linux / OS Lead)  
> **MILESTONE TARGET:** 28 September 2026 (`AgenticOS-v0.1-Alpha.iso`)  
> **BUILD STATUS:** STANDALONE ISO BUILD TOOLCHAIN IS **UNDEFINED / BLOCKED**  
> **DATE:** 27 September 2026  

---

## 1. Executive Summary & Core Architectural Question

> ### Core Architectural Question:
> **What exactly must the final AgenticOS bootable/installable artifact contain, and what is the approved build path?**

In the master architecture plan (`AgenticOS_Architecture_Target_Employee_Daily_Plan_27Sep_15Oct.docx`), the milestone target for 28 September 2026 specifies:
* **Deliverable:** "first branded bootable ISO + systemd services".
* **Verification Criterion:** "Clean ISO boots; core services start; telemetry returns valid data. Fresh VM boot/install + vertical E2E + smoke suite PASS."

This document establishes the virtual machine hardware profiles, QEMU configuration, candidate packaging pathways, firmware requirements, and current tooling status.

> ### ⚠️ MANDATORY DEPLOYMENT BOUNDARY:
> **Standalone ISO generation and physical disk installation have NOT been implemented or verified.**  
> Current Phase 14–17 deliverables provide the **Layer 10/12 Linux user-space foundation, virtual machine specifications, and architectural documentation only**. No ISO image has been compiled, downloaded, or booted.

---

## 2. Target Virtual Machine Hardware Profile

To evaluate the integrated AgenticOS stack in a clean, reproducible virtualized environment (such as QEMU, VirtualBox, or UTM), the following baseline hardware profile is specified:

| Hardware Resource | Minimum Specification | Recommended Specification | Virtual Emulation Model |
| :--- | :--- | :--- | :--- |
| **Architecture** | `x86_64` (AMD64) | `x86_64` (AMD64) | Standard x86_64 Q35 chipset |
| **Processor (vCPUs)**| 2 vCPUs | 4 vCPUs | Host pass-through (`-cpu host`) or QEMU `max` |
| **System Memory (RAM)**| 4096 MB (4 GB) | 8192 MB (8 GB) | VirtIO balloon driver support |
| **Virtual Storage** | 20 GB dynamic disk | 40 GB dynamic disk | VirtIO Block (`virtio-blk-pci`) or NVMe |
| **Firmware** | Legacy BIOS (SeaBIOS) | UEFI (OVMF x86_64) | OVMF with standard UEFI NVRAM |
| **Network Interface**| User-mode NAT | User-mode NAT with port forwarding | `virtio-net-pci` or Intel `e1000` |
| **Graphics / Display**| Standard VGA (1024x768) | VirtIO-GPU with 3D acceleration | `virtio-vga` or `virtio-gpu-pci` |

---

## 3. QEMU Execution Reference

QEMU 8.2.2 is available within the Ubuntu WSL2 runtime (`/usr/bin/qemu-system-x86_64`), and QEMU 8.x is installed on the Windows host (`C:\Program Files\qemu`). 

When a candidate ISO or pre-configured disk image is produced, it can be tested using the following standardized, unprivileged QEMU invocation:

```bash
# Standard QEMU invocation for testing AgenticOS ISO in virtual machine (Reference)
qemu-system-x86_64 \
  -machine q35,accel=kvm:tcg \
  -cpu host \
  -smp 4 \
  -m 4G \
  -boot d \
  -cdrom AgenticOS-v0.1-Alpha.iso \
  -drive file=agenticos-test-disk.qcow2,if=virtio,format=qcow2 \
  -netdev user,id=net0,hostfwd=tcp::8080-:8080 \
  -device virtio-net-pci,netdev=net0 \
  -vga virtio \
  -display default
```

*(Note: On Windows host without Linux KVM acceleration, replace `-accel kvm:tcg` with `-accel whpx` or `-accel tcg`.)*

---

## 4. Target Artifact Requirements (from Master Plan)

According to the master architecture document, the final bootable release artifact must satisfy:

1. **Artifact Filename:** `AgenticOS-v0.1-Alpha.iso`.
2. **Format:** Hybrid ISO 9660 / UDF image bootable directly from USB flash drives or VM optical drives with dual UEFI and legacy BIOS El Torito support.
3. **Core Operating System Runtime:**
   * Standard Linux LTS kernel (Ubuntu LTS 6.8+).
   * Systemd init system functioning as PID 1.
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

## 5. Candidate Build Pathways Evaluation

Creating a bootable ISO requires a deterministic build framework. Under strict governance, **no build system has been chosen yet**. The four candidate approaches are evaluated below:

| Candidate Build Pathway | Mechanism | Advantages | Constraints & Blockers | Evaluation Status |
| :--- | :--- | :--- | :--- | :--- |
| **Option A: Ubuntu Live Build (`live-build` / `casper`)** | Generates an ephemeral live squashfs filesystem with Ubuntu packages and casper boot scripts. | Standardized live-boot workflow; ephemeral RAM overlay; ideal for demonstration. | Requires root (`sudo`), host kernel loop devices (`/dev/loop*`), and heavy package downloads. Brittle inside WSL2. | **Candidate approach; requires team evaluation and approval.** |
| **Option B: Subiquity Remaster (`xorriso` + autoinstall)** | Unpacks an official Ubuntu 24.04 ISO, injects `cloud-init` / `autoinstall.yaml`, and repacks with `xorriso`. | 100% reproducible; retains Canonical-signed UEFI/SecureBoot shims; automated installation to virtual disk. | Requires multi-gigabyte base ISO download; primarily oriented toward unattended disk installation rather than live memory session. | **Candidate approach; requires team evaluation and approval.** |
| **Option C: Debootstrap + Custom GRUB** | Bootstraps a minimal Debian/Ubuntu rootfs, creates squashfs, and manually configures GRUB bootloader. | Minimal image size (< 400 MB); zero extraneous packages. | Extremely high maintenance; complex manual EFI/initramfs assembly. | **Candidate approach; high complexity, requires team evaluation.** |
| **Option D: Pre-Built VM Disk Image (`.qcow2` / `.vhdx`)** | Builds a direct virtual disk image using `qemu-img` or Packer. | Boots in seconds in QEMU; bypasses complex ISO installer squashing. | Does not satisfy the strict `.iso` delivery format specified in the 28 September milestone. | **Supplemental developer artifact; requires team evaluation.** |

---

## 6. Firmware & Boot Considerations: UEFI vs. Legacy BIOS

Modern hardware and virtualization environments require strict attention to firmware boot standards:

1. **UEFI (Unified Extensible Firmware Interface):**
   * **Target:** Primary firmware target for AgenticOS.
   * **Partitioning:** GPT (GUID Partition Table) with dedicated EFI System Partition (ESP) formatted as FAT32 (`/boot/efi`).
   * **Bootloader:** GRUB 2 (`grub-efi-amd64-signed`) utilizing standard canonical EFI binaries (`bootx64.efi`).
2. **Legacy BIOS (CSM):**
   * Supported via hybrid MBR El Torito boot records for legacy virtual machines.
3. **Secure Boot Compatibility:**
   * In Option B (Subiquity remaster), official Canonical Secure Boot signatures are preserved.
   * In Option C (custom debootstrap), Secure Boot must be disabled in VM firmware unless keys are custom-enrolled.

---

## 7. Three-Tier Runtime Differentiation

To avoid overclaiming, technical verification across AgenticOS environments is explicitly separated into three distinct tiers:

```
+-------------------------------------------------------------------------+
|                  Three-Tier Runtime Verification Matrix                 |
+-------------------------------------------------------------------------+
|  Tier 1: WSL2 (Ubuntu 24.04)   -> VERIFIED (75 unit tests passing)     |
|  Tier 2: Real Virtual Machine  -> UNTESTED (Specifications drafted)    |
|  Tier 3: Bare-Metal Hardware   -> UNTESTED (No physical boot performed)|
+-------------------------------------------------------------------------+
```

1. **Tier 1: WSL2 Linux Runtime (Current Workspace):**
   * Verified: All 75 automated unit tests pass; real `/proc` and `/sys` interfaces read cleanly; systemd user session query verified.
   * Limitation: Hardware is virtualized by Hyper-V; loop devices and raw partition formatting are restricted.
2. **Tier 2: Real Virtual Machine (QEMU / VirtualBox / UTM):**
   * Status: **UNTESTED**. VM profiles and commands are documented, but no standalone VM has been booted with an AgenticOS ISO.
3. **Tier 3: Bare-Metal Physical PC Hardware:**
   * Status: **UNTESTED**. The prototype has never been booted directly on bare-metal motherboard hardware. Physical thermal, battery, and PCI controller behavior remains unverified.

---

## 8. Current Host Packaging Tooling Audit

An audit of installed packaging software in the current environment confirmed:
* **Installed:** Python 3.12, GCC 13.3, GNU Make 4.3, QEMU 8.2.2.
* **NOT Installed:** ISO creation tools (`xorriso`, `genisoimage`, `mkisofs`), live filesystem builders (`live-build`, `casper`, `debootstrap`), and squashfs utilities (`squashfs-tools`).
* **Governance Compliance:** In accordance with the Phase 14 least-privilege boundary, **no packaging packages have been installed and no root commands have been executed**.

---

## 9. Implementation Status Matrix

| Subsystem / Deliverable | Current Status | Test Evidence | Classification |
| :--- | :---: | :---: | :--- |
| **VM Hardware Specifications** | **DOCUMENTED** | `test_artifact_and_vm_specifications_present` | Approved Reference |
| **QEMU Invocation Parameters** | **DOCUMENTED** | `test_artifact_and_vm_specifications_present` | Approved Reference |
| **Build Pathways Evaluation** | **CANDIDATES DOCUMENTED** | `test_artifact_and_vm_specifications_present` | **UNDEFINED / BLOCKED** |
| **Prohibition of Destructive Scripts** | **VERIFIED** | `test_prohibition_of_destructive_packaging_scripts` | Security Invariant |
| **Official ISO Build System Selection**| **NOT IMPLEMENTED** | N/A | **Awaiting Team Decision** |
| **Standalone Bootable ISO Generation** | **NOT IMPLEMENTED** | N/A | **Target Requirement** |
| **Physical Disk Installation** | **NOT TESTED** | N/A | **Target Requirement** |
