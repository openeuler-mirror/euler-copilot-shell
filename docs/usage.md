# Witty CLI 使用文档

> **Witty CLI** — openEuler 终端 AI 助手
> 目标平台：openEuler 24.03 LTS（x86_64 / aarch64）

---

## 目录

1. [简介](#1-简介)
2. [安装](#2-安装)
3. [快速上手](#3-快速上手)
4. [命令参考](#4-命令参考)
5. [Shell 集成](#5-shell-集成)
6. [Slash 控制命令](#6-slash-控制命令)
7. [配置](#7-配置)
8. [Provider 管理](#8-provider-管理)
9. [Server 生命周期管理](#9-server-生命周期管理)
10. [环境诊断](#10-环境诊断)
11. [常见问题](#11-常见问题)

---

## 1. 简介

Witty CLI 是 openEuler 终端场景下的 AI 助手。它提供两种使用方式：

- **Shell 直输**：在普通 Bash 提示符下直接输入自然语言，即可触发 AI 助手
- **REPL 交互**：运行 `witty` 进入完整交互式 CLI

两种方式共享同一套会话、渲染、权限与展示核心，差别仅在入口形式。

### 1.1 工作原理

Witty CLI 的所有后端交互建立在 `opencode serve` 之上：

- 会话操作走 HTTP API
- 流式事件走 SSE
- 权限 / Question 回复走 API

Witty CLI 会自动启动和管理 `opencode serve` 进程，无需用户手动操作。

### 1.2 两种入口对比

| 入口 | 用户动作 | 实际实现 |
| ---- | -------- | -------- |
| **Shell 直输** | 在普通 Bash 提示符直接输入自然语言 | Shell Adapter 调用 `witty ask` |
| **REPL** | 运行 `witty` | 启动交互式 REPL，内部调用同一套核心 |

无论哪种入口，输出风格、会话连续性、控制命令都保持一致。

---

## 2. 安装

### 2.1 RPM 安装（推荐）

```bash
sudo dnf install witty
```

安装后，Shell 集成通过 `/etc/profile.d/witty.sh` 对所有用户默认生效。
重新打开终端或执行 `source /etc/profile` 后即可使用。

### 2.2 验证安装

```bash
witty version
```

输出示例：

```text
version: 3.1.2
commit: 4e4b8a9
date: 2026-07-30T07:48:22Z
```

### 2.3 依赖

- **opencode**：Witty CLI 需要系统中安装 `opencode` CLI。如果未安装，`witty doctor` 会提示。
- **Bash ≥ 4.0**：Shell 直输功能需要 Bash 4.0 及以上交互式终端。

---

## 3. 快速上手

### 3.1 Shell 直输（最简方式）

安装完成后，直接在 Bash 终端输入自然语言：

```bash
检查系统内存
```

Witty CLI 会自动识别这是自然语言而非 shell 命令，调用 AI 助手并流式输出回答。

```bash
systemctl 怎么看 nginx 日志
```

以已知命令开头但包含中文疑问词的输入，也会被正确路由到 AI 助手。

### 3.2 REPL 模式

```bash
witty
```

进入交互式 REPL，提示符格式为 `witty [<agent>:<model>] >`（末尾含空格）。
在 REPL 中可以连续对话：

```text
witty [witty-builtin-agent] > 帮我分析一下 dmesg 里的 OOM 日志
...（流式输出回答）...
witty [witty-builtin-agent] > 那怎么优化内存配置呢
...（基于上一轮上下文继续回答）...
```

输入 `/exit` 或按 `Ctrl+D` 退出 REPL。

### 3.3 单次提问

```bash
witty ask "检查系统内存"
```

单次请求，流式输出回答后退出。

### 3.4 通过管道传入

```bash
echo "explain this function" | witty ask
```

```bash
dmesg | witty ask "分析这段内核日志中的异常"
```

### 3.5 连接 Provider 并切换模型

以下示例展示从连接 provider 到选择模型的完整交互式流程：

```text
$ witty provider connect deepseek
Enter API key: ****（输入不可见）
connected provider deepseek

$ witty
witty [witty-builtin-agent] > /model
```

此时终端切换到全屏模型选择器：

```text
Select model:

❯ 1) opencode/north-mini-code-free  — North Mini Code Free
  2) opencode/ling-3.0-flash-free   — Ling-3.0-flash Free
  3) opencode/laguna-s-2.1-free     — Laguna S 2.1 Free
  4) opencode/deepseek-v4-flash-free — DeepSeek V4 Flash Free
  5) opencode/mimo-v2.5-free        — MiMo V2.5 Free
  6) opencode/big-pickle            — Big Pickle
  7) opencode/nemotron-3-ultra-free — Nemotron 3 Ultra Free
  8) deepseek/deepseek-v4-flash     — DeepSeek V4 Flash
  9) deepseek/deepseek-v4-pro       — DeepSeek V4 Pro

  ↑/↓ navigate  ↵ select  esc cancel
```

按下 `8` 快速选择 `deepseek/deepseek-v4-flash`，随后出现变体选择器：

```text
Select variant for deepseek/deepseek-v4-flash:

❯ 1) high
  2) low
  3) max
  4) medium

  ↑/↓ navigate  ↵ select  esc cancel
```

按下 `3` 选择 `max` 变体，返回 REPL 并显示确认信息：

```text
[model] set to "deepseek/deepseek-v4-flash" (variant: max, saved to ~/.config/witty/config.toml)

witty [witty-builtin-agent:deepseek/deepseek-v4-flash] >
```

> 变体列表的顺序每次运行可能不同（Go map 迭代顺序随机），请根据实际显示选择。

---

## 4. 命令参考

### 4.1 全局选项

以下选项可用于所有子命令：

| 选项 | 类型 | 默认值 | 说明 |
| ---- | ---- | ------ | ---- |
| `--config` | string | `""` | 指定配置文件路径 |
| `--server-url` | string | `""` | 指定 opencode server 地址 |
| `--agent` | string | `""` | 指定默认 agent |
| `--model` | string | `""` | 指定默认模型（格式 `provider/model`） |
| `--variant` | string | `""` | 指定模型变体（如推理级别） |
| `--debug` | bool | `false` | 启用调试日志 |
| `--no-color` | bool | `false` | 禁用彩色输出 |
| `--version`, `-v` | — | — | 打印版本信息 |

### 4.2 `witty`（无子命令）— 启动 REPL

```bash
witty
```

启动交互式 REPL。自动恢复当前目录的最近会话；若无则新建。

### 4.3 `witty ask` — 单次提问

```bash
witty ask [prompt]
```

发送一条消息并流式输出回答，回答结束后退出。

**参数**：`[prompt]` — 提问内容，可作为命令行参数传入。

**选项**：

| 选项 | 类型 | 说明 |
| ---- | ---- | ---- |
| `--new` | bool | 创建新会话，不复用当前目录会话 |
| `--session` | string | 继续指定会话 ID |

> `--new` 和 `--session` 不能同时使用。

**示例**：

```bash
# 直接传参
witty ask "check system memory"

# 通过管道传入
echo "explain this function" | witty ask --new

# 继续指定会话
witty ask --session ses_123 "continue the last refactoring"
```

当未提供参数且 stdin 不是 TTY 时，从 stdin 读取提问内容。

### 4.4 `witty init bash` — 生成 Shell 集成脚本

```bash
witty init bash
```

输出 Bash 集成脚本到 stdout。通常配合 `eval` 使用：

```bash
eval "$(witty init bash)"
```

RPM 安装后已通过 `/etc/profile.d/witty.sh` 自动完成集成，一般无需手动执行。

### 4.5 `witty session` — 会话管理

#### 列出会话

```bash
witty session list
```

输出**全部**会话列表（不按目录过滤），格式为制表符分隔：`ID  Title  Directory  Updated`。
其中 `Updated` 为 Unix 毫秒时间戳。

#### 继续会话

```bash
witty session continue <id>
```

切换到指定会话。

> 也可使用顶层快捷命令 `witty continue <id>`。

### 4.6 `witty provider` — Provider 管理

详见 [§8 Provider 管理](#8-provider-管理)。

### 4.7 `witty server` — Server 管理

详见 [§9 Server 生命周期管理](#9-server-生命周期管理)。

### 4.8 `witty doctor` — 环境诊断

详见 [§10 环境诊断](#10-环境诊断)。

### 4.9 `witty version` — 版本信息

```bash
witty version
```

打印版本号、commit 和构建日期。

---

## 5. Shell 集成

### 5.1 工作原理

Shell 集成通过 Bash 的 `DEBUG` trap（配合 `extdebug` 选项）实现。在每条命令**即将执行前**拦截，由分类器判断路由：

| 路由 | 行为 |
| ---- | ---- |
| **shell** | 正常交给 Bash 执行，零侵入 |
| **agent** | 转交给 `witty ask` 处理 |
| **control** | 转交给 `witty` 解释 slash 控制命令 |

分类遵循"Shell 优先、Agent 兜底"原则——无法明确识别为自然语言的输入默认交给 Shell 执行。

### 5.2 路由示例

| 输入 | 路由 | 判定依据 |
| ---- | ---- | -------- |
| `检查系统内存` | Agent | CJK 字符 |
| `systemctl 怎么看 nginx 日志` | Agent | 中文触发词"怎么看" |
| `systemctl status nginx` | Shell | 已知命令 + 无 NL 特征 |
| `grep error /var/log/messages` | Shell | 已知命令 + 无 NL 特征 |
| `cat /etc/os-release \| grep NAME` | Shell | 管道 |
| `/session list` | Control | 白名单 slash 命令 |
| `/ask systemctl 怎么看 nginx 日志` | Control | 白名单 slash 命令，内部强制走 Agent 提问 |
| `/usr/bin/ls` | Shell | 显式路径 |
| `FOO=bar env` | Shell | 变量赋值 |
| `for i in 1; do` | Shell | Shell 语法（含 `;` 等强语法特征） |
| `how do I restart nginx` | Agent | 英文触发词 |
| `explain how to check memory` | Agent | 英文触发词 |

### 5.3 启用与禁用

**默认状态**：RPM 安装后对所有用户默认启用。

**临时禁用**（当前终端会话）：

```bash
export WITTY_SHELL_ENABLE=0
```

**永久禁用**：在 `~/.bashrc` 中添加：

```bash
export WITTY_SHELL_ENABLE=0
```

**手动启用**（未通过 RPM 安装时）：

```bash
eval "$(witty init bash)"
```

### 5.4 调试模式

```bash
export WITTY_SHELL_DEBUG=1
```

开启后在 stderr 输出分类结果等调试信息（如 `witty shell: classify agent: ...`）。

### 5.5 强制走 Agent

如果分类器误将自然语言识别为 shell 命令，可使用 `/ask` 逃生口强制走 Agent：

```bash
/ask docker 镜像怎么删
```

### 5.6 安装前提

Shell 集成仅在以下条件满足时安装：

- 当前 shell 为 Bash
- 交互式会话（`$-` 含 `i`）
- stdin/stdout 为 TTY

非交互式脚本、zsh / fish 等不支持的 shell 不会安装集成。

---

## 6. Slash 控制命令

在 REPL 和 Shell 直输模式下均可使用以下 slash 命令：

| 命令 | 作用 |
| ---- | ---- |
| `/help` | 显示帮助 |
| `/exit`、`/quit`、`/q` | 退出 REPL（不接受参数） |
| `/ask <prompt>` | 强制将当前输入作为 Agent 请求 |
| `/agent [name]` | 显示或切换默认 agent |
| `/model [provider/model]` | 显示或切换默认模型 |
| `/new` | 下一次提问时新建会话 |
| `/session list` | 列出会话 |
| `/session continue <id>` | 继续指定会话 |

### 6.1 `/agent` — 切换 Agent

不带参数时，如果当前是 TTY 终端，会显示交互式 agent 选择器（列出所有非隐藏、非 subagent 型 agent）。
带参数时直接切换：

```text
/agent witty-diagnosis-agent
```

切换后会持久化到用户配置文件，并输出确认信息：

```text
[agent] set to "witty-diagnosis-agent" (saved to ~/.config/witty/config.toml)
```

### 6.2 `/model` — 切换模型

模型格式必须为 `provider/model`，例如：

```text
/model openai/gpt-4
```

不带参数时显示交互式模型选择器，仅列出已连接 provider 的模型。

#### 交互式选择器

输入 `/model`（不带参数）后，终端切换到全屏选择器界面：

```text
Select model:

❯ 1) opencode/north-mini-code-free  — North Mini Code Free
  2) opencode/ling-3.0-flash-free   — Ling-3.0-flash Free
  3) opencode/laguna-s-2.1-free     — Laguna S 2.1 Free
  4) opencode/deepseek-v4-flash-free — DeepSeek V4 Flash Free
  5) opencode/mimo-v2.5-free        — MiMo V2.5 Free
  6) opencode/big-pickle            — Big Pickle
  7) opencode/nemotron-3-ultra-free — Nemotron 3 Ultra Free
  8) deepseek/deepseek-v4-flash     — DeepSeek V4 Flash
  9) deepseek/deepseek-v4-pro       — DeepSeek V4 Pro
     deepseek/deepseek-chat          — DeepSeek Chat
     deepseek/deepseek-reasoner      — DeepSeek Reasoner

  ↑/↓ navigate  ↵ select  esc cancel
```

操作方式：

| 按键 | 行为 |
| ---- | ---- |
| `↑` / `↓` | 上下移动选择 |
| `1`–`9` | 快速选择第 N 项（仅前 9 项支持） |
| `Enter` | 确认选择 |
| `Esc` | 取消 |
| `Ctrl+C` | 取消 |

> 前 9 项显示数字快捷键（`1)`–`9)`），第 10 项及之后无快捷键，需用方向键选择。

#### 变体选择

如果选中的模型支持变体（variant），会进一步显示变体选择器：

```text
Select variant for deepseek/deepseek-v4-flash:

❯ 1) high
  2) low
  3) max
  4) medium

  ↑/↓ navigate  ↵ select  esc cancel
```

> 变体列表的顺序是随机的（每次运行可能不同），请根据实际显示选择。

#### 确认信息

选择完成后，输出确认信息并持久化到配置文件：

```text
[model] set to "deepseek/deepseek-v4-flash" (variant: max, saved to ~/.config/witty/config.toml)
```

不带变体时：

```text
[model] set to "opencode/big-pickle" (saved to ~/.config/witty/config.toml)
```

### 6.3 参数校验规则

| 命令 | 参数要求 |
| ---- | -------- |
| `/ask` | **必须**带 prompt |
| `/agent` | 可选参数 |
| `/model` | 可选参数 |
| `/session list` | 无参数 |
| `/session continue` | **必须**带 session id |
| `/new` | 无参数 |
| `/help` | 无参数 |
| `/exit`、`/quit`、`/q` | 无参数 |

参数格式不合法的 slash 命令不会被识别为控制命令，行为因入口而异：

- **Shell 直输**：按默认规则路由，通常走 shell 执行
- **REPL**：未识别的 `/xxx` 会被当作普通提问发送给 AI；`/exit`、`/quit`、`/q` 即使带参数也会直接退出 REPL

---

## 7. 配置

### 7.1 配置文件

Witty CLI 使用 TOML 格式配置文件，搜索顺序（后者覆盖前者）：

1. `/etc/witty/config.toml` — 系统级配置
2. `~/.config/witty/config.toml` — 用户级配置

也可通过 `--config <path>` 或环境变量 `WITTY_CONFIG` 指定。

### 7.2 完整配置项

```toml
# 顶层配置
default_agent = "witty-builtin-agent"  # 默认 agent
default_model = ""                     # 默认模型（格式 provider/model）
default_variant = ""                   # 模型变体（如推理级别）
debug = false                          # 调试日志
theme = "auto"                         # 主题（auto）
no_color = false                       # 禁用彩色输出
stream_mode = 1                        # 流式输出模式（1=分段渲染，2=逐字回显）

# Server 生命周期管理
[server]
auto_start = true              # 自动启动 opencode serve
port = 0                       # 0 = 自动选择端口，正整数 = 固定端口
hostname = "127.0.0.1"         # 绑定地址
startup_timeout_seconds = 10   # 等待 server 启动的最大时间（秒）
idle_timeout_minutes = 30      # 闲置超时自动停止（0 = 禁用）

# REPL 配置
[repl]
auto_resume = true             # 自动恢复当前目录最近会话

# Shell 集成配置
[shell]
enabled = true                 # 启用 Shell 集成
debug = false                  # Shell 集成调试模式

# 诊断配置
[doctor]
timeout_seconds = 5            # 诊断超时时间（秒）

# 显示配置
[display]
show_reasoning = "show"        # 推理过程展示：show / minimal / hide
tool_mode = "compact"          # 工具调用展示：compact / verbose
group_context_tools = true     # 合并连续的读取类工具调用展示
step_style = "line"            # 步骤展示风格：line / minimal / none
```

### 7.3 环境变量

环境变量优先于配置文件，CLI 选项优先于环境变量。

#### 配置覆盖类

| 环境变量 | 对应配置项 | 说明 |
| -------- | ---------- | ---- |
| `WITTY_CONFIG` | — | 指定配置文件路径 |
| `WITTY_AGENT` | `default_agent` | 默认 agent |
| `WITTY_MODEL` | `default_model` | 默认模型 |
| `WITTY_VARIANT` | `default_variant` | 模型变体 |
| `WITTY_DEBUG` | `debug` | 调试日志（`true`/`false`） |
| `WITTY_SHELL_ENABLE` | `shell.enabled` | 启用 Shell 集成（`true`/`false`） |
| `WITTY_SHELL_DEBUG` | `shell.debug` | Shell 集成调试模式（`true`/`false`） |
| `WITTY_SERVER_AUTO_START` | `server.auto_start` | 自动启动（`true`/`false`） |
| `WITTY_SERVER_PORT` | `server.port` | server 端口 |
| `WITTY_SERVER_HOSTNAME` | `server.hostname` | 绑定地址 |
| `WITTY_DISPLAY_SHOW_REASONING` | `display.show_reasoning` | 推理过程展示 |
| `WITTY_DISPLAY_STEP_STYLE` | `display.step_style` | 步骤展示风格 |
| `NO_COLOR` | `no_color` | 设置任意值即禁用彩色输出（遵循 [NO_COLOR](https://no-color.org/) 标准） |

#### 运行时类

| 环境变量 | 说明 |
| -------- | ---- |
| `WITTY_STATE_PATH` | 会话状态文件路径（`state.json`）；server 状态文件放在同目录 |
| `XDG_STATE_HOME` | 状态目录回退（默认 `~/.local/state/witty`） |
| `__WITTY_SHELL_INIT_LOADED` | 由集成脚本设置为 `1`，用于检测 Shell 集成是否已加载 |

#### Provider API Key

`witty provider connect` 在未通过 `--key` / stdin / 交互输入提供密钥时，会按以下优先级查找环境变量：

1. Provider 声明的环境变量列表（如 `OPENAI_API_KEY`）
2. 约定回退：`<PROVIDER_ID 大写>_API_KEY`（非字母数字转为 `_`）

---

## 8. Provider 管理

### 8.1 列出 Provider

```bash
witty provider list
```

列出所有支持 API Key 认证的 provider，标注连接状态。输出格式：

```text
STATUS     ID        NAME          DEFAULT_MODEL
-          openai    OpenAI        gpt-4
connected  deepseek  DeepSeek      deepseek-chat
```

仅列出已连接的 provider：

```bash
witty provider list --connected
```

### 8.2 连接 Provider

```bash
witty provider connect <provider> --key <api-key>
```

`<provider>` 可以是 provider 的 ID 或名称（支持不区分大小写匹配）。

**API Key 的传入方式**（按优先级）：

1. `--key` 参数
2. 交互式终端提示（如果 stdin 是 TTY，会提示 `Enter API key:`，输入不可见）
3. stdin 管道读取
4. 环境变量（如 `OPENAI_API_KEY`、`DEEPSEEK_API_KEY`）

**示例**：

```bash
# 通过 --key 参数（非交互式）
witty provider connect deepseek --key sk-xxxx

# 通过环境变量
export DEEPSEEK_API_KEY=sk-xxxx
witty provider connect deepseek

# 通过交互式输入（不传 --key 时自动提示）
witty provider connect deepseek
```

交互式输入时，终端会提示输入 API Key（输入内容不可见，类似密码输入）：

```text
$ witty provider connect deepseek
Enter API key: ****（输入不可见）
connected provider deepseek
```

连接成功后输出 `connected provider deepseek`。如果 provider 仍不可用，
witty 会自动重启 server 以重新加载凭据。

**错误处理**：

- provider 不存在 → 报错并提示可用 provider
- provider 存在但不支持 API Key 认证 → `the current provider does not support API key authentication`
- 多个 provider 模糊匹配 → 报错并提示精确指定

---

## 9. Server 生命周期管理

Witty CLI 自动管理 `opencode serve` 进程的完整生命周期，通常无需用户干预。

### 9.1 自动启动

当 `server.auto_start = true`（默认）时，witty 首次使用时自动启动 `opencode serve` 子进程。启动后：

- server 作为守护进程运行，witty 退出后继续运行
- 状态持久化到 `~/.local/state/witty/server-state.json`（权限 0600）
- 下次启动 witty 时通过状态文件无缝复用

### 9.2 查看状态

```bash
witty server status
```

输出示例：

```text
Running:    yes
Port:       4096
PID:        12345
Managed:    no
StartedAt:  2026-07-30T10:30:00+08:00
```

- `Running`：server 是否正在运行——判断 server 状态以此字段为准
- `Managed: yes`：server 由当前 witty **进程**启动
- `Managed: no`：server 由之前的 witty 进程启动（从状态文件恢复），或由只读命令查询

> `Managed` 表示"是否由当前进程启动"，**不是**"是否受 witty 管理"。
> witty 的自动启动、端口复用与闲置超时停止等管理动作对 `Managed: no` 的 server 同样生效。
> 由于 CLI 每次调用都是独立进程，且 `witty server status` 是只读命令（自身不启动 server），
> 该命令下的 `Managed` 恒为 `no`，属预期行为；如需确认 server 是否在运行，请查看 `Running`。

### 9.3 停止 Server

```bash
witty server stop
```

优先调用 `POST /global/dispose` 优雅关机；如果 HTTP 不可达，兜底用 SIGTERM 信号停止进程。

### 9.4 重启 Server

```bash
witty server restart
```

停止当前 server 并启动新实例。**在安装或修改 agent / skill / MCP 配置文件后使用**，让 server 重新加载配置：

```bash
# 安装新 agent 后
sudo dnf install witty-diagnosis-agent
witty server restart
```

### 9.5 关闭自动启动

在配置文件中设置：

```toml
[server]
auto_start = false
```

或通过环境变量：

```bash
export WITTY_SERVER_AUTO_START=false
```

关闭后需手动启动 `opencode serve`（监听 `[server].hostname` + `port`），witty 将探测该地址寻找已有 server。若需连接其他地址的 server，请使用 `--server-url` CLI 标志。

### 9.6 闲置超时

默认 30 分钟无活动后自动停止 server（`server.idle_timeout_minutes = 30`）。设为 `0` 禁用此功能。

### 9.7 多用户安全隔离

同一台服务器上，不同用户的 server 实例互相隔离：

- 每个用户有独立的随机密码（HTTP Basic Auth）
- 状态文件权限 0600，其他用户无法读取
- 密码仅通过环境变量传递给子进程，不出现在命令行参数中

---

## 10. 环境诊断

```bash
witty doctor
```

运行环境诊断，检查以下项目：

| 检查项 | 说明 |
| ------ | ---- |
| **config** | 配置文件加载情况、当前 server/agent/model/shell 设置 |
| **server reachable** | opencode server 是否可达 |
| **/doc endpoint** | OpenAPI 文档端点是否可用 |
| **server management** | server 管理状态（managed/discovered/manual） |
| **shell integration** | Shell 集成是否已加载（检查 `__WITTY_SHELL_INIT_LOADED`） |
| **bash environment** | `TERM` 设置、Bash 版本（需 ≥ 4.0） |
| **terminal** | stdout TTY 状态、终端宽度、颜色支持 |

每项状态为 `OK`、`WARN`、`FAIL` 或 `SKIP`，并附带详情和修复建议。

输出示例：

```text
witty doctor — environment diagnostics

  [OK]   config: loaded: /etc/witty/config.toml, /root/.config/witty/config.toml; server=http://127.0.0.1:4096 agent=witty-builtin-agent model=(none) shell=enabled
  [OK]   server reachable: connected to http://127.0.0.1:4096 (opencode 1.17.13)
  [OK]   /doc endpoint: HTTP 200
  [OK]   server management: running (discovered), port=4096, pid=12345
  [OK]   shell integration: witty bash integration is loaded
  [OK]   bash environment: TERM=xterm-256color; bash 5.2.15(1)-release
  [OK]   terminal: stdout is a terminal; width=200; color enabled

Summary: 7 OK, 0 WARN, 0 FAIL, 0 SKIP
```

> 实际输出会因环境而异（如 server 地址、端口、TERM 设置等）。
> 非交互式环境（如管道）中 `bash environment` 和 `terminal` 项可能显示 WARN，
> 例如 `terminal: stdout is piped (non-TTY); width=80; no color (non-TTY)`。
>
> `witty doctor` 不会启动 server（无副作用），适合用于排查问题。

---

## 11. 常见问题

### 11.1 Shell 直输不生效

**可能原因**：Shell 集成未加载。

**排查步骤**：

1. 运行 `witty doctor`，检查 `shell integration` 项
2. 如果显示 `not loaded`，手动执行：

   ```bash
   eval "$(witty init bash)"
   ```

3. 如果仍不生效，检查是否设置了 `WITTY_SHELL_ENABLE=0`

### 11.2 自然语言被当成 shell 命令执行

分类器采用"Shell 优先"策略，部分边界场景可能误判。可使用 `/ask` 强制走 Agent：

```bash
/ask docker 镜像怎么删
```

### 11.3 提示 server 不可达或 "no opencode server found"

**如果开启了自动启动**（默认）：

- 检查 `opencode` 是否已安装：`which opencode`
- 若未安装，报错形如：
  `ensure opencode server: auto-start opencode server: opencode binary not found (install opencode or set server.auto_start=false and start it manually)`
- 运行 `witty doctor` 查看详细诊断
- 尝试 `witty server restart`

**如果关闭了自动启动**：

- 报错形如：
  `ensure opencode server: no opencode server found on 127.0.0.1:4096 and auto_start is disabled; start one with 'opencode serve --port 4096' or enable auto_start in config`
- 需手动启动：`opencode serve --port 4096`
- 或通过 `--server-url` 指定已有 server 地址

### 11.4 Provider 连接后仍不可用

连接 provider 后，witty 会自动重启 server 以加载凭据。如果仍未生效：

```bash
witty server restart
witty provider list --connected  # 确认连接状态
```

### 11.5 会话上下文丢失

Witty CLI 按当前目录管理会话：

- 在同一目录下执行 `witty` 或 Shell 直输会自动恢复最近会话
- 切换目录后会话不共享
- 使用 `/new` 或 `witty ask --new` 可强制新建会话
- 使用 `/session list` 查看可用会话，`/session continue <id>` 切换

### 11.6 如何完全禁用 Witty CLI

**禁用 Shell 集成**：

```bash
export WITTY_SHELL_ENABLE=0
```

**停止后台 server**：

```bash
witty server stop
```

**卸载**：

```bash
sudo dnf remove witty
```

卸载后自动移除 `/etc/profile.d/witty.sh`，零残留。

### 11.7 REPL 中如何取消当前请求

按 `Ctrl+C` 可取消正在进行的 AI 请求（输出 `[cancelled]`），不会退出 REPL。

---

## 附录

### 相关文档

- [设计文档：Witty CLI 产品概览](design/witty-overview.md)
- [设计文档：Shell Adapter](design/shell-adapter.md)
- [设计文档：Server 生命周期管理](design/server-lifecycle.md)
