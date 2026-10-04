# AgenticOS Prompt UI — Linux Integration Report

> **DOCUMENT TYPE:** Application Integration & Service Specification Report<br>
> **ENGINEERING LEAD:** Magesh (Linux / OS Lead — Layer 9 & 12 Boundary)<br>
> **TARGET MILESTONE:** AgenticOS v0.1 Alpha Web-Based Prompt UI<br>
> **DATE:** 29 September 2026<br>
> **STATUS:** Prototyped, Service-Integrated, and Empirically Validated

---

## 1. Executive Summary & Purpose

The Prompt UI prototype provided by the AgenticOS team has been integrated into the AgenticOS repository under `applications/prompt-ui/`. The UI provides a modern, dark cybernetic natural-language prompt interface with:
* Command input with real-time status indicators.
* One-click presets for safe queries, task optimization, sensitive action checks, and error simulations.
* A 4-stage pipeline visualization (`Intent Parsing`, `Policy & Permissions`, `Agent Execution`, `Result Synthesis`).
* Explicit operator confirmation modals for simulated destructive actions.
* Fault trap visualization for simulated execution errors.

> **CRITICAL ARCHITECTURAL BOUNDARIES:**<br>
> 1. **HEADLESS SERVER ARCHITECTURE:** The current AgenticOS image is Ubuntu Server Minimal without a graphical desktop, display server (Xorg/Wayland), or pre-installed web browser. The Prompt UI is **not** a native desktop OS GUI interface; it is an AgenticOS web-based application/service exposed locally on port 8000.<br>
> 2. **MOCK BACKEND BOUNDARY:** All prompt parsing, intent risk classification, telemetry metrics, and responses are simulated client-side via `request-handler.js`. The Prompt UI is **not** connected to the real Agent Core or live system services at this stage.

---

## 2. Repository Location

All UI assets and integration scripts reside strictly under:
```text
AgenticOS/
├── applications/
│   └── prompt-ui/
│       ├── index.html                           # Semantic UI markup & layout
│       ├── styles.css                           # Cybernetic dark theme stylesheet
│       ├── app.js                               # UI controller & DOM event manager
│       ├── request-handler.js                   # Decoupled MockAgenticEngine simulation
│       ├── server.py                            # Zero-dependency Python 3 HTTP server
│       ├── launch.py                            # User-space CLI & desktop launcher
│       ├── agenticos-prompt-ui.desktop.template # FreeDesktop XDG desktop entry template
│       └── README.md                            # Teammate documentation & usage instructions
└── linux_integration/
    └── systemd/
        └── agenticos-prompt-ui.service.template # Declarative systemd service unit template
```

---

## 3. How to Launch the Prompt UI

### Method A: Declarative systemd Service (Production / OS Service)
Inside AgenticOS, the Prompt UI is managed via standard systemd lifecycle:
```bash
# Check service status:
systemctl status agenticos-prompt-ui

# Start / stop / restart service:
sudo systemctl start agenticos-prompt-ui
sudo systemctl stop agenticos-prompt-ui
sudo systemctl restart agenticos-prompt-ui
```
- **Service Unit:** `agenticos-prompt-ui.service`
- **ExecStart:** Direct Python invocation: `/usr/bin/python3 /opt/agenticos/applications/prompt-ui/server.py`
- **Security:** Runs as unprivileged `User=nobody`, `Group=nogroup` with `NoNewPrivileges=true`, `ProtectSystem=strict`, and `ProtectHome=true`.
- **Restart Policy:** Bounded `Restart=on-failure` with `RestartSec=5s`.

### Method B: Safe Python Launcher (Interactive CLI)
From the user terminal:
```bash
# Start server in background without opening browser (headless):
python3 /opt/agenticos/applications/prompt-ui/launch.py --no-browser

# Check server status:
python3 /opt/agenticos/applications/prompt-ui/launch.py --status

# Stop background server:
python3 /opt/agenticos/applications/prompt-ui/launch.py --stop
```

### Method C: Direct Foreground Python Server
```bash
cd /opt/agenticos/applications/prompt-ui
python3 server.py
```
Bound to `0.0.0.0:8000`, accessible locally at `http://127.0.0.1:8000`.

---

## 4. Systemd Service Specification

```ini
[Unit]
Description=AgenticOS Prompt UI Web Server
Documentation=https://github.com/agenticos/agenticos
After=network.target

[Service]
Type=simple
Environment=PYTHONUNBUFFERED=1
WorkingDirectory=/opt/agenticos/applications/prompt-ui
ExecStart=/usr/bin/python3 /opt/agenticos/applications/prompt-ui/server.py
Restart=on-failure
RestartSec=5s
StandardOutput=journal
StandardError=journal

# Security: Unprivileged execution
User=nobody
Group=nogroup
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

---

## 5. FreeDesktop `.desktop` Entry Template

A declarative FreeDesktop.org standard `.desktop` entry template is provided at:
`applications/prompt-ui/agenticos-prompt-ui.desktop.template`

- **Status:** Uninstalled template only (not installed into `/usr/share/applications/` on host or server image).
- **Exec:** Calls `/usr/bin/python3 applications/prompt-ui/launch.py`.

---

## 6. Architecture & Mock Execution Boundary

The boundary between UI presentation and execution is strictly maintained:

```text
[ CURRENT IMPLEMENTED BASELINE ]
Prompt UI (index.html / app.js)
    ↓ (ES6 Method Invocations & Progress Callbacks)
Mock Request Handler (request-handler.js)
    ↓ (Simulated Delays & Heuristic Classifier)
MockAgenticEngine (In-Memory Simulated Workflows)
```

```text
[ FUTURE TARGET ARCHITECTURE — CURRENTLY UNIMPLEMENTED ]
Prompt UI (index.html / app.js)
    ↓ (HTTP REST / WebSocket JSON RPC)
AgenticOS Backend API Daemon
    ↓ (IPC / Authorization Gate)
Agent Orchestration / Policy Engine / Linux System Services
```

---

## 7. Known Limitations

1. **Headless OS Environment:** The base OS contains no graphical browser. Users access the Prompt UI via HTTP on port 8000 (either via curl/scripts locally, or over forwarded VM networking to a host browser).
2. **Mock Backend Only:** The UI currently relies on simulated responses in `request-handler.js`. It does not execute live commands or communicate with hardware/kernel adapters.
3. **Template Installation Deferred:** System-wide desktop shortcut registration remains uninstalled.
