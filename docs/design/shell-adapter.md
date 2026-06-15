# 设计文档：Shell Adapter（Bash 接入层）

> **适用范围**：openEuler Bash 5.x 交互式终端

---

## 1. 背景

Shell Adapter 是 `witty` 中最靠近用户终端输入的一层。它的职责是把 Bash 中用户敲下的一整行输入，稳定地分流到以下三类路径之一：

1. **普通 shell 命令**：保持原样交给 Bash 执行
2. **控制命令**：转交给 `witty` 解释（如 `/session list`）
3. **自然语言请求**：转交给 `witty ask` 处理

这层的难点在于：

- 必须在 **shell 真正执行之前** 拿到整行原始输入；
- 不能只覆盖"未知命令"场景，还要覆盖 `systemctl 怎么看 nginx 日志` 这类**以真实命令开头**的自然语言；
- 不能明显破坏 Bash 的原生体验，包括历史、补全、交互式程序、管道、多行命令与常见 prompt 行为；
- 要给出**稳定、可解释**的路由规则。

---

## 2. 目标与非目标

### 2.1 目标

1. **在 Bash 执行前拿到完整输入行**
2. **支持已知命令开头的自然语言**，例如：
   - `systemctl 怎么看 nginx 日志`
   - `git 怎么只看最近一次提交`
3. **对 shell 路由尽量保持原生语义**
4. **与 `witty` Core 解耦**：Adapter 只负责接入与路由，不重复实现会话/渲染/权限
5. **支持显式逃生口**：用户可以稳定地强制走 Agent 或控制命令
6. **在 openEuler Bash 5.x 上可落地实现**，使用 Bash 自身提供的机制

### 2.2 非目标

本设计**不追求**：

- 100% 无歧义地判断自然语言与 shell 命令
- 支持 Bash 之外的所有 shell（如 zsh/fish）
- 重新实现一个完整 shell parser
- 在 Adapter 层承担 Markdown 渲染、SSE、权限交互等 `witty` Core 职责
- 让"多段自然语言、多行编辑"在普通 shell 模式下媲美专用 REPL

> Shell Adapter 的目标是"**可靠接入 + 可解释路由**"，而不是"理解一切输入"。

---

## 3. 设计决策

### 3.1 主方案

Shell Adapter 的方案为：

> **Bash Readline Hook + `accept-line` 包装 + `READLINE_LINE` 改写 + 内部 dispatch 函数**

在 Enter 预处理阶段判断路由；如需转 Agent / 控制命令，将 `READLINE_LINE` 改写为内部 dispatch 函数调用，然后仍由 Bash 的 `accept-line` 执行——shell 路由时原命令完全不变，Agent 路由也走正常 accept-line 路径，避免了在 `bind -x` handler 中直接跑长任务带来的 prompt、history 和 TTY 输出混乱，退出码等语义也由 Bash 自己处理。

之所以不在 Enter Hook 里直接调用 `witty ask`，是因为当前输入行尚未正式 accept，会导致 history 行为不自然、prompt 显示时机混乱、交互式输出和退出码传递难以保持一致。改写命令行再交给 `accept-line` 的方式更顺着 Bash 的工作方式。

### 3.3 设计原则

1. **对 shell 路径零侵入或最小侵入**
2. **对 Agent 路径用"改写 + dispatch"而不是"立即执行"**
3. **分类逻辑确定性优先**，避免黑盒 NLP 分类器
4. **保留 escape hatch**，允许显式命令强制走 Agent / 控制路径
5. **在 Bash 能力边界内做事**，不让 Adapter 变成第二个 shell

---

## 4. 总体架构

```mermaid
graph TD
    A[用户在 Bash 输入一行]:::accent0 --> B[Enter 宏绑定]:::accent1
    B --> C[预处理 Hook<br/>读取 READLINE_LINE]:::accent2
    C --> D{判路}:::accent3
    D -->|Shell| E[保留原始行]:::accent4
    D -->|Agent / Control| F[改写为内部 dispatch 调用]:::accent5
    E --> G[accept-line]:::accent6
    F --> G
    G --> H[Bash 正常求值]:::accent7
    H --> I{执行内容}
    I -->|原始命令| J[Shell 正常执行]
    I -->|dispatch 函数| K[witty ask / witty 控制命令]
```

