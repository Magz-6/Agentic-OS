# AgenticOS First-Boot Account Setup Wizard

- **Owner:** Magesh (Linux/OS Lead)
- **Layer:** Layer 12 (Linux Integration Boundary) & Layer 10 (System Services)
- **Status:** Integrated

## Purpose

The First-Boot Account Setup Wizard provides a clean, secure initial user account creation flow on the primary virtual/physical console (`tty1`) during first boot of AgenticOS.

AgenticOS intentionally does not pre-bake any universal credentials or demo passwords into the ISO. Instead, this wizard:
1. Detects whether initial account setup has already been completed.
2. If setup is needed, displays a welcome banner on `tty1`.
3. Prompts the operator to create a local username and password.
4. Validates inputs against POSIX naming constraints and password confirmation.
5. Uses standard Linux account management (`useradd` with `sudo`/`adm` groups) and standard OS password authentication (`chpasswd` via PAM/shadow).
6. Records the completion marker `/var/lib/agenticos/firstboot-completed`.
7. Transitions control cleanly to the standard Linux login manager (`agetty` on `tty1`).

## Security Constraints

- **No Hardcoded Passwords:** No default credentials exist in code, documentation, or the ISO image.
- **Normal Non-Root User:** The created account is a standard Linux user (`UID >= 1000`) with standard shell `/bin/bash`.
- **PAM/Shadow Compliant:** Passwords are cryptographically hashed and managed solely by the Linux PAM/shadow database; no credentials are ever written to disk or logs.
- **Bypass Protection:** On subsequent boots, the wizard detects completion and immediately steps aside for standard `agetty` login.

## Invocation & CLI Usage

```bash
# Check setup completion status
python3 setup_wizard.py --check

# Test dry-run mode (non-destructive)
python3 setup_wizard.py --test

# Non-interactive automated provisioning (for testing environments)
python3 setup_wizard.py --test --username operator --password securepass
```
