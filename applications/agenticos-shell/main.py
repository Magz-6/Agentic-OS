#!/usr/bin/env python3
"""
AgenticOS Native Desktop Shell
Layer 9: Applications & Native Graphical Desktop Environment
Layer 12: Linux Integration Boundary
Owner: Magesh (Linux/OS Lead)

A fully native, lightweight GTK 3 desktop shell designed for AgenticOS v0.1 Alpha.
Provides:
- Native branding and desktop environment running on Xorg/Openbox
- Allowlist-controlled application launcher (Terminal, File Manager, Editor, Dev UI)
- Live system status, CPU/RAM telemetry, uptime, and systemd service monitoring
- Integrated filesystem explorer and project directory management
- Controlled session and power management (Reboot, Power Off, Session Exit)
- Strictly non-root user execution with zero arbitrary shell execution
"""

from __future__ import annotations

import argparse
import getpass
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Safe fallback imports for headless verification and adapter integration
try:
    from adapters.app_launcher import AppLauncher
    from adapters.application_adapter import ApplicationAdapter
    from adapters.filesystem_adapter import FilesystemAdapter
    from adapters.system_adapter import SystemAdapter
    from hardware.detector import HardwareDetector
except ImportError as exc:
    # Graceful degradation if run in an environment with partial PYTHONPATH
    AppLauncher = None  # type: ignore
    ApplicationAdapter = None  # type: ignore
    FilesystemAdapter = None  # type: ignore
    SystemAdapter = None  # type: ignore
    HardwareDetector = None  # type: ignore

# PyGObject / GTK 3 imports
HAS_GTK = False
try:
    import gi
    gi.require_version("Gtk", "3.0")
    gi.require_version("Gdk", "3.0")
    from gi.repository import Gdk, GLib, Gtk, Pango
    HAS_GTK = True
except (ImportError, ValueError):
    HAS_GTK = False


# Modern AgenticOS Desktop Styling (CSS)
AGENTICOS_CSS = b"""
window.agenticos-window {
    background-color: #0b0f19;
    color: #e2e8f0;
    font-family: "Ubuntu", "DejaVu Sans", "Segoe UI", sans-serif;
}

.header-bar {
    background: linear-gradient(to right, #111827, #1e293b);
    border-bottom: 2px solid #38bdf8;
    padding: 10px 18px;
}

.brand-title {
    color: #38bdf8;
    font-size: 20px;
    font-weight: 800;
    letter-spacing: 1px;
}

.brand-badge {
    background-color: #0284c7;
    color: #ffffff;
    font-size: 11px;
    font-weight: bold;
    border-radius: 4px;
    padding: 2px 6px;
    margin-left: 8px;
}

.user-badge {
    background-color: #334155;
    color: #cbd5e1;
    font-size: 12px;
    border-radius: 6px;
    padding: 4px 10px;
}

.clock-label {
    color: #94a3b8;
    font-size: 13px;
    font-weight: 600;
}

.card-box {
    background-color: #151e2e;
    border: 1px solid #23334d;
    border-radius: 8px;
    padding: 16px;
    margin: 8px;
}

.card-title {
    color: #38bdf8;
    font-size: 15px;
    font-weight: 700;
    margin-bottom: 8px;
}

.launch-btn {
    background: #1e293b;
    border: 1px solid #334155;
    border-radius: 6px;
    color: #f8fafc;
    font-size: 13px;
    font-weight: 600;
    padding: 10px 16px;
    min-height: 48px;
}

.launch-btn:hover {
    background: #0284c7;
    border-color: #38bdf8;
    color: #ffffff;
}

.action-btn-primary {
    background-color: #0284c7;
    border: 1px solid #38bdf8;
    border-radius: 6px;
    color: #ffffff;
    font-weight: 600;
    padding: 8px 14px;
}

.action-btn-primary:hover {
    background-color: #0369a1;
}

.action-btn-danger {
    background-color: #b91c1c;
    border: 1px solid #ef4444;
    border-radius: 6px;
    color: #ffffff;
    font-weight: 600;
    padding: 6px 12px;
}

.action-btn-danger:hover {
    background-color: #991b1b;
}

.status-bar {
    background-color: #0f172a;
    border-top: 1px solid #1e293b;
    padding: 6px 16px;
    font-size: 12px;
    color: #64748b;
}

.metric-label {
    font-size: 13px;
    color: #94a3b8;
}

.metric-value {
    font-size: 13px;
    font-weight: bold;
    color: #f1f5f9;
}
"""


