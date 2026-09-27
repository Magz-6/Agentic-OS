# AgenticOS — Known Limitations & Architectural Dependencies Register

> **DOCUMENT STATUS:** APPROVED BASELINE DOCUMENTATION  
> **MAINTAINER:** Magesh (Linux / OS Lead)  
> **SCOPE:** Layers 9, 10, 11, 12, 13 (Linux User-Space Foundation)  
> **DATE:** 27 September 2026  

---

## 1. Guiding Engineering Philosophy

> ### Core Principle:
> **A limitation is not necessarily a failure.**  
> In systems engineering, an explicit limitation marks a verified boundary where software either awaits an upstream architectural decision from the broader team or requires a different runtime environment (e.g. bare-metal hardware or dedicated CI).

This register documents all known operational constraints, virtualization artifacts, unverified execution scenarios, and unapproved team interfaces for Magesh's Linux user-space foundation as of 27 September 2026.

---

## 2. Virtualization & Environment Limitations (WSL2)

Because initial development and testing take place in Ubuntu 24.04.5 LTS under Windows Subsystem for Linux 2 (WSL2), several kernel and hardware interfaces operate under Hyper-V virtualization constraints:

1. **Virtual Block Storage:**
   * **Observation:** Disks appear as virtual SCSI devices (`sda`, `sdb`, `sdc`, `sdd`).
   * **Limitation:** Physical NVMe SMART health metrics, bus topology, and direct disk controller registers are not exposed to unprivileged user space.
2. **Synthetic DMI / SMBIOS Data:**
   * **Observation:** `/sys/class/dmi/id/sys_vendor` reports `Microsoft Corporation`, and `product_name` reports `Virtual Machine`.
   * **Limitation:** Host motherboard manufacturer metadata and physical BIOS revisions are virtualized.
3. **Absence of Physical Hardware Sensors:**
   * **Observation:** Kernel hardware monitoring directories (`/sys/class/thermal/`, `/sys/class/hwmon/`, `/sys/class/power_supply/`) are empty or unpopulated.
   * **Limitation:** Battery charge level, thermal throttling, and fan speed telemetry are not accessible under WSL2.
4. **Virtual NAT Network Interface:**
   * **Observation:** Network interface counters reflect virtual Hyper-V adapters (`eth0`).
   * **Limitation:** Raw 802.11 Wi-Fi frames, physical Ethernet PHY link speed negotiations, and wireless signal strength cannot be queried.
5. **Restricted Loop Device Operations:**
   * **Observation:** Unprivileged user space cannot create loopback block devices (`/dev/loop*`) or mount filesystem images.
   * **Limitation:** Building squashfs images or ISOs directly inside the WSL2 guest without root privileges is blocked.

---

## 3. Untested Operational Scenarios

To prevent misleading claims, the following operational dimensions are formally classified as **UNTESTED**:

1. **Bare-Metal PC Boot:**
   * AgenticOS has not been booted directly on physical PC hardware without virtualization. Physical ACPI, GPU hardware initialization, and direct peripheral enumeration remain untested.
2. **Standalone Bootable ISO Candidate:**
   * `AgenticOS-v0.1-Alpha.iso` has not been built or booted. Standalone ISO generation remains a milestone requirement for 28 September, not a verified deliverable of 27 September.
3. **Physical UEFI & Secure Boot Firmware:**
   * Real motherboard NVRAM variable manipulation and Secure Boot key enrollment have not been tested.
4. **Daemon Auto-Start & Persistence:**
   * The `agenticos-telemetry.service` unit file has not been installed into `/etc/systemd/system` or started as a persistent daemon.
   * *(Note: While systemctl reports `inactive/dead`, proving the service is not currently running, its strictly uninstalled state is established by automated test assertions verifying its complete absence from `/etc/systemd/system`, `/usr/lib/systemd/user`, and `~/.config/systemd/user`.)*
5. **Standalone Desktop Shell:**
   * While WSLg provides Wayland and X11 display server access for individual application windows, a full standalone desktop environment (such as GNOME Shell or KDE Plasma) has not been integrated or tested.

---

## 4. Blocked & Undefined Architecture Decisions

The following items are designated as **UNDEFINED / BLOCKED** pending official cross-layer specification:

### A. Official Application Allowlist (`UNDEFINED / BLOCKED`)
* **Current State:** `AppLauncher` implements a provisional allowlist with 4 categories (`browser`, `terminal`, `text_editor`, `file_manager`).
* **Blocker:** The master architecture plan does not officially define approved application IDs, candidate binaries, or tool execution parameters for Layer 9.
* **Mitigation:** The provisional allowlist is restricted to GUI terminal emulators (`gnome-terminal`, `x-terminal-emulator`, `xfce4-terminal`, `alacritty`), rejecting raw shells (`bash`) and command-wrapping flags (`-c`, `/c`, `--command`).

### B. Official System Service Contracts & Lifecycle (`UNDEFINED / BLOCKED`)
* **Current State:** A project-local systemd unit template (`agenticos-telemetry.service.template`) exists in the repository.
* **Blocker:** Official service names, user-level vs. system-level execution models, restart policies, and health aggregation contracts have not been finalized across the team.
* **Mitigation:** The unit file is preserved as an uninstalled reference proposal.

