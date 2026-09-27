#!/usr/bin/env bash
# AgenticOS v0.1 Alpha — Reproducible ISO Build Script
# Architecture: Candidate B — Ubuntu 24.04.5 LTS + Casper/OverlayFS + Custom xorriso/GRUB
# Status: AUTHORING SKELETON — EXECUTION STRICTLY BLOCKED PENDING ARTIFACT VALIDATION
#
# Preflight Constraints:
# - Runs 100% in unprivileged user space (NO sudo, NO root operations)
# - Requires verified upstream live media artifact or verified staged components
# - Service installation remains UNDEFINED / BLOCKED pending team approval

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
CONFIG_FILE="${PROJECT_ROOT}/packaging/config/build.conf"

if [[ ! -f "${CONFIG_FILE}" ]]; then
    echo "ERROR: Configuration file missing: ${CONFIG_FILE}" >&2
    exit 1
fi

# Load configuration
# shellcheck source=../config/build.conf
source "${CONFIG_FILE}"

STAGING_PATH="${PROJECT_ROOT}/${STAGING_DIR}"
SOURCE_ISO="${STAGING_PATH}/${UPSTREAM_ISO_NAME}"
ISO_ROOT_DIR="${PROJECT_ROOT}/${ISO_ROOT}"
# SQUASHFS_ROOT_DIR is located on native ext4 (/tmp) to ensure full POSIX semantics and avoid NTFS permission failures
SQUASHFS_ROOT_DIR="/tmp/agenticos_squashfs_root"
OUTPUT_ISO_PATH="${PROJECT_ROOT}/${OUTPUT_DIR}/${ISO_NAME}"

echo "====================================================================="
echo "AgenticOS — Reproducible ISO Build Pipeline"
echo "Target Artifact: ${ISO_NAME}"
echo "Build Architecture: Candidate B (Casper / OverlayFS)"
echo "====================================================================="

# -----------------------------------------------------------------------------
# Preflight 1: Architectural Governance & Service Contract Guard
# -----------------------------------------------------------------------------
if [[ "${INSTALL_SYSTEMD_SERVICE}" -ne 0 ]] || [[ "${ENABLE_SYSTEMD_SERVICE}" -ne 0 ]]; then
    echo "CRITICAL BLOCKER: Automatic systemd service installation or enablement" >&2
    echo "is currently UNDEFINED / BLOCKED pending team architecture contract." >&2
    echo "Aborting build pipeline." >&2
    exit 1
fi

