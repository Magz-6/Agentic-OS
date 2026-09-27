# Magesh — Linux / OS Lead: Role & Architecture Boundaries

> **DOCUMENT STATUS:** APPROVED BASELINE DOCUMENTATION  
> **MAINTAINER:** Magesh (Linux / OS Lead)  
> **PROJECT:** AgenticOS v0.1 Alpha  
> **DATE:** 27 September 2026  

---

## 1. Executive Summary & Role Purpose

Magesh serves as the **Linux / OS Lead** for AgenticOS v0.1 Alpha. The primary mandate of this role is to build, verify, and document a robust, secure, and strictly unprivileged **Linux user-space foundation** that bridges the standard Linux operating system with the upper-layer AgenticOS intelligence stack.

### Milestone Focus
* **27 September 2026 Milestone:** Environment verification, Linux source audit/decision, hardware detection, dynamic system telemetry, safe user-space adapters (process, memory, filesystem, application launcher), service health inspection, and cross-platform verification.
* **28 September 2026 Target:** ISO/VM architecture proposal, service integration template, and documentation. *(Note: Standalone ISO generation itself is NOT YET IMPLEMENTED pending team build-path approval).*

---

## 2. Architecture Layer Responsibilities

The AgenticOS master architecture defines 13 functional layers. Magesh holds primary engineering responsibility for the Linux user-space foundation across the following layers:

```
+-------------------------------------------------------------------------+
|                  AgenticOS Architecture Layer Mapping                   |
+-------------------------------------------------------------------------+
|  Layer 9:  Applications & Services          -> Magesh (Launcher / Safe Adapters)
|  Layer 10: System Services                  -> Magesh (Process / Memory / FS Adapters)
|  Layer 11: Kernel Intelligence / Telemetry  -> Magesh (Telemetry Collector) / Vidhyuth
|  Layer 12: Microkernel / Linux Integration  -> Magesh (Health / Service Templates)
|  Layer 13: Hardware Detection & Reporting   -> Magesh (Hardware Detector)
+-------------------------------------------------------------------------+
```

### Detailed Breakdown by Layer

#### Layer 9: Applications & Services
* **Implemented & Verified:** `adapters/app_launcher.py`. Direct process dispatch using `subprocess.Popen` with `shell=False`, strict regex metacharacter filtering, and command-execution flag rejection (`-c`, `/c`, `--command`).
* **Proposed Architecture:** Provisional 4-category application allowlist (`browser`, `terminal`, `text_editor`, `file_manager`).
* **Status:** **PROVISIONAL ONLY**. The official AgenticOS application allowlist is `UNDEFINED / BLOCKED` pending team approval.

#### Layer 10: System Services
* **Implemented & Verified:**
  * `adapters/process_adapter.py`: Read-only process enumeration, RSS memory, CPU ticks, and vanishing PID handling via `/proc/[pid]`.
  * `adapters/memory_adapter.py`: Read-only memory counter parsing (total, available, free, used, buffers, cached, swap) via `/proc/meminfo`.
  * `adapters/filesystem_adapter.py`: Read-only file/directory inspection, symlink safety, disk capacity via `os.statvfs()`, and mount point parsing via `/proc/mounts`.
* **Proposed Architecture:** Project-local, uninstalled systemd unit template (`linux_integration/systemd/agenticos-telemetry.service.template`).
* **Status:** Service contracts and persistent daemon auto-start are **PROVISIONAL / NOT INSTALLED**.

#### Layer 11/13: System Telemetry & Hardware Detection
* **Implemented & Verified:**
  * `hardware/detector.py`: CPU model, core counts, memory size, block devices, and network interfaces via `/proc` and `/sys`.
  * `telemetry/collector.py`: Cumulative CPU jiffies, delta percentage calculation, 1m/5m/15m load averages, system uptime, and interface network traffic.
* **Team Boundary:** Downstream metrics are designed for consumption by Vidhyuth (Layer 11: Kernel Intelligence).
* **Status:** Implemented and backed by unit tests.

#### Layer 12: Linux Integration & Service Health
* **Implemented & Verified:**
  * `linux_integration/health.py`: Read-only `ServiceHealthInspector` querying `systemctl --user show` with double-dash `--` separators, unit name regex validation, and timeout guards.
  * `linux_integration/contracts.py`: Strongly typed dataclasses (`ServiceStatus`, `HealthReport`).
