# AgenticOS — Hardware Detection & System Telemetry Specification (Layer 11 & 13)

> **DOCUMENT STATUS:** APPROVED BASELINE DOCUMENTATION  
> **MAINTAINER:** Magesh (Linux / OS Lead)  
> **DOWNSTREAM CONSUMER:** Vidhyuth (Layer 11: Kernel Intelligence)  
> **CONTRACT STATUS:** `TEMPORARY LOCAL INTERFACE — REQUIRES TEAM API APPROVAL`  
> **DATE:** 27 September 2026  

---

## 1. Architectural Scope & Purpose

AgenticOS requires structured, machine-readable observability of both the static underlying hardware environment (**Layer 13: Hardware Detection**) and the dynamic operational system performance (**Layer 11: System Telemetry**).

In Magesh's Linux user-space architecture:
1. **`hardware/detector.py`** extracts static machine specifications (CPU model, core counts, RAM capacity, virtual/block devices, and network interfaces).
2. **`telemetry/collector.py`** continuously samples dynamic system behavior (CPU utilization %, 1m/5m/15m load averages, memory and swap pressure, uptime, network I/O, and process counts).
3. **Downstream Integration:** These raw metrics provide the empirical grounding data for Vidhyuth's Layer 11 (Kernel Intelligence) machine learning models and scheduling optimizations.

```
+-------------------------------------------------------------------------+
|                  Layer 11: Kernel Intelligence (Vidhyuth)               |
+-------------------------------------------------------------------------+
                                    ▲
                                    │ (Structured JSON Snapshots)
+-------------------------------------------------------------------------+
| Layer 11 & 13: Linux User-Space Observability (Magesh)                  |
|                                                                         |
|  +-----------------------------------+  +-----------------------------+ |
|  |     HardwareDetector (Layer 13)   |  | SystemTelemetryCollector    | |
|  |  - Static platform / core count   |  |   (Layer 11 / 13)           | |
|  |  - Total RAM / block devices      |  |  - Dynamic CPU % & jiffies  | |
|  |  - Net interfaces / DMI metadata  |  |  - Memory / swap utilization| |
|  |                                   |  |  - Load averages & uptime   | |
|  |  Data: /proc/cpuinfo, /sys/block  |  |  Data: /proc/stat, /loadavg | |
|  +-----------------------------------+  +-----------------------------+ |
+-------------------------------------------------------------------------+
                                    │
                                    ▼ (Read-Only POSIX Filesystem Queries)
+-------------------------------------------------------------------------+
| Linux Kernel (6.8+) Pseudo-Filesystems: /proc and /sys                  |
+-------------------------------------------------------------------------+
```

---

## 2. Hardware Detector (`hardware/detector.py`)

The `HardwareDetector` collects a comprehensive static profile of the computing host. It is completely decoupled from system-specific paths by accepting custom `proc_path` and `sys_path` constructor parameters, enabling high-fidelity unit testing with mocks.

### Metrics & Virtual Interface Mapping

| Subsystem | Data Source | Extracted Attributes | Output Format |
| :--- | :--- | :--- | :--- |
| **CPU** | `/proc/cpuinfo`, `os.cpu_count()` | `model_name`, `logical_cores`, `architecture`, `mhz`, `flags` | Standardized dictionary; core count defaults to `os.cpu_count()` if file is missing. |
| **Memory** | `/proc/meminfo` | `total_bytes`, `available_bytes`, `free_bytes`, `swap_total_bytes`, `swap_free_bytes` | Standardized integer byte counts (converted from kB). |
| **Platform** | Python `platform` standard module | `system`, `release`, `version`, `machine`, `python_version`, `is_virtualized_environment` | System metadata string mappings and boolean virtualization flag. |
| **Block Devices**| `/sys/class/block` or `/sys/block` | `name`, `size_bytes`, `removable`, `read_only` | List of non-ram/non-loop block devices; sector counts multiplied by 512 bytes. |
| **Network** | `/sys/class/net` | `interface`, `operstate`, `mtu`, `mac_address` | List of network interface summaries (`operstate`: up, down, unknown). |
| **DMI Metadata**| `/sys/class/dmi/id/` | `sys_vendor`, `product_name`, `product_version`, `bios_vendor`, `bios_version` | Machine vendor and BIOS metadata; falls back to `"unavailable"` when restricted. |

