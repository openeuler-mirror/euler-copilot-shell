# Witty 开发 Todo List 与验收 Checkpoint

> 本文是 [`implementation-plan.md`](implementation-plan.md) 的执行清单版本：把模块级设计拆成可领取的开发任务，并为每个阶段定义可验证的验收 checkpoint。
>
> 适用范围：`witty` Go Core、Bash Shell Adapter、SSE/Event、Markdown Renderer、REPL、Doctor、发布打包。

---

## 1. 使用方式

### 1.1 状态标记

- `[ ]` 未开始
- `[~]` 进行中
- `[x]` 已完成
- `[!]` 阻塞，需要补充上下文或上游依赖

### 1.2 任务编号规则

| 前缀 | 含义 |
| --- | --- |
| `P0-*` | 工程脚手架与基础设施 |
| `P1-*` | 核心 MVP 闭环 |
| `P2-*` | REPL 与控制命令 |
| `P3-*` | 展示、流式增强与可靠性 |
| `P4-*` | 产品化、运维与发布 |
| `QG-*` | 全局质量门禁 |

### 1.3 Done Definition

任何任务完成前必须满足：

1. 代码符合 `.agents/rules/` 中的 Go、Bash、测试、安全与跨平台规则。
2. 新增模块包含对应测试；外部依赖通过 mock 或 fake 隔离。
3. 所有 internal 模块通过 `internal/app/wiring.go` 组装，避免跨模块隐式耦合。
4. SSE 使用手写 `bufio.Reader` 解析；不得使用 `ClientWithResponses` 处理流式事件。
5. Bash 模板使用 `[[ ]]` 作为 Go template 分隔符；不得使用 `{{ }}`。
6. 本地快速验证通过；涉及 Bash/PTY/RPM 的任务最终必须在 openEuler 环境验收。

---

## 2. 全局质量门禁

### QG-0：每次提交前快速检查

- [x] `go fmt ./...`
- [x] `go test -count=1 ./...`
- [x] `go build -ldflags="-s -w" ./cmd/witty`
- [x] 如果修改 Bash 模板：`shellcheck internal/shellinit/templates/*.bash.tmpl`

### QG-1：PR 前完整检查

- [x] `go test -count=1 ./...`
- [x] `golangci-lint run ./...`
- [x] `shellcheck internal/shellinit/templates/*.bash.tmpl`
- [x] 如修改 OpenAPI spec：执行接口回归测试并确认生成代码仅在允许目录变更。
- [x] 如修改 Renderer：执行 Markdown golden tests，人工确认快照变化合理。
- [x] 如修改 Shell Adapter：执行 PTY 集成测试。

### QG-3：集成测试（opencode 可用时）

> 当 opencode server 在 `127.0.0.1:4096` 可达时，执行真实环境集成测试。

- [x] 确认 opencode server 可达：`curl -s http://127.0.0.1:4096/global/health`
- [x] 运行集成测试：`go test -v -tags=integration -count=1 -timeout 300s ./test/integration/`

### QG-2：openEuler 最终验证

> 连接方式由 `.agents/config.yaml` 决定。若文件不存在，先按 `.agents/config.template.yaml` 配置 OrbStack / WSL / SSH 环境。

- [x] 在 openEuler 上执行 `go test -count=1 ./...`
- [x] 在 openEuler 上执行 `go build -ldflags="-s -w" ./cmd/witty`
- [x] 在 openEuler 上执行 `TERM=xterm-256color go test -v -tags=pty ./test/pty/`
- [x] 发布前执行 `goreleaser release --snapshot --clean --skip=publish`

---

## 3. Phase 0：工程脚手架与基础设施

目标：建立可编译、可测试、可扩展的 Go CLI 骨架；固化 OpenAPI spec；让 `witty --help`、`witty version`、`witty init bash` 占位路径可运行。

### P0-1：初始化 Go module 与目录结构

- [x] 创建 `go.mod`，声明 Go 版本与模块路径。
- [x] 建立目录：
  - [x] `cmd/witty/`
  - [x] `internal/app/`
  - [x] `internal/cli/`
  - [x] `internal/config/`
  - [x] `internal/terminal/`
  - [x] `internal/version/`
  - [x] `test/testdata/`
  - [x] `test/pty/`
- [x] 添加 `.gitignore` 覆盖本地配置、构建产物与临时文件。
- [x] 确认 `CGO_ENABLED=0` 构建路径可用。

#### 验收 checkpoint：C0-1

- [x] `go mod tidy` 成功。
- [x] `go test ./...` 成功，即使暂时只有空测试或基础测试。
- [x] `CGO_ENABLED=0 go build ./cmd/witty` 成功。
- [x] 仓库中不包含 `.agents/config.yaml`、token、密钥或本机路径敏感信息。

### P0-2：`cmd/witty` 程序入口

- [x] `main.go` 只负责调用 `app.New()` / `cli.Execute()`，不放业务逻辑。
- [x] 版本信息通过 `ldflags` 注入，默认值可在开发态显示。
- [x] 业务错误以用户可读方式输出，debug 模式下保留更多上下文。

#### 验收 checkpoint：C0-2

- [x] `witty --help` 正常显示命令帮助。
- [x] `witty version` 输出 version / commit / date，未注入时显示 dev fallback。
- [x] `cmd/witty/main.go` 无直接依赖 transport、renderer、session 等业务包。

### P0-3：Cobra 命令树

- [x] 根命令 `witty`。
- [x] 子命令占位：
  - [x] `ask`
  - [x] `init bash`
  - [x] `session list`
  - [x] `session continue <id>`
  - [x] `continue <id>`
  - [x] `doctor`
  - [x] `version`
- [x] 全局 flags：
  - [x] `--config`
  - [x] `--server-url`
  - [x] `--agent`
  - [x] `--model`
  - [x] `--debug`
  - [x] `--no-color`
- [x] 命令参数错误返回可读提示，不 panic。

#### 验收 checkpoint：C0-3

- [x] `witty --help`、`witty ask --help`、`witty init bash --help` 输出稳定。
- [x] 参数错误时返回非 0 退出码。
- [x] CLI 层只做参数解析和调用 app service，不直接实现核心业务。

### P0-4：配置加载 `internal/config`

- [x] 使用 koanf v2，实现三层加载：默认值 → 配置文件 → 环境变量 / CLI override。
- [x] 支持用户配置路径：`~/.config/witty/config.toml`。
- [x] 支持系统配置路径：`/etc/witty/config.toml`。
- [x] 字段覆盖：
  - [x] `server_url`
  - [x] `default_agent`
  - [x] `default_model`
  - [x] `debug`
  - [x] `theme`
  - [x] `repl.auto_resume`
  - [x] `shell.enabled`
  - [x] `doctor.timeout_seconds`
- [x] 环境变量建议：`WITTY_SERVER_URL`、`WITTY_AGENT`、`WITTY_MODEL`、`WITTY_DEBUG`、`NO_COLOR`。
- [x] key 大小写保持敏感，不引入 viper 风格隐式转换。

