# Witty — openEuler 终端 AI 助手

## 项目概述

Go 1.26+ CLI 工具，对接 opencode MCP Server，为 openEuler 提供终端 AI 助手。
关键架构：单二进制 + Shell Adapter (Bash) + Go Core + SSE 流式传输。

## 技术栈

| 层 | 技术 | 约束 |
| --- | ---- | ---- |
| 语言 | Go 1.26+ | CGO_ENABLED=0 |
| CLI 框架 | cobra v1.10+ | — |
| HTTP 客户端 | net/http（标准库） | 禁止 ClientWithResponses 处理 SSE |
| Markdown 渲染 | glamour v2 (charm.land/glamour/v2) | 批量渲染器，需 BlockBuffer |
| 终端样式 | lipgloss v2 (charm.land/lipgloss/v2) | — |
| 配置 | koanf v2 (github.com/knadh/koanf/v2) | key 大小写敏感 |
| 日志 | log/slog（标准库） | 非 TTY 时降级至 io.Discard |
| 构建 | goreleaser v2 + nFPM v2 | goamd64=v1, CGO_ENABLED=0 |
| Shell 检查 | shellcheck + shfmt | 系统工具 |
| PTY 测试 | go-expect (github.com/Netflix/go-expect) | TERM=xterm-256color |
| 目标平台 | openEuler (Linux amd64/arm64) | 唯一交付平台 |

## 关键命令

- 初始化: `go mod download && go mod tidy`
- 构建: `OUTDIR="build/$(go env GOOS)-$(go env GOARCH)" && mkdir -p "$OUTDIR" && go build -ldflags="-s -w" -o "$OUTDIR/witty" ./cmd/witty`
- 测试全部: `go test ./...`
- 测试单包: `go test -v -run TestName ./internal/<package>/`
- Lint: `golangci-lint run ./...`
- Shell 检查: `shellcheck internal/shellinit/templates/*.bash.tmpl`
- 更新 OpenAPI: `bash scripts/update-openapi.sh`
- PTY 集成测试: `go test -v -tags=pty ./test/pty/`
- opencode 集成测试: `go test -v -tags=integration -count=1 -timeout 300s ./test/integration/`（若 `127.0.0.1:4096` 不可达，Agent 应先在同一环境中尝试启动 `opencode serve --port 4096`，重试 health check 后再继续）
- GoReleaser 本地验证: `goreleaser release --snapshot --clean --skip=publish`
- 格式化: `go fmt ./...`

### openEuler 远程执行

连接方式由 `.agents/config.yaml` 定义。**重要**：该文件通常被 `.gitignore` 排除，某些文件搜索或目录扫描结果可能看不到它，但文件仍然真实存在。Agent 在需要 openEuler 远程执行时，应**直接读取已知路径** `shell/.agents/config.yaml`，不要先用 `find_path`、目录扫描或其它发现型工具判断是否存在；若直接读取失败，再回退参考 `.agents/config.template.yaml`。

Agent 读取该配置后，通过对应的方式（orb/wsl/ssh）在 openEuler 环境中执行命令。典型用法：

```bash
# OrbStack:  orb -m <vm> -u <user> sh -lc 'cd <work_dir> && go test ./...'
# WSL:       wsl -d <distro> -u <user> -- sh -lc 'cd <work_dir> && go test ./...'
# SSH:       ssh <user>@<host> "cd <work_dir> && go test ./..."
```

> **重要（对 Agent）**：OrbStack / WSL 的非交互命令必须显式经 shell 执行；不要把整段 `cd <work_dir> && ...` 直接当成远程命令名传给 `orb` / `wsl`，否则很容易遇到 `No such file or directory`。

## 项目结构