---

## 3. System Telemetry Collector (`telemetry/collector.py`)

The `SystemTelemetryCollector` samples dynamic operating system health counters without elevated privileges.

### Core Telemetry Metrics

1. **CPU Telemetry:**
   * **Cumulative Ticks ("Jiffies"):** Parsed directly from the first line of `/proc/stat` across all states: `user`, `nice`, `system`, `idle`, `iowait`, `irq`, `softirq`, `steal`.
   * **Calculated Usage Percentage:** Derived via delta comparison over an elapsed interval.
2. **Memory Utilization:**
   * **RAM Pressure:** Total, available, used, and free bytes; calculates real-time `usage_percent = round((used / total) * 100.0, 2)`.
   * **Swap Pressure:** Total, free, and used swap bytes; calculates `swap_usage_percent`.
3. **Load Average & Uptime:**
   * **Load:** 1-minute, 5-minute, and 15-minute exponentially decayed load averages from `/proc/loadavg`.
   * **Uptime:** Total elapsed system uptime and cumulative idle seconds from `/proc/uptime`.
4. **Network I/O:**
   * Cumulative received bytes (`rx_bytes`) and transmitted bytes (`tx_bytes`) per network interface from `/proc/net/dev`.
5. **Process Census:**
   * Total active process count and currently running (`state == 'R'`) process count gathered safely from `/proc/[pid]/stat`.

---

## 4. CPU Percentage Calculation Methodology

Linux does not expose an instantaneous "CPU percentage" register; instead, the kernel provides cumulative clock ticks ("jiffies") since system boot in `/proc/stat`.

### Mathematical Delta Formulation

To compute the true CPU utilization percentage across an interval between time \(t_1\) and \(t_2\):

1. **Sample 1 (\(t_1\)):**
   $$\text{Idle}_1 = \text{idle} + \text{iowait}$$
   $$\text{NonIdle}_1 = \text{user} + \text{nice} + \text{system} + \text{irq} + \text{softirq} + \text{steal}$$
   $$\text{Total}_1 = \text{Idle}_1 + \text{NonIdle}_1$$

2. **Sample 2 (\(t_2\)):**
   $$\text{Idle}_2 = \text{idle} + \text{iowait}$$
   $$\text{NonIdle}_2 = \text{user} + \text{nice} + \text{system} + \text{irq} + \text{softirq} + \text{steal}$$
   $$\text{Total}_2 = \text{Idle}_2 + \text{NonIdle}_2$$

3. **Delta Calculation:**
   $$\Delta \text{Total} = \text{Total}_2 - \text{Total}_1$$
   $$\Delta \text{Idle} = \text{Idle}_2 - \text{Idle}_1$$

4. **Percentage Calculation:**
   $$\text{CPU \%} = \begin{cases} 
   0.0 & \text{if } \Delta \text{Total} \le 0 \\
   \min\left(100.0, \max\left(0.0, \frac{\Delta \text{Total} - \Delta \text{Idle}}{\Delta \text{Total}} \times 100.0\right)\right) & \text{otherwise}
   \end{cases}$$

### Sampling & Non-Blocking Guidelines
* **Synchronous Mode (Default):** `collector.get_cpu_telemetry(sample_interval=0.05)` introduces a short 50ms pause (`time.sleep(0.05)`) between samples to calculate an immediate delta.
* **Asynchronous / Cached Mode (Recommended for Event Loops):** When called with `sample_interval=0.0`, the collector calculates utilization against the stored sample from the previous collection cycle (`self._last_cpu_sample`), eliminating thread-blocking delays.

---

## 5. Fault Tolerance & Graceful Degradation

In production Linux environments, individual `/proc` or `/sys` virtual files may be unreadable due to permission restrictions, kernel security hardening (e.g. `hidepid`), or virtualized execution.

