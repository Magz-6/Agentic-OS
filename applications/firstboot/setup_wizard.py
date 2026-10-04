#!/usr/bin/env python3
"""
AgenticOS - First-Boot Account Setup Wizard
Layer 12: Agentic Microkernel / Linux Integration Boundary
Component: First-Run Account Provisioning

Presents an interactive setup on tty1 on first boot, validates credentials,
creates a local non-root user via standard Linux OS mechanisms (useradd/chpasswd),
records the completion marker, and transitions cleanly to the standard login.
"""

import argparse
import datetime
import getpass
import os
import re
import subprocess
import sys
import time
from pathlib import Path

# Completion marker location
DEFAULT_MARKER_PATH = "/var/lib/agenticos/firstboot-completed"
DEFAULT_PASSWD_PATH = "/etc/passwd"

# System reserved usernames that should never be registered as primary interactive user
RESERVED_USERNAMES = {
    "root",
    "daemon",
    "bin",
    "sys",
    "sync",
    "games",
    "man",
    "lp",
    "mail",
    "news",
    "uucp",
    "proxy",
    "www-data",
    "backup",
    "list",
    "irc",
    "gnats",
    "nobody",
    "_apt",
    "systemd-network",
    "systemd-resolve",
    "systemd-timesync",
    "systemd-coredump",
    "messagebus",
    "sshd",
    "syslog",
    "uuidd",
    "tcpdump",
}

USERNAME_REGEX = re.compile(r"^[a-z_][a-z0-9_-]{0,31}$")


def validate_username(username: str, passwd_path: str = DEFAULT_PASSWD_PATH) -> tuple[bool, str]:
    """
    Validate POSIX-compliant Linux username against format, length, and reserved accounts.
    """
    if not username:
        return False, "Username cannot be empty."

    if len(username) > 32:
        return False, "Username must be 32 characters or fewer."

    if not USERNAME_REGEX.match(username):
        return (
            False,
            "Username must begin with a lowercase letter or underscore, "
            "and contain only lowercase letters, digits, underscores, or hyphens.",
        )

    if username in RESERVED_USERNAMES:
        return False, f"Username '{username}' is reserved by the system."

    # Check if user already exists in passwd file
    try:
        if os.path.exists(passwd_path):
            with open(passwd_path, "r", encoding="utf-8") as f:
                for line in f:
                    parts = line.strip().split(":")
                    if parts and parts[0] == username:
                        return False, f"User '{username}' already exists."
    except Exception as e:
        return False, f"Error checking existing accounts: {e}"

    return True, ""


def validate_password(password: str, confirm: str) -> tuple[bool, str]:
    """
    Validate password non-emptiness, length, and confirmation matching.
    """
    if not password:
        return False, "Password cannot be empty."

    if len(password) < 4:
        return False, "Password must be at least 4 characters long."

    if password != confirm:
        return False, "Passwords do not match."

    return True, ""


def is_setup_completed(
    marker_path: str = DEFAULT_MARKER_PATH, passwd_path: str = DEFAULT_PASSWD_PATH
) -> bool:
    """
    Detect whether first-boot account setup has already been completed.
    Returns True if marker file exists or if an interactive non-root user (UID >= 1000) exists.
    """
    if os.path.exists(marker_path):
        return True

    # Check if a non-root regular user (UID in range 1000-59999) already exists
    if os.path.exists(passwd_path):
        try:
            with open(passwd_path, "r", encoding="utf-8") as f:
                for line in f:
                    parts = line.strip().split(":")
                    if len(parts) >= 3:
                        try:
                            uid = int(parts[2])
                            # Standard Linux non-root regular users start at UID 1000
                            # Exclude nobody (usually 65534)
                            if 1000 <= uid < 65534:
                                return True
                        except ValueError:
                            continue
        except Exception:
            pass

    return False


def check_setup(
    marker_path: str = DEFAULT_MARKER_PATH, passwd_path: str = DEFAULT_PASSWD_PATH
) -> int:
    """
    Check if first-boot account setup is completed.
    Returns integer exit code:
      0 if setup is COMPLETED
      1 if setup is REQUIRED
    """
    if is_setup_completed(marker_path, passwd_path):
        print("First-boot setup is COMPLETED.")
        return 0
    print("First-boot setup is REQUIRED.")
    return 1


