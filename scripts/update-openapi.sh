#!/usr/bin/env bash
set -euo pipefail

SERVER_URL="${WITTY_OPENAPI_SERVER_URL:-http://127.0.0.1:4096}"
SPEC_PATH="${WITTY_OPENAPI_SPEC_PATH:-api/opencode/openapi.json}"
CONFIG_PATH="${WITTY_OPENAPI_CONFIG_PATH:-api/opencode/oapi-codegen.yaml}"
GENERATED_PATH="${WITTY_OPENAPI_GENERATED_PATH:-internal/transport/generated/models.go}"
FETCH_SPEC="${WITTY_OPENAPI_FETCH:-1}"

if [[ -n "${OAPI_CODEGEN:-}" ]]; then
  GENERATOR="${OAPI_CODEGEN}"
elif command -v oapi-codegen-exp >/dev/null 2>&1; then
  GENERATOR="oapi-codegen-exp"
elif command -v oapi-codegen >/dev/null 2>&1; then
  GENERATOR="oapi-codegen"
else
  cat >&2 <<'EOF'
oapi-codegen v3 generator not found.
Install the OpenAPI 3.1 capable generator first, for example:
  go install github.com/oapi-codegen/oapi-codegen-exp/experimental/cmd/oapi-codegen@latest
EOF
  exit 127
fi

mkdir -p "$(dirname "${SPEC_PATH}")" "$(dirname "${GENERATED_PATH}")"

if [[ "${FETCH_SPEC}" != "0" ]]; then
  curl -fsSL -H "Accept: application/json" "${SERVER_URL%/}/doc" >"${SPEC_PATH}"
fi

NORMALIZED_SPEC="$(mktemp)"
trap 'rm -f "${NORMALIZED_SPEC}"' EXIT

python3 - "${SPEC_PATH}" "${NORMALIZED_SPEC}" <<'PY'
import json
import sys

spec_path = sys.argv[1]
normalized_path = sys.argv[2]

with open(spec_path, encoding="utf-8") as f:
    spec = json.load(f)

version = spec.get("openapi", "")
if not version.startswith("3.1"):
    raise SystemExit(f"OpenAPI spec must be 3.1.x, got {version!r}")

def dedupe_anyof(node):
    if isinstance(node, dict):
        anyof = node.get("anyOf")
        if isinstance(anyof, list):
            seen = set()
            deduped = []
            for item in anyof:
                key = json.dumps(item, sort_keys=True, separators=(",", ":"))
                if key in seen:
                    continue
                seen.add(key)
                deduped.append(item)
            node["anyOf"] = deduped
        for value in node.values():
            dedupe_anyof(value)
    elif isinstance(node, list):
        for item in node:
            dedupe_anyof(item)

dedupe_anyof(spec)

with open(normalized_path, "w", encoding="utf-8") as f:
    json.dump(spec, f, separators=(",", ":"))
PY

"${GENERATOR}" -config "${CONFIG_PATH}" -output "${GENERATED_PATH}" "${NORMALIZED_SPEC}"

gofmt -w "${GENERATED_PATH}"
