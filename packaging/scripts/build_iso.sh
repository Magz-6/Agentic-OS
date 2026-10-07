#!/usr/bin/env bash
# AgenticOS v0.1 Alpha — Reproducible ISO Build Script
# Architecture: Candidate B — Ubuntu 24.04.5 LTS + Casper/OverlayFS + Custom xorriso/GRUB
# Status: VALIDATED BUILD PIPELINE — FINAL VALIDATION REQUIRED
#
# Preflight Constraints:
# - Runs in unprivileged user space through fakeroot
# - No sudo or real root operations are required
# - Requires verified upstream live media or verified staged components
# - System-service installation is controlled by build.conf
# - GUI/minimal SquashFS selection is controlled by BUILD_TARGET

set -euo pipefail

# -----------------------------------------------------------------------------
# 0. Fakeroot Requirement
# -----------------------------------------------------------------------------

# fakeroot provides simulated root ownership/metadata while keeping the build
# process unprivileged.
if [[ "$(id -u)" -ne 0 ]]; then
    if command -v fakeroot >/dev/null 2>&1; then
        echo "[Build Pipeline] Re-executing under fakeroot..."
        exec fakeroot -- bash "$0" "$@"
    else
        echo "ERROR: 'fakeroot' is required for this build." >&2
        exit 1
    fi
fi

# -----------------------------------------------------------------------------
# 1. Project Paths
# -----------------------------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

CONFIG_FILE="${PROJECT_ROOT}/packaging/config/build.conf"
GUI_PACKAGE_MANIFEST="${PROJECT_ROOT}/packaging/config/gui-packages.conf"

if [[ ! -f "${CONFIG_FILE}" ]]; then
    echo "ERROR: Configuration file missing: ${CONFIG_FILE}" >&2
    exit 1
fi

# Load project configuration.
# shellcheck source=../config/build.conf
source "${CONFIG_FILE}"

STAGING_PATH="${PROJECT_ROOT}/${STAGING_DIR}"
SOURCE_ISO="${STAGING_PATH}/${UPSTREAM_ISO_NAME}"
ISO_ROOT_DIR="${PROJECT_ROOT}/${ISO_ROOT}"

# Native Linux filesystem is used for SquashFS extraction/repacking.
# This avoids NTFS/OneDrive POSIX permission problems.
SQUASHFS_ROOT_DIR="/tmp/agenticos_squashfs_root"

# -----------------------------------------------------------------------------
# 2. Build Target Selection
# -----------------------------------------------------------------------------

BUILD_TARGET="${BUILD_TARGET:-minimal}"

case "${BUILD_TARGET}" in
    minimal)
        TARGET_SQUASHFS="${BASE_SQUASHFS_NAME}"
        ;;
    gui)
        TARGET_SQUASHFS="${GUI_SQUASHFS_NAME}"
        ;;
    *)
        echo "ERROR: Unsupported BUILD_TARGET='${BUILD_TARGET}'." >&2
        echo "Supported targets: minimal, gui" >&2
        exit 1
        ;;
esac

# The final ISO name can be overridden by TARGET_ISO_NAME.
ISO_NAME="${TARGET_ISO_NAME:-${ISO_NAME}}"
OUTPUT_ISO_PATH="${PROJECT_ROOT}/${OUTPUT_DIR}/${ISO_NAME}"

# The SquashFS filename placed inside /casper/.
LIVE_SQUASHFS_NAME="${LIVE_SQUASHFS_NAME:-${TARGET_SQUASHFS}}"

echo "====================================================================="
echo "AgenticOS — Reproducible ISO Build Pipeline"
echo "====================================================================="
echo "Project Root : ${PROJECT_ROOT}"
echo "Build Target : ${BUILD_TARGET}"
echo "SquashFS     : ${TARGET_SQUASHFS}"
echo "Live Image   : ${LIVE_SQUASHFS_NAME}"
echo "Output ISO   : ${OUTPUT_ISO_PATH}"
echo "====================================================================="

# -----------------------------------------------------------------------------
# 3. Architectural Governance & Service Contract Guard
# -----------------------------------------------------------------------------

# These switches control whether AgenticOS system services are injected.
#
# IMPORTANT:
# If build.conf contains:
#
#     INSTALL_SYSTEMD_SERVICE=0
#     ENABLE_SYSTEMD_SERVICE=0
#
# this build MUST NOT install or enable AgenticOS services.

if [[ "${INSTALL_SYSTEMD_SERVICE}" -ne 0 ]] || \
   [[ "${ENABLE_SYSTEMD_SERVICE}" -ne 0 ]]; then

    echo "[Governance] System-service integration requested by build configuration."

    if [[ "${INSTALL_SYSTEMD_SERVICE}" -ne 1 ]] || \
       [[ "${ENABLE_SYSTEMD_SERVICE}" -ne 1 ]]; then
        echo "ERROR: INSTALL_SYSTEMD_SERVICE and ENABLE_SYSTEMD_SERVICE must both" >&2
        echo "be set to 1 when service integration is explicitly approved." >&2
        exit 1
    fi

else
    echo "[Governance] System-service installation/enablement is DISABLED."
fi

# -----------------------------------------------------------------------------
# 4. Preflight — Required Tools
# -----------------------------------------------------------------------------

REQUIRED_TOOLS=(
    "fakeroot"
    "xorriso"
    "mksquashfs"
    "unsquashfs"
    "mformat"
    "mcopy"
    "mmd"
    "grub-mkimage"
    "truncate"
    "sha256sum"
)

for tool in "${REQUIRED_TOOLS[@]}"; do
    if ! command -v "${tool}" >/dev/null 2>&1; then
        echo "ERROR: Required build tool '${tool}' is not installed." >&2
        exit 1
    fi
done

