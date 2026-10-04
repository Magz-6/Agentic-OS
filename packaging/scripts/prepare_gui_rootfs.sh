#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

BASE_SQUASHFS="${1:-}"
OUTPUT_ROOTFS="${2:-}"

if [[ -z "${BASE_SQUASHFS}" || -z "${OUTPUT_ROOTFS}" ]]; then
    echo "ERROR: Base SquashFS and output rootfs paths are required." >&2
    echo "Usage: $0 <base-squashfs> <output-rootfs>" >&2
    exit 1
fi

if [[ ! -f "${BASE_SQUASHFS}" ]]; then
    echo "ERROR: Base SquashFS does not exist: ${BASE_SQUASHFS}" >&2
    exit 1
fi

if [[ -e "${OUTPUT_ROOTFS}" ]]; then
    echo "ERROR: Output rootfs already exists: ${OUTPUT_ROOTFS}" >&2
    echo "Refusing to overwrite it." >&2
    exit 1
fi

GUI_PACKAGE_MANIFEST="${PROJECT_ROOT}/packaging/config/gui-packages.conf"

if [[ ! -f "${GUI_PACKAGE_MANIFEST}" ]]; then
    echo "ERROR: GUI package manifest missing: ${GUI_PACKAGE_MANIFEST}" >&2
    exit 1
fi

if [[ "$(id -u)" -ne 0 ]]; then
    echo "[GUI RootFS] Re-running with sudo..."
    exec sudo "$0" "$@"
fi

mapfile -t GUI_PACKAGES < <(
    grep -Ev '^[[:space:]]*(#|$)' "${GUI_PACKAGE_MANIFEST}"
)

if [[ "${#GUI_PACKAGES[@]}" -eq 0 ]]; then
    echo "ERROR: GUI package manifest contains no packages." >&2
    exit 1
fi

MOUNTS=()

cleanup() {
    set +e
    for mountpoint in "${MOUNTS[@]}"; do
        umount -lf "${OUTPUT_ROOTFS}${mountpoint}" 2>/dev/null || true
    done
}

trap cleanup EXIT

echo "[GUI RootFS] Base SquashFS: ${BASE_SQUASHFS}"
echo "[GUI RootFS] Output rootfs: ${OUTPUT_ROOTFS}"
echo "[GUI RootFS] Package manifest: ${GUI_PACKAGE_MANIFEST}"

echo "[GUI RootFS] Extracting base SquashFS..."
mkdir -p "${OUTPUT_ROOTFS}"
unsquashfs -f -d "${OUTPUT_ROOTFS}" "${BASE_SQUASHFS}"

echo "[GUI RootFS] Preparing chroot environment..."

mkdir -p \
    "${OUTPUT_ROOTFS}/dev" \
    "${OUTPUT_ROOTFS}/proc" \
    "${OUTPUT_ROOTFS}/sys" \
    "${OUTPUT_ROOTFS}/run"

mount --bind /dev "${OUTPUT_ROOTFS}/dev"
MOUNTS+=("/dev")

mount -t proc proc "${OUTPUT_ROOTFS}/proc"
MOUNTS+=("/proc")

mount --rbind /sys "${OUTPUT_ROOTFS}/sys"
mount --make-rslave "${OUTPUT_ROOTFS}/sys"
MOUNTS+=("/sys")

mount --bind /run "${OUTPUT_ROOTFS}/run"
MOUNTS+=("/run")

cp -L /etc/resolv.conf "${OUTPUT_ROOTFS}/etc/resolv.conf"

echo "[GUI RootFS] Updating APT indexes..."
chroot "${OUTPUT_ROOTFS}" apt-get update

echo "[GUI RootFS] Installing GUI packages:"
printf '  - %s\n' "${GUI_PACKAGES[@]}"

chroot "${OUTPUT_ROOTFS}" apt-get install -y --no-install-recommends \
    "${GUI_PACKAGES[@]}"

echo "[GUI RootFS] Verifying GUI packages..."
chroot "${OUTPUT_ROOTFS}" dpkg-query -W \
    -f='${Package} ${Status}\n' \
    "${GUI_PACKAGES[@]}"

echo "[GUI RootFS] GUI rootfs preparation complete."
