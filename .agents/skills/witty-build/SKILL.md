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

所有显式构建产物写入 `build/<GOOS>-<GOARCH>/`，按平台隔离。二进制名在 Linux/macOS 为 `witty`，在 Windows 为 `witty.exe`：

```text
build/
  <goos>-<goarch>/witty        # Linux / macOS
  <goos>-<goarch>/witty.exe    # Windows
```

例如（宿主机 + openEuler VM 各一份）：

```text
build/
  darwin-arm64/witty               # 宿主机：macOS arm64
  windows-amd64/witty.exe          # 宿主机：Windows amd64
  linux-arm64/witty                # openEuler VM（arm64 示例）
  linux-amd64/witty                # openEuler VM（amd64 示例）
```

`build/` 目录已加入 `.gitignore`，不会被提交。

## 🔴 构建铁律（绝对严格，违反即错误）

每次修改代码后，必须执行**两步编译**，缺一不可：

### 第一步：宿主机编译

在当前开发机上编译**当前架构**的二进制，写入对应子目录：

```bash
OUTDIR="build/$(go env GOOS)-$(go env GOARCH)" && mkdir -p "$OUTDIR" && CGO_ENABLED=0 go build -ldflags="-s -w" -o "$OUTDIR/witty" ./cmd/witty
```

> `$(go env GOOS)-$(go env GOARCH)` 会自动匹配宿主机架构，不写死。

### 第二步：openEuler 虚拟机编译

读取 `.agents/config.yaml`，在 openEuler 虚拟机上编译 Linux 产物。**VM 架构按验证目标选择，无需与宿主机匹配**（验证 `GOAMD64=v1` 用 amd64 VM，验证 ARM 服务器用 arm64 VM）：

```bash
orb run -m <vm> -u <user> sh -lc 'cd <work_dir> && OUTDIR="build/$(go env GOOS)-$(go env GOARCH)" && mkdir -p "$OUTDIR" && CGO_ENABLED=0 go build -ldflags="-s -w" -o "$OUTDIR/witty" ./cmd/witty'
```

> VM 产物固定为 `build/linux-<arch>/witty`，`<arch>` 由 VM 自身的 `go env GOARCH` 决定。

**两步都成功才算编译通过。** 缺任何一步都应报告失败并停止后续操作。

### 第三步：试运行（使用刚产出的二进制）

两步编译各产出二进制后，必须立即用 `build/` 中**刚产出的二进制**做一次试运行，确认产物可执行：

```bash
# 宿主机
"build/$(go env GOOS)-$(go env GOARCH)/witty" version

# openEuler VM
orb run -m <vm> -u <user> sh -lc 'cd <work_dir> && "build/$(go env GOOS)-$(go env GOARCH)/witty" version'
```

`version` 子命令不加载配置、不连接 server，是最安全的冒烟测试。禁止用 `go run ./cmd/witty` 代替——那验证的是源码而非 `build/` 中的真实产物。

### 架构匹配规则

宿主机与 openEuler VM 是**两个独立的原生构建环境**，架构无需匹配。宿主机常见组合：macOS arm64、Windows amd64、Windows arm64，有时 Linux（amd64/arm64）；VM 固定为 openEuler Linux。VM 架构按**验证目标**选择——amd64 用于验证 `GOAMD64=v1` 兼容性，arm64 用于验证 ARM 服务器，两者都需验证则依次启动对应 VM。

| 场景 | 行为 |
| ---- | ---- |
| 宿主机任意架构 + VM 同架构 | ✅ 各自原生编译，各自试运行 |
| 宿主机任意架构 + VM 不同架构 | ✅ 允许；各自原生编译、各自在本地试运行（VM 跑在模拟层上会较慢，属正常） |
| 用户明确指定某 VM 架构 | ✅ 按用户指令选择 VM |

> 原则：每个环境只构建并运行**自己原生的**二进制。host 与 VM 架构不同是允许的，但绝不把一个环境产出的二进制拷贝到另一个环境运行。

### 绝对禁止

