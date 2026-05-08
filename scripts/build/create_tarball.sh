#!/usr/bin/env bash
# create_tarball.sh: create a tarball of current repo for RPM build.
set -euo pipefail

# Parse arguments
DEV_MODE=0
STAGED_MODE=0
while [[ $# -gt 0 ]]; do
    case "$1" in
    --dev)
        DEV_MODE=1
        shift
        ;;
    --staged)
        STAGED_MODE=1
        shift
        ;;
    *)
        echo "Unknown parameter: $1" >&2
        echo "Usage: $0 [--dev] [--staged]" >&2
        exit 1
        ;;
    esac
done

# Locate spec file relative to repo root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
SPEC_FILE="${REPO_ROOT}/distribution/linux/euler-copilot-shell.spec"

# Extract name and version from spec
NAME=$(grep -E '^Name:' "$SPEC_FILE" | awk '{print $2}')
VERSION=$(grep -E '^Version:' "$SPEC_FILE" | awk '{print $2}')

# 如果是 dev 模式，添加时间戳
if [[ ${DEV_MODE} -eq 1 ]]; then
    TIMESTAMP=$(date +%Y%m%d%H%M%S)
fi

# Create build directory in repo
BUILD_DIR="${REPO_ROOT}/build"
mkdir -p "${BUILD_DIR}"
TARBALL="${NAME}-${VERSION}.tar.gz"

echo "Creating tarball ${TARBALL} in ${BUILD_DIR}" >&2
# Determine archive source: staged index or committed HEAD
if [[ ${STAGED_MODE} -eq 1 ]]; then
    echo "Using staged content (git index) for archive..." >&2
    ARCHIVE_SOURCE=$(git -C "${REPO_ROOT}" write-tree)
else
    ARCHIVE_SOURCE="HEAD"
fi

# Collect top-level archive paths and exclude non-source top-level directories from source packages.
ARCHIVE_PATHS=()
while IFS= read -r path; do
    case "${path}" in
    "" | "tests" | ".claude" | ".github" | "distribution")
        continue
        ;;
    "scripts")
        # Include scripts but exclude scripts/build and filter scripts/tools
        while IFS= read -r subpath; do
            case "${subpath}" in
            "build")
                continue
                ;;
            "tools")
                # Include only i18n-manager.sh from scripts/tools
                while IFS= read -r toolfile; do
                    case "${toolfile}" in
                    "i18n-manager.sh")
                        ARCHIVE_PATHS+=("scripts/tools/${toolfile}")
                        ;;
                    *)
                        continue
                        ;;
                    esac
                done < <(git -C "${REPO_ROOT}" ls-tree --name-only "${ARCHIVE_SOURCE}:scripts/tools/")
                ;;
            *)
                ARCHIVE_PATHS+=("scripts/${subpath}")
                ;;
            esac
        done < <(git -C "${REPO_ROOT}" ls-tree --name-only "${ARCHIVE_SOURCE}:scripts/")
        ;;
    *)
        ARCHIVE_PATHS+=("${path}")
        ;;
    esac
done < <(git -C "${REPO_ROOT}" ls-tree --name-only "${ARCHIVE_SOURCE}")

if [[ ${#ARCHIVE_PATHS[@]} -eq 0 ]]; then
    echo "Error: no archive paths resolved for ${ARCHIVE_SOURCE}" >&2
    exit 1
fi

# Archive the selected source into tarball with proper prefix.
git -C "${REPO_ROOT}" archive --format=tar.gz --prefix="${NAME}-${VERSION}/" -o "${BUILD_DIR}/${TARBALL}" "${ARCHIVE_SOURCE}" "${ARCHIVE_PATHS[@]}"

# 输出变量用于 build_rpm.sh 的 eval
echo "BUILD_DIR=${BUILD_DIR}"
echo "TARBALL=${TARBALL}"
if [[ ${DEV_MODE} -eq 1 ]]; then
    echo "TIMESTAMP=${TIMESTAMP}"
fi
