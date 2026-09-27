# AgenticOS Desktop Integration

- **Component:** `desktop/agenticos.desktop.template`
- **Owner:** Magesh (Linux/OS Lead)
- **Architecture Layer:** Layer 9 (Applications) & Desktop Integration Boundary
- **Status:** Template Only — **NOT INSTALLED**
- **Contract Status:** `TEMPORARY LOCAL INTERFACE — REQUIRES TEAM API APPROVAL`

## Purpose

This directory provides declarative FreeDesktop XDG Desktop Entry templates (`.desktop`) for AgenticOS. They provide standard application launcher shortcuts for Linux desktop environments (GNOME, XFCE, KDE, WSLg) without modifying the desktop shell or requiring elevated privileges.

## Security Boundary & Guardrails

1. **NOT INSTALLED:** Stored strictly as a project template (`.template`). It is **not** copied to `~/.local/share/applications/` or `/usr/share/applications/`.
2. **No Shell Replacement:** Does not modify the window manager, compositor, or desktop shell.
3. **No System Configuration Changes:** Does not modify `/etc/xdg/`, dconf databases, or global panel settings.
4. **No Arbitrary Shell Execution:** All actions invoke explicit Python module commands (`/usr/bin/python3 -m ...`) with strict arguments; never `sh -c` or arbitrary command strings.
5. **Controlled Application Launching:** Terminal and browser actions route strictly through Magesh's `AppLauncher` allowlist.

## Desktop Actions Supported

- **Main:** AgenticOS Status & Diagnostics Dashboard
- **Action SystemInfo:** View hardware and OS metrics (`hardware.detector`)
- **Action HealthCheck:** Inspect active service states (`linux_integration.health`)
- **Action LaunchTerminal:** Open approved terminal emulator (`adapters.app_launcher`)
- **Action LaunchBrowser:** Open approved web browser (`adapters.app_launcher`)