- ❌ **交叉编译**：禁止在宿主机上用 `GOOS=linux` 产出 Linux 二进制，也禁止在 VM 上产出非 Linux 二进制
- ❌ **跳过 VM 编译**：不能在宿主机编译完就声称完成
- ❌ **跨环境运行二进制**：不能把一个环境产出的二进制拷贝到另一个环境运行；host 与 VM 架构不同是允许的，但各自只运行自己构建的产物
- ❌ **产物目录混淆**：不同平台的构建产物必须落在不同子目录
- ❌ **在 SKILL.md 中写死特定宿主 OS 名称**：用 `$(go env GOOS)` 自适应
- ❌ **用 `go run` 代替试运行**：试运行必须执行 `build/` 中刚产出的二进制
- ❌ **用 `go build -o /dev/null` 跳过产物刷新**：测试验证流程必须刷新并验证 `build/` 二进制

## 标准构建命令

始终显式使用 `CGO_ENABLED=0`。在 Linux amd64 发布验证场景下，如环境允许，优先补上 `GOAMD64=v1` 以贴合项目约束。

```bash
OUTDIR="build/$(go env GOOS)-$(go env GOARCH)" && mkdir -p "$OUTDIR" && CGO_ENABLED=0 go build -ldflags="-s -w" -o "$OUTDIR/witty" ./cmd/witty
```

仅验证编译、但不留下文件：

```bash
CGO_ENABLED=0 go build -o /dev/null ./cmd/witty
```

> ⚠️ `go build -o /dev/null` 仅用于临时语法检查，**不刷新** `build/` 中的二进制。在测试验证流程（快速检查 / 完整质量门）中必须使用写入 `build/` 的命令，不得用 `-o /dev/null` 代替。

运行构建产物（仅限当前系统架构）：

```bash
"build/$(go env GOOS)-$(go env GOARCH)/witty" --help
```

## 快速检查（每次提交前）

这些步骤应当在当前阶段**默认执行**。宿主机与 openEuler VM 必须**同时**编译，每次都刷新 `build/` 中的二进制，并用刚产出的二进制做试运行：

```bash
# === 宿主机 ===
go fmt ./...
go vet ./...
# 第一步：宿主机编译（刷新 build/<host-goos>-<host-goarch>/witty）
OUTDIR="build/$(go env GOOS)-$(go env GOARCH)" && mkdir -p "$OUTDIR" && CGO_ENABLED=0 go build -ldflags="-s -w" -o "$OUTDIR/witty" ./cmd/witty
go test -count=1 ./...
# 试运行：用刚产出的二进制验证可执行
"build/$(go env GOOS)-$(go env GOARCH)/witty" version

# === openEuler VM（必须，架构匹配时自动执行）===
# 第二步：VM 编译（刷新 build/linux-<arch>/witty）+ 测试 + 试运行
orb run -m <vm> -u <user> sh -lc 'cd <work_dir> && OUTDIR="build/$(go env GOOS)-$(go env GOARCH)" && mkdir -p "$OUTDIR" && CGO_ENABLED=0 go build -ldflags="-s -w" -o "$OUTDIR/witty" ./cmd/witty && go test -count=1 ./... && "build/$(go env GOOS)-$(go env GOARCH)/witty" version'
```

> 即使是快速检查也遵循 🔴 构建铁律：宿主机与 VM 两步编译缺一不可，试运行必须使用 `build/` 中刚产出的二进制，禁止用 `go run` 或 `go build -o /dev/null` 代替。

## 完整质量门（PR 前 / 较大改动后）

宿主机 + openEuler VM 双平台验证，每次编译都刷新 `build/` 二进制，并用刚产出的二进制试运行：

```bash
# === 宿主机 ===
go fmt ./...
go vet ./...
go test -v -count=1 ./...
OUTDIR="build/$(go env GOOS)-$(go env GOARCH)" && mkdir -p "$OUTDIR" && CGO_ENABLED=0 go build -ldflags="-s -w" -o "$OUTDIR/witty" ./cmd/witty
# 试运行：用刚产出的二进制验证可执行
"build/$(go env GOOS)-$(go env GOARCH)/witty" version

# === openEuler VM（必须，架构匹配时自动执行）===
orb run -m <vm> -u <user> sh -lc 'cd <work_dir> && go test -v -count=1 ./... && OUTDIR="build/$(go env GOOS)-$(go env GOARCH)" && mkdir -p "$OUTDIR" && CGO_ENABLED=0 go build -ldflags="-s -w" -o "$OUTDIR/witty" ./cmd/witty && "build/$(go env GOOS)-$(go env GOARCH)/witty" version'
```

