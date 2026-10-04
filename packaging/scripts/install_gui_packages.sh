#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
GUI_PACKAGE_MANIFEST="${PROJECT_ROOT}/packaging/config/gui-packages.conf"
ROOTFS="${1:-}"

if [[ -z "${ROOTFS}" ]]; then
    echo "ERROR: Root filesystem path is required." >&2
    echo "Usage: $0 <rootfs>" >&2
    exit 1
fi
if [[ ! -d "${ROOTFS}" ]]; then
    echo "ERROR: Root filesystem does not exist: ${ROOTFS}" >&2
    exit 1
fi
if [[ ! -f "${GUI_PACKAGE_MANIFEST}" ]]; then
    echo "ERROR: GUI package manifest missing: ${GUI_PACKAGE_MANIFEST}" >&2
    exit 1
fi
mapfile -t GUI_PACKAGES < <(
    grep -Ev '^[[:space:]]*(#|$)' "${GUI_PACKAGE_MANIFEST}"
)
if [[ "${#GUI_PACKAGES[@]}" -eq 0 ]]; then
    echo "ERROR: GUI package manifest contains no packages." >&2
    exit 1
fi
echo "[GUI Installer] Target rootfs: ${ROOTFS}"
echo "[GUI Installer] Package manifest: ${GUI_PACKAGE_MANIFEST}"
echo "[GUI Installer] Packages:"
printf '  - %s\n' "${GUI_PACKAGES[@]}"
echo "[GUI Installer] Installing GUI packages..."

sudo chroot "${ROOTFS}" /usr/bin/apt-get install -y --no-install-recommends \
    "${GUI_PACKAGES[@]}"