- `cmd/witty/` — 程序入口（仅启动，无业务逻辑）
- `internal/app/` — 应用组装与依赖注入（wiring.go）
- `internal/cli/` — Cobra 命令树
- `internal/config/` — koanf 三层配置
- `internal/core/` — AskRunner 核心执行引擎
- `internal/transport/` — SSE HTTP 客户端（手写解析）
- `internal/event/` — 事件归一化（RawEvent → AppEvent）
- `internal/renderer/` — 流式 Markdown 渲染
- `internal/presenter/` — 结构化展示
- `internal/permission/` — 权限与问题交互管理
- `internal/session/` — 会话解析与管理
- `internal/repl/` — REPL 循环与 slash 命令
- `internal/shellinit/` — `witty init bash` 模板生成
- `internal/shellbridge/` — Shell 路由与 history
- `internal/terminal/` — TTY 检测、宽度、prompt
- `internal/doctor/` — 运维诊断
- `api/opencode/openapi.json` — vendored OpenAPI 3.1.0 spec
- `test/integration/` — opencode 真实环境集成测试（build tag: integration）
- `.agents/config.template.yaml` — 远程环境配置模板

## 编码约定

### Go 代码

- 接口定义在消费方，构造函数返回接口类型
- 错误使用 `fmt.Errorf("context: %w", err)` 包装
- 禁止 `panic` 处理业务错误（仅用于不可恢复的初始化失败）
- SSE 解析必须手写 `bufio.Reader`，严禁使用 `ClientWithResponses`
- Bash 模板分隔符用 `[[ ]]`，不是 `{{ }}`
- 所有 internal 模块通过 `app/wiring.go` 组装，避免包间直接耦合

### 模块结构

- 导出接口优先，struct 字段小写
- 包名小写单词（如 `shellbridge`，不是 `shell_bridge`）
- 构造函数命名 `New<Type>`，返回接口
- 新增模块必须包含 `<module>.go` 和 `<module>_test.go`

### Shell 模板

- Bash 函数前缀 `__witty_`
- 所有模板变更后运行 `shellcheck`
- 禁止在 Bash Hook 中执行长时间 AI 调用

## 测试规则

- 单元测试: `go test ./internal/<package>/`
- Golden Test: 快照比对，更新用 `go test -update`
- PTY 测试: 强制 `TERM=xterm-256color`，必须在 openEuler 上运行
- 测试数据: `test/testdata/`
- 覆盖率目标: 核心模块 > 80%

## 边界

### ✅ 允许（无需确认）

- 读文件、列目录、搜索代码
- 运行 `go build`, `go test`, `golangci-lint`, `shellcheck`, `go fmt`
- 更新 `*_test.go` 文件
- 新增 `test/integration/` 下的集成测试文件

### ⚠️ 需要确认

- 新增或删除 Go 依赖（修改 go.mod）
- 删除非测试文件
- 修改 `api/opencode/openapi.json`（vendored spec）
- 修改 `.goreleaser.yaml`

### 🚫 严禁

- 提交 secrets、token、credentials
- Force push 到 main
- 修改 `transport/generated/` 目录（自动生成代码）
- 使用 `CGO_ENABLED=1`
- 在 Bash 模板中使用 `{{ }}` 分隔符
- 引用不存在的依赖或虚构的 API

## 关键约束（不可协商）

1. **CGO_ENABLED=0** — 静态链接
2. **goamd64=v1** — openEuler 全平台兼容（含旧型服务器）
3. **openEuler 是唯一交付平台** — 所有测试最终在 openEuler 上验证
4. **Glamour 是批量渲染器** — 流式输出经过 BlockBuffer，不能直传
5. **SSE 手写解析** — 禁止 ClientWithResponses（会 buffer 整个响应体）
6. **模板分隔符 `[[ ]]`** — 不能使用 `{{ }}`
7. **Bash Shell Adapter 不执行 AI** — 只做路由，AI 执行在 Go Core

## 非显而易见模式

- `glamour.Render` 不支持增量输入 → 用 BlockBuffer 积累到完整 Markdown 块再渲染
- `session.idle` 是唯一可靠的流结束信号（不能用 `io.EOF`）
- opencode `/doc` 输出是 OpenAPI 3.1.0（不是 3.0.x），v2 oapi-codegen 不可用
- koanf key 大小写敏感（优于 viper）
- 日志在非 TTY 时降级至 `io.Discard`
- CJK 字符宽度用 `go-runewidth` 计算（Phase 2 行数追踪）

## 开发环境