#### 验收 checkpoint：C0-4

- [x] 配置优先级测试覆盖默认值、文件、环境变量、CLI override。
- [x] 配置文件不存在时可使用默认值启动。
- [x] 无效配置返回带上下文的错误：`fmt.Errorf("load config: %w", err)`。
- [x] 非 TTY 场景日志默认降级，不污染管道输出。

### P0-5：终端能力 `internal/terminal`

- [x] TTY 检测。
- [x] 终端宽度探测。
- [x] color/no-color 判定。
- [x] prompt 输入抽象，供 permission/question/repl 复用。
- [x] CJK 宽度处理预留 `go-runewidth` 集成点。

#### 验收 checkpoint：C0-5

- [x] TTY 与非 TTY 单元测试覆盖。
- [x] 宽度不可用时回退到安全默认值。
- [x] `NO_COLOR` 生效。

### P0-6：OpenAPI spec 与 generated models

- [x] 从 `opencode /doc` 固化 OpenAPI 3.1.0 spec 到 `api/opencode/openapi.json`。
- [x] 使用 oapi-codegen v3 生成 models/types；不得使用生成 client 处理 SSE。
- [x] 将生成代码隔离在约定目录，后续禁止人工编辑 `transport/generated/`。
- [x] 记录 spec 来源版本、更新时间和更新命令。

#### 验收 checkpoint：C0-6

- [x] `api/opencode/openapi.json` 是有效 JSON。
- [x] `go test ./...` 编译通过。
- [x] 生成代码 diff 与 spec 变更对应；无手写逻辑混入 generated 目录。
- [x] 文档中明确 OpenAPI 3.1.0 与 oapi-codegen v3 约束。

### P0-7：应用组装 `internal/app`

- [x] 定义 App / Container 结构，统一持有 config、logger、transport、session、core、renderer、presenter、permission、repl、doctor。
- [x] 构造函数返回接口或窄类型，避免 CLI 直接 new 各模块实现。
- [x] logger 在非 TTY 或非 debug 场景避免污染 stdout。
- [x] wiring 中只做依赖装配，不塞业务流程。

#### 验收 checkpoint：C0-7

- [x] `internal/app/wiring.go` 可读且无循环依赖。
- [x] CLI 命令只通过 app 暴露的 service 调用业务。
- [x] 单元测试可用 fake dependency 构造 app。

---

## 4. Phase 1：核心 MVP 闭环

目标：实现 `witty ask` 与 Shell 直输的最小闭环。用户能发起 prompt，客户端通过 transport 发送请求，订阅 SSE，按 `session.idle` 结束，Markdown 按块边界持续输出，permission/question 能阻塞式处理。

### P1-1：Transport HTTP Client

- [x] 实现基础 HTTP client：base URL、timeout、User-Agent、debug logging。
- [x] 实现健康检查 / server 信息探测。
- [x] 实现 session 创建、列表、继续。
- [x] 实现发送 prompt 的 API 调用。
- [x] 实现 permission reply / question reply / question reject。
- [x] HTTP 错误返回结构化错误类型，包含 status code、endpoint、响应摘要。

#### 验收 checkpoint：C1-1

- [x] transport 单元测试覆盖请求路径、方法、body、错误响应。
- [x] context cancel 能中断请求。
- [x] debug 日志不输出 token、session secret 等敏感字段。
- [x] **集成测试**：真实 opencode 上验证 Health、CreateSession、ListSessions、SendPromptAsync、ReplyPermission。

### P1-2：手写 SSE Parser

- [x] 用 `bufio.Reader` 实现 SSE 行解析。
- [x] 支持字段：`event:`、`data:`、`id:`、`retry:`。
- [x] 支持多行 `data:` 拼接。
- [x] 支持注释行 `:` 忽略。
- [x] 支持空行触发 event dispatch。
- [x] 解析与 HTTP 连接生命周期分离，便于单元测试。

#### 验收 checkpoint：C1-2

- [x] 单元测试覆盖单事件、多行 data、注释、空 data、EOF 前残留、畸形 retry。
- [x] 代码中不存在 `ClientWithResponses` 处理 SSE 的路径。
- [x] reader 返回 `io.EOF` 时不直接等价为业务完成；业务完成以 `session.idle` 为准。
- [x] **集成测试**：真实 SSE 事件流正确解析（`message.part.delta`、`session.idle` 等）。

### P1-3：Event 归一化 `internal/event`

- [x] 定义 `AppEventKind`：
  - [x] `EventTextDelta`
  - [x] `EventReasoningDelta`
  - [x] `EventStepStarted`
  - [x] `EventStepEnded`
  - [x] `EventToolCalled`
  - [x] `EventToolSucceeded`
  - [x] `EventToolFailed`
  - [x] `EventPermissionAsked`
  - [x] `EventQuestionAsked`
  - [x] `EventSessionIdle`
  - [x] `EventUnknown`
- [x] 以 `message.part.delta` / `message.part.updated` 为主路径解析文本、工具、步骤状态。
- [x] 兼容 `session.next.*` 类事件，但不让其绕过统一 AppEvent。
- [x] 实现 sessionID 过滤；`GET /event` 是全局事件总线，不可默认全量消费。
- [x] Unknown 事件保留摘要，debug 模式可展示。

#### 验收 checkpoint：C1-3

- [x] fixture 测试覆盖 text delta、reasoning delta、tool call/result、permission、question、idle、unknown。
- [x] sessionID 不匹配的事件被过滤。
- [x] schema 漂移不会 panic；返回 unknown 或带上下文错误。
- [x] **集成测试**：真实 opencode 事件归一化正确（step → reasoning(×32) → text → step ended → idle）。

### P1-4：Session Manager

- [x] 当前默认 session 解析策略。
- [x] `--new` / ForceNew 创建新 session。
- [x] `continue <id>` 指定 session。
- [x] `session list` 展示历史会话摘要。
- [x] 本地状态文件最小化，避免过早引入 DB。

#### 验收 checkpoint：C1-4

- [x] 创建、继续、列表逻辑有 fake transport 测试。
- [x] session id 不存在时错误清晰。
- [x] 状态文件路径符合 XDG 或项目约定，不写入仓库。
- [x] **集成测试**：真实 opencode 上验证 Resolve(复用) + ForceNew + Continue + List + 无效ID报错。

### P1-5：Renderer Phase 1：块边界渲染

- [x] 定义 `TextRenderer` 接口：`WriteDelta(ctx, delta)`、`Flush(ctx)`。
- [x] 实现 `BlockBuffer`，积累 delta 到完整 Markdown 块。
- [x] 识别段落、空行、ATX heading、列表、引用、围栏代码块、thematic break。
- [x] 使用 glamour v2 批量渲染完整块。
- [x] Flush 时渲染剩余未闭合内容。
- [x] 渲染错误降级为原文输出，不中断 ask 主流程。

#### 验收 checkpoint：C1-5

