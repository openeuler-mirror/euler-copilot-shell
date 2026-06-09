# opencode OpenAPI Spec

This directory vendors the opencode OpenAPI schema used by Witty.

- Spec file: `api/opencode/openapi.json`
- Source endpoint: `GET /doc` from a running opencode server
- Current OpenAPI version: `3.1.0`
- Current `info.version`: `1.0.0`
- Last validated by Agent: `2026-06-08`

## Update workflow

Start an opencode server on `127.0.0.1:4096`, then run:

```bash
bash scripts/update-openapi.sh
```

The script:

1. fetches `http://127.0.0.1:4096/doc` with `Accept: application/json`,
2. validates that the result is JSON and OpenAPI `3.1.x`,
3. writes a temporary normalized copy with duplicate `anyOf` entries removed,
4. regenerates `internal/transport/generated/models.go` with the OpenAPI 3.1 capable `oapi-codegen` v3 experimental generator and `api/opencode/oapi-codegen.yaml`.

To regenerate from the vendored spec without contacting a running server:

```bash
WITTY_OPENAPI_FETCH=0 bash scripts/update-openapi.sh
```

## Generator constraint

Use the OpenAPI 3.1 capable generator from `github.com/oapi-codegen/oapi-codegen-exp`, for example:

```bash
go install github.com/oapi-codegen/oapi-codegen-exp/experimental/cmd/oapi-codegen@latest
```

Do not generate or use the typed HTTP client for SSE. Witty's transport layer must use handwritten `net/http` requests and a handwritten SSE parser; generated code is limited to schema models/types.

## Known spec/generator compatibility notes

- The vendored opencode spec currently contains duplicate `anyOf` refs in event union schemas. Duplicate `anyOf` entries are semantically redundant, but the experimental generator emits duplicate Go helper methods for them. `scripts/update-openapi.sh` removes duplicate `anyOf` entries only in a temporary file used for generation; it does not modify `api/opencode/openapi.json`.
- The spec has a schema named `File`, which conflicts with the generator's embedded binary helper type. `api/opencode/oapi-codegen.yaml` maps this schema to `OpenCodeFile`.