开发者自行选择并搭建 openEuler 环境：

- **macOS**: OrbStack openEuler VM → 参考 `dev/setup/macos-orbstack.sh`
- **Windows**: WSL openEuler → 参考 `dev/setup/windows-wsl.sh`
- **自定义**: 远程 SSH openEuler 服务器 → 参考 `.agents/config.template.yaml`

环境就绪后，复制 `.agents/config.template.yaml` 为 `.agents/config.yaml` 并填入实际值。
Agent 将自动读取此配置，在 openEuler 环境中执行测试和构建。

## 关键文件

- `cmd/witty/main.go` — 应用入口
- `internal/app/wiring.go` — 依赖注入图
- `api/opencode/openapi.json` — API 事实来源
- `.goreleaser.yaml` — 构建与打包配置
- `.agents/config.yaml` — 远程环境配置（本地，gitignored）
- `docs/development/implementation-plan.md` — 详细模块实现计划
- `docs/development/sse-client.md` — SSE 客户端技术参考
- `docs/development/streaming-renderer.md` — 流式渲染器技术参考
- `docs/development/message-display-design.md` — 消息展示设计（思考/工具/Step）

## Rules 与 Skills

详细的领域规则和开发流程位于 `.agents/` 目录下。

- `.agents/rules/` — 编码与工程规则
- `.agents/skills/` — 领域技能（开发流程引导）

## ⚠️ 重要：Agent 启动时必须执行（所有 Agent 适用）

**本段指令面向 Coding Agent 本身，而非人类开发者。**

在开始任何编码任务之前，你必须按以下顺序加载项目上下文：

1. **读取 Rules 目录**：列出 `.agents/rules/` 下的所有文件，并完整读取每一个 `.md` 文件。
   这些规则定义了本项目的编码规范、测试策略、安全红线和跨平台约束。
   即使你的运行时已经自动加载了 `.agents/` 目录，你仍应显式读取这些文件以确保完整性。

2. **扫描 Skills 目录**：列出 `.agents/skills/` 下的所有子目录，读取每个 `SKILL.md` 的
   YAML frontmatter（`name` 和 `description` 字段）。这将告诉你有哪些领域技能可用。
   当后续任务匹配某个 skill 的 description 时，再加载该 SKILL.md 的完整 body。

3. **读取远程环境配置**：如果任务涉及在 openEuler 上运行测试或构建，**直接读取已知路径** `shell/.agents/config.yaml`
   以确定远程连接方式；不要先依赖 `find_path`、目录扫描或其它发现型工具判断存在性。该文件可能被 `.gitignore` 隐藏但仍然真实存在。只有在直接读取失败时，才提示开发者参考 `.agents/config.template.yaml` 完成配置。

**Rules 文件清单（必须全部读取）：**

- `.agents/rules/go-coding.md`
- `.agents/rules/bash-template.md`
- `.agents/rules/testing.md`
- `.agents/rules/cross-platform.md`
- `.agents/rules/security.md`
- `.agents/rules/git.md`

**Skills 目录清单（必须扫描 description）：**

- `.agents/skills/witty-dev-setup/SKILL.md`
- `.agents/skills/witty-module/SKILL.md`
- `.agents/skills/witty-build/SKILL.md`
- `.agents/skills/witty-openapi/SKILL.md`
- `.agents/skills/witty-sse-debug/SKILL.md`
- `.agents/skills/witty-shell-adapter/SKILL.md`
- `.agents/skills/witty-renderer/SKILL.md`
- `.agents/skills/witty-release/SKILL.md`
- `.agents/skills/witty-integration-test/SKILL.md`

### 文档维护规则

**Agent 完成开发任务后必须同步更新状态**：

1. `docs/development/development-todo.md` 是所有模块开发进度的**事实来源**。每完成一个 Phase 或 Px-N 任务，必须将该任务及其 checkpoint 下的所有 `[ ]` 标记为 `[x]`。
2. 新增模块或测试目录后，必须更新本 `AGENTS.md` 的项目结构一节。
3. 新增跨模块验证流程（如集成测试）后，必须创建或更新对应的 `.agents/skills/` Skill 文件。