- [x] 块边界单元测试覆盖段落、标题、列表、引用、代码围栏、未闭合代码块。
- [x] Golden test 覆盖典型 Markdown ANSI 输出。
- [x] `witty ask` 输出不是等完整回答结束后一次性打印，而是按完整块持续刷新。
- [x] 非 TTY 输出避免写 ANSI 控制码。

### P1-6：Presenter 基础展示

- [x] 定义 tool/step/error/permission/question 的基础展示接口。
- [x] 工具调用开始、成功、失败有统一样式。
- [x] 错误展示区分用户错误、网络错误、server 错误、schema 错误。
- [x] 样式依赖 lipgloss v2，遵守 no-color。

#### 验收 checkpoint：C1-6

- [x] presenter 单元测试或 golden test 覆盖主要输出。
- [x] 快捷模式与 REPL 复用同一 presenter。
- [x] 非 TTY 输出可读且无多余 ANSI。

### P1-7：Permission / Question Manager

- [x] 接管 permission asked 事件。
- [x] 接管 question asked 事件。
- [x] TTY 中阻塞式提问，提交 reply API。
- [x] 非 TTY 场景给出明确错误或安全默认拒绝策略。
- [x] 支持 multiple choice / custom answer 的数据结构。

#### 验收 checkpoint：C1-7

- [x] fake transport 测试覆盖 approve/reject、question answer、question reject。
- [x] permission/question 出现时暂停正文渲染或保证输出不交错。
- [x] Ctrl+C 能取消当前交互并释放 goroutine。

### P1-8：AskRunner 核心执行管线

- [x] 定义 `AskRequest`：prompt、cwd、session、force new、agent、model、mode。
- [x] 执行步骤：解析 session → 发送 prompt → 订阅/过滤事件 → 分发 renderer/presenter/permission → 等待 `session.idle` → flush。
- [x] 统一处理 context cancel、SIGINT、server error、stream EOF without idle。
- [x] 不在 core 中实现 CLI 参数解析或 Bash 分类逻辑。

#### 验收 checkpoint：C1-8

- [x] AskRunner fake event stream 测试覆盖正常完成、EOF without idle、permission、question、tool failed、cancel。
- [x] 收到 `session.idle` 后一定调用 renderer `Flush()`。
- [x] ask 命令退出码符合结果：成功 0，用户取消/网络错误/服务端错误非 0。

### P1-9：`witty ask` 命令闭环

- [x] 支持 `witty ask "prompt"`。
- [x] 支持 stdin prompt：`echo "..." | witty ask`。
- [x] 支持 cwd 传递。
- [x] 支持 `--new`、`--session`、`--agent`、`--model`。
- [x] 用户可读错误输出到 stderr。

#### 验收 checkpoint：C1-9

- [x] `witty ask --help` 完整。
- [x] `witty ask "检查系统内存"` 在 opencode server 可用时能流式输出。
- [x] opencode server 不可用时错误包含 server URL 与排查建议，不 panic。
- [x] stdout 只包含用户期望内容；debug/log 不污染 stdout。

### P1-9B：Provider 管理 `witty provider` [增补阶段]

增补背景：`opencode serve` 与 opencode TUI 进程独立，TUI 中 connect 的 provider 不会自动对 server 生效。
需要通过 `witty provider` 命令让用户在终端内完成 provider 连接，避免打开 TUI 或手动构造 curl 请求。

- [x] `witty provider list` 列出支持 API Key 认证的 provider，标注 connected 状态。
- [x] `witty provider list --connected` 仅列出已连接且支持 API Key 认证的 provider。
- [x] `witty provider connect <provider> --key <api-key>` 通过 API Key 连接 provider（调用 `PUT /auth/{providerID}`），支持 provider id / name 解析。
- [x] `connect` 前先查询 `/provider` 解析输入，再查询 `/provider/auth` 过滤出支持 `type=api` 的 provider。
- [x] `--key` 未提供时提示从 stdin 或环境变量读取。
- [x] `connect` 成功后重新查询 provider 列表确认 connected 状态已更新。
- [x] provider 不存在时给出友好错误提示（不是裸 HTTP 状态码）。
- [x] provider 存在但 `/provider/auth` 不支持 `type=api` 时，返回明确错误：`当前 Provider 暂不支持 API Key 认证方式`。
- [x] 连接失败（如 key 无效）时错误信息包含排查建议。

#### 验收 checkpoint：C1-9B

- [x] `witty provider list` 输出仅包含支持 API Key 认证的 provider 条目，connected 状态正确。
- [x] `witty provider list --connected` 仅显示 connected 且支持 API Key 认证的 provider（初始可能为空或仅有 opencode）。
- [x] `witty provider connect deepseek --key <valid-key>` 成功，再次 `list --connected` 可见 deepseek。
- [x] `witty provider connect nonexistent --key sk-xxx` 返回可读错误，exit code 非 0。
- [x] `witty provider connect <provider-without-api-auth> --key sk-xxx` 返回明确错误：`当前 Provider 暂不支持 API Key 认证方式`。
- [x] `witty provider connect deepseek`（无 `--key`）给出明确的使用说明，不 panic。
- [x] `go test -count=1 ./internal/cli/ ./internal/transport/ ./internal/app/` 通过。
- [x] VM 环境验证：使用 `witty provider connect` 连接 deepseek 后，`witty ask --model deepseek/deepseek-v4-flash --variant reasoning-high --new "hello"` 能正常完成。

### P1-10：Shell Init 模板 `internal/shellinit`

- [x] `witty init bash` 输出 Bash 集成脚本。
- [x] 使用 `embed.FS` 管理模板。
- [x] Go template 分隔符设置为 `[[ ]]`。
- [x] Bash 函数统一 `__witty_` 前缀。
- [x] 脚本支持幂等加载。
- [x] 提供环境变量开关禁用 adapter。

#### 验收 checkpoint：C1-10

- [x] `witty init bash` 输出中不包含 `{{` / `}}` 模板分隔符。
- [x] `shellcheck internal/shellinit/templates/*.bash.tmpl` 通过。
- [x] `go test -v -run TestBashTemplate ./internal/shellinit/` 通过。
- [x] 重复 `eval "$(witty init bash)"` 不重复绑定或污染环境。

### P1-11：Shell Bridge 分类与 dispatch

