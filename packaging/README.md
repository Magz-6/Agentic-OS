# AgenticOS Packaging & Virtual Machine Specification

> **STATUS:** ISO boot validated under QEMU; reproducible build codification in progress.<br>
> **MILESTONE TARGET:** 28 September 2026 (`AgenticOS-v0.1-Alpha.iso`)<br>
> **MAINTAINER:** Magesh (Linux / OS Lead — Layer 10 & Layer 12 User-Space)

---

## 1. Core Architectural Question

> **What exactly must the final AgenticOS bootable/installable artifact contain, and what is the approved build path?**

This document establishes the technical audit, artifact requirements, build methodology, and Virtual Machine execution specifications for the AgenticOS Alpha milestone.

---

## 2. Artifact Requirements

According to the master architecture document (`AgenticOS_Architecture_Target_Employee_Daily_Plan_27Sep_15Oct.docx`), the primary deployment target is:

* **Artifact Filename:** `AgenticOS-v0.1-Alpha.iso`
* **Format:** Hybrid ISO 9660 / UDF Image (bootable via standard USB flash drives or VM optical drives with both UEFI and legacy BIOS El Torito support).

### Target Architecture Requirements for the Bootable Artifact (from Master Plan)

*Note: Current milestone provides the Layer 10/12 foundation, provisional user-space modules, and live ISO packaging. System-wide service installation remains governed by strict project boundaries.*

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

## 3. Evaluation & Selection of Build Pathways

Building `AgenticOS-v0.1-Alpha.iso` requires a deterministic, reproducible build pipeline:

| Build Pathway | Mechanism | Advantages | Disadvantages & Blockers | Evaluation Status |
| :--- | :--- | :--- | :--- | :--- |
| **Option A: Ubuntu Live Build (`live-build` / `casper`)** | Builds an ephemeral live squashfs image based on Ubuntu packages. | Native live-boot workflow with RAM overlay (`casper`). Clean live environment without persistent disk changes. | Requires root (`sudo`), host kernel loopback devices (`/dev/loop*`), and heavy package downloads. May encounter WSL2-specific limitations. | Evaluated; unselected due to loopback/privilege requirements. |
| **Option B: Subiquity / Live Server Remaster (`xorriso` + custom GRUB)** | Extracts official Ubuntu 24.04.5 Live Server kernel, initrd, and minimal rootfs; packages custom GRUB and OverlayFS. | 100% reproducible; unprivileged user-space build (zero `sudo`); compact footprint (~235 MiB); dual BIOS/UEFI boot. | Requires explicit Casper layer redirection and UUID matching. | **SELECTED & IMPLEMENTED (Candidate B)** |
| **Option C: Debootstrap + Custom GRUB** | Bootstraps minimal Debian/Ubuntu rootfs into a directory, adds custom squashfs, builds GRUB bootloader. | Absolute minimal size (< 400 MB), zero unwanted bloat packages. | Extremely high maintenance; manual EFI bootloader configuration; complex initramfs assembly. | Evaluated; unselected due to maintenance overhead. |
| **Option D: Pre-Built VM Disk Image (`.qcow2` / `.vhdx`)** | Build a direct virtual disk image via `qemu-img` and Packer or VM export. | Bypasses ISO installer overhead; bootable in seconds in QEMU/VirtualBox; ideal for developer testing. | Does not satisfy the strict `.iso` delivery requirement stated in the milestone plan. | Supplemental developer artifact only. |

---

## 4. Verified Upstream Components & Casper Requirements

### Verified Upstream Release Components
The packaging pipeline builds directly from official, GPG-verified Ubuntu 24.04.5 LTS (Noble Numbat) Live Server release media:
* **Source Artifact:** Ubuntu 24.04.5 Live Server (`ubuntu-24.04.5-live-server-amd64.iso`)
* **Live Kernel:** Ubuntu stock `6.8.0-139-generic` (`/casper/vmlinuz`, 15,059,336 bytes)
* **Live Initramfs:** Casper-enabled `initrd` (78,777,934 bytes, zstd-compressed cpio with 50 Casper hooks)
* **Base Root Filesystem:** `ubuntu-server-minimal.squashfs` (166,932,480 bytes, SHA256: `bd1ce4815bb1988b171cc863b63ac367311af9a2f30c9b13a2ddddee7b89a5ea`)

