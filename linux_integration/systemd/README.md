# AgenticOS systemd Service Templates

- **Owner:** Magesh (Linux/OS Lead)
- **Layer:** Layer 12 (Linux Integration Boundary) & Layer 10 (System Services)
- **Status:** Integrated Service Templates
- **Contract Status:** `TEMPORARY LOCAL INTERFACE — REQUIRES TEAM API APPROVAL`

## Purpose

This directory contains declarative `systemd` service unit templates for AgenticOS background services. These templates demonstrate how services run with least privilege within an unprivileged execution context.

## Security Boundary

1. **Host Isolation:** Service templates reside strictly inside the project repository during development. They are **not** copied to `~/.config/systemd/user/` or `/etc/systemd/system/` on the build host.
2. **Build-Time Packaging:** Services enabled in the AgenticOS ISO are placed strictly inside the target squashfs root filesystem during ISO build Stage 3.
3. **Zero Root Privileges:** Long-running services like Prompt UI run under unprivileged system accounts (`User=nobody`, `Group=nogroup`) with `NoNewPrivileges=true`, `ProtectSystem=strict`, and `ProtectHome=true`.
4. **No Shell Execution:** Uses direct binary invocation (`/usr/bin/python3 ...`) rather than `sh -c` shell wrappers.
5. **Safe Restart Policy:** Configured with `Restart=on-failure` and bounded `RestartSec=5s` to prevent fast crash-restart loops.

## Template Specifications

### 1. `agenticos-prompt-ui.service.template`
- **Description:** AgenticOS Prompt UI Web Server background service.
- **ExecStart:** Direct Python invocation of `/opt/agenticos/applications/prompt-ui/server.py`.
- **Port:** Local web server listening on port 8000 (`http://127.0.0.1:8000`).
- **Security:** `User=nobody`, `Group=nogroup`, `NoNewPrivileges=true`, `ProtectSystem=strict`, `ProtectHome=true`, `PrivateTmp=true`.
- **Restart Policy:** `Restart=on-failure`, `RestartSec=5s`.

### 2. `agenticos-firstboot.service.template`
- **Description:** AgenticOS First-Boot Account Setup Wizard on `/dev/tty1`.
- **ExecStart:** Direct Python invocation of `/opt/agenticos/applications/firstboot/setup_wizard.py`.
- **Condition:** Runs only when `/var/lib/agenticos/firstboot-completed` is absent.

### 3. `agenticos-goal-runtime.service.template`
- **Description:** AgenticOS Goal Runtime Service (Layer 3).
- **ExecStart:** Direct Python invocation of `/opt/agenticos/system-services/goal-runtime/runner.py`.
- **Port / Sockets:** None (zero network attack surface, zero unauthorized IPC).
- **Security:** `DynamicUser=yes`, `NoNewPrivileges=true`, `ProtectSystem=strict`, `ProtectHome=true`, `PrivateTmp=true`.
- **Restart Policy:** `Restart=on-failure`, `RestartSec=5s`.
- **OS-Level State Directory:** `StateDirectory=agenticos/goal-runtime` (`/var/lib/agenticos/goal-runtime`).
- **Integration Boundary:**
  - *Vivek's Domain:* `src.goal_runtime` lifecycle logic, finite state machine, validation, and domain models.
  - *Magesh's Domain:* Systemd service unit, Linux daemon runner, unprivileged sandboxing, and OS lifecycle management.
- **Persistence Boundary:**
  - *Process Persistence:* Service starts automatically at boot and recovers from unexpected process failure.
  - *Goal Data Persistence:* **BLOCKED / PENDING TEAM APPROVAL**. Vivek's runtime holds state in-memory; on-disk data storage requires a future team-approved storage interface.

### 4. `agenticos-telemetry.service.template`
- **Description:** AgenticOS System Telemetry Collector (User Service Template).
- **Status:** Unlinked reference template only (not installed or enabled).
