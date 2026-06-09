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

- [ ] 定义 `TextRenderer` 接口：`WriteDelta(ctx, delta)`、`Flush(ctx)`。
- [ ] 实现 `BlockBuffer`，积累 delta 到完整 Markdown 块。
- [ ] 识别段落、空行、ATX heading、列表、引用、围栏代码块、thematic break。
- [ ] 使用 glamour v2 批量渲染完整块。
- [ ] Flush 时渲染剩余未闭合内容。
- [ ] 渲染错误降级为原文输出，不中断 ask 主流程。

#### 验收 checkpoint：C1-5

- [ ] 块边界单元测试覆盖段落、标题、列表、引用、代码围栏、未闭合代码块。
- [ ] Golden test 覆盖典型 Markdown ANSI 输出。
- [ ] `witty ask` 输出不是等完整回答结束后一次性打印，而是按完整块持续刷新。
- [ ] 非 TTY 输出避免写 ANSI 控制码。

### P1-6：Presenter 基础展示

- [ ] 定义 tool/step/error/permission/question 的基础展示接口。
- [ ] 工具调用开始、成功、失败有统一样式。
- [ ] 错误展示区分用户错误、网络错误、server 错误、schema 错误。
- [ ] 样式依赖 lipgloss v2，遵守 no-color。

#### 验收 checkpoint：C1-6

- [ ] presenter 单元测试或 golden test 覆盖主要输出。
- [ ] 快捷模式与 REPL 复用同一 presenter。
- [ ] 非 TTY 输出可读且无多余 ANSI。

### P1-7：Permission / Question Manager

- [ ] 接管 permission asked 事件。
- [ ] 接管 question asked 事件。
- [ ] TTY 中阻塞式提问，提交 reply API。
- [ ] 非 TTY 场景给出明确错误或安全默认拒绝策略。
- [ ] 支持 multiple choice / custom answer 的数据结构。

#### 验收 checkpoint：C1-7

- [ ] fake transport 测试覆盖 approve/reject、question answer、question reject。
- [ ] permission/question 出现时暂停正文渲染或保证输出不交错。
- [ ] Ctrl+C 能取消当前交互并释放 goroutine。

### P1-8：AskRunner 核心执行管线

- [ ] 定义 `AskRequest`：prompt、cwd、session、force new、agent、model、mode。
- [ ] 执行步骤：解析 session → 发送 prompt → 订阅/过滤事件 → 分发 renderer/presenter/permission → 等待 `session.idle` → flush。
- [ ] 统一处理 context cancel、SIGINT、server error、stream EOF without idle。
- [ ] 不在 core 中实现 CLI 参数解析或 Bash 分类逻辑。

#### 验收 checkpoint：C1-8

- [ ] AskRunner fake event stream 测试覆盖正常完成、EOF without idle、permission、question、tool failed、cancel。
- [ ] 收到 `session.idle` 后一定调用 renderer `Flush()`。
- [ ] ask 命令退出码符合结果：成功 0，用户取消/网络错误/服务端错误非 0。

### P1-9：`witty ask` 命令闭环

- [ ] 支持 `witty ask "prompt"`。
- [ ] 支持 stdin prompt：`echo "..." | witty ask`。
- [ ] 支持 cwd 传递。
- [ ] 支持 `--new`、`--session`、`--agent`、`--model`。
- [ ] 用户可读错误输出到 stderr。

#### 验收 checkpoint：C1-9

- [ ] `witty ask --help` 完整。
- [ ] `witty ask "检查系统内存"` 在 opencode server 可用时能流式输出。
- [ ] opencode server 不可用时错误包含 server URL 与排查建议，不 panic。
- [ ] stdout 只包含用户期望内容；debug/log 不污染 stdout。

### P1-9B：Provider 管理 `witty provider` [增补阶段]

增补背景：`opencode serve` 与 opencode TUI 进程独立，TUI 中 connect 的 provider 不会自动对 server 生效。
需要通过 `witty provider` 命令让用户在终端内完成 provider 连接，避免打开 TUI 或手动构造 curl 请求。

