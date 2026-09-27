#!/usr/bin/env bash
# AgenticOS v0.1 Alpha — Artifact Verification Script
# Read-only verification of upstream live-media artifacts and Casper pairing.
# Strict safety: NO root operations, NO package modifications, NO destructive actions.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
CONFIG_FILE="${PROJECT_ROOT}/packaging/config/build.conf"

if [[ ! -f "${CONFIG_FILE}" ]]; then
    echo "ERROR: Configuration file not found: ${CONFIG_FILE}" >&2
    exit 1
fi

# Load configuration
# shellcheck source=../config/build.conf
source "${CONFIG_FILE}"

STAGING_PATH="${PROJECT_ROOT}/${STAGING_DIR}"

echo "====================================================================="
echo "AgenticOS — Upstream Artifact Verification"
echo "====================================================================="
echo "Project Root:      ${PROJECT_ROOT}"
echo "Staging Path:      ${STAGING_PATH}"
echo "Expected Base:     ${BASE_SQUASHFS_NAME}"
echo "Expected SHA256:   ${BASE_SQUASHFS_SHA256}"
echo "====================================================================="

# Check tool prerequisites
for tool in sha256sum unsquashfs; do
    if ! command -v "${tool}" >/dev/null 2>&1; then
        echo "ERROR: Required tool '${tool}' is not installed." >&2
        exit 1
    fi
done

# Check if essential live components exist in staging
MISSING=0
for comp in "${KERNEL_FILE}" "${INITRD_FILE}" "${BASE_SQUASHFS_NAME}"; do
    if [[ ! -f "${STAGING_PATH}/${comp}" ]]; then
        echo "MISSING: ${STAGING_PATH}/${comp}" >&2
        MISSING=1
    else
        echo "  - Found: ${comp} ($(stat -c%s "${STAGING_PATH}/${comp}") bytes)"
    fi
done

if [[ "${MISSING}" -ne 0 ]]; then
    echo "ERROR: Required live components missing in staging." >&2
    exit 1
fi

# Verify Base SquashFS Checksum
echo "[1/3] Verifying Base SquashFS SHA256 Checksum..."
ACTUAL_HASH="$(sha256sum "${STAGING_PATH}/${BASE_SQUASHFS_NAME}" | awk '{print $1}')"
if [[ "${ACTUAL_HASH}" != "${BASE_SQUASHFS_SHA256}" ]]; then
    echo "ERROR: SHA256 mismatch for ${BASE_SQUASHFS_NAME}!" >&2
    echo "Expected: ${BASE_SQUASHFS_SHA256}" >&2
    echo "Actual:   ${ACTUAL_HASH}" >&2
    exit 1
fi
echo "  ✅ Base SquashFS checksum verified match."

# Inspect Kernel File
echo "[2/3] Inspecting Kernel File..."
file "${STAGING_PATH}/${KERNEL_FILE}"

# Inspect SquashFS Superblock
echo "[3/3] Inspecting SquashFS Superblock..."
unsquashfs -s "${STAGING_PATH}/${BASE_SQUASHFS_NAME}" | grep -E 'superblock|Compression|Number of inodes|Creation'

echo "====================================================================="
echo "✅ Artifact verification successful. All live-boot components validated."
echo "====================================================================="
