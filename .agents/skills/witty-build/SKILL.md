---
name: witty-build
description: 构建、测试、lint、质量门禁与跨平台验证。只要用户提到 build、编译失败、质量门、回归检查、lint、shellcheck、发布前验证、openEuler 远程验证，或想确认改动没有破坏 CLI 行为时，都应优先使用这个 skill。它既覆盖当前阶段可直接执行的 Go 构建/测试，也保留 PTY、Shell Adapter、模板检查等后续阶段会启用的检查项，并要求按仓库当前状态有条件地启用它们。
---

# 构建与质量检查

## 使用原则

1. 先跑 **当前阶段一定成立** 的检查；
2. 再按仓库现状决定是否启用 **条件检查**；
3. 在 openEuler 上做最终验证时，尽量复现目标交付平台；
4. 明确报告"已执行""跳过""跳过原因"。

**未来会派上用场的检查不要删掉**；但在当前仓库里尚未接入的检查，也**不要硬跑到失败**。

## ⚠️ Agent 终端工具约束

Agent 终端工具**禁止**命令参数中含 shell 替换（`$()`、`$VAR`、反引号等）。**所有构建一律通过 `scripts/build.sh`**——脚本内部用 `go env` 动态解析架构，不写死任何 OS 或 ARCH，Agent 只需调用 `bash scripts/build.sh`。脚本将产物路径打印到 stdout，Agent 读取后用**字面值**做试运行。

如果脚本不可用：先单独运行 `go env GOOS` 和 `go env GOARCH` 获取字面值，再用字面值拼装 `mkdir -p` + `go build` 命令。**禁止**因终端工具限制而将产物写到 `build/` 以外（`/tmp/`、项目根目录、随机文件名）；如果无法正确构建，应**报告失败并停止**。

宿主机与 VM 架构均为未知，始终由脚本或 `go env` 在运行时动态发现。

## 读取 `.agents/config.yaml`（重要）

`.agents/config.yaml` 通常被 `.gitignore` 排除但**文件仍然真实存在**。涉及 openEuler 远程验证时：

1. **不要**先用 `find_path`、目录扫描或其它"发现文件"的方式判断它是否存在。
2. 直接尝试读取已知路径 `shell/.agents/config.yaml`。
3. 如果直接读取失败，再回退读取 `shell/.agents/config.template.yaml`，并明确提示开发者补齐本地配置。

## 构建产物目录

所有显式构建产物写入 `build/<GOOS>-<GOARCH>/`，按平台隔离。`scripts/build.sh` 自动处理 Windows `.exe` 后缀。`build/` 已加入 `.gitignore`。

## 🔴 构建铁律（绝对严格，违反即错误）

每次修改代码后，必须执行**两步编译**，缺一不可：

### 第一步：宿主机编译

```bash
bash scripts/build.sh
# 输出产物路径，如: build/darwin-arm64/witty
```

### 第二步：openEuler 虚拟机编译

读取 `.agents/config.yaml`，在 openEuler VM 上编译 Linux 产物。**VM 架构按验证目标选择，无需与宿主机匹配**（验证 `GOAMD64=v1` 用 amd64 VM，验证 ARM 服务器用 arm64 VM）：

```bash
orb run -m <vm> -u <user> sh -lc 'cd <work_dir> && bash scripts/build.sh'
# 输出产物路径，如: build/linux-arm64/witty
```

**两步都成功才算编译通过。** 缺任何一步都应报告失败并停止后续操作。

### 第三步：试运行（使用刚产出的二进制）

必须立即用 `build/` 中**刚产出的二进制**做试运行，路径由 `scripts/build.sh` 输出决定，Agent 读取后用字面值执行：

```bash
# 宿主机 — 路径以第一步脚本输出为准
build/<host-goos>-<host-goarch>/witty version

# openEuler VM — 路径以第二步脚本输出为准
orb run -m <vm> -u <user> sh -lc 'cd <work_dir> && build/linux-<arch>/witty version'
```

`version` 子命令不加载配置、不连接 server，是最安全的冒烟测试。禁止用 `go run ./cmd/witty` 代替。

### 架构匹配规则

宿主机与 openEuler VM 是**两个独立的原生构建环境**，架构无需匹配。VM 架构按**验证目标**选择——amd64 用于验证 `GOAMD64=v1` 兼容性，arm64 用于验证 ARM 服务器，两者都需验证则依次启动对应 VM。

| 场景 | 行为 |
| ---- | ---- |
| 宿主机任意架构 + VM 同架构 | ✅ 各自原生编译，各自试运行 |
| 宿主机任意架构 + VM 不同架构 | ✅ 允许；各自原生编译、各自在本地试运行（VM 跑在模拟层上会较慢，属正常） |
| 用户明确指定某 VM 架构 | ✅ 按用户指令选择 VM |

> 原则：每个环境只构建并运行**自己原生的**二进制。host 与 VM 架构不同是允许的，但绝不把一个环境产出的二进制拷贝到另一个环境运行。

### 绝对禁止

