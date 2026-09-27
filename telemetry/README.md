# Layer 11/13: System Telemetry Collector

- **Component:** `telemetry/collector.py`
- **Owner:** Magesh (Linux/OS Lead)
- **Downstream Consumer:** Vidhyuth (Kernel Intelligence Layer)
- **Status:** Initial Prototype (Phase 7)
- **Contract Status:** `TEMPORARY LOCAL INTERFACE — REQUIRES TEAM API APPROVAL`

## Purpose

The System Telemetry Collector provides safe, lightweight, read-only dynamic system metrics for the AgenticOS runtime. It queries Linux user-space interfaces (`/proc`) without requiring root access, elevated privileges, or heavy third-party daemons.

## Telemetry Metrics & Data Sources

| Metric Group | Specific Counters | Data Source |
| :--- | :--- | :--- |
| **CPU** | Total percentage, logical count, user/nice/system/idle/iowait jiffies | `/proc/stat`, `os.cpu_count()` |
| **Memory** | Total, available, used bytes, memory usage %, swap total/free/used | `/proc/meminfo` |
| **Load Average** | 1-minute, 5-minute, 15-minute load | `/proc/loadavg` |
| **Uptime** | System uptime in seconds, idle seconds | `/proc/uptime` |
| **Network** | Interface names, received bytes (rx), transmitted bytes (tx) | `/proc/net/dev` |
| **Processes** | Total process count, running process count | `/proc/[pid]/stat` |

## CPU Percentage Calculation Methodology

Linux exposes CPU time as cumulative ticks ("jiffies") in `/proc/stat` under the `cpu` line:
```text
cpu  user nice system idle iowait irq softirq steal guest guest_nice
```

To calculate the CPU utilization percentage over an interval:
1. **Sample 1:** Read `/proc/stat` at time \(t_1\), computing:
   - \(\text{Idle}_1 = \text{idle} + \text{iowait}\)
   - \(\text{NonIdle}_1 = \text{user} + \text{nice} + \text{system} + \text{irq} + \text{softirq} + \text{steal}\)
   - \(\text{Total}_1 = \text{Idle}_1 + \text{NonIdle}_1\)
2. **Interval:** Wait for a configurable duration (default: 0.1s) or compare against the previous stored cycle.
3. **Sample 2:** Read `/proc/stat` at time \(t_2\), computing \(\text{Total}_2\) and \(\text{Idle}_2\).
4. **Delta:**
   - \(\Delta \text{Total} = \text{Total}_2 - \text{Total}_1\)
   - \(\Delta \text{Idle} = \text{Idle}_2 - \text{Idle}_1\)
5. **Percentage:**
   \[
   \text{CPU \%} = \frac{\Delta \text{Total} - \Delta \text{Idle}}{\Delta \text{Total}} \times 100.0
   \]

## Security Constraints

- **Strictly Read-Only:** Queries only virtual files; never kills, interrupts, or alters processes.
- **Least Privilege:** Executes completely as an unprivileged user (`no sudo`).
- **No Direct Mutation:** Does not modify cgroups, CPU governor, or scheduler priorities.

## Synchronous CPU Sampling Considerations (Architecture Guideline)

In `SystemTelemetryCollector.get_cpu_telemetry()`, the default behavior uses `sample_interval=0.05` (`time.sleep(0.05)`):
- When integrating with event-driven loops or high-frequency polling daemons, callers should specify `sample_interval=0.0` to utilize cached previous jiffy samples rather than blocking the thread with a synchronous sleep.
- For async runtimes, a non-blocking background collector cycle or timestamped delta approach should be used.
