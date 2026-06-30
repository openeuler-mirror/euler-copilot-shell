#!/usr/bin/env bash
# packaging/scripts/prepare-release.sh
# Prepare all source files needed for an openEuler RPM build.
#
# Usage:
#   bash packaging/scripts/prepare-release.sh <version> [<go_version>]
#
# Defaults:
#   go_version = 1.26.4
#
# Outputs (under build/release/):
#   euler-copilot-shell-<version>.tar.gz → Source0 (source code)
#   go<go_version>.linux-amd64.tar.gz   → Source1 (Go toolchain amd64)
#   go<go_version>.linux-arm64.tar.gz   → Source2 (Go toolchain arm64)
#   witty-vendor-<version>.tar.xz       → Source3 (vendored deps)
#   build-info                          → Source4 (commit + date)

set -euo pipefail

VERSION="${1:-}"
GO_VERSION="${2:-1.26.4}"

if [ -z "$VERSION" ]; then
  echo "Usage: $0 <version> [go_version]" >&2
  echo "Example: $0 3.0.0" >&2
  echo "Example: $0 3.0.0 1.26.4" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
OUTDIR="build/release"

mkdir -p "${OUTDIR}"

SOURCE_TARBALL="${OUTDIR}/euler-copilot-shell-${VERSION}.tar.gz"
GO_AMD64="${OUTDIR}/go${GO_VERSION}.linux-amd64.tar.gz"
GO_ARM64="${OUTDIR}/go${GO_VERSION}.linux-arm64.tar.gz"
VENDOR_TARBALL="${OUTDIR}/witty-vendor-${VERSION}.tar.xz"
BUILD_INFO="${OUTDIR}/build-info"

# ── Step 1: Source tarball ─────────────────────────────────────────
echo "==> [1/5] Generating source tarball: ${SOURCE_TARBALL}"
if git rev-parse --git-dir >/dev/null 2>&1; then
  if git rev-parse "v${VERSION}" >/dev/null 2>&1; then
    git archive --format=tar.gz --prefix="euler-copilot-shell-${VERSION}/" \
      -o "${SOURCE_TARBALL}" "v${VERSION}"
  else
    echo "WARNING: tag v${VERSION} not found, archiving HEAD" >&2
    git archive --format=tar.gz --prefix="euler-copilot-shell-${VERSION}/" \
      -o "${SOURCE_TARBALL}" HEAD
  fi
else
  echo "ERROR: not in a git repository; cannot create source tarball" >&2
  exit 1
fi
echo "       ${SOURCE_TARBALL} ($(du -h "${SOURCE_TARBALL}" | cut -f1))"

# ── Step 2: Go toolchain (amd64) ───────────────────────────────────
echo "==> [2/5] Go toolchain (amd64): ${GO_AMD64}"
if [ -f "${GO_AMD64}" ]; then
  echo "       ${GO_AMD64} already exists, skipping"
else
  curl -fSL "https://go.dev/dl/$(basename "${GO_AMD64}")" -o "${GO_AMD64}"
  echo "       ${GO_AMD64} ($(du -h "${GO_AMD64}" | cut -f1))"
fi

# ── Step 3: Go toolchain (arm64) ───────────────────────────────────
echo "==> [3/5] Go toolchain (arm64): ${GO_ARM64}"
if [ -f "${GO_ARM64}" ]; then
  echo "       ${GO_ARM64} already exists, skipping"
else
  curl -fSL "https://go.dev/dl/$(basename "${GO_ARM64}")" -o "${GO_ARM64}"
  echo "       ${GO_ARM64} ($(du -h "${GO_ARM64}" | cut -f1))"
fi

# ── Step 4: Vendor tarball ─────────────────────────────────────────
echo "==> [4/5] Generating vendor tarball: ${VENDOR_TARBALL}"
bash "${SCRIPT_DIR}/prepare-vendor.sh" "${VERSION}" "${OUTDIR}"

# ── Step 5: Build info ─────────────────────────────────────────────
echo "==> [5/5] Generating build-info: ${BUILD_INFO}"
COMMIT=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
DATE=$(date -u +%Y-%m-%dT%H:%M:%SZ)
cat >"${BUILD_INFO}" <<EOF
%global commit ${COMMIT}
%global date   ${DATE}
EOF
cat "${BUILD_INFO}"

echo ""
echo "══ All artifacts ready for openEuler build ══"
echo ""
echo "Output directory: ${OUTDIR}/"
echo ""
ls -lh "${OUTDIR}/"
echo ""
echo "Upload the following files to the openEuler build system:"
echo "  Source0: ${SOURCE_TARBALL}"
echo "  Source1: ${GO_AMD64}"
echo "  Source2: ${GO_ARM64}"
echo "  Source3: ${VENDOR_TARBALL}"
echo "  Source4: ${BUILD_INFO}"
echo ""
echo "Then run:"
echo "  rpmbuild -ba packaging/euler-copilot-shell.spec"
