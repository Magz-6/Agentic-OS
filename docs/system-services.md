# AgenticOS — System Services & Adapters Specification (Layer 10 & 12)

> **DOCUMENT STATUS:** APPROVED BASELINE DOCUMENTATION  
> **MAINTAINER:** Magesh (Linux / OS Lead)  
> **ARCHITECTURE LAYERS:** Layer 10 (System Services) & Layer 12 (Linux Integration)  
> **CONTRACT STATUS:** `TEMPORARY LOCAL INTERFACE — REQUIRES TEAM API APPROVAL`  
> **DATE:** 27 September 2026  

---

## 1. Architectural Scope & Purpose

In the AgenticOS 13-layer master plan, **Layer 10 (System Services)** provides the foundational operating system services and runtime abstractions required by higher intelligence layers (Layer 1: Agentic Core, Layer 2: LLM Interface, Layer 3: Agent Runtime).

To ensure that autonomous agents can observe and reason about the operating system without risking catastrophic stability failures or data loss, Magesh's implementation establishes a **strictly unprivileged, read-only adapter architecture**.

```
+-------------------------------------------------------------------------+
|                  AgenticOS Upper Layers (1 - 8, 11)                     |
+-------------------------------------------------------------------------+
                                    │
                                    ▼ (Read-Only API)
+-------------------------------------------------------------------------+
| Layer 10 / 12: System Services & Linux Integration Boundary             |
|                                                                         |
|  +--------------------+  +--------------------+  +--------------------+ |
|  |   ProcessAdapter   |  |   MemoryAdapter    |  | FilesystemAdapter  | |
|  | (/proc/[pid]/...)  |  |  (/proc/meminfo)   |  | (stat, statvfs, ro)| |
|  +--------------------+  +--------------------+  +--------------------+ |
|                                                                         |
|  +--------------------------------------------------------------------+ |
|  | ServiceHealthInspector  (systemctl --user show -- <unit>)          | |
|  +--------------------------------------------------------------------+ |
|                                                                         |
|  +--------------------------------------------------------------------+ |
|  | agenticos-telemetry.service.template  (PROPOSAL — NOT INSTALLED)   | |
|  +--------------------------------------------------------------------+ |
+-------------------------------------------------------------------------+
                                    │
                                    ▼ (POSIX / Kernel Virtual Interfaces)
+-------------------------------------------------------------------------+
| Linux Kernel (6.8+) / /proc / /sys / systemd (PID 1)                    |
+-------------------------------------------------------------------------+
```

---

## 2. Safe System Adapters (Layer 10)

Layer 10 encompasses three core read-only adapters located in `adapters/`:

### A. Process Service Adapter (`adapters/process_adapter.py`)
* **Purpose:** Inspect active Linux processes without relying on external packages or elevated privileges.
* **Data Sources:** Linux `/proc/[pid]/comm`, `/proc/[pid]/cmdline`, `/proc/[pid]/status`, and `/proc/[pid]/stat`.
* **Extracted Attributes:**
  * Process ID (`pid`) and Parent PID (`ppid`).
  * Executable name (`name`) and command line vector (`cmdline`).
  * Process execution state (`state`: `R`, `S`, `D`, `Z`, `T`).
  * Thread count (`threads`).
  * Memory consumption: Resident Set Size (`vm_rss_bytes`) and Virtual Memory Size (`vm_size_bytes`).
  * CPU tick counters (`utime`, `stime`, `starttime_ticks`).
* **Resilience Mechanisms:** Handles ephemeral processes vanishing mid-scan gracefully (`_read_file_safe`), skipping terminated PIDs without raising exceptions.
* **Prohibited Capabilities:** Zero methods to kill (`SIGKILL`/`SIGTERM`), pause (`SIGSTOP`), resume (`SIGCONT`), alter priority (`nice`/`renice`), or spawn arbitrary processes.

### B. Memory Service Adapter (`adapters/memory_adapter.py`)
* **Purpose:** Provides comprehensive, structured kernel memory statistics.
* **Data Sources:** `/proc/meminfo`.
* **Extracted Counters:** Total physical memory, available memory, free memory, used memory, buffers, page cache, reclaimable slab, and total/free/used swap.
* **Standardization:** All values are converted from kB to exact integer byte counts.
* **Prohibited Capabilities:** Zero memory allocation manipulation, cgroup memory limit modifications, or swap configuration changes.

### C. Filesystem Service Adapter (`adapters/filesystem_adapter.py`)
* **Purpose:** Inspect file metadata, directory listings, mount tables, and volume capacity.
* **Data Sources:** POSIX system calls (`os.stat`, `os.lstat`, `os.scandir`, `os.statvfs`) and `/proc/mounts`.
* **Key Methods:**
  * `inspect_path(path)`: Safely checks path existence, distinguishing regular files, directories, valid symlinks, and broken symlinks. Captures file size, modification timestamps, and permissions without throwing exceptions.
  * `list_directory(path, limit=100)`: Uses context-managed `os.scandir()` to stream entry summaries with configurable entry limits.
  * `get_usage(path)`: Queries volume capacity, free space, and usage percentage via `os.statvfs()` (with `shutil.disk_usage` fallback for Windows host support).
  * `get_mounts()`: Parses `/proc/mounts` into structured device, mount point, filesystem type, and read-only (`is_read_only`) flags.