# Check GRUB module directories.
if [[ ! -d "/usr/lib/grub/x86_64-efi" ]] || \
   [[ ! -d "/usr/lib/grub/i386-pc" ]]; then

    echo "ERROR: Required GRUB module directories not found." >&2
    exit 1
fi

# -----------------------------------------------------------------------------
# 5. Preflight — Source Artifact Validation
# -----------------------------------------------------------------------------

HAVE_STAGED_COMPONENTS=0

STAGED_SQUASHFS="${STAGING_PATH}/${TARGET_SQUASHFS}"

if [[ -f "${STAGING_PATH}/${KERNEL_FILE}" ]] && \
   [[ -f "${STAGING_PATH}/${INITRD_FILE}" ]] && \
   [[ -f "${STAGED_SQUASHFS}" ]]; then

    echo "[Preflight] Verified staged ${BUILD_TARGET} components found."

    CALC_SQUASH_HASH="$(
        sha256sum "${STAGED_SQUASHFS}" | awk '{print $1}'
    )"

    EXPECTED_SQUASH_HASH=""

    if [[ "${BUILD_TARGET}" == "minimal" ]]; then
        EXPECTED_SQUASH_HASH="${BASE_SQUASHFS_SHA256:-}"
    elif [[ "${BUILD_TARGET}" == "gui" ]]; then
        EXPECTED_SQUASH_HASH="${GUI_SQUASHFS_SHA256:-}"
    fi

    if [[ -n "${EXPECTED_SQUASH_HASH}" ]]; then
        if [[ "${CALC_SQUASH_HASH}" != "${EXPECTED_SQUASH_HASH}" ]]; then
            echo "ERROR: ${BUILD_TARGET} SquashFS checksum mismatch!" >&2
            echo "Expected: ${EXPECTED_SQUASH_HASH}" >&2
            echo "Actual:   ${CALC_SQUASH_HASH}" >&2
            exit 1
        fi

        echo "  ✅ ${BUILD_TARGET} SquashFS checksum verified."
    else
        echo "  ⚠️ No expected SquashFS SHA256 configured."
        echo "  Continuing with staged artifact."
    fi

    HAVE_STAGED_COMPONENTS=1

elif [[ -f "${SOURCE_ISO}" ]]; then

    echo "[Preflight] Source ISO found. Verifying SHA256 checksum..."

    CALCULATED_HASH="$(
        sha256sum "${SOURCE_ISO}" | awk '{print $1}'
    )"

    if [[ "${CALCULATED_HASH}" != "${UPSTREAM_SHA256}" ]]; then
        echo "ERROR: Source ISO checksum mismatch!" >&2
        echo "Expected: ${UPSTREAM_SHA256}" >&2
        echo "Actual:   ${CALCULATED_HASH}" >&2
        exit 1
    fi

    echo "  ✅ Source ISO checksum verified."

else
    echo "ERROR: No valid staged ${BUILD_TARGET} components or source ISO found." >&2
    echo "Expected source: ${SOURCE_ISO}" >&2
    echo "Expected SquashFS: ${STAGED_SQUASHFS}" >&2
    exit 1
fi

# -----------------------------------------------------------------------------
# 6. Preflight — Disk Space
# -----------------------------------------------------------------------------

AVAILABLE_KB="$(df -k "${STAGING_PATH}" | awk 'NR==2 {print $4}')"

if [[ "${AVAILABLE_KB}" -lt 5242880 ]]; then
    echo "ERROR: Less than 5 GB free space available." >&2
    exit 1
fi

# -----------------------------------------------------------------------------
# Stage 1/7 — Clean & Prepare Staging Trees
# -----------------------------------------------------------------------------

echo "[Stage 1/7] Preparing clean staging trees..."

mkdir -p \
    "${ISO_ROOT_DIR}" \
    "${SQUASHFS_ROOT_DIR}" \
    "${PROJECT_ROOT}/${OUTPUT_DIR}"

find "${ISO_ROOT_DIR}" -mindepth 1 -delete 2>/dev/null || true
find "${SQUASHFS_ROOT_DIR}" -mindepth 1 -delete 2>/dev/null || true

# -----------------------------------------------------------------------------
# Stage 2/7 — Stage Kernel, Initrd & SquashFS
# -----------------------------------------------------------------------------

echo "[Stage 2/7] Staging live-boot components..."

mkdir -p "${ISO_ROOT_DIR}/casper"

if [[ "${HAVE_STAGED_COMPONENTS}" -eq 1 ]]; then

    cp \
        "${STAGING_PATH}/${KERNEL_FILE}" \
        "${ISO_ROOT_DIR}/casper/vmlinuz"

    cp \
        "${STAGING_PATH}/${INITRD_FILE}" \
        "${ISO_ROOT_DIR}/casper/initrd"

    cp \
        "${STAGED_SQUASHFS}" \
        "${ISO_ROOT_DIR}/casper/${LIVE_SQUASHFS_NAME}"

else

    # The upstream Ubuntu ISO contains the minimal Ubuntu SquashFS.
    # A GUI-specific SquashFS must therefore be staged separately.
    if [[ "${BUILD_TARGET}" != "minimal" ]]; then
        echo "ERROR: GUI build requires a staged GUI SquashFS." >&2
        echo "The upstream Live Server ISO does not provide our AgenticOS GUI layer." >&2
        exit 1
    fi

    xorriso \
        -indev "${SOURCE_ISO}" \
        -extract /casper/vmlinuz \
        "${ISO_ROOT_DIR}/casper/vmlinuz"

    xorriso \
        -indev "${SOURCE_ISO}" \
        -extract /casper/initrd \
        "${ISO_ROOT_DIR}/casper/initrd"

    xorriso \
        -indev "${SOURCE_ISO}" \
        -extract "/casper/${LIVE_SQUASHFS_NAME}" \
        "${ISO_ROOT_DIR}/casper/${LIVE_SQUASHFS_NAME}"
fi

# Casper medium identification metadata.
mkdir -p "${ISO_ROOT_DIR}/.disk"

