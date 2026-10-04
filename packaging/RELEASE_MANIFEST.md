# AgenticOS v0.1 Alpha — Release Manifest
## October 2, 2026 Validated Release Candidate

- **Release Name:** AgenticOS v0.1 Alpha
- **Designation:** October 2, 2026 Validated Release Candidate
- **Maintainer:** Magesh (Linux Integration & System Services Lead)
- **Status:** Validated Release Candidate (Frozen)

---

## 1. Canonical Release Candidate Artifact

| Attribute | Specification |
| :--- | :--- |
| **Artifact Filename** | `AgenticOS-v0.1-Alpha-AgenticOSSplash-Demo.iso` |
| **Relative Path** | `packaging/output/AgenticOS-v0.1-Alpha-AgenticOSSplash-Demo.iso` |
| **File Size** | `246,908,928 bytes` (235.47 MiB) |
| **SHA-256 Checksum** | `7058b4f0395892f789da11d23a5f58d3df9a42b01d90549f2ed94e48b2bcb754` |
| **Format** | Hybrid ISO 9660 / UDF (UEFI & BIOS El Torito bootable) |
| **Volume ID** | `AGENTICOS_V01` |
| **Casper UUID** | `50c98eb4-4c0f-4c1a-82d2-4234cf187d50` |

> [!NOTE]
> Per release governance decisions, the canonical release candidate retains its exact build filename (`AgenticOS-v0.1-Alpha-AgenticOSSplash-Demo.iso`) to preserve end-to-end traceability across build logs and validation sessions. It is not renamed to `AgenticOS-v0.1-Alpha.iso`.

---

## 2. Git Provenance & Working-Tree State

* **Git Branch:** `magesh/linux-os-foundation`
* **Base Commit Hash:** `9642c62f0db244b958eae149d1dba8237d59f696`
* **Base Commit Subject:** `docs(packaging): add Phase 20 integration handoff report`
* **Base Commit Date:** `Mon Sep 28 02:11:54 2026 +0530`

### Working-Tree State Notice
The October 2, 2026 validated release candidate was assembled from the **uncommitted working tree atop commit `9642c62f0db244b958eae149d1dba8237d59f696`**. The modifications and additions incorporated into this release candidate include:
1. **Goal Runtime Linux Packaging (Layer 3 & 12):**
   * Daemon runner: `system-services/goal-runtime/runner.py`
   * Unit template: `linux_integration/systemd/agenticos-goal-runtime.service.template`
   * Runtime source: `src/goal_runtime/`
   * Unit tests: `tests/test_goal_runtime_service.py`, `tests/test_goal_runtime.py`
2. **Prompt UI Web Application Packaging (Layer 9):**
   * Server and assets: `applications/prompt-ui/server.py`, `index.html`, `app.js`, `styles.css`
   * Unit template: `linux_integration/systemd/agenticos-prompt-ui.service.template`
   * Unit tests: `tests/test_prompt_ui.py`
3. **First-Boot Setup Wizard (Layer 12):**
   * Setup wizard: `applications/firstboot/setup_wizard.py`
   * Unit template: `linux_integration/systemd/agenticos-firstboot.service.template`
   * Unit tests: `tests/test_firstboot.py`
4. **Plymouth Boot Splash Configuration:**
   * Theme definition: `linux_integration/plymouth/agenticos/agenticos.plymouth`
   * GRUB configuration: `packaging/config/grub.cfg` (`plymouth.theme=agenticos`)
   * Unit tests: `tests/test_plymouth_theme.py`
5. **Application & System Adapter Framework (Layers 9 & 10):**
   * Core contracts & registry: `adapters/base.py`, `adapters/registry.py`, `adapters/result.py`
   * Adapters: `adapters/application_adapter.py`, `adapters/filesystem_adapter.py`, `adapters/system_adapter.py`
   * Unit tests: `tests/test_adapter_framework.py`, `tests/test_application_adapter.py`, `tests/test_filesystem_adapter.py`, `tests/test_system_adapter.py`
6. **Build Pipeline Enhancements:**
   * `packaging/scripts/build_iso.sh` (fakeroot preservation, ext4 staging, Stage 3 service and theme injection)

---

## 3. Historical ISO Artifact Lineage