* **Prohibited Capabilities:** Zero file creation, deletion, truncation, renaming, permission alteration (`chmod`/`chown`), mount operations, or disk formatting (`mkfs`/`dd`).

---

## 3. Systemd Integration & Service Health Inspection (Layer 12)

### Service Health Inspector (`linux_integration/health.py`)
The `ServiceHealthInspector` queries the operational state of systemd services without controlling them:
* **User Session Scoping:** All operations strictly target `systemctl --user`. System-level daemons are not queried directly, maintaining least privilege.
* **Non-Blocking Query Execution:** Every query enforces a hard `timeout=3` second guard to prevent D-Bus deadlocks.
* **Command Injection Hardening:**
  * Unit names are strictly validated against `SAFE_UNIT_NAME_REGEX = re.compile(r"^[a-zA-Z0-9_@\.-]+$")`.
  * Names starting with a hyphen (`-`) or containing metacharacters are rejected immediately with `invalid_service_name`.
  * Invocations use the double-dash `--` operand separator (`[systemctl, "--user", "show", "--", service_name, ...]`).
* **Strict Control Boundary:** Verified by unit tests to expose zero lifecycle manipulation methods (`start`, `stop`, `restart`, `enable`, `disable`, `reload`, `mask`).

### Health & Status Semantics
Service health inspection produces typed `ServiceStatus` and `HealthReport` dataclasses with precise semantics:

| Property | Values | Description |
| :--- | :--- | :--- |
| `active_state` | `active`, `inactive`, `failed`, `timeout`, `unavailable`, `rejected` | The high-level lifecycle state reported by systemd. |
| `substate` | `running`, `dead`, `exited`, `failed` | Detailed unit substate. |
| `main_pid` | `int` or `None` | Active MainPID if running; `None` if stopped or dead. |
| `healthy` | `True` / `False` | **`True` ONLY when `active_state == "active"` AND `substate == "running"`**. |
| `error` | `str` or `None` | Error diagnosis (e.g. `service_failed`, `systemctl_not_found`, `systemctl_timeout`, `invalid_service_name`). |

---

## 4. Provisional Telemetry Service Unit Template

To support the 28 September milestone target ("first branded bootable ISO + systemd services"), a project-local systemd unit template was authored:
* **File Location:** `linux_integration/systemd/agenticos-telemetry.service.template`

### Unit Configuration Design
```ini
[Unit]
Description=AgenticOS Telemetry Service (Prototype)
After=network.target

[Service]
Type=simple
User=%u
Group=%g
WorkingDirectory=%h/AgenticOS
ExecStart=/usr/bin/python3 -m telemetry.collector
Restart=on-failure
RestartSec=5s
StandardOutput=journal
StandardError=journal
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=read-only

[Install]
WantedBy=default.target
```

### Critical Security Constraints
1. **Unprivileged User Session:** Configured with `User=%u` and `Group=%g`, intended exclusively for user-session managers (`systemd --user`).
2. **Direct Execution:** `ExecStart` invokes `/usr/bin/python3` directly. No shell wrappers (`sh -c` or `bash -c`) are used.
3. **Hardening Directives:** Incorporates `NoNewPrivileges=true`, `ProtectSystem=strict`, and `ProtectHome=read-only` to constrain service privileges.

---

## 5. Explicit Installation Status Declaration

> ### ⚠️ MANDATORY DEPLOYMENT BOUNDARY:
> The `agenticos-telemetry.service` unit file is **STRICTLY UNINSTALLED, UNREGISTERED, AND NOT RUNNING**.
> 
> * It is **NOT** installed into `/etc/systemd/system/` (system-wide services).
> * It is **NOT** installed into `/usr/lib/systemd/user/` or `~/.config/systemd/user/` (user services).
> * It has **NOT** been enabled via `systemctl enable`.
> * It has **NOT** been started via `systemctl start`.
> * It exists purely as an inspected, non-installed configuration template within the repository.
> * Unit test `test_service_strictly_uninstalled` continuously asserts that this file is absent from all system directories.

---

## 6. Implementation Status Matrix

| Subsystem / Component | Current Status | Test Coverage | Classification |
| :--- | :---: | :---: | :--- |
| `ProcessAdapter` | **IMPLEMENTED & VERIFIED** | 5 unit tests | Provisional Local Contract |
| `MemoryAdapter` | **IMPLEMENTED & VERIFIED** | 4 unit tests | Provisional Local Contract |
| `FilesystemAdapter` | **IMPLEMENTED & VERIFIED** | 10 unit tests | Provisional Local Contract |
| `ServiceHealthInspector` | **IMPLEMENTED & VERIFIED** | 12 unit tests | Provisional Local Contract |
| Health Dataclass Contracts | **IMPLEMENTED & VERIFIED** | Integrated | `TEMPORARY LOCAL INTERFACE` |
| Systemd Service Template | **PROPOSED TEMPLATE** | 6 unit tests | Project-Local Proposal |
| Service Installation & Startup | **NOT IMPLEMENTED** | N/A | **UNDEFINED / BLOCKED** |
| Official Service Allowlist & APIs | **NOT IMPLEMENTED** | N/A | **UNDEFINED / BLOCKED** |
