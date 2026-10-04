#!/usr/bin/env python3
"""
AgenticOS Desktop Session Runner
Layer 9: Applications & Desktop Integration Boundary
Layer 12: Linux Integration Boundary
Owner: Magesh (Linux/OS Lead)

Starts the AgenticOS graphical session:
1. Waits for First-Boot completion (if pending) and resolves the non-root regular user.
2. Quits Plymouth if active to release the framebuffer / DRM device.
3. Starts Xorg on display :0 (vt7).
4. Waits for the X11 server socket to be ready.
5. Configures X access for the local unprivileged user.
6. Launches Openbox Window Manager as the unprivileged user.
7. Launches Falkon browser pointing to http://127.0.0.1:8000 as the unprivileged user.
8. Monitors child processes and cleanly terminates on SIGTERM/SIGINT.
"""

import os
import pwd
import signal
import subprocess
import sys
import time
from pathlib import Path

FIRSTBOOT_MARKER = Path("/var/lib/agenticos/firstboot-completed")
PROMPT_UI_URL = "http://127.0.0.1:8000"
DISPLAY_NUM = ":0"
VT_NUM = "vt7"
X11_SOCKET = Path(f"/tmp/.X11-unix/X{DISPLAY_NUM.lstrip(':')}")


def resolve_user(marker_path: Path = FIRSTBOOT_MARKER, passwd_path: Path = Path("/etc/passwd")) -> str | None:
    """
    Determine the primary interactive non-root user.
    Checks First-Boot marker file first, then scans passwd for regular users (UID >= 1000).
    """
    if marker_path.is_file():
        try:
            content = marker_path.read_text(encoding="utf-8")
            for line in content.splitlines():
                if line.startswith("CREATED_USER="):
                    user = line.split("=", 1)[1].strip()
                    if user:
                        try:
                            pwd.getpwnam(user)
                            return user
                        except KeyError:
                            pass
        except Exception as e:
            print(f"[Desktop] Warning reading marker file: {e}", file=sys.stderr)

    # Fallback: scan passwd entries for regular user with UID 1000-59999
    if passwd_path.is_file():
        try:
            for user_entry in pwd.getpwall():
                if 1000 <= user_entry.pw_uid < 65534:
                    return user_entry.pw_name
        except Exception as e:
            print(f"[Desktop] Warning reading passwd entries: {e}", file=sys.stderr)

    return None


def wait_for_user(timeout_seconds: float = 300.0, poll_interval: float = 1.0) -> str:
    """
    Wait for First-Boot setup to create a user account.
    """
    print("[Desktop] Resolving AgenticOS user account...", flush=True)
    start_time = time.time()
    while time.time() - start_time < timeout_seconds:
        user = resolve_user()
        if user:
            print(f"[Desktop] Resolved AgenticOS user: '{user}'", flush=True)
            return user
        time.sleep(poll_interval)

    raise TimeoutError("Timed out waiting for First-Boot user account creation.")


def release_plymouth() -> None:
    """Ensure Plymouth is quit so Xorg can claim the DRM/KMS device."""
    plymouth_bin = Path("/usr/bin/plymouth")
    if plymouth_bin.is_file():
        try:
            subprocess.run([str(plymouth_bin), "quit"], check=False, timeout=3)
        except Exception:
            pass