- [x] Bash 侧实现 DEBUG trap + extdebug + 分类器 + dispatch。
- [x] **DEBUG trap 方案**：`__witty_debug_hook` 中 agent/control 路由返回 1 跳过 Bash 执行，转交 `__witty_shell_dispatch`；shell/empty 路由返回 0 正常执行。
- [x] 分类路径：empty / shell / agent / control。
- [x] 强 shell 特征优先：管道、重定向、变量赋值、显式路径、shell 关键字、多行续行等。
- [x] 白名单 slash 命令：`/ask`、`/agent`、`/model`、`/session list`、`/session continue`、`/new`、`/help`。
- [x] **slash 命令参数校验**：Bash 侧分类器对 `/exit`、`/new`、`/help` 只匹配无参数版本；`/ask` 必须带参数；裸 `/ask` 不应匹配为 control（见 shell-adapter.md §6.7）。
- [x] `/usr/bin/ls` 等绝对路径不得误判为 slash 控制命令。
- [x] dispatch 只调用 `witty ask` 或控制命令；Bash Hook 中不得执行长时间 AI 调用。
- [x] **英文自然语言触发词**：Bash 侧 `__witty_classify` 补充英文触发词（`how`、`what`、`why`、`explain`、`tell me`、`show me`、`please`、`help me`、`can you`），与 Go 侧 `hasNaturalLanguageSignal` 对齐。
- [x] **`witty` 前缀显式检测**：分类器中显式检测首个 token 为 `witty` 时走 shell，避免默认路由变更后误判。
- [x] **命令存在性检查**：当首个 token 既不在已知命令列表中，也无 NL 特征时，用 `type -t` 检查命令是否存在；存在 → shell，不存在 → agent。
- [x] **`command_not_found_handle` 兜底**：安装 `__witty_command_not_found_handle`，Shell 执行 `command not found` 时转交 Agent；保存用户已有 handler 并链式调用。
- [x] **`HISTIGNORE` 设置**：初始化时追加 `__witty_shell_dispatch *` 到 `HISTIGNORE`，确保 wrapper 不进入 history。
- [x] **History 统一写入点**：`__witty_shell_dispatch` 中 `history -s "$raw"` 写入用户原始输入。
- [x] history 保留用户原始输入，隐藏内部 wrapper 命令。

#### 验收 checkpoint：C1-11

- [x] 分类器单元测试覆盖 `检查系统内存` → agent。
- [x] 分类器单元测试覆盖 `systemctl status nginx` → shell。
- [x] 分类器单元测试覆盖 `systemctl 怎么看 nginx 日志` → agent。
- [x] 分类器单元测试覆盖 `cat /etc/os-release | grep NAME` → shell。
- [x] 分类器单元测试覆盖 `explain how to check memory` → agent（英文触发词）。
- [x] 分类器单元测试覆盖 `how do I restart nginx` → agent（英文触发词）。
- [x] 分类器单元测试覆盖 `my_custom_script arg1` → shell（命令存在性检查通过）。
- [x] 分类器单元测试覆盖 `some_unknown_nonsense` → agent（命令存在性检查失败）。
- [x] 分类器单元测试覆盖 `/exit foo` → shell（slash 命令参数校验）。
- [x] 分类器单元测试覆盖 `/ask` → shell（裸 `/ask` 不匹配为 control）。
- [x] 分类器单元测试覆盖 `witty ask "something"` → shell（`witty` 前缀显式检测）。
- [x] PTY 测试验证自然语言直输能触发 `witty ask`。
- [x] PTY 测试验证普通 shell 命令不被拦截。
- [x] PTY 测试验证 `__witty_debug_hook` 使用 DEBUG trap + extdebug 方案，shell 路由返回 0，agent 路由返回 1。
- [x] PTY 测试验证 history 中不出现 `__witty_shell_dispatch ...`。
- [x] PTY 测试验证 `command_not_found_handle` 兜底：未知命令走 Agent。

### P1-11B：全局 Shell 集成（`/etc/profile.d/witty.sh`）

- [ ] 创建 `packaging/profile.d/witty.sh` 入口脚本，内容为 `eval "$(witty init bash 2>/dev/null)" || true`，带 `BASH_VERSION` 和幂等检查。
- [ ] RPM spec 中声明 `%config(noreplace) /etc/profile.d/witty.sh`，安装/卸载不修改系统 bashrc。
- [ ] 用户禁用机制：`WITTY_SHELL_ENABLE=0` 在 `~/.bashrc` 中设置后，`witty init bash` 内部跳过绑定。
- [ ] 卸载验证：RPM 卸载后 `/etc/profile.d/witty.sh` 被删除，新打开的 shell 不再加载 witty 集成。
- [ ] 升级验证：RPM 升级后 `/etc/profile.d/witty.sh` 被更新，新打开的 shell 加载新版本逻辑。

#### 验收 checkpoint：C1-11B

- [ ] 在 openEuler 上安装 RPM 后，新打开的交互式 Bash 自动加载 witty 集成。
- [ ] 在 `~/.bashrc` 中加 `export WITTY_SHELL_ENABLE=0` 后，witty 集成不加载。
- [ ] RPM 卸载后，新打开的 shell 无 witty 集成残留。
- [ ] `witty` 二进制不存在时，`/etc/profile.d/witty.sh` 不报错（`2>/dev/null || true`）。
- [ ] 非交互式 shell（如 `bash -c 'echo hello'`）不加载 witty 集成。

### P1-12：MVP 端到端验收

#### 验收 checkpoint：C1-E2E

- [x] 本地或 openEuler 环境启动 opencode server。
- [x] `witty doctor` 或临时 health check 能确认 server 可达。
- [x] `witty ask "检查系统内存"` 能完成一轮问答。
- [x] 输出按 Markdown 块边界持续刷新。
- [x] 出现 tool call 时有基础展示。
- [x] 出现 permission/question 时可交互回复。
- [x] `session.idle` 到达后进程退出，退出码为 0。
- [x] `eval "$(witty init bash)"` 后：
  - [x] `检查系统内存` → Agent。
  - [x] `systemctl status nginx` → Shell。
  - [x] `/ask systemctl 怎么看 nginx 日志` → Agent。
  - [x] `/usr/bin/ls` → Shell。

---

## 5. Phase 2：REPL 与控制命令

目标：`witty` 无参数启动完整 REPL；REPL 与 Shell 快捷模式共享 AskRunner、Presenter、Renderer、Permission、Session 管线；控制命令在两种入口表现一致。

### P2-1：REPL 基础循环

- [x] `witty` 无参数进入 REPL。
- [x] prompt 显示当前 session / agent / model 的简要状态。
- [x] 普通文本输入调用 AskRunner。
- [x] Ctrl+C 取消当前请求但不一定退出 REPL。
- [x] Ctrl+D / `/exit` 退出 REPL。

#### 验收 checkpoint：C2-1

- [x] REPL 中输入 `检查系统内存` 能得到与 `witty ask` 一致的输出。
- [x] 当前请求 Ctrl+C 后 goroutine 退出，无卡死。
- [x] Ctrl+D 返回 0 或约定退出码。

### P2-2：Slash 命令解释器

- [x] `/help`。
- [x] `/new`。
- [x] `/session list`。
- [x] `/session continue <id>`。
- [x] `/agent <name>`。
- [x] `/model <id>`。
- [x] `/ask <prompt>`。
- [x] `/exit`。
- [x] 未知 slash 命令给出建议。

#### 验收 checkpoint：C2-2

- [x] REPL slash 命令 table-driven tests 覆盖。
- [x] Shell Adapter control 命令与 REPL 使用同一解析/执行逻辑或共享同一语义测试。
- [x] `/usr/bin/ls` 在 Shell 模式仍不被当成 slash 命令。

### P2-3：Session 控制与 auto resume

