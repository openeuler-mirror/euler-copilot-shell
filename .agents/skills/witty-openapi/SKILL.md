---
name: witty-openapi
description: 更新 vendored OpenAPI 规范并重新生成类型代码。从 opencode /doc 端点拉取 3.1.0 spec，使用 oapi-codegen v3 生成 models。用于上游 API 变更时。
---

# OpenAPI 规范更新

## 前提

- opencode server 运行在 `127.0.0.1:4096`
- `oapi-codegen` v3 (`oapi-codegen-exp`) 已安装

## 更新流程

1. 拉取最新 OpenAPI 3.1.0 spec:

   ```bash
   curl -H "Accept: application/json" http://127.0.0.1:4096/doc > api/opencode/openapi.json
   ```

   或使用封装脚本: `bash scripts/update-openapi.sh`

2. 验证 spec 版本（必须是 OpenAPI 3.1.0）:

   ```bash
   head -5 api/opencode/openapi.json | grep '"openapi"' | grep '"3.1"'
   ```

3. 生成类型代码:

   ```bash
   oapi-codegen-exp -package generated api/opencode/openapi.json > internal/transport/generated/models.go
   ```

4. 编译检查:

   ```bash
   go build ./internal/transport/...
   ```

5. 接口回归测试:

   ```bash
   go test -v -run TestEventSchema ./internal/event/
   ```

## 关键陷阱

- **v2 oapi-codegen 不可用**: `exclusiveMinimum` 字段类型不兼容 OpenAPI 3.1
- **必须 v3**: 使用 `github.com/oapi-codegen/oapi-codegen-exp`
- **不依赖 generated client**: HTTP transport 与 SSE 解析全部手写，generated 仅提供类型定义
- spec 变更后必须提交 `api/opencode/openapi.json` 到版本控制