### 4.1 模块划分

Shell Adapter 拆成 5 个小模块：

1. **Installer**
   - `witty init bash` 输出 Bash 集成脚本
   - 做环境探测、幂等安装、key binding 注入

2. **Binding Layer**
   - 定义 Enter 宏绑定
   - 定义内部私有 key sequence
   - 将预处理 hook 串到 `accept-line` 前

3. **Classifier**
   - 基于 `READLINE_LINE` 的规则分类
   - 输出 `empty` / `shell` / `agent` / `control`

4. **Dispatcher**
   - 真正执行 `witty ask` / `witty session` / 其它控制动作
   - 维护 Shell 模式下需要保留的最小状态

5. **History / Safety Layer**
   - 隐藏内部 wrapper 命令
   - 保留用户原始输入到 history
   - 提供禁用、debug、fallback 能力

---

## 5. 关键实现：Enter 包装与行改写

采用两级绑定，不直接把 Enter 绑到 shell 函数：

1. 内部私有 key sequence 绑到预处理函数（`bind -x`）
2. 另一个内部私有 key sequence 绑到 `accept-line`
3. Enter 绑定为宏：先触发预处理 key sequence，再触发 `accept-line`

这保证了在 accept 前读到 `READLINE_LINE`，预处理函数有机会保留或改写整行，最终仍由 Bash 完成 accept 和执行——而不是在 `bind -x` handler 中直接执行 `witty ask`，后者难以无缝恢复默认回车行为。

预处理函数遵循以下逻辑：

```bash
__witty_pre_accept() {
    local raw="$READLINE_LINE"
    local route quoted

    route="$(__witty_classify "$raw")"

    case "$route" in
        empty|shell)
            return 0
            ;;
        control|agent)
            printf -v quoted '%q' "$raw"
            READLINE_LINE="__witty_shell_dispatch $route -- $quoted"
            READLINE_POINT=${#READLINE_LINE}
            return 0
            ;;
    esac
}
```

- **shell 路径**：完全不改原命令
- **agent/control 路径**：将原输入改写为 Bash 函数调用，`accept-line` 后 Bash 执行函数调用而非原文本

行改写把"应该执行什么"预先改好再交给 Bash，而非在 Readline 钩子里自己管理执行流，显著降低 prompt 混乱、history 不自然、退出码传播异常和 TTY 输出错位等风险。

> **⚠️ 实现偏差警告**：早期实现曾在 `__witty_pre_accept` 中直接调用 `command "$__WITTY_BINARY" ask -- "$raw"`，这违反了行改写架构。直接在 `bind -x` handler 中执行长任务会导致：① prompt 重绘时机错乱；② 退出码 `$?` 无法正确传播；③ Ctrl+C 信号处理异常；④ 交互式输出与 prompt 交错。**必须使用行改写方案**：将 `READLINE_LINE` 改写为 `__witty_shell_dispatch` 调用，由 `accept-line` 执行。

---

## 6. 路由与分类器设计

### 6.1 决策顺序

Adapter 采用**确定性优先级路由**，遵循"Shell 优先、Agent 兜底"原则：

1. **空输入** → `empty`
2. **白名单 slash 命令** → `control` / `agent`
3. **显式 `witty ...` 命令** → `shell`
4. **强 shell 特征** → `shell`
5. **自然语言高置信度** → `agent`
6. **首个 token 为已知 shell 命令且无 NL 特征** → `shell`
7. **首个 token 通过命令存在性检查** → `shell`
8. **首个 token 未通过命令存在性检查且无强 shell 特征** → `agent`（兜底）

