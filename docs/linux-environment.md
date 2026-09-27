# AgenticOS — Linux Environment & Execution Runtime Specification

> **DOCUMENT STATUS:** AUDIT & BASELINE DOCUMENTATION  
> **MAINTAINER:** Magesh (Linux / OS Lead)  
> **TARGET OS:** Ubuntu 24.04.5 LTS (Noble Numbat) via WSL2  
> **HOST OS:** Windows 11 Home Single Language (AMD64)  
> **DATE:** 27 September 2026  

---

## 1. Executive Environment Overview

AgenticOS v0.1 Alpha is developed and verified across a dual-platform workstation setup: a **Windows 11 host operating system** coupled with a native **Ubuntu 24.04.5 LTS Linux environment** running under Windows Subsystem for Linux 2 (WSL2).

This document establishes the verified hardware profile, kernel version, installed toolchains, pseudo-filesystem interfaces, virtualization boundaries, and operational limitations observed during the 27 September 2026 development cycle.

---

## 2. Verified Host & Runtime Specifications

### Host Machine Profile
* **Host Operating System:** Microsoft Windows 11 Home Single Language (Version 10.0.26100 Build 26100)
* **Processor:** 13th Gen Intel(R) Core(TM) i7-13645HX (20 logical cores, base clock ~2.60 GHz)
* **Physical Memory:** 16.0 GB Total Physical RAM (~7.61 GB allocated to WSL2 virtual machine)
* **Architecture:** `x86_64` (AMD64)

### Target Linux Environment (WSL2)
* **Distribution:** Ubuntu 24.04.5 LTS (Noble Numbat)
* **Kernel Version:** `6.8.0-45-generic` (`x86_64`, SMP PREEMPT_DYNAMIC)
* **Init System (PID 1):** `systemd` (Active and running as PID 1; confirmed via `/proc/1/comm` -> `systemd`)
* **Execution User:** `mages` (Unprivileged user account, UID 1000, GID 1000)

---

## 3. Toolchain & Runtime Audit

All core build, runtime, and emulator tools required for the 27 September milestone were audited in Phase 1 and Phase 3:

| Component | Linux (WSL2) Version | Windows Host Version | Role in AgenticOS |
| :--- | :--- | :--- | :--- |
| **Python** | Python 3.12.3 (`/usr/bin/python3`) | Python 3.12.10 (`python.exe`) | Primary language for Layer 9, 10, 12, 13 modules and test runner |
| **GCC** | GCC 13.3.0 (`x86_64-linux-gnu-gcc-13`) | *N/A* | C/C++ compilation toolchain (available for future native modules) |
| **Make** | GNU Make 4.3 (`/usr/bin/make`) | *N/A* | Build automation engine |
| **QEMU** | QEMU 8.2.2 (`qemu-system-x86_64`) | QEMU 8.x (`C:\Program Files\qemu`) | Virtual Machine emulator for testing future bootable ISO candidates |
| **systemd** | systemd 255.4 (Ubuntu package) | *N/A* | User-space service manager and health inspection target |
| **Git** | Git 2.43.0 (`/usr/bin/git`) | Git 2.50.1 (`git.exe`) | Version control (initialized upon approval in Phase 19) |

---

## 4. Linux User-Space Interfaces Utilized

In accordance with the Phase 4 decision, AgenticOS operates **strictly in user space** above the Linux kernel without requiring kernel compilation, custom drivers, or out-of-tree kernel modules. All system inspection is performed using standard POSIX interfaces and Linux pseudo-filesystems:

### Pseudo-Filesystem Mappings

1. **`/proc/stat`:**
   * Parsed by: `telemetry/collector.py`
   * Data extracted: Raw cumulative CPU jiffies (`user`, `nice`, `system`, `idle`, `iowait`, `irq`, `softirq`, `steal`).
   * Algorithm: Delta-based CPU percentage calculation between successive jiffy samples.

2. **`/proc/meminfo`:**
   * Parsed by: `hardware/detector.py`, `telemetry/collector.py`, `adapters/memory_adapter.py`
   * Data extracted: `MemTotal`, `MemFree`, `MemAvailable`, `Buffers`, `Cached`, `SwapTotal`, `SwapFree`.
   * Conversion: Standardized from kB to exact integer byte counts.

