# AgenticOS systemd User Service Templates

- **Owner:** Magesh (Linux/OS Lead)
- **Layer:** Layer 12 (Linux Integration Boundary) & Layer 10 (System Services)
- **Status:** Template Only — **NOT INSTALLED / NOT ENABLED**
- **Contract Status:** `TEMPORARY LOCAL INTERFACE — REQUIRES TEAM API APPROVAL`

## Purpose

This directory contains declarative `systemd` service unit templates for AgenticOS background services. These templates demonstrate how services run with least privilege within an unprivileged user session (`systemd --user`).

## Security Boundary

1. **NOT INSTALLED:** This unit template resides strictly inside the project repository. It is **not** copied to `~/.config/systemd/user/` or `/etc/systemd/system/`.
2. **NOT ENABLED:** No autostart, persistence, or background daemons are activated on the host.
3. **Zero Root Privileges:** The service runs within the current user's session without `sudo`, root capabilities, or administrative privileges.
4. **No Shell Execution:** Uses direct Python module invocation (`/usr/bin/python3 -m ...`) rather than `sh -c` shell wrappers.
5. **Safe Restart Policy:** Configured with `Restart=on-failure` and `RestartSec=5s` to prevent fast crash-restart loops.

## Template Specification

- **File:** `agenticos-telemetry.service.template`
- **ExecStart:** Direct Python invocation of the telemetry collector.
- **Environment:** `PYTHONUNBUFFERED=1` (ensures live, unbuffered logging to `journald`).
- **Logging:** Direct integration with `systemd-journald`.