### Empirically Discovered Casper Boot Requirements
During QEMU validation, two upstream Casper initialization mechanisms were empirically isolated and permanently codified:
1. **Casper Medium Discovery & UUID Matching:**
   * The Ubuntu Live Server initrd embeds `/conf/uuid.conf` containing build UUID `50c98eb4-4c0f-4c1a-82d2-4234cf187d50`.
   * Casper's `/scripts/casper` function `matches_uuid()` scans candidate block devices (`/dev/sr0`) checking for `/.disk/casper-uuid-generic`.
   * Without this matching file, Casper reports `Unable to find a medium containing a live file system`.
   * The build pipeline automatically writes `/.disk/casper-uuid-generic` and `/.disk/info` (`AgenticOS v0.1 Alpha`).
2. **Live Server Layer Selection (`layerfs-path`):**
   * Live Server initrd defaults to multi-layer installer squashfs trees (`conf/conf.d/default-layer.conf`).
   * Because AgenticOS uses the clean standalone `ubuntu-server-minimal.squashfs`, the kernel command line must specify:
     ```text
     layerfs-path=ubuntu-server-minimal.squashfs
     ```
   * This parameter instructs Casper to mount `ubuntu-server-minimal.squashfs` directly as the OverlayFS base on `tmpfs`.

---

## 5. QEMU Virtual Machine Boot Validation

The assembled ISO was empirically boot-tested under QEMU 8.2.2 across both BIOS (El Torito) and UEFI (OVMF) boot paths.

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
* **ISO Path:** `packaging/output/AgenticOS-v0.1-Alpha.iso`
* **File Size:** `246,796,288 bytes` (~246.8 MB / 235.36 MiB)
* **SHA256:** `54790d1f5ccff2736fa16a1b7b1cf4035580fe23e97a7028ca0d22232c07e77e`
* **BIOS Boot:** ✅ Verified via El Torito catalog
* **UEFI Boot:** ✅ Verified via FAT ESP (`/boot/grub/efi.img`) and OVMF firmware
* **Live Guest Output:**
  ```text
  Welcome to Ubuntu 24.04.5 LTS!
  Hostname set to <agenticos>.
  systemd 255.4-1ubuntu8.17 running in system mode
  ```

---

## 6. Target VM Hardware Profile & QEMU Invocation

### Target VM Hardware Profile
* **Architecture:** `x86_64` (AMD64)
* **vCPUs:** Minimum 2 cores (4 recommended for agent concurrency)
* **RAM:** Minimum 4096 MB (4 GB)
* **Virtual Disk:** Minimum 20 GB (dynamic allocation, VirtIO or NVMe bus)
* **Firmware:** UEFI (OVMF) preferred; Legacy BIOS supported
* **Network:** User-mode NAT with DHCP (`virtio-net-pci` or `e1000`)
* **Display / Graphics:** VirtIO-GPU or standard VGA (1024x768 minimum)

### QEMU Execution Reference (Reproducible Commands)

```bash
# BIOS Boot Validation (Headless Serial Console):
qemu-system-x86_64 \
  -m 2048 \
  -cdrom packaging/output/AgenticOS-v0.1-Alpha.iso \
  -boot d \
  -nographic \
  -serial mon:stdio

# UEFI Boot Validation (OVMF Firmware):
qemu-system-x86_64 \
  -m 2048 \
  -bios /usr/share/OVMF/OVMF_CODE.fd \
  -cdrom packaging/output/AgenticOS-v0.1-Alpha.iso \
  -boot d \
  -nographic \
  -serial mon:stdio
```

---

## 7. Operational Boundaries & Service Governance

To prevent overclaiming and uphold rigorous architectural governance:

1. **Virtual Machine Scope:**
   The QEMU result establishes virtualized boot validation, **not universal hardware compatibility**.
   We do **NOT** claim:
   * production-ready
   * installation-ready
   * hardware compatibility validated
   * physical-machine boot validated
   * universal UEFI/BIOS compatibility

2. **Service Governance Safeguards:**
   Automatic installation or enablement of systemd services into `/etc/systemd/system` remains **NOT YET IMPLEMENTED** and is strictly **UNDEFINED / BLOCKED** pending team architectural approval:
   ```text
   INSTALL_SYSTEMD_SERVICE=0
   ENABLE_SYSTEMD_SERVICE=0
   ```
   Physical bare-metal disk installation remains **NOT YET IMPLEMENTED / BLOCKED**. Provisional AgenticOS modules reside in `/opt/agenticos` inside the live SquashFS for inspection only.