| Filename | File Size | SHA-256 Checksum | Role / Distinction |
| :--- | :--- | :--- | :--- |
| `AgenticOS-v0.1-Alpha-AgenticOSSplash-Demo.iso` | 246,908,928 | `7058b4f0395892f789da11d23a5f58d3df9a42b01d90549f2ed94e48b2bcb754` | **Current Validated Release Candidate**: Full service integration (Goal Runtime, Prompt UI, First-Boot wizard), user-space modules, Plymouth configuration, fakeroot permissions. |
| `AgenticOS-v0.1-Alpha-GoalRuntime-Demo.iso` | 246,892,544 | `7a27da6c8835ec7dedc0c2f737ddc85a38ca0b97085ca51fe9d14b1eeb8cc53a` | Intermediate demo build validating Goal Runtime service packaging prior to Plymouth theme updates. |
| `AgenticOS-v0.1-Alpha-FirstBoot-Demo.iso` | 246,855,680 | `adb20e825f47e0b287eefe1462b608ed033e16f82435a63627800896eabc6f2b` | Intermediate demo build validating First-Boot setup wizard and Prompt UI prior to Goal Runtime service packaging. |
| `AgenticOS-v0.1-Alpha.iso` | 246,843,392 | `e8a26fbc23be45f82a627062c970e9f5ed06c60fd68d90de384a8d44755ad22a` | **Historical Baseline ISO**: Initial clean assembly built on September 29 (08:15 UTC) prior to application/runtime systemd service packaging and Plymouth integration. Preserved untouched. |

---

## 4. Reproducible Build Inputs & Toolchain

* **Build Script:** `packaging/scripts/build_iso.sh` (executed under `fakeroot`)
* **Upstream Live Media Components:**
  * Base SquashFS: `ubuntu-server-minimal.squashfs` (SHA-256: `bd1ce4815bb1988b171cc863b63ac367311af9a2f30c9b13a2ddddee7b89a5ea`)
  * Linux Kernel: `vmlinuz` (6.8.0-139-generic, size: 15,059,336 bytes)
  * Live Initrd: `initrd` (size: 78,777,934 bytes)
* **Build Tools Used:**
  * `fakeroot` (preserves root:root UID/GID 0 ownership and file mode metadata)
  * `xorriso 1.5.6` (hybrid ISO creation with RockRidge and El Torito boot records)
  * `mksquashfs 4.0` (parameters: `-noappend -comp xz -Xbcj x86 -b 1048576`)
  * `grub-mkimage` (generates i386-pc-eltorito and x86_64-efi core images)
  * `mtools` (`mformat`, `mcopy`, `mmd` for FAT EFI system partition image)

---

## 5. Packaged System Services & Security Verification

Read-only inspection of the squashfs root filesystem within `AgenticOS-v0.1-Alpha-AgenticOSSplash-Demo.iso` confirmed:

1. **`agenticos-goal-runtime.service`**:
   * Installed: `/etc/systemd/system/agenticos-goal-runtime.service`
   * Auto-Start: Symlinked in `/etc/systemd/system/multi-user.target.wants/`
   * Executable: `/opt/agenticos/system-services/goal-runtime/runner.py`
   * Security Controls: `DynamicUser=yes`, `NoNewPrivileges=true`, `ProtectSystem=strict`, `ProtectHome=true`, `PrivateTmp=true`, `StateDirectory=agenticos/goal-runtime`
   * Restart Policy: `Restart=on-failure`, `RestartSec=5s`
2. **`agenticos-prompt-ui.service`**:
   * Installed: `/etc/systemd/system/agenticos-prompt-ui.service`
   * Auto-Start: Symlinked in `/etc/systemd/system/multi-user.target.wants/`
   * Executable: `/opt/agenticos/applications/prompt-ui/server.py`
   * Security Controls: `DynamicUser=yes`, `NoNewPrivileges=true`, `ProtectSystem=strict`, `ProtectHome=true`, `PrivateTmp=true`
   * Restart Policy: `Restart=on-failure`, `RestartSec=5s`
3. **`agenticos-firstboot.service`**:
   * Installed: `/etc/systemd/system/agenticos-firstboot.service`
   * Auto-Start: Symlinked in `/etc/systemd/system/multi-user.target.wants/` (oneshot on `/dev/tty1`)
   * Executable: `/opt/agenticos/applications/firstboot/setup_wizard.py`
   * Condition: `ConditionPathExists=!/var/lib/agenticos/firstboot-completed`
4. **File Ownership & SUID Security**:
   * `/usr/bin/sudo`: Mode `04755` (`-rwsr-xr-x`), Owner `0:0` (root:root)
   * `/etc/sudo.conf`: Mode `0644` (`-rw-r--r--`), Owner `0:0` (root:root)

---

## 6. Validation Summary

* **Unit Test Suite:** 209 unit tests passing across all subsystem suites in WSL (`python3 -m unittest discover tests`).
* **Service Packaging Tests:** `tests/test_goal_runtime_service.py`, `tests/test_prompt_ui.py`, `tests/test_firstboot.py`, `tests/test_service_template.py`, and `tests/test_packaging.py` validated.
* **VirtualBox Execution:** Live ISO booted headless; GRUB dual-bootloader verified; first-boot account provisioning completed; user login verified; systemd services verified active; reboot sequence validated.