- [x] `repl.auto_resume` 生效。
- [x] `/new` 创建新 session 并设为当前。
- [x] `/session continue <id>` 切换当前 session。
- [x] session 列表输出包含 id、title/summary、更新时间。

#### 验收 checkpoint：C2-3

- [x] REPL 重启后按配置恢复或不恢复 session。
- [x] session id 无效时不改变当前 session。
- [x] session 列表非 TTY 输出可被脚本消费。

### P2-4：Shell control 路径

- [x] Shell 直输 `/new` 转到 witty 控制命令。
- [x] Shell 直输 `/session list` 展示列表。
- [x] Shell 直输 `/session continue <id>` 切换后续默认 session。
- [x] Shell 直输 `/agent`、`/model` 更新默认值或当前 shell 会话状态。

#### 验收 checkpoint：C2-4

- [x] PTY 测试覆盖 `/new`、`/session list`、`/session continue`。
- [x] 控制命令的退出码可被 Bash 正确感知。
- [x] 控制命令不会触发 AI 请求。

### P2-5：History、debug、可关闭性与全局集成

- [x] Shell Adapter debug 模式可输出路由决策到 stderr（`__witty_debug` + `WITTY_SHELL_DEBUG`）。
- [x] 提供环境变量禁用 Shell Adapter（`WITTY_SHELL_ENABLE=0` + `__witty_should_enable`）。
- [x] history 保真：`__witty_shell_dispatch` 中 `history -s "$raw"` 写入用户原始输入。
- [x] 内部 dispatch 命令不进入历史（`HISTIGNORE="__witty_shell_dispatch *"`）。
- [x] `__witty_uninstall_bindings` 函数：恢复已有 DEBUG trap，关闭 `extdebug`。
- [x] 已有 DEBUG trap 保存与链式调用（`__witty_prev_debug_trap`）。
- [x] `extdebug` 安装与卸载（`shopt -s extdebug` / `shopt -u extdebug`）。
- [x] 全局集成：创建 `packaging/profile.d/witty.sh` 入口脚本（见 P1-11B）。
- [x] `set -o vi` 模式下自然语言直输能触发 Agent（DEBUG trap 不绑定 keymap，自动兼容；已验证 `set -o vi` + `extdebug` + DEBUG trap 正常工作）。
- [x] 多条命令（`cmd1; cmd2`）和管道（`cmd1 | cmd2`）场景下 DEBUG trap 行为验证：`BASH_COMMAND` 逐条触发（非整行），但分类器中 `*";"*` / `*"|"*` 等强 shell 特征匹配在用户输入时即拦截整行，不会出现管道中某条命令被误分类为 agent 的情况。
- [x] `witty init bash` 输出脚本中 `WITTY_SHELL_ENABLE` 和 `WITTY_SHELL_DEBUG` 的默认值与 `witty.yaml` 配置联动（`app.go` 中 `a.cfg.Shell.Enabled` / `a.cfg.Shell.Debug` 传入 `BashOptions`）。
- [x] DEBUG trap 递归安全：Bash 的 DEBUG trap 在 trap handler 内部不会递归触发，`__witty_shell_dispatch` 中的 `command` 调用不会再次触发 `__witty_debug_hook`。

#### 验收 checkpoint：C2-5

- [x] PTY 测试验证 history：Agent 路由后 `history` 显示用户原始输入，不含 `__witty_shell_dispatch`。
- [x] debug 模式能解释为什么某一行走 shell/agent/control（`WITTY_SHELL_DEBUG=1` 输出路由决策）。
- [x] 禁用开关生效后 DEBUG trap 不安装，Bash 行为完全恢复默认。
- [x] `__witty_uninstall_bindings` 后 DEBUG trap 恢复为安装前的状态。
- [x] `set -o vi` 模式下自然语言直输能触发 Agent。
- [x] 多命令和管道场景不被误路由。
- [x] RPM 安装后 `/etc/profile.d/witty.sh` 对所有新会话生效。

### P2-6：Phase 2 端到端验收

#### 验收 checkpoint：C2-E2E

- [ ] `witty` 启动 REPL。
- [ ] REPL 与 `witty ask` 的 Markdown、tool、permission、error 展示一致。
- [ ] REPL 中 `/new`、`/session list`、`/help` 可用。
- [ ] Shell 快捷模式中 `/session list`、`/new` 可用。
- [ ] `go test -count=1 ./...` 通过。
- [ ] `TERM=xterm-256color go test -v -tags=pty ./test/pty/` 在 openEuler 通过。

---

## 6. Phase 3：展示、流式增强与可靠性

目标：提升交互体验和故障恢复能力。完善 presenter，增加 Renderer Phase 2 即时回显能力，补充 SSE 断线处理和诊断日志。

### P3-1：Presenter 完整展示

- [ ] Agent / SubAgent 开始、切换、完成展示。
- [ ] Tool call 参数摘要展示，避免输出敏感或超长内容。
- [ ] Tool result 成功/失败分层展示。
- [ ] Step ended 展示 cost、tokens、耗时等信息。
- [ ] Permission/question 展示与输入提示样式统一。
- [ ] Unknown event debug 展示。

#### 验收 checkpoint：C3-1

- [ ] Golden tests 覆盖 tool、step、permission、question、error、unknown。
- [ ] 长输出有截断策略且可配置或可 debug 查看。
- [ ] no-color 与非 TTY 输出稳定。

### P3-2：Renderer Phase 2 即时回显

- [ ] 可配置开关启用 Phase 2，默认是否开启由稳定性决定。
- [ ] delta 到达时先原文即时回显。
- [ ] 块完成后使用 ANSI 擦除原文行，再替换为 glamour 渲染块。
- [ ] 追踪终端宽度与 CJK 字符宽度。
- [ ] 处理 SIGWINCH 后重建 renderer 或安全降级。
- [ ] 非 TTY 自动禁用即时回显替换。

#### 验收 checkpoint：C3-2

- [ ] 行数追踪单元测试覆盖 ASCII、CJK、ANSI、emoji/宽字符边界。
- [ ] PTY 测试验证即时回显后最终渲染正确。
- [ ] Resize 场景不 panic，最差降级为 Phase 1。
- [ ] 未闭合代码块 Flush 后输出可读。

### P3-3：SSE 断线与错误策略

- [ ] 区分网络错误、HTTP 错误、schema 错误、业务 idle 超时。
- [ ] EOF before idle 返回 `ErrStreamEndedWithoutIdle`。
- [ ] Phase 3 可选重连：指数退避、最大重试次数、context cancel 可打断。
- [ ] 重连后继续按 sessionID 过滤，避免串流。
- [ ] debug 日志记录 event id / type 摘要，不记录敏感 payload。

#### 验收 checkpoint：C3-3

- [ ] fake SSE server 测试覆盖断线、重连、idle、取消。
- [ ] 重连不会重复渲染已处理 delta，或文档中明确当前幂等边界。
- [ ] ask 命令在 server 中断时给出明确错误和排查建议。

### P3-4：性能与资源控制