echo "${CASPER_UUID}" \
    > "${ISO_ROOT_DIR}/.disk/casper-uuid-generic"

echo "AgenticOS v0.1 Alpha" \
    > "${ISO_ROOT_DIR}/.disk/info"

# -----------------------------------------------------------------------------
# Stage 3/7 — Unpack & Integrate AgenticOS Layer
# -----------------------------------------------------------------------------

echo "[Stage 3/7] Unpacking SquashFS root filesystem..."

rm -rf "${SQUASHFS_ROOT_DIR}"

unsquashfs \
    -d "${SQUASHFS_ROOT_DIR}" \
    "${ISO_ROOT_DIR}/casper/${LIVE_SQUASHFS_NAME}"

# -----------------------------------------------------------------------------
# Stage 3A — Remove Stale Xorg Configuration
# -----------------------------------------------------------------------------

STALE_XORG_FALLBACK="${SQUASHFS_ROOT_DIR}/etc/X11/xorg.conf.d/10-framebuffer.conf"

if [[ -f "${STALE_XORG_FALLBACK}" ]]; then
    echo "[Stage 3/7] Removing stale inherited Xorg framebuffer configuration..."
    rm -f "${STALE_XORG_FALLBACK}"
fi

# -----------------------------------------------------------------------------
# Stage 3B — Stage AgenticOS User-Space Components
# -----------------------------------------------------------------------------

echo "[Stage 3/7] Staging AgenticOS user-space components..."

TARGET_DIR="${SQUASHFS_ROOT_DIR}/${PROPOSED_INSTALL_DIR}"

mkdir -p "${TARGET_DIR}"

for module in \
    "adapters" \
    "hardware" \
    "telemetry" \
    "linux_integration" \
    "system-services" \
    "applications" \
    "src"
do
    if [[ -d "${PROJECT_ROOT}/${module}" ]]; then
        cp -a \
            "${PROJECT_ROOT}/${module}" \
            "${TARGET_DIR}/"
    fi
done

# Clean Python caches and developer artifacts from staged directory
find "${TARGET_DIR}" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "${TARGET_DIR}" -type f -name "*.pyc" -delete 2>/dev/null || true

# Integrate staged packages (GTK 3.0 typelibs, etc.) if available
DEB_STAGING_DIR="${PROJECT_ROOT}/packaging/staging/debs"
if [[ -d "${DEB_STAGING_DIR}" ]] && compgen -G "${DEB_STAGING_DIR}/*.deb" > /dev/null; then
    echo "[Stage 3/7] Integrating staged packages into root filesystem..."
    for deb in "${DEB_STAGING_DIR}"/*.deb; do
        dpkg-deb -x "${deb}" "${SQUASHFS_ROOT_DIR}"
    done
fi

chown -R 0:0 "${TARGET_DIR}"

# -----------------------------------------------------------------------------
# Stage 3C — AgenticOS Identity
# -----------------------------------------------------------------------------

if [[ -f "${SQUASHFS_ROOT_DIR}/etc/os-release" ]]; then
    sed -i \
        's/^NAME=.*/NAME="AgenticOS"/' \
        "${SQUASHFS_ROOT_DIR}/etc/os-release"

    sed -i \
        's/^PRETTY_NAME=.*/PRETTY_NAME="AgenticOS v0.1 Alpha"/' \
        "${SQUASHFS_ROOT_DIR}/etc/os-release"
fi

printf 'AgenticOS v0.1 Alpha\n' \
    > "${SQUASHFS_ROOT_DIR}/etc/issue"

printf 'AgenticOS v0.1 Alpha\n' \
    > "${SQUASHFS_ROOT_DIR}/etc/issue.net"

# -----------------------------------------------------------------------------
# Stage 3D — AgenticOS Service Integration
# -----------------------------------------------------------------------------

SYSTEMD_TEMPLATE_DIR="${PROJECT_ROOT}/linux_integration/systemd"

