# AGENTICOS v0.1 ALPHA - Prompt Web UI Shell

A sleek, cybernetic, dark-mode web user interface shell built for **AgenticOS v0.1 Alpha**.

---

## 🌟 Features Included

1. **Dark, Professional AgenticOS Theme**:
   - Cyber-themed obsidian palette (`#07090e`), neon cyan, matrix emerald, caution amber, and glowing crimson highlights.
   - Glassmorphic panels, responsive cards, and live telemetry badges (`SYS_ALPHA`, `KERNEL: READY`, `POLICY: STRICT`).
2. **Command Prompt & Suggestions**:
   - Prompt input with the placeholder: `"What would you like me to do?"`.
   - Primary **Execute** button (and `Ctrl+Enter` shortcut).
   - One-click preset chips to immediately test:
     - 🔍 *Safe Query* (telemetry check)
     - ⚡ *Task Simulation* (workflow graph optimization)
     - ⚠️ *Sensitive Action Check* (destructive partition purge)
     - 💥 *Simulate Error State* (core neural dispatcher exception)
3. **Four-Stage Intent & Permission Pipeline**:
   - Visual multi-stage execution tracker:
     1. `Intent Parsing & Validation`
     2. `Permission & Policy Check`
     3. `Simulated Agent Execution`
     4. `Result Synthesis`
   - Real-time timestamped event stream ticker.
4. **Destructive / Sensitive Action Confirmation**:
   - Intercepts destructive patterns (e.g. `format`, `partition`, `wipe`, `rm -rf`, `drop table`, `kill kernel`).
   - Presents a high-priority hazard modal with risk classification, targeted resource, and explanation.
   - Requires explicit operator choice: **Confirm & Proceed** or **Cancel Action**.
5. **Simulated Error State**:
   - Traps simulated faults with a dedicated cybernetic fault banner showing error codes (`SIM_ERR_CORE_FAULT`), affected subsystem, fault vector, and recovery instructions.
6. **Decoupled Architecture**:
   - The UI presentation layer (`app.js`) is completely separate from the request handler (`request-handler.js`).
   - Mock responses only — no real system commands, file edits, or terminal operations are executed.
   - Easily swappable for a live AgenticOS backend API / WebSocket in future milestones.

---

## 🖥️ AgenticOS Architecture Notice

AgenticOS v0.1 Alpha is built upon Ubuntu Server Minimal without a graphical desktop environment, display server (Xorg/Wayland), or pre-installed web browser. The Prompt UI is **not** a native desktop GUI; it is an AgenticOS web-based application and system service exposed locally on port 8000 (`http://127.0.0.1:8000`).

---

## 🚀 How to Run Inside AgenticOS

### Option 1: As an AgenticOS systemd Service
```bash
sudo systemctl status agenticos-prompt-ui
sudo systemctl start agenticos-prompt-ui
```

### Option 2: Via the Safe Python Launcher (Headless CLI)
```bash
python3 /opt/agenticos/applications/prompt-ui/launch.py --no-browser
```

### Option 3: Direct Foreground Server
```bash
python3 /opt/agenticos/applications/prompt-ui/server.py
```

---

## 💻 Local Developer Testing (Windows / Linux Workstation)

1. Open a terminal in this directory:
   ```bash
   python3 server.py
   ```
2. Open your web browser and navigate to:
   ```text
   http://localhost:8000
   ```

---

## 📁 File Structure

```
AgenticOS-UI/
├── index.html           # Semantic markup, shell layout, modal & status panels
├── styles.css           # High-tech cyber dark theme, typography, glowing animations
├── app.js               # UI controller, event bindings, modal & pipeline manager
├── request-handler.js   # Decoupled mock engine, intent validation & permission auditor
├── server.py            # Zero-dependency Python HTTP server
└── README.md            # Documentation and instructions
```

---

## 🔌 Connecting to a Real AgenticOS Backend Later

To connect a live backend service in the future:
1. Open `request-handler.js`.
2. Replace the simulated methods in `MockAgenticEngine` (`executePrompt`, `confirmAction`, `cancelAction`) with standard `fetch()` or `WebSocket` calls to your AgenticOS backend endpoint (e.g., `http://localhost:5000/api/execute`).
3. Because the UI strictly subscribes to the progress callbacks (`onProgress`) and structured return schema (`{ status, responseText, auditLog, metrics }`), no changes to `index.html` or `app.js` are required.