Both collectors enforce strict resilience guarantees:
* **Zero Unhandled Exceptions:** All file access uses `_read_file_safe()`, which catches `FileNotFoundError`, `PermissionError`, `OSError`, and `UnicodeDecodeError`.
* **Explicit Status Markers:** If a data source is inaccessible, the returned dictionary includes `"status": "unavailable"` or `"status": "partial"` rather than crashing.
* **Corrupt Input Handling:** Malformed lines or missing columns in `/proc/stat` or `/proc/meminfo` are handled via `try/except (ValueError, IndexError)` and fall back safely.

---

## 6. WSL2 Virtual Hardware vs. Physical Hardware Telemetry

> ### ⚠️ CRITICAL OBSERVABILITY BOUNDARY:
> Telemetry gathered in the current WSL2 execution environment reflects **Hyper-V virtualized resources**, NOT direct physical motherboard telemetry:
>
> 1. **Block Devices:** Disks reported (`sda`, `sdb`, `sdc`, `sdd`) are virtual Hyper-V SCSI disks. Physical NVMe SMART health metrics, temperatures, and raw bus IDs are not surfaced to WSL2 user space.
> 2. **DMI / Motherboard BIOS:** `/sys/class/dmi/id/sys_vendor` reports `Microsoft Corporation` and `product_name` reports `Virtual Machine`. Physical motherboard manufacturer data (e.g. ASUS, Dell, Lenovo) is not accessible.
> 3. **Thermal & Power Sensors:** Linux hardware monitoring interfaces (`/sys/class/hwmon`, `/sys/class/thermal`, `/sys/class/power_supply`) are not populated by Hyper-V in WSL2. Battery status and CPU package temperatures return empty.
> 4. **Network Interfaces:** Network counters reflect the virtual Hyper-V NAT adapter (`eth0`), not physical 802.11 Wi-Fi frames or physical Ethernet PHY counters.

---

## 7. Security & Read-Only Boundaries

To protect system integrity:
1. **Strictly Read-Only:** Queries only virtual files in `/proc` and `/sys`. Contains zero file mutation, creation, or deletion logic.
2. **Zero Control Actions:** Does not alter CPU governors, processor frequencies, power states, or cgroup quotas.
3. **Zero Elevated Privileges:** All metrics are collected as an unprivileged user (`no sudo`).

---

## 8. Implementation Status Matrix

| Subsystem / Metric Group | Implementation Status | Test Coverage | Classification |
| :--- | :---: | :---: | :--- |
| **CPU Info Detection** | **IMPLEMENTED & VERIFIED** | `test_normal_cpu_info_parsing` | User-Space Module |
| **Memory Detection** | **IMPLEMENTED & VERIFIED** | `test_normal_memory_info_parsing` | User-Space Module |
| **Sysfs Block Devices** | **IMPLEMENTED & VERIFIED** | `test_block_devices_parsing` | User-Space Module |
| **Sysfs Network Interfaces** | **IMPLEMENTED & VERIFIED** | `test_network_interfaces_parsing` | User-Space Module |
| **DMI / Virtualization Check** | **IMPLEMENTED & VERIFIED** | `test_structured_output_format` | User-Space Module |
| **CPU Ticks & Usage %** | **IMPLEMENTED & VERIFIED** | `test_cpu_percent_calculation` | User-Space Module |
| **System Load & Uptime** | **IMPLEMENTED & VERIFIED** | `test_load_average_parsing`, `test_uptime_parsing` | User-Space Module |
| **Memory & Swap Telemetry** | **IMPLEMENTED & VERIFIED** | `test_memory_and_swap_parsing` | User-Space Module |
| **Network Traffic Telemetry** | **IMPLEMENTED & VERIFIED** | `test_network_byte_parsing` | User-Space Module |
| **Process Census** | **IMPLEMENTED & VERIFIED** | `test_process_counting` | User-Space Module |
| **Downstream ML Analysis** | **NOT IMPLEMENTED** | Owned by Vidhyuth | **Layer 11 Dependency** |
| **Bare-Metal Physical Sensors**| **NOT TESTED** | N/A | **Hardware/WSL2 Limitation** |