- [ ] `witty provider list` 列出支持 API Key 认证的 provider，标注 connected 状态。
- [ ] `witty provider list --connected` 仅列出已连接且支持 API Key 认证的 provider。
- [ ] `witty provider connect <provider> --key <api-key>` 通过 API Key 连接 provider（调用 `PUT /auth/{providerID}`），支持 provider id / name 解析。
- [ ] `connect` 前先查询 `/provider` 解析输入，再查询 `/provider/auth` 过滤出支持 `type=api` 的 provider。
- [ ] `--key` 未提供时提示从 stdin 或环境变量读取。
- [ ] `connect` 成功后重新查询 provider 列表确认 connected 状态已更新。
- [ ] provider 不存在时给出友好错误提示（不是裸 HTTP 状态码）。
- [ ] provider 存在但 `/provider/auth` 不支持 `type=api` 时，返回明确错误：`当前 Provider 暂不支持 API Key 认证方式`。
- [ ] 连接失败（如 key 无效）时错误信息包含排查建议。

#### 验收 checkpoint：C1-9B

- [ ] `witty provider list` 输出仅包含支持 API Key 认证的 provider 条目，connected 状态正确。
- [ ] `witty provider list --connected` 仅显示 connected 且支持 API Key 认证的 provider（初始可能为空或仅有 opencode）。
- [ ] `witty provider connect deepseek --key <valid-key>` 成功，再次 `list --connected` 可见 deepseek。
- [ ] `witty provider connect nonexistent --key sk-xxx` 返回可读错误，exit code 非 0。
- [ ] `witty provider connect <provider-without-api-auth> --key sk-xxx` 返回明确错误：`当前 Provider 暂不支持 API Key 认证方式`。
- [ ] `witty provider connect deepseek`（无 `--key`）给出明确的使用说明，不 panic。
- [ ] `go test -count=1 ./internal/cli/ ./internal/transport/ ./internal/app/` 通过。
- [ ] VM 环境验证：使用 `witty provider connect` 连接 deepseek 后，`witty ask --model deepseek/deepseek-v4-falsh --variant reasoning-high --new "hello"` 能正常完成。

### P1-10：Shell Init 模板 `internal/shellinit`

- [ ] `witty init bash` 输出 Bash 集成脚本。
- [ ] 使用 `embed.FS` 管理模板。
- [ ] Go template 分隔符设置为 `[[ ]]`。
- [ ] Bash 函数统一 `__witty_` 前缀。
- [ ] 脚本支持幂等加载。
- [ ] 提供环境变量开关禁用 adapter。

#### 验收 checkpoint：C1-10

- [ ] `witty init bash` 输出中不包含 `{{` / `}}` 模板分隔符。
- [ ] `shellcheck internal/shellinit/templates/*.bash.tmpl` 通过。
- [ ] `go test -v -run TestBashTemplate ./internal/shellinit/` 通过。
- [ ] 重复 `eval "$(witty init bash)"` 不重复绑定或污染环境。

### P1-11：Shell Bridge 分类与 dispatch

- [ ] Bash 侧实现 Readline Hook + `accept-line` 包装 + `READLINE_LINE` 改写。
- [ ] 分类路径：empty / shell / agent / control。
- [ ] 强 shell 特征优先：管道、重定向、变量赋值、显式路径、shell 关键字、多行续行等。
- [ ] 白名单 slash 命令：`/ask`、`/agent`、`/model`、`/session list`、`/session continue`、`/new`、`/help`。
- [ ] `/usr/bin/ls` 等绝对路径不得误判为 slash 控制命令。
- [ ] dispatch 只调用 `witty ask` 或控制命令；Bash Hook 中不得执行长时间 AI 调用。
- [ ] history 保留用户原始输入，隐藏内部 wrapper 命令。

#### 验收 checkpoint：C1-11

- [ ] 分类器单元测试覆盖 `检查系统内存` → agent。
- [ ] 分类器单元测试覆盖 `systemctl status nginx` → shell。
- [ ] 分类器单元测试覆盖 `systemctl 怎么看 nginx 日志` → agent。
- [ ] 分类器单元测试覆盖 `cat /etc/os-release | grep NAME` → shell。
- [ ] PTY 测试验证自然语言直输能触发 `witty ask`。
- [ ] PTY 测试验证普通 shell 命令不被改写。
- [ ] PTY 测试验证 history 中不出现 `__witty_shell_dispatch ...`。

### P1-12：MVP 端到端验收

