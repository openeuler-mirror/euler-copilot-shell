#!/usr/bin/env bash
# packaging/scripts/prepare-vendor.sh
# Generate a vendor tarball containing all Go module dependencies.
#
# This script produces the vendor.tar.xz archive referenced as Source3
# in the RPM spec file. It must be run before uploading sources to the
# openEuler build system.
#
# Usage:
#   bash packaging/scripts/prepare-vendor.sh <version>
#
# Output:
#   witty-vendor-<version>.tar.xz

set -euo pipefail

VERSION="${1:-}"
if [ -z "$VERSION" ]; then
  echo "Usage: $0 <version>" >&2
  echo "Example: $0 3.0.0" >&2
  exit 1
fi

OUTPUT="witty-vendor-${VERSION}.tar.xz"

echo "==> Running go mod vendor..."
go mod vendor

echo "==> Verifying vendored modules..."
go mod verify

echo "==> Creating vendor archive: ${OUTPUT}"
tar -cJf "${OUTPUT}" vendor/

echo "==> Cleaning up vendor/ directory..."
rm -rf vendor/

echo "==> Done: ${OUTPUT} ($(du -h "${OUTPUT}" | cut -f1))"
