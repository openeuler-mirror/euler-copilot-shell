---
name: witty-build
description: 构建、测试、lint、质量门禁与跨平台验证。只要用户提到 build、编译失败、质量门、回归检查、lint、shellcheck、发布前验证、openEuler 远程验证，或想确认改动没有破坏 CLI 行为时，都应优先使用这个 skill。它既覆盖当前阶段可直接执行的 Go 构建/测试，也保留 PTY、Shell Adapter、模板检查等后续阶段会启用的检查项，并要求按仓库当前状态有条件地启用它们。
---

# 构建与质量检查

## 使用原则

这个 skill 的目标不是机械地把一串命令全跑一遍，而是：

1. 先跑 **当前阶段一定成立** 的检查；
2. 再按仓库现状决定是否启用 **条件检查**；
3. 在 openEuler 上做最终验证时，尽量复现目标交付平台；
4. 明确报告“已执行”“跳过”“跳过原因”。

换句话说：

- **未来会派上用场的检查不要删掉**；
- 但在当前仓库里尚未接入的检查，也**不要硬跑到失败**。

## 读取 `.agents/config.yaml`（重要）

`.agents/config.yaml` 通常被 `.gitignore` 排除；某些路径搜索或目录扫描结果可能看不到它，**但文件仍然真实存在**。

涉及 openEuler 远程验证时，遵循下面规则：

1. **不要**先用 `find_path`、目录扫描或其它“发现文件”的方式判断它是否存在。
2. 直接尝试读取已知路径 `shell/.agents/config.yaml`。
3. 如果直接读取失败，再回退读取 `shell/.agents/config.template.yaml`，并明确提示开发者补齐本地配置。
4. 不要因为搜索结果为空就宣称“`.agents/config.yaml` 不存在”。

## 构建产物目录

所有显式构建产物写入 `build/<GOOS>-<GOARCH>/witty`，按平台隔离：

```text
build/
  <goos>-<goarch>/witty
```

例如：

```text
build/
  linux-amd64/witty
  linux-arm64/witty
```

`build/` 目录已加入 `.gitignore`，不会被提交。

## 标准构建命令

始终显式使用 `CGO_ENABLED=0`。在 Linux amd64 发布验证场景下，如环境允许，优先补上 `GOAMD64=v1` 以贴合项目约束。

```bash
OUTDIR="build/$(go env GOOS)-$(go env GOARCH)" && mkdir -p "$OUTDIR" && CGO_ENABLED=0 go build -ldflags="-s -w" -o "$OUTDIR/witty" ./cmd/witty
```

仅验证编译、但不留下文件：

```bash
CGO_ENABLED=0 go build -o /dev/null ./cmd/witty
```

运行构建产物：

```bash
"build/$(go env GOOS)-$(go env GOARCH)/witty" --help
```

> ⚠️ 不要在与目标平台不兼容的环境里直接运行构建出的二进制。必要时用 `file build/*/witty` 确认类型。

## 快速检查（每次提交前）

这些步骤应当在当前阶段**默认执行**：

```bash
go fmt ./...
go vet ./...
CGO_ENABLED=0 go build -o /dev/null ./cmd/witty
go test -count=1 ./...
```

如用户只要最小反馈，这一组通常就够了。

## 完整质量门（PR 前 / 较大改动后）

基础完整版：

```bash
go fmt ./...
go vet ./...
go test -v -count=1 ./...
OUTDIR="build/$(go env GOOS)-$(go env GOARCH)" && mkdir -p "$OUTDIR" && CGO_ENABLED=0 go build -ldflags="-s -w" -o "$OUTDIR/witty" ./cmd/witty
```

如果仓库中已配置 `golangci-lint`，再补：

```bash
golangci-lint run ./...
```

> 如果环境里没有安装 `golangci-lint`，应明确报告“未执行，原因是工具缺失”，而不是假装已经通过。

## 条件检查（按仓库当前状态启用）

下面这些检查**保留在 skill 中**，因为它们很快会派上用场；但只有在对应文件/目录已经存在时才应执行。

### 1. Shell 模板检查

当仓库中存在 `internal/shellinit/templates/*.bash.tmpl` 时，运行：

```bash
shellcheck internal/shellinit/templates/*.bash.tmpl
```

如果模板目录尚不存在，应报告：