- [ ] Markdown buffer 有最大容量保护。
- [ ] 单个 event / data payload 有大小限制或合理防护。
- [ ] 长会话输出不导致 unbounded memory growth。
- [ ] goroutine 生命周期可追踪。
- [ ] context cancel 覆盖 transport/event/core/renderer。

#### 验收 checkpoint：C3-4

- [ ] 长文本 fake stream 测试无明显内存暴涨。
- [ ] `go test -race ./internal/...` 在可行环境通过或记录不可行原因。
- [ ] Ctrl+C 后无 goroutine 泄漏的测试或手动验证记录。

### P3-5：Phase 3 端到端验收

#### 验收 checkpoint：C3-E2E

- [ ] tool/step/agent/permission/question 展示完整。
- [ ] Renderer Phase 2 开关可用；关闭后稳定回到 Phase 1。
- [ ] 网络中断或 server 停止时错误可理解。
- [ ] `go test -count=1 ./...`、`golangci-lint run ./...` 通过。
- [ ] openEuler PTY 测试通过。

### P3-6：中间过程展示优化（思考、工具调用、Step 分组）

> 设计文档：[`./message-display-design.md`](./message-display-design.md)
>
> **基于 OpenCode 真实源码（`anomalyco/opencode` `dev` 分支）逐文件分析。**
> 关键发现：
>
> - TUI PART_MAPPING 仅渲染 3 种 Part（text/tool/reasoning）
> - StepStartPart/StepFinishPart 在 `toModelMessages` 中被显式过滤，**完全不渲染**
> - Cost/Tokens 是 **per-message**（AssistantMessage），非 per-step
> - `todowrite` 在 Web UI 中是 HIDDEN_TOOLS（TUI 中显示）
> - `question` 在 pending/running 期间隐藏
> - `CONTEXT_GROUP_TOOLS = {read, glob, grep, list}` 在 Web UI 中可折叠分组（TUI 无此功能）
> - Reasoning 使用 left-border + 完整 Markdown 渲染，**不是 box drawing**
> - Permission/Question 是独立对话框，非内联消息
>
> **Witty CLI 核心差异**：行式输出（不可折叠），必须通过 buffering + timing 模拟 Web UI 的分组能力。
>
> **实际参考文件**（`anomalyco/opencode` dev 分支，commit `7daea69e` 附近）：
>
> - `packages/opencode/src/session/message-v2.ts` — Part schema + ToolPart 4 态状态机 + toModelMessages 过滤
> - `packages/opencode/src/cli/cmd/tui/routes/session/index.tsx` — TUI PART_MAPPING（仅 3 种）、ReasoningPart、TextPart、ToolPart 渲染
> - `packages/ui/src/components/message-part.tsx` — Web UI PART_MAPPING、HIDDEN_TOOLS、CONTEXT_GROUP_TOOLS、renderable()、ContextToolGroup、ToolRegistry
> - `packages/sdk/js/src/v2/gen/types.gen.ts` — SDK Event/Part 类型定义

#### P3-6D：Step 中间零输出 + 回答完汇总 🔴 最高优先级（最小改动，最大影响）

> OpenCode TUI PART_MAPPING 中不存在 StepStart/StepFinish。它们在 `toModelMessages` 中被过滤。
> Cost/Tokens 在 `AssistantMessage` metadata 中，**是 per-message 的，不是 per-step 的**。
> StepStartPart 的 schema 仅有 `{ type: "step-start" }` 一个字段——无任何数据。

- [ ] **`EventStepStarted` / `EventStepEnded` 不产生任何终端输出**。
- [ ] `EventStepStarted` 仅内部使用：flush context buffer，初始化 reasoning renderer。
- [ ] `EventStepEnded` 仅内部使用：flush context buffer，累计 cost/tokens。
- [ ] **仅在 `EventSessionIdle` 后输出一行汇总**。
- [ ] 汇总格式：`── answered in {duration} · ${cost} · {tokens} tokens ──`。
- [ ] 汇总行使用 lipgloss Faint（暗色），线宽 = 终端宽度。
- [ ] 从 `AssistantMessage` metadata 提取 cost/tokens/duration（不是从 StepFinishPart）。
- [ ] `display.step_style` 配置：`line`（分隔线，默认）/ `minimal`（仅空行）/ `none`。
- [ ] 非 TTY 降级：`--- 3.2s  $0.0015  448 tokens ---`（纯 ASCII）。

##### 验收 checkpoint：C3-6D

- [ ] Step 中间零输出，`[step]` 文字完全消失。
- [ ] 仅 `EventSessionIdle` 后显示一行汇总统计。
- [ ] `[step] started/finished` 不再出现在任何输出中。
- [ ] Golden test 覆盖三种 step_style（line/minimal/none）。
- [ ] 现有测试全部通过（移除对 step 输出的断言）。

#### P3-6B：Reasoning left-border + Markdown 渲染 🔴 高优先级

> OpenCode TUI 使用 `border={["left"]}` + 完整 Markdown 渲染，`fg={theme.textMuted}`（暗色），
> 前缀 `"_Thinking:_ " + content()`。**不是 box drawing**。
> 3 种思考模式（来源 `context/thinking.ts`）：show（完整）、hide（折叠单行）、展开 toggle。

- [ ] 在 `internal/renderer/` 新增独立的 Reasoning 渲染通道（`reasoning.go`）。
- [ ] reasoning 通过 glamour 渲染后，每行加 `│ ` left-border 前缀输出（lipgloss Faint 颜色）。
- [ ] 首行 `_Thinking:_` 标识（lipgloss Italic + Faint）。
- [ ] 流式渲染：reasoning delta 积累到完整 Markdown 块后通过 BlockBuffer → glamour → left-border 输出。
- [ ] `display.show_reasoning` 配置：`"show"`（默认）/ `"minimal"` / `"hide"`。
- [ ] minimal 模式：仅输出单行 `▶ Thinking: {首句摘要}...  {duration}`。
- [ ] hide 模式：完全不输出 reasoning 内容。
- [ ] reasoning 走独立渲染通道，不干扰 text delta 的 glamour 渲染管线。
- [ ] 非 TTY 模式：`  | ` 前缀纯文本。

##### 验收 checkpoint：C3-6B

- [ ] reasoning 使用 `│ ` left-border + glamour Markdown 渲染，与 text delta 视觉分离。
- [ ] 暗色文字（lipgloss Faint）正确应用。
- [ ] show / minimal / hide 三种模式 golden test 通过。
- [ ] `show_reasoning = "hide"` 时完全不输出。
- [ ] reasoning 输出不干扰 text delta 渲染（独立管道验证）。

#### P3-6A：上下文工具分组（ContextToolGroup）🔴 高优先级

> OpenCode Web UI 的 `CONTEXT_GROUP_TOOLS = new Set(["read", "glob", "grep", "list"])`。
> 注意：TUI **没有**此功能（TUI 每个工具独立渲染），Witty 借鉴 Web UI 的降噪策略。
> CLI 无折叠能力，改为 **delay-buffer-then-aggregate** 策略。