# -----------------------------------------------------------------------------
# Preflight 2: Tooling Verification
# -----------------------------------------------------------------------------
REQUIRED_TOOLS=(
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

# Check GRUB module libraries
if [[ ! -d "/usr/lib/grub/x86_64-efi" ]] || [[ ! -d "/usr/lib/grub/i386-pc" ]]; then
    echo "ERROR: GRUB EFI or i386-pc module directories not found." >&2
    exit 1
fi

# -----------------------------------------------------------------------------
# Preflight 3: Source Artifact Presence & Checksum Validation
# -----------------------------------------------------------------------------
HAVE_STAGED_COMPONENTS=0
if [[ -f "${STAGING_PATH}/${KERNEL_FILE}" ]] && \
   [[ -f "${STAGING_PATH}/${INITRD_FILE}" ]] && \
   [[ -f "${STAGING_PATH}/${BASE_SQUASHFS_NAME}" ]]; then
    echo "[Preflight] Staged components found. Verifying Base SquashFS checksum..."
    CALC_SQUASH_HASH="$(sha256sum "${STAGING_PATH}/${BASE_SQUASHFS_NAME}" | awk '{print $1}')"
    if [[ "${CALC_SQUASH_HASH}" != "${BASE_SQUASHFS_SHA256}" ]]; then
        echo "ERROR: Checksum mismatch for staged ${BASE_SQUASHFS_NAME}!" >&2
        exit 1
    fi
    echo "  ✅ Staged Base SquashFS checksum verified."
    HAVE_STAGED_COMPONENTS=1
elif [[ -f "${SOURCE_ISO}" ]]; then
    echo "[Preflight] Source ISO found. Verifying SHA256 checksum..."
    CALCULATED_HASH="$(sha256sum "${SOURCE_ISO}" | awk '{print $1}')"
    if [[ "${CALCULATED_HASH}" != "${UPSTREAM_SHA256}" ]]; then
        echo "ERROR: Checksum mismatch for source artifact!" >&2
        echo "Expected: ${UPSTREAM_SHA256}" >&2
        echo "Actual:   ${CALCULATED_HASH}" >&2
        exit 1
    fi
    echo "  ✅ Source ISO checksum verified."
else
    echo "ERROR: Neither staged live components nor source ISO found in ${STAGING_PATH}" >&2
    exit 1
fi

# -----------------------------------------------------------------------------
# Preflight 4: Available Disk Space Check (Requires >= 5 GB in staging)
# -----------------------------------------------------------------------------
AVAILABLE_KB="$(df -k "${STAGING_PATH}" | awk 'NR==2 {print $4}')"
if [[ "${AVAILABLE_KB}" -lt 5242880 ]]; then
    echo "ERROR: Less than 5 GB free space available in staging area." >&2
    exit 1
fi

# -----------------------------------------------------------------------------
# Stage 1: Clean & Prepare Staging Trees
# -----------------------------------------------------------------------------
echo "[Stage 1/7] Preparing clean staging trees..."
mkdir -p "${ISO_ROOT_DIR}" "${SQUASHFS_ROOT_DIR}" "${PROJECT_ROOT}/${OUTPUT_DIR}"

# Safe clean of previous intermediate staging contents
find "${ISO_ROOT_DIR}" -mindepth 1 -delete 2>/dev/null || true
find "${SQUASHFS_ROOT_DIR}" -mindepth 1 -delete 2>/dev/null || true

# -----------------------------------------------------------------------------
# Stage 2: Stage Live-Boot Kernel, Initrd, and Base SquashFS
# -----------------------------------------------------------------------------
echo "[Stage 2/7] Staging live-boot components..."
mkdir -p "${ISO_ROOT_DIR}/casper"

if [[ "${HAVE_STAGED_COMPONENTS}" -eq 1 ]]; then
    cp "${STAGING_PATH}/${KERNEL_FILE}" "${ISO_ROOT_DIR}/casper/vmlinuz"
    cp "${STAGING_PATH}/${INITRD_FILE}" "${ISO_ROOT_DIR}/casper/initrd"
    cp "${STAGING_PATH}/${BASE_SQUASHFS_NAME}" "${ISO_ROOT_DIR}/casper/${BASE_SQUASHFS_NAME}"
else
    xorriso -indev "${SOURCE_ISO}" -extract /casper/vmlinuz "${ISO_ROOT_DIR}/casper/vmlinuz"
    xorriso -indev "${SOURCE_ISO}" -extract /casper/initrd "${ISO_ROOT_DIR}/casper/initrd"
    xorriso -indev "${SOURCE_ISO}" -extract "/casper/${BASE_SQUASHFS_NAME}" "${ISO_ROOT_DIR}/casper/${BASE_SQUASHFS_NAME}"
fi

# Casper medium identification metadata:
# The Ubuntu 24.04.5 Live Server initrd contains /conf/uuid.conf with UUID
# 50c98eb4-4c0f-4c1a-82d2-4234cf187d50. Casper's matches_uuid() function in
# /scripts/casper compares /conf/uuid.conf against /.disk/casper-uuid-generic
# on optical and USB block devices. Without this matching file, Casper fails to
# detect and mount the live boot medium.
mkdir -p "${ISO_ROOT_DIR}/.disk"
echo "${CASPER_UUID:-50c98eb4-4c0f-4c1a-82d2-4234cf187d50}" > "${ISO_ROOT_DIR}/.disk/casper-uuid-generic"
echo "AgenticOS v0.1 Alpha" > "${ISO_ROOT_DIR}/.disk/info"


# -----------------------------------------------------------------------------
# Stage 3: Unpack SquashFS & Integrate AgenticOS Layer
# -----------------------------------------------------------------------------
echo "[Stage 3/7] Unpacking squashfs root filesystem..."
rm -rf "${SQUASHFS_ROOT_DIR}"
unsquashfs -f -no-exit-code -no-xattrs -d "${SQUASHFS_ROOT_DIR}" "${ISO_ROOT_DIR}/casper/${BASE_SQUASHFS_NAME}"

echo "[Stage 3/7] Staging provisional AgenticOS user-space components..."
TARGET_DIR="${SQUASHFS_ROOT_DIR}/${PROPOSED_INSTALL_DIR}"
mkdir -p "${TARGET_DIR}"

# Copy user-space modules to provisional location
for module in "adapters" "hardware" "telemetry" "linux_integration"; do
    if [[ -d "${PROJECT_ROOT}/${module}" ]]; then
        cp -a "${PROJECT_ROOT}/${module}" "${TARGET_DIR}/"
    fi
done

# Note: systemd service file is NOT enabled or placed in /etc/systemd/system/
# It is staged purely as an unlinked reference file under the provisional location
mkdir -p "${TARGET_DIR}/systemd"
cp -a "${PROJECT_ROOT}/linux_integration/systemd/"* "${TARGET_DIR}/systemd/" || true

# -----------------------------------------------------------------------------
# Stage 4: Repack Compressed SquashFS
# -----------------------------------------------------------------------------
echo "[Stage 4/7] Repacking compressed squashfs..."
rm -f "${ISO_ROOT_DIR}/casper/${BASE_SQUASHFS_NAME}"
mksquashfs "${SQUASHFS_ROOT_DIR}" "${ISO_ROOT_DIR}/casper/${BASE_SQUASHFS_NAME}" \
    -noappend \
    -comp xz \
    -Xbcj x86 \
    -b 1048576

# Clean up temporary ext4 unpack tree
rm -rf "${SQUASHFS_ROOT_DIR}"

# -----------------------------------------------------------------------------
# Stage 5: Configure Dual Bootloader (BIOS & UEFI)
# -----------------------------------------------------------------------------
echo "[Stage 5/7] Staging GRUB bootloaders and configurations..."
mkdir -p "${ISO_ROOT_DIR}/boot/grub/i386-pc"

# 5A: GRUB Configuration
cp "${PROJECT_ROOT}/packaging/config/grub.cfg" "${ISO_ROOT_DIR}/boot/grub/grub.cfg"

# 5B: BIOS GRUB El Torito Core Image
grub-mkimage -O i386-pc \
    -p /boot/grub \
    -o "${ISO_ROOT_DIR}/boot/grub/i386-pc/eltorito.img" \
    biosdisk iso9660 part_gpt part_msdos normal test

# 5C: UEFI FAT ESP Image via mtools (user-space, no loop mount)
EFI_IMG="${ISO_ROOT_DIR}/boot/grub/efi.img"
truncate -s 4M "${EFI_IMG}"
mformat -i "${EFI_IMG}" -F -T 8192 ::
mmd -i "${EFI_IMG}" ::/EFI ::/EFI/BOOT

TEMP_BOOTX64="$(mktemp /tmp/bootx64.XXXXXX.efi)"
grub-mkimage -O x86_64-efi \
    -p /boot/grub \
    -o "${TEMP_BOOTX64}" \
    fat iso9660 part_gpt part_msdos normal test
mcopy -i "${EFI_IMG}" "${TEMP_BOOTX64}" ::/EFI/BOOT/BOOTX64.EFI
rm -f "${TEMP_BOOTX64}"

# -----------------------------------------------------------------------------
# Stage 6: Master Hybrid ISO Image via xorriso
# -----------------------------------------------------------------------------
echo "[Stage 6/7] Mastering hybrid ISO via xorriso..."
xorriso -as mkisofs \
    -r -V "${VOLUME_ID}" \
    -J -joliet-long -l \
    -b boot/grub/i386-pc/eltorito.img \
    -c boot.catalog \
    -no-emul-boot -boot-load-size 4 -boot-info-table \
    --embedded-boot /usr/lib/grub/i386-pc/boot_hybrid.img \
    --eltorito-alt-boot \
    -e boot/grub/efi.img \
    -no-emul-boot \
    -isohybrid-gpt-basdat \
    -output "${OUTPUT_ISO_PATH}" \
    "${ISO_ROOT_DIR}"

# -----------------------------------------------------------------------------
# Stage 7: Integrity Checksum Generation
# -----------------------------------------------------------------------------
echo "[Stage 7/7] Generating SHA256 checksum..."
sha256sum "${OUTPUT_ISO_PATH}" > "${OUTPUT_ISO_PATH}.sha256"

echo "====================================================================="
echo "✅ Build Complete: ${OUTPUT_ISO_PATH}"
echo "Checksum: $(cat "${OUTPUT_ISO_PATH}.sha256")"
echo "====================================================================="