def start_x_server(display: str = DISPLAY_NUM, vt: str = VT_NUM) -> subprocess.Popen:
    """
    Start Xorg display server.
    """
    xorg_bin = "/usr/bin/Xorg" if os.path.exists("/usr/bin/Xorg") else "/usr/bin/X"
    cmd = [
        xorg_bin,
        display,
        vt,
        "-nolisten",
        "tcp",
        "-noreset",
    ]
    print(f"[Desktop] Starting X server: {' '.join(cmd)}", flush=True)
    return subprocess.Popen(
        cmd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def switch_vt(vt: str = VT_NUM, chvt_path: str | None = None) -> bool:
    """
    Switch active virtual console to the specified VT (e.g. vt7 -> 7).
    Ensures the Linux display switches to the graphical session.
    """
    vt_num = vt.lstrip("vt")
    if chvt_path is None:
        chvt_bin = "/usr/bin/chvt" if os.path.exists("/usr/bin/chvt") else "/bin/chvt"
    else:
        chvt_bin = chvt_path

    if os.path.exists(chvt_bin):
        try:
            print(f"[Desktop] Switching console to VT {vt_num} via {chvt_bin}...", flush=True)
            res = subprocess.run([chvt_bin, vt_num], check=False, timeout=3)
            return res.returncode == 0
        except Exception as e:
            print(f"[Desktop] Warning switching VT: {e}", file=sys.stderr)
            return False
    return False


def wait_for_x_server(socket_path: Path = X11_SOCKET, timeout_seconds: float = 15.0) -> bool:
    """
    Wait for X11 domain socket to become available.
    """
    start_time = time.time()
    while time.time() - start_time < timeout_seconds:
        if socket_path.is_socket():
            print(f"[Desktop] X server socket ready at {socket_path}", flush=True)
            return True
        time.sleep(0.1)
    return False


def get_user_env(username: str, display: str = DISPLAY_NUM) -> tuple[dict[str, str], int, int]:
    """
    Prepare unprivileged user environment variables, XDG runtime, and UID/GID.
    """
    pw = pwd.getpwnam(username)
    uid = pw.pw_uid
    gid = pw.pw_gid
    home = pw.pw_dir

    # Ensure /run/user/<uid> exists with correct permissions
    xdg_runtime = Path(f"/run/user/{uid}")
    try:
        xdg_runtime.mkdir(parents=True, exist_ok=True)
        os.chown(xdg_runtime, uid, gid)
        os.chmod(xdg_runtime, 0o700)
    except Exception as e:
        print(f"[Desktop] Warning preparing XDG runtime dir: {e}", file=sys.stderr)

    env = dict(os.environ)
    env.update({
        "DISPLAY": display,
        "HOME": home,
        "USER": username,
        "LOGNAME": username,
        "SHELL": pw.pw_shell or "/bin/bash",
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "XDG_RUNTIME_DIR": str(xdg_runtime),
    })
    return env, uid, gid


def allow_x_access(username: str, env: dict[str, str]) -> None:
    """Grant the local unprivileged user permission to connect to X."""
    xhost_bin = Path("/usr/bin/xhost")
    if xhost_bin.is_file():
        try:
            subprocess.run([str(xhost_bin), f"+SI:localuser:{username}"], env=env, check=False, timeout=3)
        except Exception:
            try:
                subprocess.run([str(xhost_bin), "+local:"], env=env, check=False, timeout=3)
            except Exception:
                pass


def launch_session(username: str, url: str = PROMPT_UI_URL, display: str = DISPLAY_NUM) -> tuple[subprocess.Popen, subprocess.Popen]:
    """
    Launch Openbox window manager and the native AgenticOS GTK shell
    as the unprivileged user.
    """
    env, uid, gid = get_user_env(username, display)
    allow_x_access(username, env)

    # 1. Start Openbox Window Manager as unprivileged user
    openbox_bin = "/usr/bin/openbox-session" if os.path.exists("/usr/bin/openbox-session") else "/usr/bin/openbox"
    print(f"[Desktop] Starting Openbox as '{username}' (UID {uid})...", flush=True)
    openbox_proc = subprocess.Popen(
        [openbox_bin],
        user=uid,
        group=gid,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # Give Openbox a moment to map the root window
    time.sleep(1.0)

    # 2. Start native AgenticOS GTK shell as unprivileged user
    shell_bin = "/opt/agenticos/applications/agenticos-shell/main.py"
    print(f"[Desktop] Starting AgenticOS native shell as '{username}'...", flush=True)
    shell_proc = subprocess.Popen(
        ["/usr/bin/python3", shell_bin],
        user=uid,
        group=gid,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    return openbox_proc, shell_proc


if __name__ == "__main__":
    sys.exit(main())