- [ ] 在 `internal/presenter/` 新增 `context_group.go`（ContextGroup buffer）。
- [ ] 连续的 `read`/`grep`/`glob`/`list` 调用积累到 buffer，**不立即输出**。
- [ ] 遇到非上下文工具（bash/write/edit/task/webfetch/websearch/skill/question）时 flush buffer。
- [ ] StepEnd 时 flush buffer。
- [ ] SessionIdle 时 flush buffer。
- [ ] flush 时输出一行摘要：`🔍 context  N reads, M searches, K lists`。
- [ ] 上下文工具 running 期间不输出（它们通常很快完成）。
- [ ] `display.group_context_tools`（bool，默认 `true`）。
- [ ] `group_context_tools = false` 时降级为逐个展示（走 P3-6C 的独立工具格式化）。

##### 验收 checkpoint：C3-6A

- [ ] 连续上下文工具合并为一行摘要展示。
- [ ] 组摘要准确统计 read/search/list 数量。
- [ ] `group_context_tools = false` 时降级为逐个展示。
- [ ] Golden test 覆盖分组与降级场景。

#### P3-6C：工具调用 per-type 格式化 🟡 中优先级

> OpenCode 使用 `ToolRegistry.register()` 为每种工具注册独立渲染器。
> `todowrite` 是 HIDDEN_TOOLS；`question` 在 pending/running 期间隐藏。
> TUI 中所有工具使用 `InlineTool` 包装器（icon + 状态指示 + 文本）。

- [ ] bash：提取 `command` + `description`，格式 `$ bash {command} — {description}`。输出行用 `│ ` 前缀缩进。
- [ ] read：提取 `filePath`（仅文件名），格式 `📖 read {filename}`。归入 context group（P3-6A），关闭分组时单独展示。
- [ ] write：提取 `filePath`（仅文件名），格式 `✎ write {filename}`。
- [ ] edit：提取 `filePath` + 变更统计（如 `+3 −2`）。
- [ ] task：提取 `description` + agent 名称，格式 `⚙ task {agent} — {description}  {duration} · {N} calls`。
- [ ] skill：提取 `name`，格式 `🧠 skill {name}`。
- [ ] grep/glob/list：归入 context group（P3-6A），仅在关闭分组时单独展示。
- [ ] webfetch：提取 `url`，格式 `🌐 fetch {url}`。
- [ ] websearch：提取 `query` + provider，格式 `🔎 search "{query}"  {N} results`。
- [ ] apply_patch：提取文件数，格式 `📝 patch {N} files`。
- [ ] 工具状态图标：running `◌`，completed `✓`（绿色），error `✗`（红色）。
- [ ] 工具 running 时输出标题行（spinner），completed 时更新为 success（替换行或追加）。
- [ ] 工具输出超过 10 行自动截断，末尾 `... (N more lines)`。
- [ ] **所有工具不显示 callID**（与 OpenCode 一致）。
- [ ] **`todowrite` 永不显示**（与 OpenCode Web UI HIDDEN_TOOLS 一致）。
- [ ] **`question` 工具 pending/running 期间隐藏**（与 OpenCode `renderable()` 一致）。
- [ ] `question` completed 时显示 Q&A 对：`❓ Questions ({N})`。
- [ ] 非 TTY 降级：Unicode → ASCII（`◌` → `[..]`, `✓` → `[OK]`, `✗` → `[FAIL]`, `📖` → `[read]` 等）。

##### 验收 checkpoint：C3-6C

- [ ] bash/read/write/edit/task/skill 各有独立格式化。
- [ ] 3 态展示：running (◌)、completed (✓绿)、error (✗红) 全部正确。
- [ ] Golden test 覆盖所有工具类型的 3 种状态。
- [ ] 非 TTY 输出无 ANSI 且可读。
- [ ] callID 不在任何工具输出中出现。
- [ ] `todowrite` 输出完全不存在。
- [ ] `question` running 期间输出完全不存在。

#### P3-6E：配置项与事件过滤完善 🟢 低优先级

- [ ] 新增 `display.show_reasoning`（string: `"show"` / `"minimal"` / `"hide"`，默认 `"show"`）。
- [ ] 新增 `display.group_context_tools`（bool，默认 `true`）。
- [ ] 新增 `display.step_style`（string: `"line"` / `"minimal"` / `"none"`，默认 `"line"`）。
- [ ] `todowrite` 工具事件静默（不产生 AppEvent，在 event router 层过滤）。
- [ ] `question` 工具 pending/running 事件静默。
- [ ] 非 TTY 自动降级（去除 ANSI + Unicode 图标，纯 ASCII 替换）。

##### 验收 checkpoint：C3-6E

- [ ] 三项配置可正常读取并影响渲染行为。
- [ ] `todowrite` 完全不产生输出。
- [ ] `question` pending/running 期间完全不产生输出。
- [ ] 非 TTY 输出可读（管道到文件验证）。

#### P3-6F：端到端验收

##### 验收 checkpoint：C3-6-E2E

- [ ] 思考过程、工具调用、最终回答三者视觉清晰分离。
- [ ] 上下文工具合并为一组，视觉噪音大幅降低。
- [ ] `witty ask` 在 openEuler PTY 下交互流畅。
- [ ] `go test -count=1 ./...`、`golangci-lint run ./...` 通过。
- [ ] openEuler PTY 测试通过。
- [ ] Golden test 覆盖完整事件流（reasoning → context tools → bash → task → text → idle summary）。

---

## 7. Phase 4：产品化、Doctor 与发布

目标：提供可诊断、可安装、可发布的 openEuler 产物。完成 `witty doctor`、配置/日志完善、RPM 打包和发布前验证。

### P4-1：Doctor 诊断命令

- [ ] 检查 config 加载路径与有效值摘要。
- [ ] 检查 opencode server URL 可达。
- [ ] 检查 `/doc` 与 `/event` 基础可用性。
- [ ] 检查 shell integration 是否已加载。
- [ ] 检查 Bash 版本、readline 能力、TERM。
- [ ] 检查 terminal TTY、宽度、color/no-color。
- [ ] 输出分级：OK / WARN / FAIL / SKIP。

#### 验收 checkpoint：C4-1

- [ ] `witty doctor` 在 server 未启动时能定位到连接失败。
- [ ] `witty doctor` 在非交互环境不误报 Bash Hook 必须存在。
- [ ] doctor 输出不泄露 token、完整 header 或本机敏感路径。

### P4-2：配置与日志完善

- [ ] 首次运行可创建用户默认配置，或明确提示如何创建。
- [ ] debug 日志目标明确：TTY stderr 或日志文件。
- [ ] 日志内容结构化，包含模块、操作、错误上下文。
- [ ] 非 TTY 默认不输出日志到 stdout。
- [ ] 支持配置主题、server、agent、model、renderer phase、shell enabled。

#### 验收 checkpoint：C4-2

- [ ] 配置 migration 或兼容策略明确。
- [ ] debug/off 两种模式测试通过。
- [ ] 日志脱敏测试覆盖常见敏感字段。