> **为什么默认 shell 而非 agent？** Shell Adapter 无法识别的输入，Shell 自身可能仍然可以执行（自定义脚本、新安装的工具、alias 等）。如果默认走 agent，这些合法命令会被误路由到 AI，导致命令无法执行。正确做法是：Adapter 无法识别时交给 Shell 尝试执行；Shell 也无法解析（`command not found`）时，再通过 `command_not_found_handle` 兜底转交 Agent（见 §6.6）。这样两层都无法处理的输入才最终走 Agent，既保证合法命令不被误拦截，又确保自然语言不会丢失。

### 6.2 白名单控制命令

仅拦截明确白名单，避免误伤路径：

- `/ask <prompt>`
- `/agent <name>`
- `/model <id>`
- `/session list`
- `/session continue <id>`
- `/new`
- `/help`

`/usr/bin/ls`、`/opt/tools/foo` 这类绝对路径**不能**当成控制命令；slash 命令判定基于**白名单前缀**，而不是"以 `/` 开头"。

### 6.3 强 shell 特征

以下任一命中时，应优先走 shell：

- 管道 / 重定向：`|` `>` `>>` `<` `<<`
- 链式执行：`&&` `||` `;`
- 命令替换：`$(...)` `` `...` ``
- 变量赋值开头：`FOO=bar cmd`
- 显式路径执行：`./x` `../x` `/usr/bin/x`
- 通配/展开意图明显：`*.log` `?` `{a,b}`
- shell 关键字与多行结构：`for` `while` `if` `case` `do` `then` `fi` `done` `esac`
- 行尾续行：反斜杠结尾

### 6.4 自然语言高置信度特征

以下任一命中且不含强 shell 特征时，可优先走 Agent：

- **中文 / CJK 字符**：输入中包含 CJK 字符（Unicode Han 范围）
- **问号**：输入中包含半角 `?` 或全角 `？`
- **中文自然语言触发词**：`怎么`、`如何`、`帮我`、`请`、`分析`、`解释`、`排查`、`总结`、`检查`、`看看`、`为什么`、`是什么`、`能不能`
- **英文自然语言触发词**：`how`、`how do`、`what`、`why`、`explain`、`tell me`、`show me`、`please`、`help me`、`can you`、`is there`、`what's`
- 整句明显是请求或问题，而不是命令调用
- 以真实命令开头，但后续 token 明显是问题句，如：
  - `systemctl 怎么看 nginx 日志`
  - `git 怎么只看最近一次提交`
  - `explain how to check memory`
  - `how do I restart nginx`

> **英文触发词的边界**：英文触发词必须以空格结尾或作为独立 token 匹配（如 `how` 而非 `how`），避免误匹配 `hower`、`whatever` 等正常命令参数。

### 6.5 命令存在性检查

当一行既没有强 shell 特征，也没有高置信度 NL 特征时，对首个 token 做命令存在性检查：

- `type -t -- <first-token>` 或 `command -v -- <first-token>`

规则：

- **存在命令 + 无 NL 特征** → `shell`
- **不存在命令 + 无强 shell 特征** → `agent`

> **性能考量**：命令存在性检查在每次 Enter 时执行，`type -t` 是 Bash 内建命令，开销极小（不 fork 子进程）。但为避免在极端场景下影响输入响应速度，建议将检查结果缓存到当前 session 的关联数组中（`__WITTY_CMD_CACHE`），首次查询后缓存，后续同一命令直接查表。

> **与 `command_not_found_handle` 的关系**：命令存在性检查在 Adapter 层（Enter Hook）执行，`command_not_found_handle` 在 Shell 层（命令执行后 `command not found` 时触发）。两者形成双层兜底：Adapter 检测到命令不存在时走 Agent；如果 Adapter 漏判（命令存在但实际执行失败），`command_not_found_handle` 仍可兜底。

### 6.6 `command_not_found_handle` 兜底

当 Shell Adapter 将输入路由到 shell，但 Shell 执行时发现命令不存在（`command not found`），`command_not_found_handle` 作为第二层兜底将输入转交给 Agent：