- ❌ **交叉编译**：禁止在宿主机上用 `GOOS=linux` 产出 Linux 二进制，也禁止在 VM 上产出非 Linux 二进制
- ❌ **跳过 VM 编译**：不能在宿主机编译完就声称完成
- ❌ **跨环境运行二进制**：不能把一个环境产出的二进制拷贝到另一个环境运行
- ❌ **产物目录混淆**：不同平台的构建产物必须落在不同子目录
- ❌ **写死架构路径**：禁止硬编码 `build/darwin-arm64/`、`build/linux-amd64/` 等；路径必须由 `scripts/build.sh` 输出或 `go env` 动态获取
- ❌ **用 `go run` 代替试运行**：试运行必须执行 `build/` 中刚产出的二进制
- ❌ **用 `go build -o /dev/null` 跳过产物刷新**：测试验证流程必须刷新并验证 `build/` 二进制
- ❌ **将构建产物写到 `build/` 以外**：禁止因终端工具限制而绕过正式构建流程，将二进制写到 `/tmp/`、项目根目录、随机文件名；如果无法正确构建，应**报告失败并停止**

## 标准构建命令

始终显式使用 `CGO_ENABLED=0`（`scripts/build.sh` 已内置）。在 Linux amd64 发布验证场景下，如环境允许，优先补上 `GOAMD64=v1`：

```bash
# 标准构建
bash scripts/build.sh

# amd64 发布构建
GOAMD64=v1 bash scripts/build.sh
```

仅验证编译、但不留下文件（临时语法检查，不刷新 `build/`）：

```bash
CGO_ENABLED=0 go build -o /dev/null ./cmd/witty
```

> ⚠️ `go build -o /dev/null` 仅用于临时语法检查。在测试验证流程中必须使用 `bash scripts/build.sh`，不得用 `-o /dev/null` 代替。

## 快速检查（每次提交前）

宿主机与 openEuler VM 必须**同时**编译，每次都刷新 `build/` 二进制并试运行：

```bash
# === 宿主机 ===
go fmt ./...
go vet ./...
bash scripts/build.sh
go test -count=1 ./...
build/<host-goos>-<host-goarch>/witty version

# === openEuler VM（必须）===
orb run -m <vm> -u <user> sh -lc 'cd <work_dir> && bash scripts/build.sh && go test -count=1 ./... && build/linux-<arch>/witty version'
```

> 快速检查也遵循 🔴 构建铁律：两步编译缺一不可，试运行必须使用 `build/` 中刚产出的二进制。

## 完整质量门（PR 前 / 较大改动后）

```bash
# === 宿主机 ===
go fmt ./...
go vet ./...
go test -v -count=1 ./...
bash scripts/build.sh
build/<host-goos>-<host-goarch>/witty version

# === openEuler VM（必须）===
orb run -m <vm> -u <user> sh -lc 'cd <work_dir> && go test -v -count=1 ./... && bash scripts/build.sh && build/linux-<arch>/witty version'
```

如果仓库中已配置 `golangci-lint`，再补 `golangci-lint run ./...`。如果未安装，应明确报告"未执行，原因是工具缺失"。

## 条件检查（按仓库当前状态启用）

下面这些检查**保留在 skill 中**；但只有在对应文件/目录已存在时才执行。

### 1. Shell 脚本与模板检查

当仓库中存在 `*.sh` 或 `*.bash.tmpl` 时，先格式化再检查：

```bash
shfmt -w -i 2 internal/shellinit/templates/*.bash.tmpl
git ls-files '*.sh' | xargs shfmt -w -i 2
shfmt -d -i 2 internal/shellinit/templates/*.bash.tmpl
git ls-files '*.sh' | xargs shfmt -d -i 2
shellcheck internal/shellinit/templates/*.bash.tmpl
```

如果模板目录尚不存在，应报告**跳过**。

### 2. PTY 测试

当 `test/pty/` 下已有 Go 测试文件时，在 openEuler 环境运行：

```bash
TERM=xterm-256color go test -v -tags=pty ./test/pty/
```

如果 `test/pty/` 为空或当前不是 openEuler 环境，应报告**跳过**。

### 3. Golden / 快照相关测试

如果某模块文档或测试提示需要 `go test -update`，应把它视为**人工确认后的显式动作**，不要默认执行。

### 4. TTY vs 非 TTY 输出一致性验证

当改动涉及 `internal/renderer/`、`internal/presenter/`、`internal/core/` 时，**必须在 openEuler 上验证 TTY 和非 TTY 两种模式下的输出一致**。用管道（`|`）或重定向（`>`）会使 stdout 变为非 TTY，验证时必须区分：

```bash
# ✅ TTY 模式 — orb run 默认分配 PTY
orb run -m <vm> -u <user> sh -lc 'cd <work_dir> && build/linux-<arch>/witty ask "echo hello" 2>/dev/null'

# ✅ 非 TTY 模式 — 重定向到文件再查看
orb run -m <vm> -u <user> sh -lc 'cd <work_dir> && build/linux-<arch>/witty ask "echo hello" 2>/dev/null > /tmp/out.txt && cat /tmp/out.txt'

# ❌ 错误：管道到 cat 会把 TTY 变成非 TTY
orb run -m <vm> -u <user> sh -lc '... | cat -n'
```