如果仓库中已配置 `golangci-lint`，再补：

```bash
golangci-lint run ./...
```

> 如果环境里没有安装 `golangci-lint`，应明确报告“未执行，原因是工具缺失”，而不是假装已经通过。

## 条件检查（按仓库当前状态启用）

下面这些检查**保留在 skill 中**，因为它们很快会派上用场；但只有在对应文件/目录已经存在时才应执行。

### 1. Shell 脚本与模板检查

当仓库中存在 shell 脚本（`*.sh`）或模板（`*.bash.tmpl`）时，先格式化再检查：

```bash
# 格式化所有 shell 脚本和模板
shfmt -w -i 2 internal/shellinit/templates/*.bash.tmpl
git ls-files '*.sh' | xargs shfmt -w -i 2

# 验证格式化无残余差异
shfmt -d -i 2 internal/shellinit/templates/*.bash.tmpl
git ls-files '*.sh' | xargs shfmt -d -i 2

# 静态分析（仅模板文件）
shellcheck internal/shellinit/templates/*.bash.tmpl
```

如果模板目录尚不存在，应报告：

- **跳过 shfmt / shellcheck**：当前仓库尚未接入 shell 脚本或模板

### 2. PTY 测试

当 `test/pty/` 下已有 Go 测试文件时，在 openEuler 环境运行：

```bash
TERM=xterm-256color go test -v -tags=pty ./test/pty/
```

如果 `test/pty/` 目录为空、还没有 Go 文件，或当前不是 openEuler 环境，应报告：

- **跳过 PTY 测试**：当前阶段未接入 PTY 用例，或运行环境不满足要求

### 3. Golden / 快照相关测试

如果某模块文档或测试提示需要 `go test -update`，应把它视为**人工确认后的显式动作**，不要默认执行。

### 4. TTY vs 非 TTY 输出一致性验证

当改动涉及 `internal/renderer/`、`internal/presenter/`、`internal/core/` 时，**必须在 openEuler 上验证 TTY 和非 TTY 两种模式下的输出一致**。

**关键陷阱**：用管道（`|`）或重定向（`>`）会使 stdout 变为非 TTY，验证时必须区分两者的测试方式：

```bash
# ✅ 正确：TTY 模式 — orb run 默认分配 PTY，二进制直接输出到终端
orb run -m <vm> -u <user> sh -lc 'cd <work_dir> && build/linux-arm64/witty ask "echo hello" 2>/dev/null'

# ✅ 正确：非 TTY 模式 — 管道到文件，再用 cat 查看
orb run -m <vm> -u <user> sh -lc 'cd <work_dir> && build/linux-arm64/witty ask "echo hello" 2>/dev/null > /tmp/out.txt && cat /tmp/out.txt'

# ❌ 错误：管道到 cat 会把 TTY 变成非 TTY，无法验证 TTY 表现
orb run -m <vm> -u <user> sh -lc '... | cat -n'
```

验证清单：

- [ ] TTY: 思考在回答之前，Unicode 图标（`◌` `✓`）、box-drawing 边框（`│`）
- [ ] 非 TTY: 思考在回答之前，ASCII 图标（`[..]` `[OK]`）、空格前缀（`  |`）、无 ANSI 转义
- [ ] 两者的事件**顺序一致**（工具 → 思考 → 回答 → 汇总）

## openEuler 远程验证（必须）

Agent 根据 `.agents/config.yaml` 自动连接远程 openEuler 环境并执行最终验证。

> 在开始远程验证前，先**直接读取** `shell/.agents/config.yaml`；不要先依赖文件搜索结果判断其是否存在。

### 远程命令包装（重要）

OrbStack / WSL 的非交互命令必须显式经 shell 执行；不要把整段 `cd ... && go test ...` 直接当成远程"命令名"传给 `orb` 或 `wsl`，否则很容易出现 `No such file or directory`。

正确示例：