```bash
__witty_command_not_found_handle() {
    local cmd="$1"
    if __witty_should_enable 2>/dev/null; then
        command "$__WITTY_BINARY" ask -- "$*"
        return $?
    fi
    printf 'witty: command not found: %s\n' "$cmd" >&2
    return 127
}

# 保存用户已有的 handler，链式调用
if [ "$(type -t command_not_found_handle 2>/dev/null)" = "function" ]; then
    __witty_prev_command_not_found_handle=command_not_found_handle
fi
command_not_found_handle() { __witty_command_not_found_handle "$@"; }
```

> **注意**：`command_not_found_handle` 是 Bash 5.x 的可选特性，部分发行版可能未启用。Adapter 安装时应检测该能力是否可用，不可用时不影响主流程——Enter Hook 分类器已覆盖大部分场景。

### 6.7 Slash 命令参数校验

白名单 slash 命令的参数规则必须在 Bash 侧和 Go 侧保持一致。Bash 侧应在分类阶段就拒绝不合法的参数格式，避免无效输入传到 Go 侧才报错：

| 命令 | 参数要求 | Bash 侧匹配规则 |
| ---- | -------- | --------------- |
| `/ask` | **必须**带 prompt | 仅匹配 `/ask 〈非空〉`；裸 `/ask` 不匹配为 control |
| `/agent` | 可选参数 | `/agent` 和 `/agent 〈name〉` 均匹配 |
| `/model` | 可选参数 | `/model` 和 `/model 〈id〉` 均匹配 |
| `/session list` | 无参数 | 仅匹配 `/session list`；`/session list 〈extra〉` 不匹配 |
| `/session continue` | **必须**带 session id | 仅匹配 `/session continue 〈id〉` |
| `/new` | 无参数 | 仅匹配 `/new`；`/new 〈extra〉` 不匹配 |
| `/help` | 无参数 | 仅匹配 `/help`；`/help 〈extra〉` 不匹配 |
| `/exit`、`/quit`、`/q` | 无参数 | 仅匹配无参数版本；带参数的不匹配 |

> **不匹配时的行为**：如果 slash 命令的参数格式不合法（如 `/exit foo`），分类器不应将其识别为 control，而应按默认规则继续判断——通常走 shell 路由，Shell 会报 `command not found`，再由 `command_not_found_handle` 兜底到 Agent。

---

## 7. History、会话与用户体验

### 7.1 History 目标

历史记录保留用户**真正输入的内容**，而不是内部包装命令。

理想效果：

```bash
$ 检查系统内存
$ history | tail -1
检查系统内存
```

而不是：

```bash
__witty_shell_dispatch agent -- 检查系统内存
```

### 7.2 推荐策略

1. 用 `HISTIGNORE` 忽略内部 wrapper 命令
2. 在 `__witty_shell_dispatch` 中显式把用户原始输入追加回 history

初始化时设置 `HISTIGNORE`：

```bash
__WITTY_HISTIGNORE="__witty_shell_dispatch *"
if [ -n "${HISTIGNORE:-}" ]; then
    HISTIGNORE="$__WITTY_HISTIGNORE:$HISTIGNORE"
else
    HISTIGNORE="$__WITTY_HISTIGNORE"
fi
export HISTIGNORE
```

`__witty_shell_dispatch` 中写入原始输入：

```bash
__witty_shell_dispatch() {
    local route="$1"
    shift
    if [ "${1:-}" = "--" ]; then
        shift
    fi
    local raw="$*"

    builtin history -s -- "$raw"

    case "$route" in
        agent)
            command "$__WITTY_BINARY" ask -- "$raw"
            ;;
        control)
            command "$__WITTY_BINARY" shell-control -- "$raw"
            ;;
    esac
}
```

> **关键**：`HISTIGNORE` 确保 `accept-line` 执行 `__witty_shell_dispatch agent -- "原始输入"` 时不会写入 history；`history -s "$raw"` 在 dispatch 函数内写入原始输入。这样 history 中只出现用户真正输入的内容。

### 7.3 会话连续性