if [[ "${INSTALL_SYSTEMD_SERVICE}" -eq 1 ]] && \
   [[ "${ENABLE_SYSTEMD_SERVICE}" -eq 1 ]]; then

    echo "[Stage 3/7] Service integration ENABLED by build configuration."

    mkdir -p "${TARGET_DIR}/systemd"

    if [[ -d "${SYSTEMD_TEMPLATE_DIR}" ]]; then
        cp -a \
            "${SYSTEMD_TEMPLATE_DIR}/"* \
            "${TARGET_DIR}/systemd/" \
            2>/dev/null || true
    fi

    # -------------------------------------------------------------------------
    # First Boot Service (CLI setup wizard — enabled for minimal target only)
    # -------------------------------------------------------------------------

    if [[ -f "${SYSTEMD_TEMPLATE_DIR}/agenticos-firstboot.service.template" ]]; then

        cp \
            "${SYSTEMD_TEMPLATE_DIR}/agenticos-firstboot.service.template" \
            "${SQUASHFS_ROOT_DIR}/etc/systemd/system/agenticos-firstboot.service"

        if [[ "${BUILD_TARGET}" != "gui" ]]; then
            echo "[Stage 3/7] Enabling First-Boot CLI Setup Wizard for ${BUILD_TARGET} target..."
            mkdir -p \
                "${SQUASHFS_ROOT_DIR}/etc/systemd/system/multi-user.target.wants"

            ln -sf \
                /etc/systemd/system/agenticos-firstboot.service \
                "${SQUASHFS_ROOT_DIR}/etc/systemd/system/multi-user.target.wants/agenticos-firstboot.service"
        else
            echo "[Stage 3/7] Installed agenticos-firstboot.service (symlink omitted for ${BUILD_TARGET}; using LightDM)."
        fi
    fi

    # -------------------------------------------------------------------------
    # Prompt UI Service
    # -------------------------------------------------------------------------

    if [[ -f "${SYSTEMD_TEMPLATE_DIR}/agenticos-prompt-ui.service.template" ]]; then

        cp \
            "${SYSTEMD_TEMPLATE_DIR}/agenticos-prompt-ui.service.template" \
            "${SQUASHFS_ROOT_DIR}/etc/systemd/system/agenticos-prompt-ui.service"

        mkdir -p \
            "${SQUASHFS_ROOT_DIR}/etc/systemd/system/multi-user.target.wants"

        ln -sf \
            /etc/systemd/system/agenticos-prompt-ui.service \
            "${SQUASHFS_ROOT_DIR}/etc/systemd/system/multi-user.target.wants/agenticos-prompt-ui.service"
    fi

    # -------------------------------------------------------------------------
    # Goal Runtime Service
    # -------------------------------------------------------------------------

    if [[ -f "${SYSTEMD_TEMPLATE_DIR}/agenticos-goal-runtime.service.template" ]]; then

        cp \
        "${SYSTEMD_TEMPLATE_DIR}/agenticos-goal-runtime.service.template" \
            "${SQUASHFS_ROOT_DIR}/etc/systemd/system/agenticos-goal-runtime.service"

        mkdir -p \
            "${SQUASHFS_ROOT_DIR}/etc/systemd/system/multi-user.target.wants"

        ln -sf \
            /etc/systemd/system/agenticos-goal-runtime.service \
            "${SQUASHFS_ROOT_DIR}/etc/systemd/system/multi-user.target.wants/agenticos-goal-runtime.service"
    fi

    # -------------------------------------------------------------------------
    # Graphical Desktop Service
    # -------------------------------------------------------------------------

    if [[ -f "${SYSTEMD_TEMPLATE_DIR}/agenticos-desktop.service.template" ]]; then

        cp \
            "${SYSTEMD_TEMPLATE_DIR}/agenticos-desktop.service.template" \
            "${SQUASHFS_ROOT_DIR}/etc/systemd/system/agenticos-desktop.service"


    fi

else

    echo "[Stage 3/7] Service integration DISABLED."
    echo "[Stage 3/7] No AgenticOS systemd services will be installed or enabled."

fi

# -----------------------------------------------------------------------------
# Stage 3E — Xorg Fallback
# -----------------------------------------------------------------------------

XORG_FALLBACK_SRC="${PROJECT_ROOT}/linux_integration/xorg/90-framebuffer-fallback.conf"

if [[ -f "${XORG_FALLBACK_SRC}" ]]; then

    echo "[Stage 3/7] Staging AgenticOS Xorg framebuffer fallback..."

    mkdir -p \
        "${SQUASHFS_ROOT_DIR}/etc/X11/xorg.conf.d"

    cp \
        "${XORG_FALLBACK_SRC}" \
        "${SQUASHFS_ROOT_DIR}/etc/X11/xorg.conf.d/90-framebuffer-fallback.conf"
fi

# -----------------------------------------------------------------------------
# Stage 3F — Install LightDM / Slick Greeter into GUI root
# -----------------------------------------------------------------------------

LIGHTDM_DEB_DIR="${PROJECT_ROOT}/packaging/staging/lightdm-debs"