def create_local_user(
    username: str,
    password: str,
    dry_run: bool = False,
    marker_path: str = DEFAULT_MARKER_PATH,
) -> bool:
    """
    Create a local Linux user using standard useradd and chpasswd commands.
    Writes the completion marker upon success.
    """
    if dry_run:
        # In dry run mode, do not execute system modification commands
        marker_p = Path(marker_path)
        marker_p.parent.mkdir(parents=True, exist_ok=True)
        marker_p.write_text(
            f"AGENTICOS_FIRSTBOOT_COMPLETED=true\n"
            f"TIMESTAMP={datetime.datetime.now(datetime.timezone.utc).isoformat()}\n"
            f"CREATED_USER={username}\n"
            f"MODE=dry_run\n",
            encoding="utf-8",
        )
        return True

    # Check root privileges
    if os.geteuid() != 0:
        raise PermissionError("Account creation requires root privileges.")

    # 1. Create user with useradd
    # -m: create home directory
    # -s /bin/bash: default bash shell
    # -G sudo,adm: grant administrative privilege groups
    cmd_useradd = ["useradd", "-m", "-s", "/bin/bash", "-G", "sudo,adm", username]
    res = subprocess.run(cmd_useradd, capture_output=True, text=True)
    if res.returncode != 0:
        # If useradd fails because groups don't exist, retry with just sudo or default
        cmd_fallback = ["useradd", "-m", "-s", "/bin/bash", username]
        res_fb = subprocess.run(cmd_fallback, capture_output=True, text=True)
        if res_fb.returncode != 0:
            raise RuntimeError(f"useradd failed: {res.stderr or res_fb.stderr}")

    # 2. Set password via chpasswd (native PAM/shadow mechanism)
    proc = subprocess.Popen(
        ["chpasswd"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    _, stderr_cp = proc.communicate(f"{username}:{password}\n")
    if proc.returncode != 0:
        raise RuntimeError(f"chpasswd failed: {stderr_cp}")

    # 3. Mark setup as completed
    marker_p = Path(marker_path)
    marker_p.parent.mkdir(parents=True, exist_ok=True)
    marker_p.write_text(
        f"AGENTICOS_FIRSTBOOT_COMPLETED=true\n"
        f"TIMESTAMP={datetime.datetime.now(datetime.timezone.utc).isoformat()}\n"
        f"CREATED_USER={username}\n",
        encoding="utf-8",
    )
    os.chmod(marker_path, 0o644)
    return True


def display_banner() -> None:
    """Print the AgenticOS Welcome / Setup banner."""
    banner = """
======================================================================
                         AgenticOS v0.1 Alpha
                  First-Time Account Setup Wizard
======================================================================
 Welcome to AgenticOS.
 To initialize the system, create your local user account below.
 No default or hardcoded credentials exist on this system.
======================================================================
"""
    print(banner)


def run_interactive_wizard(
    dry_run: bool = False,
    marker_path: str = DEFAULT_MARKER_PATH,
    passwd_path: str = DEFAULT_PASSWD_PATH,
) -> int:
    """
    Run the full interactive first-boot console wizard.
    Returns 0 on success, non-zero on failure.
    """
    # Detect if already completed
    if is_setup_completed(marker_path, passwd_path):
        return 0

    display_banner()

    # Loop until valid username
    username = ""
    while True:
        try:
            username = input("Enter new username: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nSetup cancelled.")
            return 1

        is_valid, msg = validate_username(username, passwd_path)
        if is_valid:
            break
        print(f" [!] {msg}\n")

    # Loop until valid password and confirmation match
    password = ""
    while True:
        try:
            password = getpass.getpass("Enter new password: ")
            confirm = getpass.getpass("Confirm password: ")
        except (KeyboardInterrupt, EOFError):
            print("\nSetup cancelled.")
            return 1

        is_valid, msg = validate_password(password, confirm)
        if is_valid:
            break
        print(f" [!] {msg}\n")

    print(f"\n[*] Creating user account '{username}'...")
    try:
        create_local_user(username, password, dry_run=dry_run, marker_path=marker_path)
    except Exception as e:
        print(f"\n[!] Failed to create user account: {e}")
        return 1

    print("======================================================================")
    print(f" ✅ User account '{username}' created successfully.")
    print(" Proceeding to standard AgenticOS login...")
    print("======================================================================\n")

    # Brief delay so user sees confirmation before agetty clears/resets the terminal
    time.sleep(2)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AgenticOS First-Boot Account Setup Wizard")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check if first-boot setup is completed (exits 0 if completed, 1 if needed)",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Run in test/dry-run mode without modifying system files or requiring root",
    )
    parser.add_argument(
        "--username",
        type=str,
        help="Predefined username for non-interactive test provisioning",
    )
    parser.add_argument(
        "--password",
        type=str,
        help="Predefined password for non-interactive test provisioning",
    )
    parser.add_argument(
        "--marker-path",
        type=str,
        default=DEFAULT_MARKER_PATH,
        help="Path to firstboot completion marker file",
    )
    parser.add_argument(
        "--passwd-path",
        type=str,
        default=DEFAULT_PASSWD_PATH,
        help="Path to passwd file for validation",
    )

    args = parser.parse_args(argv)

    if args.check:
        return int(check_setup(args.marker_path, args.passwd_path))

    # Non-interactive mode (used for automated test provisioning)
    if args.username and args.password:
        valid_u, err_u = validate_username(args.username, args.passwd_path)
        if not valid_u:
            print(f"Error: {err_u}", file=sys.stderr)
            return 1
        valid_p, err_p = validate_password(args.password, args.password)
        if not valid_p:
            print(f"Error: {err_p}", file=sys.stderr)
            return 1

        create_local_user(
            args.username,
            args.password,
            dry_run=args.test,
            marker_path=args.marker_path,
        )
        print(f"User '{args.username}' provisioned successfully.")
        return 0

    # Interactive wizard mode
    return int(
        run_interactive_wizard(
            dry_run=args.test,
            marker_path=args.marker_path,
            passwd_path=args.passwd_path,
        )
    )


if __name__ == "__main__":
    sys.exit(int(main()))