```bash
# OrbStack
orb run -m <vm> -u <user> sh -lc 'cd <work_dir> && go test ./...'

# WSL
wsl -d <distro> -u <user> -- sh -lc 'cd <work_dir> && go test ./...'

# SSH
ssh <user>@<host> "cd <work_dir> && go test ./..."
```

### openEuler 必跑项

VM 上的测试和编译命令遵循上方 🔴 构建铁律，使用 `$(go env GOOS)-$(go env GOARCH)` 自适应架构，不写死 `GOOS` 或 `GOARCH`：

```bash
go test -v -count=1 ./...
OUTDIR="build/$(go env GOOS)-$(go env GOARCH)" && mkdir -p "$OUTDIR" && CGO_ENABLED=0 go build -ldflags="-s -w" -o "$OUTDIR/witty" ./cmd/witty
# 试运行：用刚产出的二进制验证可执行
"build/$(go env GOOS)-$(go env GOARCH)/witty" version
go vet ./...
```

### 当对应内容已接入后再追加的检查

### 涉及 live opencode 的验证（重要）

如果这次验证不仅是纯编译/单测，而是要跑依赖 `127.0.0.1:4096` 的 live ask / integration / SSE 行为：

1. 先在**同一运行环境**里检查 health：`curl -s http://127.0.0.1:4096/global/health`
2. 若不可达，**不要直接停止**；先尝试在同一环境里启动：`opencode serve --port 4096`
3. 启动后等待数秒，再次检查 health
4. 只有在“启动失败”或“二次 health check 仍失败”时，才能报告 server 不可达

如果是在 OrbStack / WSL / SSH 远程环境中执行，上述 health check 与 `opencode serve` 也必须发生在该环境自身，而不是宿主机。

如果仓库里已经有 Shell 模板：

```bash
shfmt -w -i 2 internal/shellinit/templates/*.bash.tmpl
shfmt -d -i 2 internal/shellinit/templates/*.bash.tmpl
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
- Windows 宿主机上 `go build -o "$OUTDIR/witty"` 会产出 `witty.exe`，试运行命令相应使用 `.../witty.exe version`；Linux/macOS 宿主机与 VM 一律为 `witty`。
- 试运行 / 冒烟测试必须使用 `build/<GOOS>-<GOARCH>/` 中刚产出的二进制（如 `... witty version`）；禁止用 `go run ./cmd/witty` 代替，否则无法验证真实构建产物。
- 禁止在宿主机上运行 VM 产出的 Linux 二进制，反之亦然。

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
- 宿主机: go test -count=1 ./...
- 宿主机: go build → build/<host-goos>-<host-goarch>/witty
- 宿主机: 试运行 build/<host-goos>-<host-goarch>/witty version
- openEuler VM: go test -count=1 ./...
- openEuler VM: go build → build/linux-<arch>/witty
- openEuler VM: 试运行 build/linux-<arch>/witty version

条件跳过:
- shellcheck internal/shellinit/templates/*.bash.tmpl（模板目录尚未接入）
- TERM=xterm-256color go test -tags=pty ./test/pty/（当前无 PTY Go 测试文件）
```

## 常见问题

- **宿主机与 VM 架构不匹配**：按上方架构匹配规则处理；不同架构的 VM 仅在用户明确指令下启动。
- **编译产物无法在宿主机运行**：检查是否误用了 VM 的 Linux 产物，用 `file build/*/witty` 确认。
- **PTY 测试失败**：确认 `TERM=xterm-256color` 且运行环境为 openEuler。
- **Shell 模板检查失败**：先确认模板文件是否已存在；不存在时应跳过，而不是硬报错。
- **Golden test 需更新**：使用 `go test -update`，并人工确认快照变化合理后再提交。
- **CGO 相关错误**：本项目禁止 CGO，优先检查是否忘了加 `CGO_ENABLED=0`。
- **amd64 兼容性问题**：仅当发布目标是 amd64 时，构建时优先加 `GOAMD64=v1`。
- **远程验证与本地结果不一致**：优先相信 openEuler 结果，并检查 `.agents/config.yaml`、远程 Go 版本、GOPROXY 与 shell 工具安装状态。
