#!/usr/bin/env python3
"""
AgenticOS Prompt UI - Safe Desktop & CLI Launcher
Layer 9: Applications & Desktop Integration Boundary
Owner: Magesh (Linux/OS Lead)

Starts the zero-dependency Python UI server (if not already running)
and opens the Prompt UI in the system's default web browser.

Guarantees:
- Unprivileged user-space operation (zero sudo/root).
- Direct execution without shell wrappers (shell=False).
- Non-destructive and fully reversible.
"""

import argparse
import http.client
import json
import os
import signal
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

DEFAULT_PORT = 8000
DEFAULT_HOST = "127.0.0.1"
UI_DIR = Path(__file__).resolve().parent
PID_FILE = UI_DIR / ".server.pid"
SERVER_SCRIPT = UI_DIR / "server.py"


def is_server_responding(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> bool:
    """Check if the Prompt UI server is already listening and responding."""
    try:
        conn = http.client.HTTPConnection(host, port, timeout=1.0)
        conn.request("HEAD", "/")
        response = conn.getresponse()
        conn.close()
        return response.status in (200, 301, 302, 304)
    except Exception:
        return False


def start_server_background(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> int:
    """Start server.py as a background process and save PID."""
    if is_server_responding(host, port):
        # Already running
        if PID_FILE.is_file():
            try:
                return int(PID_FILE.read_text().strip())
            except ValueError:
                pass
        return 0

    log_path = UI_DIR / "server.log"
    with open(log_path, "a", encoding="utf-8") as log_file:
        proc = subprocess.Popen(
            [sys.executable, str(SERVER_SCRIPT)],
            cwd=str(UI_DIR),
            stdin=subprocess.DEVNULL,
            stdout=log_file,
            stderr=log_file,
            close_fds=True,
            shell=False,
            start_new_session=True,
        )

    PID_FILE.write_text(str(proc.pid), encoding="utf-8")

    # Wait up to 3 seconds for server to bind and respond
    for _ in range(30):
        time.sleep(0.1)
        if is_server_responding(host, port):
            break

    return proc.pid


def stop_server() -> bool:
    """Stop the background server if PID is recorded."""
    if not PID_FILE.is_file():
        return False

    try:
        pid = int(PID_FILE.read_text().strip())
        if pid > 0:
            os.kill(pid, signal.SIGTERM)
            time.sleep(0.3)
    except (ValueError, ProcessLookupError, PermissionError):
        pass
    finally:
        if PID_FILE.is_file():
            PID_FILE.unlink(missing_ok=True)
    return True


def launch(no_browser: bool = False, dry_run: bool = False) -> dict:
    """Main launch workflow."""
    url = f"http://{DEFAULT_HOST}:{DEFAULT_PORT}"
    
    if dry_run:
        return {
            "status": "dry_run",
            "url": url,
            "server_script": str(SERVER_SCRIPT),
            "pid_file": str(PID_FILE),
            "is_running": is_server_responding(),
        }

    pid = start_server_background()
    running = is_server_responding()

    opened_browser = False
    if running and not no_browser:
        opened_browser = webbrowser.open(url)

    return {
        "status": "launched" if running else "failed",
        "url": url,
        "pid": pid,
        "running": running,
        "browser_opened": opened_browser,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="AgenticOS Prompt UI Launcher")
    parser.add_argument("--no-browser", action="store_true", help="Start server without launching browser")
    parser.add_argument("--dry-run", action="store_true", help="Inspect configuration without starting processes")
    parser.add_argument("--status", action="store_true", help="Check if UI server is running")
    parser.add_argument("--stop", action="store_true", help="Stop background UI server")
    parser.add_argument("--json", action="store_true", help="Output results in JSON format")

    args = parser.parse_args()

    if args.status:
        res = {
            "running": is_server_responding(),
            "url": f"http://{DEFAULT_HOST}:{DEFAULT_PORT}",
            "pid_file_exists": PID_FILE.is_file(),
        }
    elif args.stop:
        stopped = stop_server()
        res = {"stopped": stopped, "running": is_server_responding()}
    else:
        res = launch(no_browser=args.no_browser, dry_run=args.dry_run)

    if args.json:
        print(json.dumps(res, indent=2))
    else:
        if args.status:
            state = "RUNNING" if res["running"] else "STOPPED"
            print(f"AgenticOS Prompt UI Server is {state} ({res['url']})")
        elif args.stop:
            print("AgenticOS Prompt UI Server stopped.")
        else:
            if res.get("status") == "dry_run":
                print(f"[Dry Run] Prompt UI targets: {res['url']}")
            elif res.get("running"):
                print("=" * 60)
                print("  AgenticOS Prompt UI Launched Successfully")
                print("=" * 60)
                print(f"  URL:     {res['url']}")
                print(f"  PID:     {res['pid']}")
                print(f"  Browser: {'Launched' if res['browser_opened'] else 'Manual (see URL)'}")
                print("=" * 60)
            else:
                print("ERROR: Failed to start Prompt UI server.", file=sys.stderr)
                sys.exit(1)


if __name__ == "__main__":
    main()
