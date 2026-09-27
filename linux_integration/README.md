# Layer 12: Agentic Microkernel / Linux Integration Boundary

- **Component:** `linux_integration/health.py`, `linux_integration/contracts.py`
- **Owner:** Magesh (Linux/OS Lead)
- **Architecture Layer:** Layer 12 (Linux Integration Boundary) & Layer 10 (System Services)
- **Status:** Initial Prototype (Phase 11)
- **Contract Status:** `TEMPORARY LOCAL INTERFACE — REQUIRES TEAM API APPROVAL`

## Purpose

Layer 12 serves as the controlled, user-space integration boundary between the higher-level AgenticOS agent/workflow runtimes and the underlying Linux operating system. It provides health monitoring, service state inspection, and temporary contract definitions without mutating Linux kernel internals or running privileged daemons.

## Master Documentation Audit (Phase 11)

1. **Official Service Names:** **UNDEFINED / BLOCKED**. (Provisional prefix: `agenticos-`).
2. **IPC Transport:** **UNDEFINED / BLOCKED**. (Provisional typed in-memory contracts used).
3. **Dedicated Service User:** **UNDEFINED / BLOCKED**. (Operates strictly as current unprivileged user via `systemctl --user`).
4. **Service Manager:** **Approved**. Standard Linux `systemd` (user session).

## Security Boundary & Prohibitions

To ensure strict system safety:
1. **STRICTLY Read-Only Health Inspection:** Only queries status (`is-active`, `is-failed`, `show`).
2. **NO Service Lifecycle Control:** Zero `start`, `stop`, `restart`, `enable`, `disable`, `mask`, `unmask`, `reload`, or `kill` methods.
3. **NO Privileged Modifications:** Zero `sudo` commands; never writes to `/etc/systemd/system`.
4. **NO Persistence or Autostart:** No auto-startup scripts, cron jobs, or boot persistence created.
5. **No Kernel / Network Changes:** Zero kernel module loading, sysctl modifications, or firewall alterations.

## Data Sources (Read-Only)

- **systemd Status:** `systemctl --user is-active <unit>`, `systemctl --user show <unit>`.
- **System Running State:** `systemctl --user is-system-running`.
- **Process State:** Direct fallback inspection via `/proc/[pid]` if systemd is unavailable.