#### 验收 checkpoint：C1-E2E

- [ ] 本地或 openEuler 环境启动 opencode server。
- [ ] `witty doctor` 或临时 health check 能确认 server 可达。
- [ ] `witty ask "检查系统内存"` 能完成一轮问答。
- [ ] 输出按 Markdown 块边界持续刷新。
- [ ] 出现 tool call 时有基础展示。
- [ ] 出现 permission/question 时可交互回复。
- [ ] `session.idle` 到达后进程退出，退出码为 0。
- [ ] `eval "$(witty init bash)"` 后：
  - [ ] `检查系统内存` → Agent。
  - [ ] `systemctl status nginx` → Shell。
  - [ ] `/ask systemctl 怎么看 nginx 日志` → Agent。
  - [ ] `/usr/bin/ls` → Shell。

---

## 5. Phase 2：REPL 与控制命令

目标：`witty` 无参数启动完整 REPL；REPL 与 Shell 快捷模式共享 AskRunner、Presenter、Renderer、Permission、Session 管线；控制命令在两种入口表现一致。

### P2-1：REPL 基础循环

- [ ] `witty` 无参数进入 REPL。
- [ ] prompt 显示当前 session / agent / model 的简要状态。
- [ ] 普通文本输入调用 AskRunner。
- [ ] Ctrl+C 取消当前请求但不一定退出 REPL。
- [ ] Ctrl+D / `/exit` 退出 REPL。

#### 验收 checkpoint：C2-1

- [ ] REPL 中输入 `检查系统内存` 能得到与 `witty ask` 一致的输出。
- [ ] 当前请求 Ctrl+C 后 goroutine 退出，无卡死。
- [ ] Ctrl+D 返回 0 或约定退出码。

### P2-2：Slash 命令解释器

- [ ] `/help`。
- [ ] `/new`。
- [ ] `/session list`。
- [ ] `/session continue <id>`。
- [ ] `/agent <name>`。
- [ ] `/model <id>`。
- [ ] `/ask <prompt>`。
- [ ] `/exit`。
- [ ] 未知 slash 命令给出建议。

#### 验收 checkpoint：C2-2

- [ ] REPL slash 命令 table-driven tests 覆盖。
- [ ] Shell Adapter control 命令与 REPL 使用同一解析/执行逻辑或共享同一语义测试。
- [ ] `/usr/bin/ls` 在 Shell 模式仍不被当成 slash 命令。

### P2-3：Session 控制与 auto resume

- [ ] `repl.auto_resume` 生效。
- [ ] `/new` 创建新 session 并设为当前。
- [ ] `/session continue <id>` 切换当前 session。
- [ ] session 列表输出包含 id、title/summary、更新时间。

#### 验收 checkpoint：C2-3

- [ ] REPL 重启后按配置恢复或不恢复 session。
- [ ] session id 无效时不改变当前 session。
- [ ] session 列表非 TTY 输出可被脚本消费。

### P2-4：Shell control 路径

- [ ] Shell 直输 `/new` 转到 witty 控制命令。
- [ ] Shell 直输 `/session list` 展示列表。
- [ ] Shell 直输 `/session continue <id>` 切换后续默认 session。
- [ ] Shell 直输 `/agent`、`/model` 更新默认值或当前 shell 会话状态。

#### 验收 checkpoint：C2-4

- [ ] PTY 测试覆盖 `/new`、`/session list`、`/session continue`。
- [ ] 控制命令的退出码可被 Bash 正确感知。
- [ ] 控制命令不会触发 AI 请求。

### P2-5：History、debug 与可关闭性

- [ ] Shell Adapter debug 模式可输出路由决策到 stderr 或日志。
- [ ] 提供环境变量禁用 Shell Adapter。
- [ ] history 保真：用户看到和检索的是原始输入。
- [ ] 内部 dispatch 命令不进入历史或可被清理。

#### 验收 checkpoint：C2-5

- [ ] PTY 测试验证 history。
- [ ] debug 模式能解释为什么某一行走 shell/agent/control。
- [ ] 禁用开关生效后 Enter 行为恢复 Bash 默认。

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
- [ ] 长时间 AI 调用不在 Bash Hook 内执行。
- [ ] 提供禁用开关与 doctor 检查。

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