Shell Adapter 自己不管理会话，只负责把请求转给 `witty`。会话策略仍由 `witty` Core 统一决定：

- 当前目录最近会话优先
- `/new` 新建会话
- `/session continue <id>` 切换会话

这保证：

- 在 shell 中直接输入自然语言后，进入 `witty` REPL 仍可接上上下文；
- Shell 快捷模式和 REPL 只是入口不同，不是两个系统。

### 7.4 Debug 模式

提供：

```bash
export WITTY_SHELL_DEBUG=1
```

打开后在 stderr 输出：

- 分类结果
- 改写前后命令
- 是否命中控制命令/强 shell 特征

---

## 8. 安装与兼容性设计

### 8.1 集成入口

```bash
eval "$(witty init bash)"
```

`witty init bash` 负责输出：

- 必要的 Bash 函数
- key bindings
- 幂等安装保护
- 可选 fallback

### 8.2 安装前提

仅在以下条件满足时安装：

- 当前 shell 为 Bash
- 交互式会话（`$-` 含 `i`）
- 启用了 Readline 编辑（非 `--noediting`）
- stdin/stdout 为 TTY

### 8.3 兼容性边界

| 场景 | 结论 |
| ---- | ---- |
| Bash 5.x + 交互式终端 | 支持 |
| Bash 非交互式脚本 | 不安装 |
| `bash --noediting` | 不支持 |
| zsh / fish | 不在本文档范围 |
| 远程 SSH TTY | 支持 |
| 重度自定义 Enter keybinding 的环境 | 需要兼容性验证 |

### 8.4 与现有增强脚本的关系

潜在冲突点：

1. **Enter 的自定义绑定**
2. **history / `HISTIGNORE` / prompt 集成脚本**

应对：

- 安装时做幂等检测；
- 尽量只覆盖 `emacs-standard` 和 `vi-insert` 的 Enter 绑定；
- **同时绑定 `\C-m`（CR）和 `\C-j`（LF）**：许多终端和 PTY 环境发送 LF 而非 CR 作为 Enter 键，只绑定 `\C-m` 会导致这些环境下行改写不生效；
- 提供环境变量开关：

```bash
export WITTY_SHELL_ENABLE=0
```

用于一键关闭 Adapter。

### 8.5 Fallback 方案

当 Readline 包装无法安装时，可选降级到：

- 显式命令：`witty ask "..."`
- 可选 `command_not_found_handle` fallback

但 fallback 只是"有总比没有好"，不能对外宣称为"完整 Shell Adapter 能力"。

---

## 9. 失败处理与安全边界

### 9.1 `witty` 不可用时

如果用户输入被路由到 Agent / Control，但 `witty` CLI 或后端不可用：

- 输出清晰错误信息；
- 返回非零退出码；
- **不要**再回退成执行原始自然语言文本。

### 9.2 分类失败时

"分类失败"不是异常，而是正常情况的一部分。

处理原则（"Shell 优先、Agent 兜底"）：

- 有明确 shell 证据 → 走 shell
- 有明确自然语言证据 → 走 agent
- 两边都不强 → 走 shell（交给 Bash 尝试执行）
- Shell 执行失败（`command not found`）→ 由 `command_not_found_handle` 兜底到 agent

这样确保合法命令不被误拦截，自然语言也不会丢失。

### 9.3 安全边界

Shell Adapter 不应：

- 自动把自然语言翻译成 shell 并偷偷执行；
- 在本地直接 `eval` 用户原始自然语言；
- 越过 `witty` Core 的权限模型。

Adapter 的责任只是**转发**，不是本地执行智能体生成的命令。

---

## 10. 分阶段实施

### Phase 1：最小可用 Adapter

目标：验证"Enter 包装 + 行改写 + dispatch"主链路。

- `witty init bash` 输出最小集成脚本
- 支持 `empty` / `shell` / `agent` 三路判定
- Agent 路由改写为 `__witty_shell_dispatch agent -- <raw>`（行改写，不在 `bind -x` 中直接调用 `witty ask`）
- 基础 history 处理（`HISTIGNORE` + dispatch 内 `history -s`）（见 §7）
- debug 输出（见 §7.4）
- `command_not_found_handle` 兜底（见 §6.6）
- 命令存在性检查 `type -t`（见 §6.5）