3. **`/proc/loadavg` & `/proc/uptime`:**
   * Parsed by: `telemetry/collector.py`
   * Data extracted: 1-minute, 5-minute, and 15-minute load averages; system uptime and idle seconds.

4. **`/proc/net/dev`:**
   * Parsed by: `telemetry/collector.py`
   * Data extracted: Network interface traffic counters (received bytes `rx_bytes`, transmitted bytes `tx_bytes`).

5. **`/proc/[pid]/` (`stat`, `status`, `cmdline`, `comm`):**
   * Parsed by: `adapters/process_adapter.py`, `telemetry/collector.py`
   * Data extracted: Process ID, process name, execution state, parent PID (`PPid`), thread count, RSS memory (`VmRSS`), virtual memory size (`VmSize`), CPU ticks (`utime`, `stime`), and null-delimited command-line vectors.

6. **`/proc/mounts`:**
   * Parsed by: `adapters/filesystem_adapter.py`
   * Data extracted: Active mounted devices, mount points, filesystem types (ext4, tmpfs, 9p), and mount options (`ro`, `rw`).

7. **`/sys/class/block` & `/sys/block`:**
   * Parsed by: `hardware/detector.py`
   * Data extracted: Block device enumeration (`sda`, `sdb`, `sdc`, `sdd`), sector counts (multiplied by 512 bytes), and removable/read-only markers.

8. **`/sys/class/net`:**
   * Parsed by: `hardware/detector.py`
   * Data extracted: Operational state (`operstate`), MTU, and MAC hardware addresses (`address`).

9. **`/sys/class/dmi/id`:**
   * Parsed by: `hardware/detector.py`
   * Data extracted: BIOS vendor, system vendor, and product version (when accessible).

---

## 5. WSL2 Hardware-Access Boundaries

Because development and testing occur within a virtualized WSL2 container under Hyper-V, specific hardware interfaces differ from bare-metal Linux installations:

1. **Virtual Block Devices:**
   * In WSL2, block devices appear as virtual SCSI devices (`sda`, `sdb`, `sdc`, `sdd`) managed by the Hyper-V virtual storage controller.
   * Physical NVMe controllers, PCI IDs, and raw SATA controller registers are not exposed directly to unprivileged user space.
2. **DMI / SMBIOS Data:**
   * `/sys/class/dmi/id/sys_vendor` reports `Microsoft Corporation`, and `product_name` reports `Virtual Machine`.
   * Motherboard-level manufacturer metadata is virtualized.
3. **Network Virtualization:**
   * Network interfaces (`eth0`) operate as virtual Hyper-V switches utilizing NAT. Direct physical Wi-Fi or Ethernet NIC manipulation is not accessible.
4. **Loop Devices & Formatting:**
   * Mounting loopback devices (`mount -o loop`) or formatting raw filesystems (`mkfs`) is restricted without root privileges and is avoided to guarantee system stability.

---

## 6. Graphical Integration: WSLg Display Subsystem

Phase 13 evaluated the desktop and display subsystem under WSL2:

* **Wayland Compositor:** Active via `WAYLAND_DISPLAY=wayland-0` (socket located at `/mnt/wslg/runtime-dir/wayland-0`).
* **X11 Fallback:** Active via `DISPLAY=:0` (socket at `/tmp/.X11-unix/X0`).
* **Application Infrastructure:** Conforms to FreeDesktop.org standards; standard directory `/usr/share/applications` exists.

> **CRITICAL ARCHITECTURAL DISTINCTION:**  
> WSLg provides **graphical window and display access** directly to the Windows host desktop. This **does NOT mean a full, conventional desktop environment (such as GNOME Shell, KDE Plasma, or XFCE) is installed or running** inside the WSL2 guest. AgenticOS v0.1 Alpha provides window-level launcher support, not a monolithic desktop manager.

---

## 7. Dual-Platform Developer Experience

The AgenticOS codebase is built to run reliably on both the primary Ubuntu runtime and the Windows host:

* **100% Pass Rate on Ubuntu 24.04:** All 75 unit tests execute and pass in ~0.10s.
* **Resilient on Windows Host:** 73 tests pass in ~0.08s; 2 tests gracefully skip because Windows lacks the POSIX `os.statvfs` error interfaces.
* **Dual Execution Paths:** Modules support direct execution (`python -m adapters.app_launcher`) and import execution across both operating systems.

---

## 8. Verification Status: Tested vs Untested

To maintain technical honesty and prevent overclaiming, the following table explicitly states what has and has not been tested:

| Operational Dimension | Status | Verification Detail |
| :--- | :---: | :--- |
| **Ubuntu 24.04 (WSL2) User-Space** | **VERIFIED** | 75/75 unit tests passing; all 6 live smoke checks verified against live kernel. |
| **Windows 11 Host Execution** | **VERIFIED** | 73 passed, 2 intentional skips; cross-platform standard library compatibility proven. |
| **systemd User Session Interaction** | **VERIFIED** | Read-only inspection of active/failed/inactive services via `systemctl --user`. |
| **Standalone Bootable ISO (QEMU)** | **BOOT VALIDATED** | ISO boot validated under QEMU; reproducible build codification in progress. Boots to `systemd 255.4`. |
| **Bare-Metal Linux Hardware Boot** | **NOT TESTED** | Prototype has not yet been booted directly on physical PC hardware without virtualization. |
| **Full Desktop Shell (GNOME/KDE)** | **NOT TESTED** | WSLg display tested; full standalone desktop manager has not been integrated. |
| **System-Wide Service Installation** | **NOT YET IMPLEMENTED** | Template created; unit not installed in `/etc/systemd/system` (`INSTALL_SYSTEMD_SERVICE=0`). |

### QEMU Boot Validation & Casper Live Environment

During Phase 20, the hybrid live ISO (`AgenticOS-v0.1-Alpha.iso`) was assembled using Candidate B (Ubuntu 24.04.5 Live Server base) and empirically validated under QEMU 8.2.2 across both BIOS and UEFI boot paths.

* **Verified Upstream Components:**
  * Ubuntu 24.04.5 Live Server release media
  * Linux kernel `6.8.0-139-generic` (`vmlinuz`)
  * Casper-enabled `initrd`
  * Base rootfs `ubuntu-server-minimal.squashfs`
* **Empirically Codified Casper Requirements:**
  * `/.disk/casper-uuid-generic` matching initrd `/conf/uuid.conf` (`50c98eb4-4c0f-4c1a-82d2-4234cf187d50`)
  * `/.disk/info` (`AgenticOS v0.1 Alpha`)
  * Kernel cmdline parameter: `layerfs-path=ubuntu-server-minimal.squashfs`
* **Verified Runtime Chain:**
  ```text
  Linux kernel
      ↓
  initrd
      ↓
  Casper
      ↓
  live optical medium
      ↓
  SquashFS
      ↓
  OverlayFS
      ↓
  systemd
      ↓
  Ubuntu 24.04.5 userspace
  ```
* **Historical Step 20.10 Test Artifact Checksum:**
  `54790d1f5ccff2736fa16a1b7b1cf4035580fe23e97a7028ca0d22232c07e77e` (size: 246,796,288 bytes).
* **Strict Boundary Declaration:**
  The QEMU result establishes virtualized boot validation, **not universal hardware compatibility**. We do **NOT** claim production-ready, installation-ready, hardware compatibility validated, physical-machine boot validated, or universal UEFI/BIOS compatibility.

---

## 9. Environment Limitations Impacting the Prototype

1. **Virtual Machine Scope:** Telemetry and boot have been validated in virtualized environments (WSL2 Hyper-V and QEMU); physical bare-metal hardware validation is pending.
2. **Absence of Bare-Metal Hardware Telemetry:** Temperature sensors (`/sys/class/thermal`) and battery metrics (`/sys/class/power_supply`) are not surfaced by Hyper-V in WSL2.
3. **Read-Only Inspection Focus:** Current adapters strictly observe the system; autonomous mutation or remedial action requires higher-layer team approval.
4. **Absence of Official Team APIs:** All inter-component communication currently uses temporary local Python dataclasses pending project-wide API freeze.