if [[ -d "${LIGHTDM_DEB_DIR}" ]] && compgen -G "${LIGHTDM_DEB_DIR}/*.deb" > /dev/null; then
    echo "[Stage 3/7] Extracting staged LightDM packages into GUI root..."

    # This build intentionally runs without real root/chroot privileges.
    # dpkg --root would attempt to chroot into the SquashFS root and fails
    # under the unprivileged WSL/fakeroot build environment.
    #
    # dpkg-deb -x extracts only the package filesystem payload. It does not
    # execute maintainer scripts or attempt to start services, which is the
    # correct behavior for offline ISO construction.

    for deb in "${LIGHTDM_DEB_DIR}"/*.deb; do
        echo "  [LightDM] Extracting $(basename "${deb}")"
        dpkg-deb -x "${deb}" "${SQUASHFS_ROOT_DIR}" || {
            echo "[Stage 3/7] ERROR: Failed to extract ${deb}."
            exit 1
        }
    done

    echo "[Stage 3/7] Verifying LightDM installation..."

    test -x "${SQUASHFS_ROOT_DIR}/usr/sbin/lightdm" || {
        echo "[Stage 3/7] ERROR: /usr/sbin/lightdm missing after extraction."
        exit 1
    }

    test -x "${SQUASHFS_ROOT_DIR}/usr/sbin/slick-greeter" || {
        echo "[Stage 3/7] ERROR: /usr/sbin/slick-greeter missing after extraction."
        exit 1
    }

    echo "[Stage 3/7] LightDM and Slick Greeter extracted successfully."

    # -------------------------------------------------------------------------
    # Offline Provisioning: LightDM System Account & Live User (agenticos)
    # -------------------------------------------------------------------------
    # dpkg-deb -x extracts package contents without executing postinst scripts.
    # We provision the required system accounts, groups, and state directories
    # statically using verified Ubuntu IDs and standard POSIX conventions.

    echo "[Stage 3/7] Provisioning LightDM daemon account and live session user..."
    SQUASHFS_ROOT_DIR="${SQUASHFS_ROOT_DIR}" python3 - << 'PYEOF'
import os
import shutil
from pathlib import Path

root_dir = Path(os.environ.get("SQUASHFS_ROOT_DIR", "/tmp/agenticos_squashfs_root"))
passwd_path = root_dir / "etc" / "passwd"
group_path = root_dir / "etc" / "group"
shadow_path = root_dir / "etc" / "shadow"

passwd_lines = passwd_path.read_text(encoding="utf-8").splitlines() if passwd_path.exists() else []
group_lines = group_path.read_text(encoding="utf-8").splitlines() if group_path.exists() else []
shadow_lines = shadow_path.read_text(encoding="utf-8").splitlines() if shadow_path.exists() else []

passwd_users = {l.split(":")[0] for l in passwd_lines if l.strip() and not l.startswith("#")}
group_names = {l.split(":")[0] for l in group_lines if l.strip() and not l.startswith("#")}
shadow_users = {l.split(":")[0] for l in shadow_lines if l.strip() and not l.startswith("#")}

# 1. Provision LightDM daemon group (GID 104) and user (UID 104)
if "lightdm" not in group_names:
    group_lines.append("lightdm:x:104:")
if "nopasswdlogin" not in group_names:
    group_lines.append("nopasswdlogin:x:105:")
if "lightdm" not in passwd_users:
    passwd_lines.append("lightdm:x:104:104:Light Display Manager:/var/lib/lightdm:/bin/false")
if "lightdm" not in shadow_users:
    shadow_lines.append("lightdm:*:20705:0:99999:7:::")

# 2. Provision agenticos live user (UID 1000, GID 1000)
if "agenticos" not in group_names:
    group_lines.append("agenticos:x:1000:")
if "agenticos" not in passwd_users:
    passwd_lines.append("agenticos:x:1000:1000:AgenticOS Live User:/home/agenticos:/bin/bash")
if "agenticos" not in shadow_users:
    # Locked/unset password; PAM authorizes local session via nopasswdlogin group
    shadow_lines.append("agenticos:*:20705:0:99999:7:::")

# 3. Add agenticos to supplementary groups
target_groups = {"sudo", "audio", "video", "render", "input", "nopasswdlogin"}
new_group_lines = []
for g_line in group_lines:
    if not g_line.strip() or g_line.startswith("#"):
        new_group_lines.append(g_line)
        continue
    parts = g_line.split(":")
    gname = parts[0]
    if gname in target_groups:
        members = [m for m in parts[3].split(",") if m] if len(parts) > 3 and parts[3] else []
        if "agenticos" not in members:
            members.append("agenticos")
        parts[3] = ",".join(members)
        new_group_lines.append(":".join(parts))
    else:
        new_group_lines.append(g_line)
group_lines = new_group_lines

# Write updated databases
passwd_path.write_text("\n".join(passwd_lines) + "\n", encoding="utf-8")
group_path.write_text("\n".join(group_lines) + "\n", encoding="utf-8")
shadow_path.write_text("\n".join(shadow_lines) + "\n", encoding="utf-8")

os.chmod(passwd_path, 0o644)
os.chmod(group_path, 0o644)
os.chmod(shadow_path, 0o640)

# 4. Create and configure LightDM state directories
for d in [root_dir / "var" / "lib" / "lightdm", root_dir / "var" / "log" / "lightdm", root_dir / "var" / "cache" / "lightdm"]:
    d.mkdir(parents=True, exist_ok=True)
    os.chmod(d, 0o750)
    shutil.chown(d, 104, 104)

# 5. Create and configure agenticos home directory
home_dir = root_dir / "home" / "agenticos"
home_dir.mkdir(parents=True, exist_ok=True)
os.chmod(home_dir, 0o755)
shutil.chown(home_dir, 1000, 1000)

skel_dir = root_dir / "etc" / "skel"
if skel_dir.is_dir():
    for item in skel_dir.iterdir():
        dest = home_dir / item.name
        if not dest.exists():
            if item.is_file():
                shutil.copy2(item, dest)
            elif item.is_dir():
                shutil.copytree(item, dest)
            shutil.chown(dest, 1000, 1000)

print("  ✅ Provisioned LightDM system account (UID/GID 104) and state directories.")
print("  ✅ Provisioned agenticos live user (UID/GID 1000) in nopasswdlogin.")
PYEOF
else
    echo "[Stage 3/7] ERROR: Staged LightDM packages not found."
    exit 1
fi

# -----------------------------------------------------------------------------
# Stage 3F — LightDM / AgenticOS Graphical Login
# -----------------------------------------------------------------------------

LIGHTDM_CONFIG_SRC="${PROJECT_ROOT}/linux_integration/lightdm/lightdm.conf"
SLICK_GREETER_CONFIG_SRC="${PROJECT_ROOT}/linux_integration/lightdm/slick-greeter.conf"
AGENTICOS_XSESSION_SRC="${PROJECT_ROOT}/linux_integration/lightdm/agenticos.desktop"

if [[ -f "${LIGHTDM_CONFIG_SRC}" && -f "${SLICK_GREETER_CONFIG_SRC}" && -f "${AGENTICOS_XSESSION_SRC}" ]]; then

    echo "[Stage 3/7] Staging AgenticOS LightDM graphical login..."

    mkdir -p         "${SQUASHFS_ROOT_DIR}/etc/lightdm/lightdm.conf.d"         "${SQUASHFS_ROOT_DIR}/usr/share/xsessions"

    cp -p         "${LIGHTDM_CONFIG_SRC}"         "${SQUASHFS_ROOT_DIR}/etc/lightdm/lightdm.conf"

    cp -p         "${SLICK_GREETER_CONFIG_SRC}"         "${SQUASHFS_ROOT_DIR}/etc/lightdm/lightdm.conf.d/60-agenticos-greeter.conf"

    cp -p         "${AGENTICOS_XSESSION_SRC}"         "${SQUASHFS_ROOT_DIR}/usr/share/xsessions/agenticos.desktop"

    chown 0:0         "${SQUASHFS_ROOT_DIR}/etc/lightdm/lightdm.conf"         "${SQUASHFS_ROOT_DIR}/etc/lightdm/lightdm.conf.d/60-agenticos-greeter.conf"         "${SQUASHFS_ROOT_DIR}/usr/share/xsessions/agenticos.desktop"

    chmod 0644         "${SQUASHFS_ROOT_DIR}/etc/lightdm/lightdm.conf"         "${SQUASHFS_ROOT_DIR}/etc/lightdm/lightdm.conf.d/60-agenticos-greeter.conf"         "${SQUASHFS_ROOT_DIR}/usr/share/xsessions/agenticos.desktop"

else

    echo "[Stage 3/7] WARNING: LightDM configuration files are incomplete; skipping LightDM staging."

fi

# -----------------------------------------------------------------------------
# Stage 3G — AgenticOS LightDM Artwork
# -----------------------------------------------------------------------------

LIGHTDM_LOGIN_ART="${PROJECT_ROOT}/packaging/staging/agenticos-login.png"
LIGHTDM_LOGO_ART="${PROJECT_ROOT}/packaging/staging/squashfs_root_lightdm/usr/share/pixmaps/agenticos-logo.png"

if [[ -f "${LIGHTDM_LOGIN_ART}" && -f "${LIGHTDM_LOGO_ART}" ]]; then

    echo "[Stage 3/7] Staging AgenticOS LightDM artwork..."

    mkdir -p         "${SQUASHFS_ROOT_DIR}/usr/share/backgrounds/agenticos"         "${SQUASHFS_ROOT_DIR}/usr/share/pixmaps"

    cp -p         "${LIGHTDM_LOGIN_ART}"         "${SQUASHFS_ROOT_DIR}/usr/share/backgrounds/agenticos/agenticos-login.png"

    cp -p         "${LIGHTDM_LOGO_ART}"         "${SQUASHFS_ROOT_DIR}/usr/share/pixmaps/agenticos-logo.png"

    chown 0:0         "${SQUASHFS_ROOT_DIR}/usr/share/backgrounds/agenticos/agenticos-login.png"         "${SQUASHFS_ROOT_DIR}/usr/share/pixmaps/agenticos-logo.png"

    chmod 0644         "${SQUASHFS_ROOT_DIR}/usr/share/backgrounds/agenticos/agenticos-login.png"         "${SQUASHFS_ROOT_DIR}/usr/share/pixmaps/agenticos-logo.png"

else
    echo "[Stage 3/7] WARNING: LightDM artwork files are incomplete; skipping artwork staging."
fi

# -----------------------------------------------------------------------------
# Stage 3G — LightDM Display Manager Selection
# -----------------------------------------------------------------------------

if [[ -f "${SQUASHFS_ROOT_DIR}/usr/sbin/lightdm" ]]; then

    echo "[Stage 3/7] Selecting LightDM as the AgenticOS display manager..."

    mkdir -p         "${SQUASHFS_ROOT_DIR}/etc/X11"         "${SQUASHFS_ROOT_DIR}/etc/systemd/system"

    printf '%s\n' '/usr/sbin/lightdm' \
        > "${SQUASHFS_ROOT_DIR}/etc/X11/default-display-manager"

    ln -sf \
        /usr/lib/systemd/system/lightdm.service \
        "${SQUASHFS_ROOT_DIR}/etc/systemd/system/display-manager.service"

    # Mask systemd-networkd-wait-online.service in Live GUI root so boot is not delayed by 120s
    ln -sf /dev/null "${SQUASHFS_ROOT_DIR}/etc/systemd/system/systemd-networkd-wait-online.service"

    chown 0:0 \
        "${SQUASHFS_ROOT_DIR}/etc/X11/default-display-manager"

    chmod 0644 \
        "${SQUASHFS_ROOT_DIR}/etc/X11/default-display-manager"

else

    echo "[Stage 3/7] WARNING: LightDM executable not found; display-manager selection skipped."

fi

# -----------------------------------------------------------------------------
# Stage 3F — Plymouth Theme
# -----------------------------------------------------------------------------

PLYMOUTH_THEME_SRC="${PROJECT_ROOT}/linux_integration/plymouth/agenticos/agenticos.plymouth"
PLYMOUTH_SCRIPT_SRC="${PROJECT_ROOT}/linux_integration/plymouth/agenticos/agenticos.script"
PLYMOUTH_IMAGE_SRC="${PROJECT_ROOT}/linux_integration/plymouth/agenticos/agenticos-splash.png"

if [[ -f "${PLYMOUTH_THEME_SRC}" ]]; then

    echo "[Stage 3/7] Staging AgenticOS Plymouth theme..."

    THEME_DIR="${SQUASHFS_ROOT_DIR}/usr/share/plymouth/themes/agenticos"

    mkdir -p "${THEME_DIR}"

    cp -p \
        "${PROJECT_ROOT}/linux_integration/plymouth/agenticos/"* \
        "${THEME_DIR}/"

    chown -R 0:0 "${THEME_DIR}"

    chmod 0644 \
        "${THEME_DIR}"/*

    mkdir -p \
        "${SQUASHFS_ROOT_DIR}/etc/plymouth"

    cat > "${SQUASHFS_ROOT_DIR}/etc/plymouth/plymouthd.conf" << 'EOF'
[Daemon]
Theme=agenticos
ShowDelay=0
DeviceTimeout=8
EOF

    chown 0:0 \
        "${SQUASHFS_ROOT_DIR}/etc/plymouth/plymouthd.conf"

    chmod 0644 \
        "${SQUASHFS_ROOT_DIR}/etc/plymouth/plymouthd.conf"

    ln -sf \
        /usr/share/plymouth/themes/agenticos/agenticos.plymouth \
        "${SQUASHFS_ROOT_DIR}/usr/share/plymouth/themes/default.plymouth"

    ln -sf \
        /usr/share/plymouth/themes/agenticos/agenticos.plymouth \
        "${SQUASHFS_ROOT_DIR}/etc/alternatives/default.plymouth"

    ln -sf \
        /usr/share/plymouth/themes/agenticos/agenticos.plymouth \
        "${SQUASHFS_ROOT_DIR}/etc/alternatives/text.plymouth"

    # Neutralize ubuntu-text theme in SquashFS so no Ubuntu branding ever renders
    if [[ -d "${SQUASHFS_ROOT_DIR}/usr/share/plymouth/themes/ubuntu-text" ]]; then
        cat > "${SQUASHFS_ROOT_DIR}/usr/share/plymouth/themes/ubuntu-text/ubuntu-text.plymouth" << 'EOF'
[Plymouth Theme]
Name=AgenticOS
Description=AgenticOS Text Mode
ModuleName=ubuntu-text

[ubuntu-text]
title=AgenticOS v0.1 Alpha
black=0x030712
white=0xffffff
brown=0x00d4ff
blue=0x00ffff
EOF
    fi

    # Neutralize any inherited ubuntu-logo.png
    if [[ -f "${SQUASHFS_ROOT_DIR}/usr/share/plymouth/ubuntu-logo.png" ]]; then
        rm -f "${SQUASHFS_ROOT_DIR}/usr/share/plymouth/ubuntu-logo.png"
    fi
fi

# -----------------------------------------------------------------------------
# Stage 3G — Integrate AgenticOS Plymouth Theme into Casper Initrd
# -----------------------------------------------------------------------------

echo "[Stage 3/7] Integrating AgenticOS Plymouth theme into Casper initrd..."

INITRD_TARGET="${ISO_ROOT_DIR}/casper/initrd"
INITRD_PATCH_DIR="/tmp/agenticos_initrd_patch"

rm -rf "${INITRD_PATCH_DIR}"
mkdir -p "${INITRD_PATCH_DIR}/unpacked"

unmkinitramfs "${INITRD_TARGET}" "${INITRD_PATCH_DIR}/unpacked"

INITRD_MAIN="${INITRD_PATCH_DIR}/unpacked/main"

if [[ -d "${INITRD_MAIN}" ]]; then
    # 1. Stage full agenticos theme assets
    mkdir -p "${INITRD_MAIN}/usr/share/plymouth/themes/agenticos"
    cp -p "${PROJECT_ROOT}/linux_integration/plymouth/agenticos/"* \
        "${INITRD_MAIN}/usr/share/plymouth/themes/agenticos/"

    # 2. Stage script plugin from squashfs
    mkdir -p "${INITRD_MAIN}/usr/lib/x86_64-linux-gnu/plymouth"
    cp -p "${SQUASHFS_ROOT_DIR}/usr/lib/x86_64-linux-gnu/plymouth/script.so" \
        "${INITRD_MAIN}/usr/lib/x86_64-linux-gnu/plymouth/script.so"

    # 3. Stage graphic rendering libraries into initrd
    cp -p "${SQUASHFS_ROOT_DIR}/usr/lib/x86_64-linux-gnu/libply-splash-graphics.so.5"* \
        "${INITRD_MAIN}/usr/lib/x86_64-linux-gnu/"

    if compgen -G "${SQUASHFS_ROOT_DIR}/usr/lib/x86_64-linux-gnu/libpng16.so.16*" > /dev/null; then
        cp -p "${SQUASHFS_ROOT_DIR}/usr/lib/x86_64-linux-gnu/libpng16.so.16"* \
            "${INITRD_MAIN}/usr/lib/x86_64-linux-gnu/"
    else
        cp -p /usr/lib/x86_64-linux-gnu/libpng16.so.16* \
            "${INITRD_MAIN}/usr/lib/x86_64-linux-gnu/"
    fi

    # 4. Configure plymouthd.conf in initrd
    mkdir -p "${INITRD_MAIN}/etc/plymouth"
    cat > "${INITRD_MAIN}/etc/plymouth/plymouthd.conf" << 'EOF'
[Daemon]
Theme=agenticos
ShowDelay=0
DeviceTimeout=8
EOF

    # 5. Set default.plymouth and text.plymouth symlinks in initrd
    ln -sf /usr/share/plymouth/themes/agenticos/agenticos.plymouth \
        "${INITRD_MAIN}/usr/share/plymouth/themes/default.plymouth"
    ln -sf /usr/share/plymouth/themes/agenticos/agenticos.plymouth \
        "${INITRD_MAIN}/usr/share/plymouth/themes/text.plymouth"

    # 6. Neutralize ubuntu-text theme inside initrd
    if [[ -d "${INITRD_MAIN}/usr/share/plymouth/themes/ubuntu-text" ]]; then
        cat > "${INITRD_MAIN}/usr/share/plymouth/themes/ubuntu-text/ubuntu-text.plymouth" << 'EOF'
[Plymouth Theme]
Name=AgenticOS
Description=AgenticOS Text Mode
ModuleName=ubuntu-text

[ubuntu-text]
title=AgenticOS v0.1 Alpha
black=0x030712
white=0xffffff
brown=0x00d4ff
blue=0x00ffff
EOF
    fi

    # 7. Neutralize any ubuntu logo image in initrd
    if [[ -f "${INITRD_MAIN}/usr/share/plymouth/ubuntu-logo.png" ]]; then
        cp -p "${PROJECT_ROOT}/linux_integration/plymouth/agenticos/agenticos-splash.png" \
            "${INITRD_MAIN}/usr/share/plymouth/ubuntu-logo.png"
    fi

    # 8. Disable Casper autologin script in initrd so LightDM displays the graphical login screen
    if [[ -f "${INITRD_MAIN}/scripts/casper-bottom/15autologin" ]]; then
        echo "  [initrd] Neutralizing Casper 15autologin to preserve LightDM login screen..."
        rm -f "${INITRD_MAIN}/scripts/casper-bottom/15autologin"
    fi

    # 9. Repack initrd: preserve all early microcode segments (up to 3rd CPIO trailer) and compress main with zstd
    python3 -c "
with open('${INITRD_TARGET}', 'rb') as f:
    data = f.read()

pos = 0
trailers = []
while True:
    idx = data.find(b'TRAILER!!!', pos)
    if idx == -1:
        break
    trailers.append(idx)
    pos = idx + 10

if len(trailers) >= 3:
    early_size = (trailers[2] + 10 + 511) & ~511
else:
    early_size = 59658752

with open('${INITRD_PATCH_DIR}/early.cpio', 'wb') as f:
    f.write(data[:early_size])
"
    (cd "${INITRD_MAIN}" && find . -mindepth 1 | cpio -H newc -o --quiet | zstd -c -1 -T0) > "${INITRD_PATCH_DIR}/main.zst"
    cat "${INITRD_PATCH_DIR}/early.cpio" "${INITRD_PATCH_DIR}/main.zst" > "${INITRD_TARGET}"
    echo "  ✅ Patched Casper initrd with AgenticOS Plymouth theme ($(stat -c%s "${INITRD_TARGET}") bytes)."
fi

rm -rf "${INITRD_PATCH_DIR}"

# -----------------------------------------------------------------------------
# Stage 4/7 — Repack SquashFS
# -----------------------------------------------------------------------------

echo "[Stage 4/7] Repacking compressed SquashFS..."

rm -f \
    "${ISO_ROOT_DIR}/casper/${LIVE_SQUASHFS_NAME}"

mksquashfs \
    "${SQUASHFS_ROOT_DIR}" \
    "${ISO_ROOT_DIR}/casper/${LIVE_SQUASHFS_NAME}" \
    -noappend \
    -comp xz \
    -Xbcj x86 \
    -b 1048576

rm -rf "${SQUASHFS_ROOT_DIR}"

# -----------------------------------------------------------------------------
# Stage 5/7 — Configure BIOS + UEFI GRUB
# -----------------------------------------------------------------------------

echo "[Stage 5/7] Staging GRUB bootloaders and configuration..."

mkdir -p \
    "${ISO_ROOT_DIR}/boot/grub/i386-pc" \
    "${ISO_ROOT_DIR}/boot/grub/x86_64-efi"

GRUB_TEMPLATE="${PROJECT_ROOT}/packaging/config/grub.cfg"
GRUB_OUTPUT="${ISO_ROOT_DIR}/boot/grub/grub.cfg"

if [[ ! -f "${GRUB_TEMPLATE}" ]]; then
    echo "ERROR: GRUB configuration template not found:" >&2
    echo "       ${GRUB_TEMPLATE}" >&2
    exit 1
fi

# Expand build-time SquashFS variable into the final GRUB configuration.
sed \
    "s|\${LIVE_SQUASHFS_NAME}|${LIVE_SQUASHFS_NAME}|g" \
    "${GRUB_TEMPLATE}" \
    > "${GRUB_OUTPUT}"

# Verify that the generated GRUB configuration contains the correct image.
if ! grep -q \
    "layerfs-path=${LIVE_SQUASHFS_NAME}" \
    "${GRUB_OUTPUT}"
then
    echo "ERROR: Generated GRUB configuration does not reference:" >&2
    echo "       ${LIVE_SQUASHFS_NAME}" >&2
    exit 1
fi

# -----------------------------------------------------------------------------
# Stage 5B — BIOS GRUB El Torito Image
# -----------------------------------------------------------------------------

grub-mkimage \
    -O i386-pc-eltorito \
    -p /boot/grub \
    -o "${ISO_ROOT_DIR}/boot/grub/i386-pc/eltorito.img" \
    biosdisk iso9660 part_msdos normal test linux echo

# -----------------------------------------------------------------------------
# Stage 5C — UEFI FAT ESP Image
# -----------------------------------------------------------------------------

EFI_IMG="${ISO_ROOT_DIR}/boot/grub/efi.img"

truncate \
    -s 4M \
    "${EFI_IMG}"

mformat \
    -i "${EFI_IMG}" \
    -F \
    -T 8192 \
    ::

mmd \
    -i "${EFI_IMG}" \
    ::/EFI

mmd \
    -i "${EFI_IMG}" \
    ::/EFI/BOOT

TEMP_BOOTX64="$(mktemp /tmp/bootx64.XXXXXX.efi)"

grub-mkimage \
    -O x86_64-efi \
    -p /boot/grub \
    -o "${TEMP_BOOTX64}" \
    fat iso9660 part_gpt part_msdos normal test linux echo

mcopy \
    -i "${EFI_IMG}" \
    "${TEMP_BOOTX64}" \
    ::/EFI/BOOT/BOOTX64.EFI

rm -f "${TEMP_BOOTX64}"

# -----------------------------------------------------------------------------
# Stage 6/7 — Master Hybrid ISO
# -----------------------------------------------------------------------------

echo "[Stage 6/7] Mastering hybrid ISO via xorriso..."

xorriso -as mkisofs \
    -r \
    -V "${VOLUME_ID}" \
    -J \
    -joliet-long \
    -l \
    -b boot/grub/i386-pc/eltorito.img \
    -c boot.catalog \
    -no-emul-boot \
    -boot-load-size 4 \
    -boot-info-table \
    --embedded-boot /usr/lib/grub/i386-pc/boot_hybrid.img \
    --eltorito-alt-boot \
    -e boot/grub/efi.img \
    -no-emul-boot \
    -isohybrid-gpt-basdat \
    -output "${OUTPUT_ISO_PATH}" \
    "${ISO_ROOT_DIR}"

# -----------------------------------------------------------------------------
# Stage 7/7 — Integrity Checksum
# -----------------------------------------------------------------------------

echo "[Stage 7/7] Generating SHA256 checksum..."

sha256sum \
    "${OUTPUT_ISO_PATH}" \
    > "${OUTPUT_ISO_PATH}.sha256"

echo "====================================================================="
echo "✅ AgenticOS ISO Build Complete"
echo "====================================================================="
echo "Target : ${BUILD_TARGET}"
echo "ISO    : ${OUTPUT_ISO_PATH}"
echo "SHA256 : $(cat "${OUTPUT_ISO_PATH}.sha256")"
echo "====================================================================="