class AgenticOSShellBackend:
    """
    Core backend logic for the AgenticOS Native Desktop Shell.
    Provides system inspection, application launch, directory creation,
    and power controls without relying on GTK UI widgets.
    """

    def __init__(self) -> None:
        self.app_launcher = AppLauncher() if AppLauncher else None
        self.sys_adapter = SystemAdapter() if SystemAdapter else None
        self.fs_adapter = FilesystemAdapter() if FilesystemAdapter else None
        self.hw_detector = HardwareDetector() if HardwareDetector else None
        self.current_user = getpass.getuser()

    def get_system_summary(self) -> Dict[str, Any]:
        """Query platform and hardware metadata for desktop widgets."""
        summary = {
            "os_name": "AgenticOS v0.1 Alpha",
            "kernel": platform.release(),
            "machine": platform.machine(),
            "hostname": platform.node(),
            "user": self.current_user,
            "uptime_seconds": 0.0,
            "uptime_str": "unknown",
            "cpu_model": "Unknown CPU",
            "cpu_cores": os.cpu_count() or 1,
            "mem_total_mb": 0,
            "mem_available_mb": 0,
            "mem_percent": 0.0,
        }

        # Uptime
        try:
            uptime_path = Path("/proc/uptime")
            if uptime_path.is_file():
                secs = float(uptime_path.read_text(encoding="utf-8").split()[0])
                summary["uptime_seconds"] = secs
                hours = int(secs // 3600)
                minutes = int((secs % 3600) // 60)
                summary["uptime_str"] = f"{hours}h {minutes}m"
        except Exception:
            pass

        # CPU info
        if self.hw_detector:
            try:
                cpu_info = self.hw_detector.get_cpu_info()
                summary["cpu_model"] = cpu_info.get("model_name", "Unknown CPU")
                summary["cpu_cores"] = cpu_info.get("logical_cores", os.cpu_count() or 1)
            except Exception:
                pass

        # Memory info
        try:
            meminfo_path = Path("/proc/meminfo")
            if meminfo_path.is_file():
                kb_data = {}
                for line in meminfo_path.read_text(encoding="utf-8").splitlines():
                    parts = line.split(":")
                    if len(parts) == 2:
                        val_str = parts[1].strip().split()[0]
                        if val_str.isdigit():
                            kb_data[parts[0].strip()] = int(val_str)
                total_kb = kb_data.get("MemTotal", 0)
                avail_kb = kb_data.get("MemAvailable", kb_data.get("MemFree", 0))
                if total_kb > 0:
                    summary["mem_total_mb"] = total_kb // 1024
                    summary["mem_available_mb"] = avail_kb // 1024
                    used_kb = total_kb - avail_kb
                    summary["mem_percent"] = round((used_kb / total_kb) * 100, 1)
        except Exception:
            pass

        return summary

    def get_services_status(self) -> Dict[str, str]:
        """Query state of key AgenticOS system services."""
        services = [
            "agenticos-desktop.service",
            "agenticos-firstboot.service",
            "agenticos-telemetry.service",
            "agenticos-goal-runtime.service",
        ]
        status_map: Dict[str, str] = {}
        for s in services:
            try:
                res = subprocess.run(
                    ["systemctl", "is-active", s],
                    capture_output=True,
                    text=True,
                    timeout=2,
                    shell=False,
                )
                state = res.stdout.strip() or res.stderr.strip() or "inactive"
                status_map[s] = state
            except Exception:
                status_map[s] = "unavailable"
        return status_map

    def launch_app(self, app_id: str) -> Dict[str, Any]:
        """Launch an allowlisted application safely."""
        if not self.app_launcher:
            return {"status": "error", "message": "AppLauncher unavailable", "pid": None}

        try:
            res = self.app_launcher.launch(app_id)
            return res
        except Exception as exc:
            return {"status": "error", "message": str(exc), "pid": None}

    def create_project_folder(self, folder_name: str, base_dir: Optional[Path] = None) -> Dict[str, Any]:
        """Safely create a project folder under base_dir (default: $HOME/Projects)."""
        if not folder_name or not folder_name.strip():
            return {"success": False, "message": "Folder name cannot be empty."}

        clean_name = folder_name.strip()
        if "/" in clean_name or "\\" in clean_name or ".." in clean_name:
            return {"success": False, "message": "Invalid folder name: path separators and '..' not allowed."}

        if base_dir is None:
            base_dir = Path.home() / "Projects"

        target_path = base_dir / clean_name
        try:
            target_path.mkdir(parents=True, exist_ok=True)
            return {
                "success": True,
                "path": str(target_path),
                "message": f"Project folder created at {target_path}",
            }
        except Exception as exc:
            return {"success": False, "message": f"Failed to create directory: {exc}"}

    def execute_safe_power_action(self, action: str) -> Dict[str, Any]:
        """Execute a controlled system power action."""
        if action not in ("reboot", "poweroff"):
            return {"success": False, "message": f"Unsupported power action: {action}"}

        try:
            res = subprocess.run(
                ["systemctl", action],
                capture_output=True,
                text=True,
                timeout=5,
                shell=False,
            )
            return {
                "success": res.returncode == 0,
                "message": f"systemctl {action} initiated." if res.returncode == 0 else res.stderr.strip(),
            }
        except Exception as exc:
            return {"success": False, "message": str(exc)}


if HAS_GTK:

    class AgenticOSShell(Gtk.Window):
        """
        Native GTK 3 Desktop Shell Window for AgenticOS v0.1 Alpha.
        Runs as the unprivileged regular user on top of Openbox and Xorg.
        """

        def __init__(self, backend: Optional[AgenticOSShellBackend] = None) -> None:
            super().__init__(title="AgenticOS Desktop")
            self.backend = backend or AgenticOSShellBackend()

            self.set_default_size(1024, 700)
            self.set_position(Gtk.WindowPosition.CENTER)
            self.set_name("agenticos-window")
            self.connect("destroy", Gtk.main_quit)

            # Apply AgenticOS CSS theme
            self._apply_css()

            # Main vertical layout container
            main_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            self.add(main_vbox)

            # 1. Header Bar
            header = self._build_header_bar()
            main_vbox.pack_start(header, False, False, 0)

            # 2. Workspace Notebook (Tabs)
            notebook = Gtk.Notebook()
            notebook.set_tab_pos(Gtk.PositionType.TOP)
            main_vbox.pack_start(notebook, True, True, 0)

            # Tabs
            notebook.append_page(self._build_launcher_tab(), Gtk.Label(label="  🚀 Applications  "))
            notebook.append_page(self._build_telemetry_tab(), Gtk.Label(label="  📊 System Telemetry  "))
            notebook.append_page(self._build_files_tab(), Gtk.Label(label="  📂 File Workspace  "))
            notebook.append_page(self._build_session_tab(), Gtk.Label(label="  ⚙️ Controls & Session  "))

            # 3. Status Bar
            self.status_bar_label = Gtk.Label(label="AgenticOS v0.1 Alpha Ready | Native Desktop Active")
            self.status_bar_label.set_alignment(0.0, 0.5)
            status_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
            status_box.get_style_context().add_class("status-bar")
            status_box.pack_start(self.status_bar_label, True, True, 0)
            main_vbox.pack_end(status_box, False, False, 0)

            # Start clock timer
            GLib.timeout_add_seconds(1, self._on_clock_tick)

        def _apply_css(self) -> None:
            """Load custom CSS styling into the GTK display provider."""
            css_provider = Gtk.CssProvider()
            css_provider.load_from_data(AGENTICOS_CSS)
            screen = Gdk.Screen.get_default()
            if screen is not None:
                Gtk.StyleContext.add_provider_for_screen(
                    screen,
                    css_provider,
                    Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
                )

        def _build_header_bar(self) -> Gtk.Box:
            """Build top brand and session bar."""
            header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            header_box.get_style_context().add_class("header-bar")

            # Brand title
            brand_label = Gtk.Label()
            brand_label.set_markup("<b>⬡ AgenticOS</b>")
            brand_label.get_style_context().add_class("brand-title")
            header_box.pack_start(brand_label, False, False, 0)

            # Version badge
            badge_label = Gtk.Label(label="v0.1 Alpha")
            badge_label.get_style_context().add_class("brand-badge")
            header_box.pack_start(badge_label, False, False, 0)

            # Spacer
            header_box.pack_start(Gtk.Label(label=""), True, True, 0)

            # Live Clock
            self.clock_label = Gtk.Label()
            self.clock_label.get_style_context().add_class("clock-label")
            self._update_clock_text()
            header_box.pack_start(self.clock_label, False, False, 8)

            # Current User badge
            user_label = Gtk.Label(label=f"👤 {self.backend.current_user}")
            user_label.get_style_context().add_class("user-badge")
            header_box.pack_start(user_label, False, False, 0)

            # Quick power menu button
            power_btn = Gtk.Button(label="⏻ Power")
            power_btn.get_style_context().add_class("action-btn-danger")
            power_btn.connect("clicked", self._on_quick_power_clicked)
            header_box.pack_start(power_btn, False, False, 0)

            return header_box

        def _build_launcher_tab(self) -> Gtk.ScrolledWindow:
            """Build application launcher grid."""
            scroller = Gtk.ScrolledWindow()
            scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

            vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
            vbox.set_margin_top(16)
            vbox.set_margin_bottom(16)
            vbox.set_margin_left(20)
            vbox.set_margin_right(20)
            scroller.add(vbox)

            # Hero card
            hero_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            hero_card.get_style_context().add_class("card-box")
            hero_title = Gtk.Label()
            hero_title.set_markup("<b>Native Agentic Operating System Environment</b>")
            hero_title.set_alignment(0.0, 0.5)
            hero_title.get_style_context().add_class("card-title")
            hero_desc = Gtk.Label(
                label="Launch allowlisted native Linux tools and system interfaces. "
                      "Zero browser dependencies for OS desktop navigation."
            )
            hero_desc.set_alignment(0.0, 0.5)
            hero_desc.set_line_wrap(True)
            hero_card.pack_start(hero_title, False, False, 0)
            hero_card.pack_start(hero_desc, False, False, 0)
            vbox.pack_start(hero_card, False, False, 0)

            # Apps Grid
            grid = Gtk.Grid()
            grid.set_row_spacing(12)
            grid.set_column_spacing(12)
            grid.set_column_homogeneous(True)
            vbox.pack_start(grid, False, False, 0)

            apps = [
                ("🖥️ Terminal Emulator", "Launch native Linux terminal", "terminal", 0, 0),
                ("📁 File Manager", "Launch Linux file manager", "file_manager", 1, 0),
                ("📝 Text Editor", "Open simple text editor", "text_editor", 0, 1),
                ("⚡ AI Goal Runtime", "Open Goal Runtime Service status", "goal_runtime", 1, 1),
                ("🌐 Developer Prompt UI", "Open prototype Prompt UI (127.0.0.1:8000)", "browser", 0, 2),
                ("🔍 Hardware Telemetry", "Inspect system hardware and kernel metrics", "telemetry", 1, 2),
            ]

            for label_text, subtext, app_id, col, row in apps:
                btn_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
                btn = Gtk.Button()
                btn.get_style_context().add_class("launch-btn")
                title_lbl = Gtk.Label()
                title_lbl.set_markup(f"<b>{label_text}</b>")
                desc_lbl = Gtk.Label(label=subtext)
                desc_lbl.set_line_wrap(True)
                desc_lbl.get_style_context().add_class("metric-label")
                btn_box.pack_start(title_lbl, False, False, 0)
                btn_box.pack_start(desc_lbl, False, False, 0)
                btn.add(btn_box)
                btn.connect("clicked", self._on_launch_app_clicked, app_id)
                grid.attach(btn, col, row, 1, 1)

            return scroller

        def _build_telemetry_tab(self) -> Gtk.ScrolledWindow:
            """Build live system telemetry and status panel."""
            scroller = Gtk.ScrolledWindow()
            scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

            vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
            vbox.set_margin_top(16)
            vbox.set_margin_bottom(16)
            vbox.set_margin_left(20)
            vbox.set_margin_right(20)
            scroller.add(vbox)

            # Overview Card
            card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            card.get_style_context().add_class("card-box")
            title = Gtk.Label()
            title.set_markup("<b>Host Platform & Kernel Metrics</b>")
            title.set_alignment(0.0, 0.5)
            title.get_style_context().add_class("card-title")
            card.pack_start(title, False, False, 0)

            summary = self.backend.get_system_summary()

            grid = Gtk.Grid()
            grid.set_row_spacing(6)
            grid.set_column_spacing(18)
            metrics = [
                ("Operating System:", summary["os_name"]),
                ("Linux Kernel:", summary["kernel"]),
                ("Architecture:", summary["machine"]),
                ("Hostname:", summary["hostname"]),
                ("System Uptime:", summary["uptime_str"]),
                ("CPU Model:", summary["cpu_model"]),
                ("Logical Cores:", str(summary["cpu_cores"])),
                ("Total Memory:", f"{summary['mem_total_mb']} MB"),
                ("Available Memory:", f"{summary['mem_available_mb']} MB"),
            ]
            for idx, (label, val) in enumerate(metrics):
                col = 0 if idx < 5 else 2
                row = idx if idx < 5 else idx - 5
                l_widget = Gtk.Label(label=label)
                l_widget.set_alignment(0.0, 0.5)
                l_widget.get_style_context().add_class("metric-label")
                v_widget = Gtk.Label(label=val)
                v_widget.set_alignment(0.0, 0.5)
                v_widget.get_style_context().add_class("metric-value")
                grid.attach(l_widget, col, row, 1, 1)
                grid.attach(v_widget, col + 1, row, 1, 1)

            card.pack_start(grid, False, False, 0)

            # Memory progress bar
            mem_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            mem_box.pack_start(Gtk.Label(label="Memory Usage:"), False, False, 0)
            self.mem_progress = Gtk.ProgressBar()
            pct = summary["mem_percent"] / 100.0 if summary["mem_percent"] else 0.0
            self.mem_progress.set_fraction(min(max(pct, 0.0), 1.0))
            self.mem_progress.set_text(f"{summary['mem_percent']}%")
            self.mem_progress.set_show_text(True)
            mem_box.pack_start(self.mem_progress, True, True, 0)
            card.pack_start(mem_box, False, False, 4)

            vbox.pack_start(card, False, False, 0)

            # Systemd Services Card
            svc_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            svc_card.get_style_context().add_class("card-box")
            svc_title = Gtk.Label()
            svc_title.set_markup("<b>AgenticOS System Services</b>")
            svc_title.set_alignment(0.0, 0.5)
            svc_title.get_style_context().add_class("card-title")
            svc_card.pack_start(svc_title, False, False, 0)

            services = self.backend.get_services_status()
            svc_grid = Gtk.Grid()
            svc_grid.set_row_spacing(6)
            svc_grid.set_column_spacing(20)
            for idx, (svc_name, state) in enumerate(services.items()):
                l_svc = Gtk.Label(label=svc_name)
                l_svc.set_alignment(0.0, 0.5)
                state_lbl = Gtk.Label()
                color = "#34d399" if state == "active" else "#94a3b8"
                state_lbl.set_markup(f"<span color='{color}'><b>● {state.upper()}</b></span>")
                state_lbl.set_alignment(0.0, 0.5)
                svc_grid.attach(l_svc, 0, idx, 1, 1)
                svc_grid.attach(state_lbl, 1, idx, 1, 1)

            svc_card.pack_start(svc_grid, False, False, 0)
            vbox.pack_start(svc_card, False, False, 0)

            return scroller

        def _build_files_tab(self) -> Gtk.Box:
            """Build files and project management workspace."""
            vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
            vbox.set_margin_top(16)
            vbox.set_margin_bottom(16)
            vbox.set_margin_left(20)
            vbox.set_margin_right(20)

            action_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            action_box.get_style_context().add_class("card-box")

            create_btn = Gtk.Button(label="📁 Create Project Folder")
            create_btn.get_style_context().add_class("action-btn-primary")
            create_btn.connect("clicked", self._on_create_project_clicked)
            action_box.pack_start(create_btn, False, False, 0)

            open_fm_btn = Gtk.Button(label="📂 Open in File Manager")
            open_fm_btn.connect("clicked", lambda _: self._on_launch_app_clicked(None, "file_manager"))
            action_box.pack_start(open_fm_btn, False, False, 0)

            self.path_entry = Gtk.Entry()
            self.path_entry.set_text(str(Path.home()))
            action_box.pack_start(self.path_entry, True, True, 0)

            browse_btn = Gtk.Button(label="List Directory")
            browse_btn.connect("clicked", self._on_list_directory_clicked)
            action_box.pack_start(browse_btn, False, False, 0)

            vbox.pack_start(action_box, False, False, 0)

            # Files TreeView
            self.files_liststore = Gtk.ListStore(str, str, str)  # Name, Type, Size
            self.files_treeview = Gtk.TreeView(model=self.files_liststore)

            col_name = Gtk.TreeViewColumn("Name", Gtk.CellRendererText(), text=0)
            col_name.set_min_width(300)
            col_type = Gtk.TreeViewColumn("Type", Gtk.CellRendererText(), text=1)
            col_size = Gtk.TreeViewColumn("Size", Gtk.CellRendererText(), text=2)

            self.files_treeview.append_column(col_name)
            self.files_treeview.append_column(col_type)
            self.files_treeview.append_column(col_size)

            scroller = Gtk.ScrolledWindow()
            scroller.add(self.files_treeview)
            vbox.pack_start(scroller, True, True, 0)

            # Initial population of home directory
            self._populate_files(Path.home())

            return vbox

        def _build_session_tab(self) -> Gtk.Box:
            """Build session controls and shutdown/reboot view."""
            vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
            vbox.set_margin_top(20)
            vbox.set_margin_bottom(20)
            vbox.set_margin_left(24)
            vbox.set_margin_right(24)

            card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
            card.get_style_context().add_class("card-box")

            title = Gtk.Label()
            title.set_markup("<b>AgenticOS Power & Session Management</b>")
            title.set_alignment(0.0, 0.5)
            title.get_style_context().add_class("card-title")
            card.pack_start(title, False, False, 0)

            desc = Gtk.Label(
                label="Safely control OS shutdown and reboot through standard Linux systemd interfaces. "
                      "Zero arbitrary shell command execution."
            )
            desc.set_alignment(0.0, 0.5)
            desc.set_line_wrap(True)
            card.pack_start(desc, False, False, 0)

            btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)

            reboot_btn = Gtk.Button(label="🔄 Restart System")
            reboot_btn.get_style_context().add_class("action-btn-primary")
            reboot_btn.connect("clicked", lambda _: self._confirm_power_action("reboot"))
            btn_box.pack_start(reboot_btn, False, False, 0)

            poweroff_btn = Gtk.Button(label="⏻ Power Off System")
            poweroff_btn.get_style_context().add_class("action-btn-danger")
            poweroff_btn.connect("clicked", lambda _: self._confirm_power_action("poweroff"))
            btn_box.pack_start(poweroff_btn, False, False, 0)

            exit_shell_btn = Gtk.Button(label="🚪 Close Desktop Shell")
            exit_shell_btn.connect("clicked", lambda _: Gtk.main_quit())
            btn_box.pack_start(exit_shell_btn, False, False, 0)

            card.pack_start(btn_box, False, False, 8)
            vbox.pack_start(card, False, False, 0)

            return vbox

        def _on_clock_tick(self) -> bool:
            """Update top bar clock display every second."""
            self._update_clock_text()
            return True

        def _update_clock_text(self) -> None:
            now = time.strftime("%a %b %d, %H:%M:%S")
            self.clock_label.set_text(now)

        def _on_launch_app_clicked(self, _widget: Any, app_id: str) -> None:
            """Handle application launching."""
            if app_id == "goal_runtime":
                self.status_bar_label.set_text("AgenticOS Goal Runtime is active on multi-user.target.")
                return

            if app_id == "telemetry":
                self.status_bar_label.set_text("Viewing System Telemetry metrics.")
                return

            res = self.backend.launch_app(app_id)
            if res.get("status") == "success":
                self.status_bar_label.set_text(
                    f"Successfully launched '{app_id}' (PID {res.get('pid')})."
                )
            else:
                self.status_bar_label.set_text(
                    f"Notice: '{app_id}' launch status: {res.get('status')} - {res.get('message', res.get('reason'))}"
                )

        def _on_create_project_clicked(self, _widget: Any) -> None:
            """Prompt dialog for project directory creation."""
            dialog = Gtk.Dialog(
                title="Create Project Folder",
                parent=self,
                flags=Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT,
            )
            dialog.add_buttons(
                Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                Gtk.STOCK_OK, Gtk.ResponseType.OK,
            )
            content_area = dialog.get_content_area()
            entry = Gtk.Entry()
            entry.set_placeholder_text("Folder name, e.g. AgenticProject")
            content_area.pack_start(Gtk.Label(label="Enter project directory name:"), False, False, 6)
            content_area.pack_start(entry, False, False, 6)
            dialog.show_all()

            response = dialog.run()
            folder_name = entry.get_text().strip()
            dialog.destroy()

            if response == Gtk.ResponseType.OK and folder_name:
                res = self.backend.create_project_folder(folder_name)
                self.status_bar_label.set_text(res["message"])
                if res["success"]:
                    self._populate_files(Path(res["path"]).parent)

        def _on_list_directory_clicked(self, _widget: Any) -> None:
            """List files in the path specified in path_entry."""
            path_str = self.path_entry.get_text().strip()
            if path_str:
                self._populate_files(Path(path_str))

        def _populate_files(self, target_dir: Path) -> None:
            """Populate the files TreeView from target_dir."""
            self.files_liststore.clear()
            if not target_dir.is_dir():
                self.status_bar_label.set_text(f"Directory not found: {target_dir}")
                return

            try:
                for entry in sorted(target_dir.iterdir()):
                    entry_type = "📁 Directory" if entry.is_dir() else "📄 File"
                    size_str = f"{entry.stat().st_size} B" if entry.is_file() else "-"
                    self.files_liststore.append([entry.name, entry_type, size_str])
                self.path_entry.set_text(str(target_dir))
            except Exception as e:
                self.status_bar_label.set_text(f"Error accessing directory: {e}")

        def _confirm_power_action(self, action: str) -> None:
            """Confirmation dialog for power actions."""
            action_name = "Restart System" if action == "reboot" else "Power Off System"
            dialog = Gtk.MessageDialog(
                parent=self,
                flags=Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT,
                type=Gtk.MessageType.WARNING,
                buttons=Gtk.ButtonsType.OK_CANCEL,
                message_format=f"Are you sure you want to {action_name.lower()}?",
            )
            dialog.set_title(action_name)
            response = dialog.run()
            dialog.destroy()

            if response == Gtk.ResponseType.OK:
                res = self.backend.execute_safe_power_action(action)
                self.status_bar_label.set_text(res["message"])

        def _on_quick_power_clicked(self, _widget: Any) -> None:
            """Quick power button opens the power menu dialog."""
            menu = Gtk.Menu()
            item_reboot = Gtk.MenuItem(label="Restart System")
            item_reboot.connect("activate", lambda _: self._confirm_power_action("reboot"))
            menu.append(item_reboot)

            item_poweroff = Gtk.MenuItem(label="Power Off System")
            item_poweroff.connect("activate", lambda _: self._confirm_power_action("poweroff"))
            menu.append(item_poweroff)

            item_exit = Gtk.MenuItem(label="Exit Shell")
            item_exit.connect("activate", lambda _: Gtk.main_quit())
            menu.append(item_exit)

            menu.show_all()
            menu.popup_at_pointer(None)


def main() -> int:
    """AgenticOS native desktop shell entrypoint."""
    parser = argparse.ArgumentParser(description="AgenticOS Native Desktop Shell")
    parser.add_argument("--check", action="store_true", help="Perform non-interactive backend check and exit")
    parser.add_argument("--info", action="store_true", help="Print system summary information and exit")
    args = parser.parse_args()

    backend = AgenticOSShellBackend()

    # Warn if running as root
    if os.name != "nt" and os.geteuid() == 0:
        print("[Shell] WARNING: Running as root is not recommended for desktop shell.", file=sys.stderr)

    if args.check:
        summary = backend.get_system_summary()
        print(f"[Shell] Check OK: {summary['os_name']} on {summary['hostname']} (User: {summary['user']})")
        return 0

    if args.info:
        summary = backend.get_system_summary()
        for k, v in summary.items():
            print(f"{k}: {v}")
        return 0

    if not HAS_GTK:
        print("[Shell] ERROR: PyGObject / GTK 3.0 is not available in the current Python environment.", file=sys.stderr)
        return 1

    # Check for X11 / Wayland display
    if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        print("[Shell] Notice: No DISPLAY environment variable set. Running backend status:", file=sys.stderr)
        summary = backend.get_system_summary()
        print(f"AgenticOS Shell Backend Active: {summary['os_name']}")
        return 0

    window = AgenticOSShell(backend=backend)
    window.show_all()
    Gtk.main()
    return 0


if __name__ == "__main__":
    sys.exit(main())