### P4-3：Shell 安装与卸载说明

- [ ] 文档说明临时启用：`eval "$(witty init bash)"`。
- [ ] 文档说明持久启用：写入 `~/.bashrc` 的推荐片段。
- [ ] 文档说明禁用方法。
- [ ] 文档说明 debug route 方法。
- [ ] 提供常见冲突排查：已有 Enter binding、TERM、非 Bash shell。

#### 验收 checkpoint：C4-3

- [ ] 新 openEuler 用户按文档可完成安装。
- [ ] 禁用后 Bash 行为恢复。
- [ ] 文档明确首版仅支持 Bash，不支持 zsh/fish。

### P4-4：GoReleaser 与 RPM 打包

- [ ] `.goreleaser.yaml` 配置 linux amd64/arm64。
- [ ] 设置 `goamd64=v1`。
- [ ] 设置 `CGO_ENABLED=0`。
- [ ] 注入 version / commit / date。
- [ ] nFPM 生成 RPM。
- [ ] 安装路径：`/usr/bin/witty`。
- [ ] 配置路径：`/etc/witty/config.toml` 使用 `config|noreplace`。
- [ ] Bash completion 安装到 openEuler 兼容路径。

#### 验收 checkpoint：C4-4

- [ ] `goreleaser release --snapshot --clean --skip=publish` 成功。
- [ ] RPM 可在 openEuler 安装、升级、卸载。
- [ ] `rpm -ql witty` 文件列表合理。
- [ ] 卸载不删除用户个人配置 `~/.config/witty/config.toml`。

### P4-5：发布前回归

- [ ] Unit tests。
- [ ] Golden tests。
- [ ] PTY tests。
- [ ] Doctor smoke tests。
- [ ] RPM install smoke tests。
- [ ] `witty ask` live smoke test。
- [ ] Shell direct input smoke test。
- [ ] REPL smoke test。

#### 验收 checkpoint：C4-E2E

- [ ] openEuler amd64 通过完整回归。
- [ ] openEuler arm64 通过构建或有明确验证计划。
- [ ] 产物包含二进制、RPM、completion、默认配置、安装说明。
- [ ] Release notes 包含 breaking changes、已知问题、验证环境。

---

## 8. 跨模块验收矩阵

| 能力 | 相关模块 | 最低验收 |
| --- | --- | --- |
| CLI 启动 | `cmd/witty`, `internal/cli`, `internal/app` | `witty --help` / `witty version` 正常 |
| 配置加载 | `internal/config` | 默认值、文件、环境变量、CLI override 优先级测试 |
| 单轮问答 | `internal/core`, `internal/transport`, `internal/event`, `internal/session` | `witty ask "..."` 等待 `session.idle` 后退出 |
| SSE 流式 | `internal/transport`, `internal/event` | 手写 parser；EOF 不等于业务完成 |
| Markdown 输出 | `internal/renderer` | Phase 1 块边界渲染，Flush 输出残留内容 |
| 工具展示 | `internal/presenter` | tool started/succeeded/failed golden tests |
| 权限与问题 | `internal/permission`, `internal/terminal` | TTY 可交互回复；非 TTY 安全失败 |
| Shell 直输 | `internal/shellinit`, `internal/shellbridge` | 自然语言走 Agent；shell 命令保持原样 |
| REPL | `internal/repl` | 与 `witty ask` 共用核心输出管线 |
| 诊断 | `internal/doctor` | server/config/shell/terminal 检查可定位常见问题 |
| 发布 | `.goreleaser.yaml`, `packaging/` | openEuler RPM 可安装运行 |

---

## 9. 关键风险与专项 checkpoint

### 9.1 SSE schema 漂移

- [ ] 所有 RawEvent fixture 从真实 `/event` 样本沉淀。
- [ ] Unknown event 不 panic。
- [ ] OpenAPI 更新后执行 event/transport 回归。
- [ ] `session.idle` 仍是唯一可靠结束信号。

### 9.2 Bash Hook 破坏用户体验

- [ ] Shell 路由时不改写 `READLINE_LINE`。
- [ ] Agent/control 路由只改写为 dispatch，仍交给 `accept-line` 执行。
- [ ] **禁止**在 `bind -x` handler 中直接调用 `witty ask`（行改写方案）。
- [ ] 长时间 AI 调用不在 Bash Hook 内执行。
- [ ] 提供禁用开关与 doctor 检查。
- [ ] 同时绑定 `\C-m` 和 `\C-j`（PTY 环境发送 LF 而非 CR）。
- [ ] `vi-insert` keymap 绑定验证。
- [ ] `HISTIGNORE` 隐藏 wrapper 命令。
- [ ] `command_not_found_handle` 兜底验证。

### 9.3 Renderer 输出错乱

- [ ] Phase 1 默认稳定可用。
- [ ] Phase 2 有开关，出现不稳定可回退。
- [ ] 非 TTY 禁用 ANSI 替换。
- [ ] CJK 宽度测试覆盖。

### 9.4 安全与隐私

- [ ] 不提交 `.agents/config.yaml`。
- [ ] 不在日志中输出 token/header/session secret。
- [ ] 不把 permission/question 的敏感输入写入 debug 日志。
- [ ] 外部输入长度有边界，避免无界内存增长。

---

## 10. 推荐开发顺序

1. `P0-1` → `P0-2` → `P0-3`：先让 CLI 可编译、可帮助、可版本化。
2. `P0-4` → `P0-5` → `P0-7`：补配置、终端能力与 app wiring。
3. `P0-6`：固化 OpenAPI spec 与生成 models。
4. `P1-1` → `P1-2` → `P1-3`：先打通 transport/event。
5. `P1-4` → `P1-8` → `P1-9`：完成 `witty ask` 主链路。
6. `P1-5` → `P1-6` → `P1-7`：让输出、工具、权限体验可用。
7. `P1-10` → `P1-11`：接入 Shell 直输。
8. `P1-12`：MVP E2E 验收。
9. `P2-*`：补 REPL 与控制命令一致性。
10. `P3-*`：增强展示、流式体验与可靠性。
11. `P4-*`：Doctor、打包、发布验证。

---

## 11. 验收记录模板

每个阶段合并前，在 PR 或开发记录中填写：

```text
Phase: P1 Core MVP
Commit/Branch: <branch-or-commit>
Environment: macOS local / openEuler OrbStack / WSL / SSH
opencode version: <version>
witty version: <version>

Commands:
- go fmt ./...
- go test -count=1 ./...
- go build -ldflags="-s -w" ./cmd/witty
- shellcheck internal/shellinit/templates/*.bash.tmpl
- TERM=xterm-256color go test -v -tags=pty ./test/pty/

Manual checks:
- witty ask "检查系统内存": PASS/FAIL
- eval "$(witty init bash)" then "检查系统内存": PASS/FAIL
- systemctl status nginx remains shell: PASS/FAIL
- permission/question interaction: PASS/FAIL/SKIP

Known issues:
- <issue id or description>
```