### C. Cross-Layer IPC & API Protocols (`UNDEFINED / BLOCKED`)
* **Current State:** Inter-component communication uses local Python dataclasses (`ServiceStatus`, `HealthReport`).
* **Blocker:** Official inter-layer communication protocols (e.g. gRPC, Unix Domain Sockets, D-Bus, or JSON-RPC) between Layer 10/12 and higher layers (Layers 1, 2, 3) are undefined.
* **Mitigation:** All interface headers are explicitly labeled:
  `TEMPORARY LOCAL INTERFACE — REQUIRES TEAM API APPROVAL`.

### D. cgroup Resource Limits & Isolation Policy (`UNDEFINED / BLOCKED`)
* **Current State:** Layer 10 adapters inspect process CPU and memory counters without enforcing quotas.
* **Blocker:** The team has not established CPU/memory limits, cgroup v2 slicing, or agent starvation defense policies.
* **Mitigation:** Adapters remain strictly read-only, avoiding unapproved resource throttling.

---

## 5. Deferred Architectural Proposals

The following features were designed and documented during Phase 16 hardening, but are **DEFERRED** from implementation to prevent premature divergence:

1. **Filesystem Workspace Sandboxing (`allowed_roots`):**
   * *Status:* **PROPOSED — NOT IMPLEMENTED**.
   * *Description:* Restricting agent directory queries to designated workspace roots via canonical path resolution (`Path.resolve()`).
   * *Reason for Deferral:* Sandboxing requires coordination with Vivek (Layer 1) and Krithikesh (Layer 3) to establish universal workspace path standards.
2. **Asynchronous Non-Blocking Telemetry Sampling:**
   * *Status:* **PROPOSED — NOT IMPLEMENTED**.
   * *Description:* Transitioning from synchronous `time.sleep(0.05)` sampling to a non-blocking background collector or cached delta queries (`sample_interval=0.0`).
   * *Reason for Deferral:* Requires integration with the upper-layer async event loop framework.

---

## 6. Cross-Layer Ownership & Dependency Register

To preserve architectural clarity, Magesh's foundation maintains strict boundaries with other layer owners:

| Upstream / Downstream Layer | Layer Owner | Boundary Description | Dependency on Magesh |
| :--- | :--- | :--- | :--- |
| **Layer 1: Agentic Core** | Vivek (Lead) | Orchestrates global workflows; coordinates inter-layer events. | Consumes health reports and filesystem/process adapters. |
| **Layer 2: LLM & Intent** | Vishnu | Parses natural language intent into structured goals. | Provides application dispatch targets for `AppLauncher`. |
| **Layer 3: Agent Runtime** | Krithikesh | Manages agent bus, multi-agent state, and execution lifecycles. | Defines IPC protocol and workspace sandbox boundaries. |
| **Layer 4 & QA: Security** | Lishanth | Threat modeling, permission matrices, and release validation. | Validates least-privilege constraints and executes QA suites. |
| **Layer 11: Kernel Intelligence**| Vidhyuth | Analyzes telemetry, models workloads, and optimizes performance. | Consumes raw metric streams from `telemetry/collector.py`. |

---

## 7. Master Limitations & Action Matrix

| # | Known Limitation | Operational Impact | Current Mitigation | Required Future Action |
| :-: | :--- | :--- | :--- | :--- |
| **1** | **WSL2 Virtual Hardware** | Block devices, DMI, and network are virtualized by Hyper-V; physical sensors missing. | Graceful degradation to `"unavailable"` or `"partial"`; standardized fallback handling. | Validate on physical bare-metal hardware during later integration milestones. |
| **2** | **No Bootable ISO** | `AgenticOS-v0.1-Alpha.iso` cannot be booted or distributed yet. | Formulated target VM profiles and compared candidate build paths in `packaging/README.md`. | Team must select approved ISO build framework (Option A vs. Option B) for 28 Sep milestone. |
| **3** | **Provisional Application Allowlist** | Only 4 generic application categories supported; not an official product contract. | Strict regex validation; rejection of `-c` flags; raw shells excluded from terminal candidates. | Layer 9 / Tool Registry lead must approve official application list and launch schemas. |
| **4** | **Uninstalled Telemetry Service** | Telemetry collector runs manually or as module; not running as a continuous background daemon. | Service template authored; uninstalled state continuously asserted by automated test. | Team must approve service name, deployment path, and user-session auto-start model. |
| **5** | **Undefined IPC / Protocol** | Higher-layer agents cannot yet communicate with adapters over network or IPC sockets. | Clean Python dataclasses used locally; all contracts marked `TEMPORARY LOCAL INTERFACE`. | Vivek / Krithikesh must define the official project-wide IPC standard (UDS / gRPC / JSON-RPC). |
| **6** | **Unimplemented Filesystem Sandboxing** | Read-only adapter can inspect any host path readable by user `mages`. | Governed by Linux DAC permissions; zero write/delete/mutate methods exist. | Implement `allowed_roots` canonical path confinement once workspace contracts are approved. |
| **7** | **Synchronous CPU Sleep** | `get_cpu_telemetry()` pauses calling thread for 50ms by default. | Supported `sample_interval=0.0` cached delta mode; documented in `telemetry/README.md`. | Implement non-blocking background collector daemon when event bus is integrated. |
| **8** | **No Bare-Metal PC Testing** | ACPI power events, physical UEFI Secure Boot, and GPU passthrough unverified. | Audited toolchains and created reproducible QEMU execution references. | Perform bare-metal smoke testing on reference physical laptop/desktop hardware. |
