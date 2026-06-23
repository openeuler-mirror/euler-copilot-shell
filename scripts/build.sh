#!/usr/bin/env bash
# scripts/build.sh — Build witty binary into build/<GOOS>-<GOARCH>/
#
# Architecture is discovered dynamically via `go env`; never hardcoded.
# Works on any host (macOS / Windows-WSL / Linux) and any arch (amd64 / arm64).
#
# Usage:
#   bash scripts/build.sh                # standard build
#   GOAMD64=v1 bash scripts/build.sh     # amd64 release build (GOAMD64=v1)
#
# Output: prints the binary path to stdout (e.g. build/linux-arm64/witty)
# Exit:  0 on success, non-zero on failure
set -euo pipefail

GOOS="$(go env GOOS)"
GOARCH="$(go env GOARCH)"
OUTDIR="build/${GOOS}-${GOARCH}"
mkdir -p "$OUTDIR"

BINARY="witty"
if [ "$GOOS" = "windows" ]; then
  BINARY="witty.exe"
fi

CGO_ENABLED=0 go build -ldflags="-s -w" -o "${OUTDIR}/${BINARY}" ./cmd/witty

echo "${OUTDIR}/${BINARY}"
