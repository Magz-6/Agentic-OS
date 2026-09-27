# AgenticOS Packaging & Virtual Machine Specification

> **STATUS:** PROPOSAL & AUDIT ONLY — STANDALONE ISO BUILD TOOLCHAIN IS CURRENTLY **UNDEFINED / BLOCKED**.  
> **MILESTONE TARGET:** 28 September 2026 (`AgenticOS-v0.1-Alpha.iso`)  
> **MAINTAINER:** Magesh (Linux / OS Lead — Layer 10 & Layer 12 User-Space)

---

## 1. Core Architectural Question

> **What exactly must the final AgenticOS bootable/installable artifact contain, and what is the approved build path?**

This document establishes the technical audit, artifact requirements, candidate build paths, and Virtual Machine execution specifications for the AgenticOS Alpha milestone.

---

## 2. Artifact Requirements

According to the master architecture document (`AgenticOS_Architecture_Target_Employee_Daily_Plan_27Sep_15Oct.docx`), the primary deployment target is:

* **Artifact Filename:** `AgenticOS-v0.1-Alpha.iso`
* **Format:** Hybrid ISO 9660 / UDF Image (bootable via standard USB flash drives or VM optical drives with both UEFI and legacy BIOS El Torito support).

### Target Architecture Requirements for the Bootable Artifact (from Master Plan)

*Note: The following represents the target artifact specification defined in the master plan; current Phase 14 work provides the Layer 10/12 foundation and documentation only.*

1. **Base Operating System Layer:**
   * Linux kernel (standard Ubuntu LTS 6.8+ kernel with standard hardware drivers).
   * Systemd init system operating as PID 1.
   * Standard POSIX user-space tools and runtime libraries (glibc, libsystemd).
   * Python 3 runtime (Python 3.12+ with standard library).

2. **System Service Foundation (Layer 10 & 12 User-Space):**
   * Pre-configured systemd service unit: `agenticos-telemetry.service`.
   * Telemetry and hardware monitoring daemon (`telemetry/collector.py`).
   * Read-only system and process adapters (`adapters/`).
   * Service health inspector (`linux_integration/health.py`).

3. **Integrated Agentic Stack (Layers 1–8, 11 - Master Plan Target):**
   * Global Agent Manager & Agent Runtime (Krithikesh).
   * LLM inference adapters and prompt interface (Vishnu).
   * Agentic Core engine and inter-layer event bus (Vivek).
   * Kernel intelligence interface (Vidhyuth).
   * Terminal / UI shell (Lishanth).

4. **Boot & Session Behavior:**
   * Automated boot to a designated unprivileged system user (`agenticos`).
   * No interactive manual partitioning required for live demonstration.
   * Read-only root filesystem with ephemeral copy-on-write overlay (Live session).

---

## 3. Evaluation of Candidate Build Paths

Building `AgenticOS-v0.1-Alpha.iso` requires a deterministic, reproducible build pipeline. The four candidate pathways are evaluated below (none are officially approved yet):

| Build Pathway | Mechanism | Advantages | Disadvantages & Blockers | Evaluation Status |
| :--- | :--- | :--- | :--- | :--- |
| **Option A: Ubuntu Live Build (`live-build` / `casper`)** | Builds an ephemeral live squashfs image based on Ubuntu packages. | Native live-boot workflow with RAM overlay (`casper`). Clean live environment without persistent disk changes. | Requires root (`sudo`), host kernel loopback devices (`/dev/loop*`), and heavy package downloads. Brittle inside WSL2. | **Candidate approach; requires team evaluation and approval.** |
| **Option B: Subiquity Remaster (`xorriso` + autoinstall)** | Unpacks an official Ubuntu 24.04 Server/Desktop ISO, injects `cloud-init` / `autoinstall.yaml`, and repacks with `xorriso`. | 100% reproducible, retains Canonical-signed UEFI/SecureBoot shims, installs cleanly to target VM virtual disk. | Requires 2.5GB+ base ISO download. Geared toward automated installation rather than instantaneous ephemeral live session. | **Candidate approach; requires team evaluation and approval.** |
| **Option C: Debootstrap + Custom GRUB** | Bootstraps minimal Debian/Ubuntu rootfs into a directory, adds custom squashfs, builds GRUB bootloader. | Absolute minimal size (< 400 MB), zero unwanted bloat packages. | Extremely high maintenance; manual EFI bootloader configuration; complex initramfs assembly. | **Candidate approach; high complexity, requires team evaluation.** |
| **Option D: Pre-Built VM Disk Image (`.qcow2` / `.vhdx`)** | Build a direct virtual disk image via `qemu-img` and Packer or VM export. | Bypasses ISO installer overhead; bootable in seconds in QEMU/VirtualBox; ideal for developer testing. | Does not satisfy the strict `.iso` delivery requirement stated in the milestone plan. | **Supplemental developer artifact; requires team evaluation.** |

### Decision & Current Status

* **Status:** **NOT YET IMPLEMENTED / AWAITING TEAM APPROVAL**.
* **Reason:** Creating the ISO requires selecting between Option A (Live ephemeral) and Option B (Automated installer), installing host packaging utilities (`xorriso`, `squashfs-tools`), and downloading multi-gigabyte bases. Under the Phase 14 least-privilege boundary, no packaging software has been installed and no ISO has been compiled.

---

## 4. Virtual Machine Specifications (QEMU / VirtualBox / UTM)

To verify the AgenticOS user-space stack in a pristine VM environment, the following baseline configuration is specified:

### Target VM Hardware Profile
* **Architecture:** `x86_64` (AMD64)
* **vCPUs:** Minimum 2 cores (4 recommended for agent concurrency)
* **RAM:** Minimum 4096 MB (4 GB)
* **Virtual Disk:** Minimum 20 GB (dynamic allocation, VirtIO or NVMe bus)
* **Firmware:** UEFI (OVMF) preferred; Legacy BIOS supported
* **Network:** User-mode NAT with DHCP (`virtio-net-pci` or `e1000`)
* **Display / Graphics:** VirtIO-GPU or standard VGA (1024x768 minimum)

### QEMU Execution Reference (Reproducible Command)

When a candidate ISO or disk image is produced, it can be tested using the pre-installed QEMU emulator:

```bash
# Example invocation for testing AgenticOS ISO in QEMU (read-only reference)
qemu-system-x86_64 \
  -machine q35,accel=kvm:tcg \
  -cpu host \
  -smp 2 \
  -m 4G \
  -boot d \
  -cdrom AgenticOS-v0.1-Alpha.iso \
  -drive file=agenticos-test-disk.qcow2,if=virtio,format=qcow2 \
  -netdev user,id=net0,hostfwd=tcp::8080-:8080 \
  -device virtio-net-pci,netdev=net0 \
  -vga virtio \
  -display default
```

*(Note: On Windows host without KVM, use `-accel whpx` or `-accel tcg`.)*

---

## 5. Local User-Space Verification (WSL2 / Linux)

Until the team selects the official ISO build toolchain for the 28 September milestone:
1. All Layer 10 (System Services) and Layer 12 (Linux Integration) modules run directly in standard user space.
2. The entire unit test suite (`tests/`) executes without root privileges or VM virtualization.
3. Service templates and desktop definitions remain as inspected, non-installed configuration proposals.
