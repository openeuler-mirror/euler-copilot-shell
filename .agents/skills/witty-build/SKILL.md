---
name: witty-build
description: 构建、测试、lint 和质量门禁检查。使用 go build、go test、golangci-lint、shellcheck。用于日常开发中的质量验证。
---

# 构建与质量检查

## 快速检查（每次提交前，< 30s）

```bash
go fmt ./...
go build -ldflags="-s -w" ./cmd/witty
go vet ./...
go test ./...
```

## 完整质量门（PR 前，< 5min）

```bash
golangci-lint run ./...
shellcheck internal/shellinit/templates/*.bash.tmpl
go test -v -count=1 ./...
```

## openEuler 远程验证（必须）

Agent 根据 `.agents/config.yaml` 自动连接远程 openEuler 环境并执行:

- `go test -v -count=1 ./...` — 完整单元测试
- `go test -v -tags=pty ./test/pty/` — PTY 集成测试

## Lint 工具安装

- macOS: `brew install golangci-lint shellcheck shfmt`
- openEuler: ShellCheck 和 shfmt 不在默认仓库，需从 GitHub 手动下载静态二进制
- golangci-lint: `go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest`

## 常见问题

- PTY 测试失败: 确保 `TERM=xterm-256color` 且在 openEuler 环境中运行
- Golden test 需更新: 使用 `go test -update`，确认变更后提交
- CGO 相关错误: 本项目禁止 CGO，不要使用依赖 CGO 的包
- 构建 ldflags: 正式构建使用 `-ldflags="-s -w"` 减小二进制体积