- **跳过 shellcheck**：当前仓库尚未接入 `internal/shellinit/templates/*.bash.tmpl`

### 2. PTY 测试

当 `test/pty/` 下已有 Go 测试文件时，在 openEuler 环境运行：

```bash
TERM=xterm-256color go test -v -tags=pty ./test/pty/
```

如果 `test/pty/` 目录为空、还没有 Go 文件，或当前不是 openEuler 环境，应报告：

- **跳过 PTY 测试**：当前阶段未接入 PTY 用例，或运行环境不满足要求

### 3. Golden / 快照相关测试

如果某模块文档或测试提示需要 `go test -update`，应把它视为**人工确认后的显式动作**，不要默认执行。

## openEuler 远程验证（必须）

Agent 根据 `.agents/config.yaml` 自动连接远程 openEuler 环境并执行最终验证。

> 在开始远程验证前，先**直接读取** `shell/.agents/config.yaml`；不要先依赖文件搜索结果判断其是否存在。

### 当前阶段必跑项

```bash
go test -v -count=1 ./...
OUTDIR="build/$(go env GOOS)-$(go env GOARCH)" && mkdir -p "$OUTDIR" && CGO_ENABLED=0 go build -ldflags="-s -w" -o "$OUTDIR/witty" ./cmd/witty
go vet ./...
```

### 当对应内容已接入后再追加的检查

如果仓库里已经有 Shell 模板：

```bash
shellcheck internal/shellinit/templates/*.bash.tmpl
```

如果 `test/pty/` 已有 Go 测试文件：

```bash
TERM=xterm-256color go test -v -tags=pty ./test/pty/
```

如果是在 `linux/amd64` 发布兼容性验证场景，优先使用：

```bash
OUTDIR="build/$(go env GOOS)-$(go env GOARCH)" && mkdir -p "$OUTDIR" && CGO_ENABLED=0 GOAMD64=v1 go build -ldflags="-s -w" -o "$OUTDIR/witty" ./cmd/witty
```

> ⚠️ 在 openEuler 上构建后，二进制通常位于 `build/linux-<arch>/witty`。不要把与当前环境不兼容的二进制直接拿来运行。

## 构建产物冲突避免

- 不同平台的二进制写在 `build/<GOOS>-<GOARCH>/` 下，互不覆盖。
- 共享工作目录下，不同环境的构建会落到不同子目录。
- 根目录下不应直接产生 `witty` 二进制。
- 如需本地快速运行，优先用：

```bash
go run ./cmd/witty ...
```

## 工具安装建议

- `golangci-lint`: `go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest`
- `shellcheck` / `shfmt`: 按当前开发环境安装；openEuler 通常需手动安装静态二进制

## 报告结果时的推荐格式

执行这个 skill 后，建议按下面结构汇报：

- **已执行**：列出真正跑过并通过/失败的命令
- **条件跳过**：列出未执行的检查及原因
- **关键失败**：如果有失败，只摘最相关的错误
- **环境说明**：本地 / openEuler / 是否使用 `.agents/config.yaml`

例如：

```text
已执行:
- go fmt ./...
- go vet ./...
- go test -count=1 ./...
- CGO_ENABLED=0 go build -o /dev/null ./cmd/witty

条件跳过:
- shellcheck internal/shellinit/templates/*.bash.tmpl（模板目录尚未接入）
- TERM=xterm-256color go test -tags=pty ./test/pty/（当前无 PTY Go 测试文件）
```

## 常见问题

- **PTY 测试失败**：确认 `TERM=xterm-256color` 且运行环境为 openEuler。
- **Shell 模板检查失败**：先确认模板文件是否已存在；不存在时应跳过，而不是硬报错。
- **Golden test 需更新**：使用 `go test -update`，并人工确认快照变化合理后再提交。
- **CGO 相关错误**：本项目禁止 CGO，优先检查是否忘了加 `CGO_ENABLED=0`。
- **amd64 兼容性问题**：发布验证或 Linux amd64 产物构建时，优先加 `GOAMD64=v1`。
- **二进制无法执行**：检查是不是在不兼容的环境里运行了目标平台二进制。
- **远程验证与本地结果不一致**：优先相信 openEuler 结果，并检查 `.agents/config.yaml`、远程 Go 版本、GOPROXY 与 shell 工具安装状态。
