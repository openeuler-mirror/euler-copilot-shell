#!/usr/bin/env bash
# build_rpm.sh: build RPM package using the tarball created by create_tarball.sh
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

# Determine script directory and repo root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# Create the tarball and set BUILD_DIR and TARBALL
TARBALL_ARGS=()
[[ ${DEV_MODE} -eq 1 ]] && TARBALL_ARGS+=(--dev)
[[ ${STAGED_MODE} -eq 1 ]] && TARBALL_ARGS+=(--staged)
eval "$("${SCRIPT_DIR}"/create_tarball.sh "${TARBALL_ARGS[@]}")"
set +u
if [[ -z "${BUILD_DIR:-}" || -z "${TARBALL:-}" ]]; then
    echo "Error: BUILD_DIR 或 TARBALL 变量未设置，create_tarball.sh 执行失败。" >&2
    exit 1
fi
set -u

# Spec file path
SPEC_FILE="${REPO_ROOT}/distribution/linux/euler-copilot-shell.spec"

# Prepare RPM build directories under BUILD_DIR
mkdir -p "${BUILD_DIR}/"{BUILD,RPMS,SOURCES,SPECS,SRPMS,BUILDROOT}

# Copy source tarball and spec into RPM tree
cp "${BUILD_DIR}/${TARBALL}" "${BUILD_DIR}/SOURCES/"
cp "${SPEC_FILE}" "${BUILD_DIR}/SPECS/"

# Build the RPMs
echo "Building RPM using topdir ${BUILD_DIR}"
if [[ ${DEV_MODE} -eq 1 ]]; then
    # 在 dev 模式下，传递时间戳给 rpmbuild
    rpmbuild --define "_topdir ${BUILD_DIR}" --define "dev_timestamp ${TIMESTAMP}" -ba "${BUILD_DIR}/SPECS/$(basename "${SPEC_FILE}")"
else
    rpmbuild --define "_topdir ${BUILD_DIR}" -ba "${BUILD_DIR}/SPECS/$(basename "${SPEC_FILE}")"
fi

# Output locations
echo "RPM build complete."
echo "SRPMs: ${BUILD_DIR}/SRPMS"
echo "Binary RPMs: ${BUILD_DIR}/RPMS"