验证清单：

- [ ] TTY: Unicode 图标（`◌` `✓`）、box-drawing 边框（`│`）
- [ ] 非 TTY: ASCII 图标（`[..]` `[OK]`）、空格前缀（`  |`）、无 ANSI 转义
- [ ] 两者的事件**顺序一致**（工具 → 思考 → 回答 → 汇总）

## openEuler 远程验证（必须）

Agent 根据 `.agents/config.yaml` 自动连接远程 openEuler 环境并执行最终验证。开始前先**直接读取** `shell/.agents/config.yaml`。

### 远程命令包装（重要）

OrbStack / WSL 的非交互命令必须显式经 shell 执行；不要把整段 `cd ... && go test ...` 直接当成远程"命令名"传给 `orb` 或 `wsl`：

```bash
# OrbStack
orb run -m <vm> -u <user> sh -lc 'cd <work_dir> && go test ./...'

# WSL
wsl -d <distro> -u <user> -- sh -lc 'cd <work_dir> && go test ./...'

# SSH
ssh <user>@<host> "cd <work_dir> && go test ./..."
```

### openEuler 必跑项

VM 上的测试和编译遵循上方 🔴 构建铁律，使用 `scripts/build.sh` 动态解析架构：

```bash
# 测试 + 编译 + go vet（远程执行）
orb run -m <vm> -u <user> sh -lc 'cd <work_dir> && go test -v -count=1 ./... && bash scripts/build.sh && go vet ./...'
# 试运行（路径以脚本输出为准）
orb run -m <vm> -u <user> sh -lc 'cd <work_dir> && build/linux-<arch>/witty version'
```

### 涉及 live opencode 的验证（重要）

如果这次验证依赖 `127.0.0.1:4096` 的 live ask / integration / SSE 行为：

1. 先在**同一运行环境**里检查 health：`curl -s http://127.0.0.1:4096/global/health`
2. 若不可达，**不要直接停止**；先尝试在同一环境里启动：`opencode serve --port 4096`
3. 启动后等待数秒，再次检查 health
4. 只有在"启动失败"或"二次 health check 仍失败"时，才能报告 server 不可达

如果是在 OrbStack / WSL / SSH 远程环境中执行，上述 health check 与 `opencode serve` 也必须发生在该环境自身。

amd64 发布兼容性验证场景优先使用 `GOAMD64=v1`：

```bash
GOAMD64=v1 bash scripts/build.sh
```

> ⚠️ 在 openEuler 上构建后，二进制通常位于 `build/linux-<arch>/witty`。不要把与当前环境不兼容的二进制直接拿来运行。

## 构建产物冲突避免

- 不同平台的二进制写在 `build/<GOOS>-<GOARCH>/` 下，互不覆盖。
- 根目录下不应直接产生 `witty` 二进制。
- `scripts/build.sh` 自动处理 Windows `.exe` 后缀；Linux/macOS 一律为 `witty`。
- 试运行必须使用 `build/` 中刚产出的二进制（路径由脚本输出）。
- 禁止在宿主机上运行 VM 产出的 Linux 二进制，反之亦然。
- 禁止将构建产物写到 `build/` 以外。

## 工具安装建议

- `golangci-lint`: `go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest`
- `shellcheck` / `shfmt`: 按当前开发环境安装；openEuler 通常需手动安装静态二进制

## 报告结果时的推荐格式

```text
已执行:
- go fmt ./...
- go vet ./...
- 宿主机: go test -count=1 ./...
- 宿主机: bash scripts/build.sh → build/<host-goos>-<host-goarch>/witty
- 宿主机: 试运行 build/<host-goos>-<host-goarch>/witty version
- openEuler VM: go test -count=1 ./...
- openEuler VM: bash scripts/build.sh → build/linux-<arch>/witty
- openEuler VM: 试运行 build/linux-<arch>/witty version

条件跳过:
- shellcheck（模板目录尚未接入）
- PTY 测试（当前无 PTY Go 测试文件）
```

## 常见问题

- **宿主机与 VM 架构不匹配**：按上方架构匹配规则处理；不同架构的 VM 仅在用户明确指令下启动。
- **编译产物无法在宿主机运行**：检查是否误用了 VM 的 Linux 产物，用 `file build/*/witty` 确认。
- **PTY 测试失败**：确认 `TERM=xterm-256color` 且运行环境为 openEuler。
- **Shell 模板检查失败**：先确认模板文件是否已存在；不存在时应跳过。
- **Golden test 需更新**：使用 `go test -update`，并人工确认快照变化合理后再提交。
- **CGO 相关错误**：本项目禁止 CGO，优先检查是否忘了加 `CGO_ENABLED=0`。
- **amd64 兼容性问题**：仅当发布目标是 amd64 时，构建时优先加 `GOAMD64=v1`。
- **远程验证与本地结果不一致**：优先相信 openEuler 结果，并检查 `.agents/config.yaml`、远程 Go 版本、GOPROXY 与 shell 工具安装状态。
- **Agent 终端工具拒绝含 `$(...)` 的命令**：预期行为，使用 `bash scripts/build.sh` 代替。
