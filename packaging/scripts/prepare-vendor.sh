#!/usr/bin/env bash
# packaging/scripts/prepare-vendor.sh
# Generate a vendor tarball containing all Go module dependencies.
#
# This script produces the vendor.tar.xz archive referenced as Source3
# in the RPM spec file. It must be run before uploading sources to the
# openEuler build system.
#
# Usage:
#   bash packaging/scripts/prepare-vendor.sh <version> [<output_dir>]
#
# Output:
#   <output_dir>/witty-cli-vendor-<version>.tar.xz  (default: .)

set -euo pipefail

if [ "$(uname -s)" != "Linux" ]; then
  echo "ERROR: This script must run on Linux. Current OS: $(uname -s)" >&2
  exit 1
fi

VERSION="${1:-}"
if [ -z "$VERSION" ]; then
  echo "Usage: $0 <version> [output_dir]" >&2
  echo "Example: $0 3.0.0" >&2
  echo "Example: $0 3.0.0 build/release" >&2
  exit 1
fi

OUTDIR="${2:-.}"
mkdir -p "${OUTDIR}"

OUTPUT="${OUTDIR}/witty-cli-vendor-${VERSION}.tar.xz"

echo "==> Running go mod vendor..."
go mod vendor

echo "==> Verifying vendored modules..."
go mod verify

echo "==> Creating vendor archive: ${OUTPUT}"
tar -cJf "${OUTPUT}" vendor/

echo "==> Cleaning up vendor/ directory..."
rm -rf vendor/

echo "==> Done: ${OUTPUT} ($(du -h "${OUTPUT}" | cut -f1))"