### Phase 2：控制命令与兼容性

- slash 命令白名单与 `control` 路径，含参数校验（见 §6.7）
- `emacs-standard` 和 `vi-insert` 双 keymap 绑定
- 同时绑定 `\C-m` 和 `\C-j`（见 §8.4）
- `HISTIGNORE` 与原有 history 配置共存（见 §7.2）

### Phase 3：增强与 fallback

- 更完整的强 shell 特征检测
- 更丰富的诊断信息与 doctor 输出
- 与 REPL 会话连续性的端到端验证（见 §7.3）
- 命令存在性检查结果缓存（`__WITTY_CMD_CACHE`）

---

## 11. 验收标准

以下场景应作为 P0 验收用例：

| 输入 | 期望路由 | 判定依据 |
| ---- | -------- | -------- |
| `检查系统内存` | Agent | CJK 字符 |
| `systemctl 怎么看 nginx 日志` | Agent | 中文触发词"怎么看" |
| `systemctl status nginx` | Shell | 已知命令 + 无 NL 特征 |
| `grep error /var/log/messages` | Shell | 已知命令 + 无 NL 特征 |
| `cat /etc/os-release \| grep NAME` | Shell | 管道 |
| `/session list` | Control | 白名单 slash 命令 |
| `/ask systemctl 怎么看 nginx 日志` | Agent | `/ask` 逃生口 |
| `/usr/bin/ls` | Shell | 显式路径 |
| `FOO=bar env` | Shell | 变量赋值 |
| `for i in 1; do` | Shell | Shell 关键字 |
| `explain how to check memory` | Agent | 英文触发词"explain" |
| `how do I restart nginx` | Agent | 英文触发词"how do" |
| `my_custom_script arg1 arg2` | Shell | 命令存在性检查通过 |
| `some_unknown_nonsense` | Agent | 命令存在性检查失败 + 无强 shell 特征 |
| `/exit foo` | Shell（→ command_not_found_handle → Agent） | `/exit` 不接受参数，降级 |
| `/ask` | Shell（→ command_not_found_handle → Agent） | `/ask` 必须带参数，裸 `/ask` 降级 |

此外还应验证：

1. **history 中保留原始输入**
2. **Agent 路由不把 wrapper 暴露给用户**
3. **Shell 路由的交互式命令行为正常**
4. **退出 `witty` 后能回到干净 prompt**
5. **禁用开关生效**

---

## 12. 已知风险

| 风险 | 应对 |
| ---- | ---- |
| Enter 绑定冲突（用户或其他插件已改写 Enter 绑定） | 安装前检测、debug 日志、可禁用能力 |
| 多行输入的自然语言体验不是主目标 | 长段 prompt 仍推荐使用 `witty` REPL |
| `vi-command` 模式细节 | 优先支持 `emacs-standard` 和 `vi-insert`，分模式补充验证 |
| history 细节差异（不同 Bash 版本与 `HISTCONTROL` / `HISTIGNORE` 组合） | 以真实终端行为验证为准 |
| `\C-j` 绑定与 heredoc / `read` / 多行续行冲突 | 同时绑定 `\C-m` 和 `\C-j`（许多 PTY 环境发送 LF 而非 CR）；已知风险，后续版本可考虑检测 PTY 类型后选择性绑定 |
| 英文自然语言触发词误匹配（如 `hower`、`whatever`） | 触发词以空格结尾或作为独立 token 匹配；`explain` 而非 `explain` |
| 命令存在性检查缓存过期（新安装的命令未命中缓存） | 缓存仅限当前 session，新 session 重新查询；可手动清除 `__WITTY_CMD_CACHE` |
| `command_not_found_handle` 与发行版已有 handler 冲突 | 保存已有 handler 并链式调用 |
