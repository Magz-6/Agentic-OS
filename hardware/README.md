# Layer 13: Hardware Detection and Reporting

- **Component:** `hardware/detector.py`
- **Owner:** Magesh (Linux/OS Lead)
- **Architecture Layer:** Layer 13 (Hardware) & Layer 12 (Linux Integration Boundary)
- **Status:** Initial Prototype (Phase 6)
- **Contract Status:** `TEMPORARY LOCAL INTERFACE — REQUIRES TEAM API APPROVAL`

## Purpose

The Hardware Detector provides safe, read-only hardware introspection on Linux systems. It gathers system specs (CPU, memory, storage devices, network interfaces, and system architecture) directly from Linux kernel user-space interfaces (`/proc` and `/sys`) without requiring root privileges or third-party CLI tools like `lspci` or `lsusb`.

## Data Sources (Read-Only)

- **CPU:** `/proc/cpuinfo`
- **Memory:** `/proc/meminfo`
- **Platform & Kernel:** Python `platform` / `os.uname` (`/proc/version`)
- **DMI / System Information:** `/sys/class/dmi/id/` (if readable)
- **Block Devices:** `/sys/block/`
- **Network Devices:** `/sys/class/net/`

## Virtualized / WSL2 Environment Handling

In virtual machines and WSL2:
- Direct physical PCI and USB devices are not passed through to user space.
- DMI tables may be restricted or absent.
- The detector never assumes physical hardware is absent simply because a virtual entry is unreadable; it returns structured `"unavailable"` or `"unknown"` values gracefully without raising exceptions.

## Security Constraints

- **Least Privilege:** Executes entirely as an unprivileged user (`no sudo`).
- **Read-Only:** Strictly queries system interfaces; never modifies device registers or kernel parameters.
- **No Third-Party Dependencies:** Relies 100% on the Python standard library.