* **Status:** Implemented for user-space health queries. System-wide service installation is **NOT IMPLEMENTED**.

#### ISO & Virtual Machine Preparation
* **Implemented & Verified:** `packaging/README.md` and `tests/test_packaging.py`.
* **Proposed Architecture:** Evaluation of candidate build pathways (Ubuntu Live Build, Subiquity Remaster, Debootstrap, VM Disk Appliance) and QEMU hardware profiles.
* **Status:** Standalone ISO generation is **NOT YET IMPLEMENTED / BLOCKED**.

---

## 3. Explicit Non-Responsibilities

To maintain strict modularity and prevent scope creep, Magesh explicitly does **NOT** own:

1. **Linux Kernel Modifications or Compilation:**
   * Formally decided in Phase 4: AgenticOS operates **entirely in user space**.
   * No kernel source downloads, no custom drivers, no kernel patches, no kernel compilation, and no custom system calls.
2. **AI Models, Prompts, & Intent Parsing (Layer 2):**
   * Owned by Vishnu. Magesh does not develop LLM adapters or prompt reasoning engines.
3. **Agent Runtime, Protocol, & Event Bus (Layer 3):**
   * Owned by Krithikesh. Magesh does not design agent IPC protocols or multi-agent orchestration.
4. **Agentic Core Engine & Inter-Layer Dispatch (Layer 1):**
   * Owned by Vivek (Project Lead).
5. **Kernel Intelligence ML Analysis (Layer 11):**
   * Owned by Vidhyuth. Magesh provides the raw telemetry collectors; Vidhyuth analyzes metrics.
6. **Security Threat Model, QA Matrix, & UI Shell (Layer 4 & QA):**
   * Owned by Lishanth.

---

## 4. Core Engineering Invariants

All code authored under Magesh's responsibility must adhere to four strict invariants:

1. **Least-Privilege Operation:**
   * Zero operations requiring `sudo` or root privileges.
   * All services run in unprivileged user sessions (`User=%u`, `systemctl --user`).
2. **Strictly Non-Destructive Adapters:**
   * Adapters are strictly read-only.
   * Zero methods for file creation, deletion, modification, permission alteration, or process termination.
3. **Guaranteed Shell Injection Prevention:**
   * `shell=True` is strictly prohibited.
   * Direct execution using array-based arguments (`[exe, *args]`).
   * Shell metacharacters (`;`, `&`, `|`, `` ` ``, `$`, `<`, `>`, `\n`) and command wrapping flags (`-c`, `/c`, `--command`) are rejected.
4. **Transparent Governance:**
   * No guesswork. All unfinalized cross-layer interfaces are explicitly marked:
     `TEMPORARY LOCAL INTERFACE — REQUIRES TEAM API APPROVAL`
   * Missing specifications are formally recorded as `UNDEFINED / BLOCKED`.

---

## 5. Status Summary Matrix

| Component / Responsibility | Implementation Status | Test Evidence | Official Team Contract Status |
| :--- | :---: | :---: | :---: |
| **Hardware Detector** | Implemented & Verified | 8/8 passed | Provisional Local Contract |
| **System Telemetry Collector** | Implemented & Verified | 10/10 passed | Provisional Local Contract |
| **Process Adapter** | Implemented & Verified | 5/5 passed | Provisional Local Contract |
| **Memory Adapter** | Implemented & Verified | 4/4 passed | Provisional Local Contract |
| **Filesystem Adapter** | Implemented & Verified | 10/10 passed | Provisional Local Contract |
| **Application Launcher** | Implemented & Verified | 10/10 passed | Allowlist is UNDEFINED / BLOCKED |
| **Service Health Inspector** | Implemented & Verified | 12/12 passed | Provisional Local Contract |
| **Systemd Service Template** | Proposal (Uninstalled) | 6/6 passed | Service Contract is UNDEFINED / BLOCKED |
| **Desktop Entry Template** | Proposal (Uninstalled) | 5/5 passed | Desktop Contract is UNDEFINED / BLOCKED |
| **VM & ISO Specification** | Proposal & Audit | 5/5 passed | Build Path is UNDEFINED / BLOCKED |
| **Standalone Bootable ISO** | **NOT IMPLEMENTED** | N/A | Target Requirement from Master Plan |
