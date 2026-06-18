# 消息展示设计：思考、工具调用与中间过程

> 基于 OpenCode 真实源码（`anomalyco/opencode` `dev` 分支）的逐文件分析。
>
> 关联文档：
>
> - [`./development-todo.md`](./development-todo.md) — 开发计划
> - [`./streaming-renderer.md`](./streaming-renderer.md) — 流式 Markdown 渲染器

---

## 1. OpenCode 真实源码分析

> 以下所有内容取自 OpenCode `dev` 分支的真实代码（commit `7daea69e` 附近），
> 关键文件：
>
> - `packages/opencode/src/session/message-v2.ts` — Part 类型定义、消息序列化
> - `packages/opencode/src/cli/cmd/tui/routes/session/index.tsx` — TUI 渲染（~2000 行）
> - `packages/ui/src/components/message-part.tsx` — Web UI 渲染（~2000 行）
> - `packages/sdk/js/src/v2/gen/types.gen.ts` — SDK 类型（事件、Part、Session）

### 1.1 Part 类型体系

OpenCode 后端定义 **13 种 Part 类型**：

```typescript
// 来源: message-v2.ts Part schema
type Part =
  | TextPart          // 最终回答文本
  | ReasoningPart     // 模型思考过程（带 time.start/end）
  | ToolPart          // 工具调用（4 态状态机）
  | StepStartPart     // 步骤开始（内部，不渲染）
  | StepFinishPart    // 步骤结束（内部，不渲染）
  | FilePart          // 用户消息中的文件附件
  | AgentPart         // 用户消息中的 Agent chip
  | SubtaskPart       // 子任务链接
  | CompactionPart    // 上下文压缩分隔
  | RetryPart         // 重试信息
  | SnapshotPart      // 快照
  | PatchPart         // 补丁
```

**TUI PART_MAPPING（决定哪些 Part 被渲染）**：

```typescript
// 来源: session/index.tsx - 仅 3 种 Part 被渲染！
const PART_MAPPING = {
  text: TextPart,         // 最终回答
  tool: ToolPart,         // 工具调用
  reasoning: ReasoningPart, // 思考过程
}
```

**StepStart / StepFinish 不存在于 PART_MAPPING 中**——它们被 `toModelMessages` 显式过滤：

```typescript
result.filter((msg) => msg.parts.some((part) => part.type !== "step-start"))
```

### 1.2 ToolPart 4 态状态机

```typescript
// 来源: message-v2.ts
// status: "pending" | "running" | "completed" | "error"
//
// pending -> running -> completed
//                    -> error
```

每个 ToolPart 携带：

- `callID` — 内部标识（不展示给用户）
- `tool` — 工具名（bash、read、write、edit、task、grep、glob、list、webfetch、websearch、skill、question、todowrite、apply_patch 等）
- `state.input` — 工具参数
- `state.output`（completed 时）— 工具输出
- `state.error`（error 时）— 错误消息
- `state.title` — 执行期间的标题（如当前操作描述）
- `state.metadata` — 工具特定元数据

### 1.3 关键隐藏规则

```typescript
// 来源: message-part.tsx

// 1. 永不显示的工具
const HIDDEN_TOOLS = new Set(["todowrite"])

// 2. question 工具在 pending/running 期间隐藏
function renderable(part, showReasoningSummaries = true) {
  if (part.type === "tool") {
    if (HIDDEN_TOOLS.has(part.tool)) return false
    if (part.tool === "question")
      return part.state.status !== "pending" && part.state.status !== "running"
    return true
  }
  if (part.type === "text") return !!part.text?.trim()
  if (part.type === "reasoning") return showReasoningSummaries && !!part.text?.trim()
  return !!PART_MAPPING[part.type]
}

// 3. 上下文工具分组
const CONTEXT_GROUP_TOOLS = new Set(["read", "glob", "grep", "list"])
```

### 1.4 Reasoning 渲染（TUI 核心）

```tsx
// 来源: session/index.tsx ReasoningPart 组件
function ReasoningPart(props) {
  // 过滤 OpenRouter [REDACTED] 占位符
  const content = () => props.part.text.replace("[REDACTED]", "").trim()

  return (
    <Show when={content() && ctx.showThinking()}>
      <box
        paddingLeft={2}
        marginTop={1}
        border={["left"]}                    // ← 仅左边框，无 box drawing
        borderColor={theme.backgroundElement} // ← 暗色边框
      >
        <code
          filetype="markdown"                // ← 完整 Markdown 渲染
          streaming={true}
          content={"_Thinking:_ " + content()} // ← 前缀标识
          fg={theme.textMuted}              // ← 暗色文字
        />
      </box>
    </Show>
  )
}
```

**关键设计决策**：

1. **仅左边框（`border={["left"]}`）** — 不是 4 边 box。大段 Markdown 中顶/底部横线会与 `#` 标题、`---` 分隔线、代码块边框产生视觉冲突。
2. **完整 Markdown 渲染** — reasoning 可包含代码块、列表、标题、加粗等复杂格式。
3. **暗色文字** — 与主文本视觉分离。
4. **`_Thinking:_` 前缀** — 斜体标识（`_` 在 Markdown 中渲染为斜体）。
5. **3 种思考模式** — `show`（完整）、`hide`（折叠单行）、以及可选的 toggle 展开。

**思考模式实现**（来源 `context/thinking`）：

```typescript
// show: 完整 left-border markdown（上图）
// hide: 单行折叠，显示 "▶ Thinking: {summary}...  {duration}"
//       点击可展开为完整渲染
const [expanded, setExpanded] = createSignal(false)
```

### 1.5 TextPart 渲染（TUI 核心）

```tsx
// 来源: session/index.tsx TextPart 组件
function TextPart(props) {
  return (
    <Show when={props.part.text.trim()}>
      <box paddingLeft={3} marginTop={1} flexShrink={0}>
        <code
          filetype="markdown"
          streaming={true}
          content={props.part.text.trim()}
          conceal={ctx.conceal()}
          fg={theme.text}
        />
      </box>
    </Show>
  )
}
```

- `paddingLeft={3}` — 比 reasoning 多 1 级缩进
- 完整 Markdown 渲染
- 空文本不渲染

### 1.6 工具调用 TUI 渲染详情

TUI 为每种工具实现独立渲染函数（共 14 种）：

| 工具 | 渲染方式 | 内容 |
| ---- | ------- | ---- |
| **bash** | `BlockTool` expandable（10 行截断） | `$ {command}\n\n{output}` |
| **read** | `InlineToolRow` | `Read {filePath}` + loaded files |
| **write** | `BlockTool` | 代码块 + 行号 |
| **edit** | `BlockTool` diff 视图（split/unified） | before/after diff |
| **glob** | `InlineToolRow` | `Glob "{pattern}" in {path} ({N} matches)` |
| **grep** | `InlineToolRow` | `Grep "{pattern}" in {path} ({N} matches)` |
| **task** | `InlineToolRow` clickable | `{Agent} Task — {description}` + 子 session 链接 |
| **list** | 未找到独立渲染（可能走 GenericTool） | 经 Web UI 分组 |
| **webfetch** | `InlineToolRow` | `WebFetch {url}` |
| **websearch** | `InlineToolRow` | `{Provider} "{query}" ({N} results)` |
| **skill** | `InlineToolRow` | `Skill "{name}"` |
| **question** | `BlockTool` | 问题列表 + 答案 |
| **todowrite** | `InlineToolRow` | Todo 列表（TUI 中**显示**，Web UI 中**隐藏**） |
| **apply_patch** | `BlockTool` | 补丁文件列表 + diff |

**InlineTool 包装器**（TUI 的核心工具展示模式）：

```tsx
// 每个工具调用包裹在 InlineTool 中，包含：
// - icon（单字符图标）
// - 状态指示（pending spinner、completed ✓、error ✗）
// - 文本内容
// - 鼠标 hover 交互
```

### 1.7 Step / Cost / Tokens 的真实位置

**Cost 和 Tokens 是 per-message 的，不是 per-step 的。**

```typescript
// 来源: message-v2.ts AssistantMessage schema
export const Assistant = Base.extend({
  // ...
  cost: z.number(),               // 总费用（美元）
  tokens: z.object({
    total: z.number().optional(),
    input: z.number(),            // 输入 token 数
    output: z.number(),           // 输出 token 数
    reasoning: z.number(),        // 思考 token 数
  }),
  time: z.object({
    created: z.number(),          // 消息创建时间戳
    completed: z.number().optional(), // 消息完成时间戳
  }),
})

// TUI 中在 TextPart 之后显示 footer：
// ▣ {mode} · {model} · {duration} · {cost} · {tokens} · interrupted
```

**StepStartPart / StepFinishPart 的定义**（来源 `message.ts v1 schema`）：

```typescript
export const StepStartPart = Schema.Struct({
  type: Schema.Literal("step-start"),
})
// 仅 type 字段，无任何数据！
```

### 1.8 权限和问题的处理

```typescript
// 来源: session/index.tsx - 权限和问题是独立对话框
// 不在消息流中内联渲染！

const permissions = createMemo(() =>
  children().flatMap((x) => sync.data.permission[x.id] ?? [])
)
const questions = createMemo(() =>
  children().flatMap((x) => sync.data.question[x.id] ?? [])
)
const visible = createMemo(() =>
  !session()?.parentID && permissions().length === 0 && questions().length === 0
)

// 权限渲染: PermissionPrompt 组件（独立于消息流）
// 问题渲染: QuestionPrompt 组件（独立于消息流）
```

### 1.9 上下文工具分组（Web UI 独有）

```typescript
// 来源: message-part.tsx ContextToolGroup 组件
// TUI 无此功能（TUI 每个工具独立渲染）

function groupParts(parts) {
  // 连续的 read/glob/grep/list → 合并为一个 context 组
  // 遇到非上下文工具时 → flush 组
  // 组内每个工具显示为可折叠条目
}

function contextToolSummary(parts) {
  return {
    read: parts.filter(p => p.tool === "read").length,
    search: parts.filter(p => p.tool === "glob" || p.tool === "grep").length,
    list: parts.filter(p => p.tool === "list").length,
  }
}
```

### 1.10 Agent / Model 信息

```typescript
// Agent 和 Model 是用户消息的元数据，不是独立的 Part
// 显示在用户消息的 header 中：
// {Agent} · {Model} · {Timestamp}

const metaHead = createMemo(() => {
  const agent = props.message.agent
  const items = [agent ? agent[0]?.toUpperCase() + agent.slice(1) : "", model()]
  return items.filter(x => !!x).join(" · ")
})
```

### 1.11 `session.idle` 事件

```typescript
// 来源: types.gen.ts
type EventSessionIdle = {
  type: "session.idle"
  properties: {
    sessionID: string
  }
}
```

**`session.idle` 是检测流结束的唯一可靠信号。** OpenCode 自身也依赖它来确定回答完成。

---

## 2. Witty CLI 与 OpenCode 的差异分析

### 2.1 核心约束：Witty 是行式 CLI，不能做全屏 TUI

| 能力 | OpenCode Web | OpenCode TUI | Witty CLI |
| ---- | ----------- | ----------- | --------- |
| 可折叠面板 | Collapsible 组件 | 可展开 BlockTool | **不可折叠，行式输出** |
| 动画效果 | TextShimmer CSS | @opentui 动画 | **仅 spinner** |
| 空间布局 | 多列弹性 | 组件树布局 | **单列缩进** |
| 交互 | 鼠标点击 | 键盘全交互 | **键盘箭头键选择器** |
| Markdown | 完整渲染 | 完整渲染 | **glamour 渲染** |
| left-border | N/A | opentui box 原生 | **lipgloss 模拟** |
| 滚动 | overflow-y | ScrollBox | **终端原生滚动** |
| 事后翻阅 | 始终可用 | 始终可用 | **终端 buffer 回滚** |

### 2.2 Witty 的设计武器（线式输出的优势）

1. **缩进**：2-4 空格表示子内容，创造视觉层次
2. **颜色**：lipgloss 样式区分信息类型（不是 ANSI 裸 escape）
3. **前缀**：每条消息有统一的前缀标识（icon 或字符）
4. **状态图标**：◌ (running)、✓ (success, green)、✗ (error, red)
5. **截断**：长输出自动截断，保护终端空间
6. **时机控制**：可 buffer 和延迟输出，合并相邻同类消息

### 2.3 什么必须和 OpenCode 一致、什么必须不同

| 行为 | 与 OpenCode 一致？ | 说明 |
| ---- | ----------------- | ---- |
| StepStart/Finish 不输出 | ✅ 必须一致 | Step 是内部概念，不应对用户可见 |
| Cost/Tokens 在消息结束时显示 | ✅ 必须一致 | per-message，非 per-step |
| Reasoning left-border | ✅ 可参考 | OpenCode 用 box border，Witty 用 `│ ` 前缀 |
| 工具不显示 callID | ✅ 必须一致 | callID 是实现细节 |
| todowrite/todoread 隐藏 | ✅ 必须一致 | OpenCode HIDDEN_TOOLS |
| question pending/running 隐藏 | ✅ 必须一致 | 仅 completed/error 时显示 |
| 上下文工具分组 | ✅ 可参考 | OpenCode Web UI 有此功能，TUI 无 |
| 可折叠工具输出 | ❌ 不可行 | CLI 无折叠能力，改为截断 |
| InlineTool 模式 | ✅ 可参考 | 单行展示 running → 完成后追加输出 |
| 用户消息 header | ✅ 可参考 | agent · model · timestamp |

### 2.4 上下文工具分组：CLI 如何做到"折叠"

OpenCode Web UI 的 ContextToolGroup 是可折叠的——用户可展开查看每个工具详情。CLI 做不到。

**Witty 的替代方案：延迟合并输出**

1. 遇到连续的上下文工具调用时，**暂不输出**
2. 累积所有调用，保持一个 pending buffer
3. 遇到非上下文工具或 Step 结束或 SessionIdle 时，flush buffer
4. Flush 时输出**一行摘要**：

   ```text
   🔍 context  3 reads, 2 searches, 1 list
   ```

5. 如果用户需要详情，`group_context_tools = false` 时降级为逐个展示

**注意**：上下文工具在 running 时不需要 spinner。它们通常执行很快（< 1 秒），等 completed 后再一起输出即可。

---

## 3. Witty CLI 完整展示设计方案

### 3.1 设计原则

1. **降噪优先** — 合并上下文工具，隐藏 callID，去除实现细节
2. **层次可视** — Reasoning（暗色 left-border）→ 工具调用（图标 + 标题）→ 文本回答（正常色）
3. **状态可见** — running（◌）、成功（✓ 绿）、失败（✗ 红）
4. **Step 零输出** — StepStart/StepFinish 不产生任何终端输出
5. **时序自然** — 工具在发生时展示，不在事后重组
6. **非 TTY 降级** — 去除 ANSI 和 Unicode 图标，纯 ASCII 替代

### 3.2 禁止显示的内容

| 内容 | 原因 |
| ---- | ---- |
| `callID` | OpenCode 不显示，内部实现细节 |
| `todowrite` / `todoread` 工具调用 | OpenCode HIDDEN_TOOLS |
| `question` pending/running 状态 | OpenCode `renderable()` 过滤 |
| 完整 JSON input | 提取 command、filePath、description |
| StepStart/StepFinish 输出 | OpenCode TUI 完全不渲染 |
| Per-step cost/tokens | OpenCode cost 是 per-message |
| 原始 SSE 事件 ID | 内部实现细节 |

### 3.3 整体输出结构

一次完整的 `witty ask` 输出如下：

```text
$ witty ask "explain the project structure"

─────────────────────────────────────────────────────────────
_Thinking:_                                                  ← reasoning（left-border + 暗色 markdown）
│ Let me explore the project structure to understand         ← 每行 "│ " 前缀
│ how it's organized.
│
│ I'll start by reading the key files...
│ ```go
│ package main
│ func main() { ... }
│ ```
─────────────────────────────────────────────────────────────

🔍 context  3 reads, 1 search                               ← 上下文工具组（合并）
◌ $ bash  ls -la src/                                       ← 工具调用 running（spinner）
✓ $ bash  ls -la src/ — 列出源码目录                          ← 工具调用 succeeded
│ total 24                                                    ← 工具输出（缩进）
│ drwxr-xr-x  5 user  staff   160 Jun 18 10:00 .
│ ...
◌ ✎ write  new_config.go                                     ← 文件写入 running
✓ ✎ write  new_config.go                                     ← 文件写入 succeeded
◌ task  General — Research the architecture                  ← 子任务 running
✓ task  General — Research the architecture  12s · 8 calls   ← 子任务完成

The project is structured as follows:                       ← 最终回答（正常 Markdown 渲染）

- `cmd/` - entry point
- `internal/` - core logic
- ...

── answered in 3.2s · $0.0015 · 448 tokens ──                ← 回答完成后汇总行
```

### 3.4 Reasoning 展示（P3-6B）

#### 展示样式

```text
_Thinking:_
│ 让我分析这个项目的目录结构...
│
│ 首先需要了解核心模块的依赖关系：
│
│ - `internal/core/` — 核心执行引擎
│ - `internal/transport/` — SSE 传输层
│ - `internal/event/` — 事件归一化
│
│ ```go
│ // 依赖注入图
│ func Wire(ctx context.Context) (*app.App, error) {
│     ...
│ }
│ ```
│
│ 基于以上分析，项目采用分层架构。
```

#### 实现方案

使用 **lipgloss** 在每行输出前添加 `│ ` 前缀：

```go
// 伪代码
func (r *ReasoningRenderer) WriteLine(ctx context.Context, text string) error {
    prefix := r.style.Render("│ ")
    fmt.Fprintf(r.out, "%s%s\n", prefix, text)
}

// 完整 Markdown 块渲染时（由 glamour 处理）：
func (r *ReasoningRenderer) RenderMarkdown(ctx context.Context, md string) error {
    rendered, _ := glamour.Render(md, "dark")
    for _, line := range strings.Split(rendered, "\n") {
        r.WriteLine(ctx, line)
    }
    return nil
}
```

#### 三种模式

| 模式 | 配置值 | 行为 |
| ---- | ----- | ---- |
| **show** | `"show"` | 完整 left-border + Markdown 渲染（默认） |
| **minimal** | `"minimal"` | 折叠为单行 `▶ Thinking: {首句摘要}... {duration}` |
| **hide** | `"hide"` | 完全不输出 reasoning 内容 |

```go
// 配置
type DisplayConfig struct {
    ShowReasoning string `koanf:"show_reasoning"` // "show" | "minimal" | "hide"
}

// minimal 模式实现
func (r *ReasoningRenderer) RenderMinimal(ctx context.Context, text string, duration time.Duration) error {
    summary := firstSentence(text, 80) // 首句，最多 80 字符
    fmt.Fprintf(r.out, "%s Thinking: %s...  %s\n",
        r.styleMinimal.Render("▶"),
        summary,
        formatDuration(duration),
    )
    return nil
}
```

#### 配置项

```yaml
# .witty.yaml
display:
  show_reasoning: "show"    # "show" | "minimal" | "hide"
```

### 3.5 工具调用展示（P3-6C）

#### 总体方案

每个工具调用遵循 **3 阶段展示**：

```text
1. running 时：    ◌ {icon} {tool_type} {summary}
2. completed 时：  ✓ {icon} {tool_type} {summary}
                   │ {output}（缩进，截断至 10 行）
3. error 时：      ✗ {icon} {tool_type} {summary}
                   │ Error: {message}
```

#### 各工具格式化规则

| 工具 | icon | running 格式 | completed 格式 | 输出 |
| ---- | ---- | ----------- | ------------- | ---- |
| **bash** | `$` | `◌ $ bash {command}` | `✓ $ bash {command} — {description}` | `│ {output}`（缩进，10 行截断） |
| **read** | `📖` | `◌ 📖 read {filename}` | `✓ 📖 read {filename}` | `│ ↳ loaded: {files}` |
| **write** | `✎` | `◌ ✎ write {filename}` | `✓ ✎ write {filename}` | — |
| **edit** | `✎` | `◌ ✎ edit {filename}` | `✓ ✎ edit {filename}` + `+N −M` | — |
| **grep** | `🔍` | 归入 context 组 | 归入 context 组 | `│ {pattern} → {matches} matches` |
| **glob** | `🔍` | 归入 context 组 | 归入 context 组 | `│ {pattern} → {N} files` |
| **list** | `📋` | 归入 context 组 | 归入 context 组 | `│ {path}` |
| **task** | `⚙` | `◌ task {agent} — {description}` | `✓ task {agent} — {description} {duration} · {N} calls` | — |
| **webfetch** | `🌐` | `◌ 🌐 fetch {url}` | `✓ 🌐 fetch {url}` | — |
| **websearch** | `🔎` | `◌ 🔎 search "{query}"` | `✓ 🔎 search "{query}" {N} results` | — |
| **skill** | `🧠` | `◌ 🧠 skill {name}` | `✓ 🧠 skill {name}` | — |
| **question** | `❓` | **不显示** | `❓ Questions ({N})` | Q&A 对 |
| **todowrite** | — | **永不显示** | **永不显示** | — |
| **apply_patch** | `📝` | `◌ 📝 patch {N} files` | `✓ 📝 patch {N} files` | — |

#### 上下文工具分组（P3-6A）

属于 `{read, grep, glob, list}` 的连续调用合并为一行：

```text
🔍 context  3 reads, 2 searches, 1 list
```

实现逻辑：

1. 维持一个 pending context buffer
2. 遇到上下文工具 → 添加到 buffer（不立即输出）
3. 遇到非上下文工具（bash/write/edit/task/webfetch/websearch/skill/question）→ flush buffer
4. 遇到 StepEnd → flush buffer
5. SessionIdle → flush buffer
6. 如果 `group_context_tools = false` → 降级为逐个展示

上下文工具的状态处理：

- running 时：不输出（它们通常很快完成）
- completed 时：积累到 buffer
- error 时：仍然积累，但不计入计数（或单独标记）

#### CallID 处理

**不显示 callID**（与 OpenCode 一致）。如果调试需要，通过 `--debug` flag 启用。

#### Question 工具特殊处理

- pending / running 期间：**完全不输出**
- completed / error 时：显示问题和答案

  ```text
  ❓ Questions (2)
    Q: 是否需要创建配置文件？
    A: Yes, create it
    Q: 使用哪种数据库？
    A: PostgreSQL
  ```

#### 非 TTY 降级

所有 Unicode 图标替换为 ASCII：

- `◌` → `[..]`
- `✓` → `[OK]`
- `✗` → `[FAIL]`
- `📖` → `[read]`
- `✎` → `[write]`
- `🔍` → `[search]`

### 3.6 Step 边界展示（P3-6D）

> **与 OpenCode TUI 一致：StepStart/StepFinish 完全不输出。**

#### 设计决策

- `EventStepStarted` / `EventStepEnded` **仅内部使用**：
  - StepStarted：reset tool call counter，flush context buffer，初始化 reasoning renderer
  - StepEnded：flush context buffer，累计 cost/tokens
- **不产生任何终端输出**
- **Cost/Tokens 是 per-message 的**，在 `session.idle` 时从 `AssistantMessage` metadata 提取

#### 回答完成后的汇总行

在 `EventSessionIdle` 被确认（即收到完整 AssistantMessage）后，输出一行汇总：

```text
── answered in 3.2s · $0.0015 · 448 tokens ──
```

格式：

- 线宽 = 终端宽度（由 `terminal.Width()` 获取）
- 颜色：暗色（lipgloss `Faint`）
- 线字符：`─`
- 内容：`answered in {duration} · ${cost} · {total_tokens} tokens`
- 非 TTY：`--- 3.2s  $0.0015  448 tokens ---`

配置项：

```yaml
display:
  step_style: "line"     # "line" | "minimal"（仅空行）| "none"（无输出）
```

### 3.7 权限和问题交互

权限和问题使用**独立的选择器 UI**（与 OpenCode 一致，不在消息流中内联）：

```text
┌──────────────────────────────────────────────────────────┐
│ 🔒  Allow bash execution?                                │
│                                                            │
│     Command: rm -rf /tmp/cache/                           │
│     Description: Clean up temporary cache files           │
│                                                            │
│  > [A] Allow once    [D] Always allow    [R] Reject       │
└──────────────────────────────────────────────────────────┘
```

### 3.8 Agent/Model 切换

Agent 和 Model 是**用户消息的属性**，切换时输出一行提示：

```text
ag: plan (read-only mode)
```

或作为用户消息 header：

```text
You (build · claude-sonnet-4 · 10:30 AM) > 分析项目结构
```

### 3.9 完整时序图

```text
用户输入           SSE 事件流                终端输出
─────────         ──────────                ────────
                   reasoning.delta ──────── _Thinking:_
                                            │ ... （延迟输出）
                   tool.called(bash) ────── ◌ $ bash ls
                   tool.succeeded(bash) ─── ✓ $ bash ls — 列出文件
                                            │ total 24
                   tool.called(read) ────── （积累到 context buffer）
                   tool.succeeded(read) ─── （积累到 context buffer）
                   tool.called(grep) ────── （积累到 context buffer）
                   tool.succeeded(grep) ─── （积累到 context buffer）
                   tool.called(task) ────── （先 flush context buffer）
                                            🔍 context  2 reads, 1 search
                                            ◌ task General — 搜索代码
                   tool.succeeded(task) ─── ✓ task General — 搜索代码  2s · 3 calls
                   text.delta ───────────── （由 renderer 处理）
                   text.delta ───────────── "项目结构如下..."
                   session.idle ────────── ── answered in 5.6s · $0.0032 · 892 tokens ──
```

---

## 4. 实现路径

### 4.1 需要修改的模块

| 模块 | 变更内容 |
| ---- | ------- |
| `internal/event/` | 新增 `EventToolPending`/`EventToolRunning`；补充 `EventAgentSwitched`/`EventModelSwitched` 的具体字段；移除对 StepStart/StepFinish 作为展示事件的处理 |
| `internal/presenter/` | 重写 PresentEvent dispatch：StepStart/StepFinish 不输出；新增 ContextGroup buffer；工具各状态独立格式化；Reasoning 行前缀渲染 |
| `internal/renderer/` | 新增 Reasoning 渲染通道（left-border + glamour） |
| `internal/core/` | AskRunner 中 StepStart/StepFinish 改为纯内部记账；session.idle 时提取 cost/tokens 并通知 presenter |
| `internal/config/` | 新增 `display.show_reasoning`、`display.group_context_tools`、`display.step_style` |

### 4.2 新增/修改的文件

```text
internal/
├── event/
│   └── types.go              # 修改：新增 tool.pending/tool.running
├── presenter/
│   ├── presenter.go          # 重写：Step 零输出、context group、per-tool 格式化
│   ├── presenter_test.go     # 重写：覆盖新行为
│   ├── context_group.go      # 新增：ContextGroup buffer 逻辑
│   └── context_group_test.go # 新增：Golden test
├── renderer/
│   ├── renderer.go           # 修改：新增 Reasoning 通道
│   ├── reasoning.go          # 新增：left-border + glamour 渲染
│   └── reasoning_test.go     # 新增
└── config/
    └── config.go             # 修改：新增 display 配置项
```

### 4.3 开发顺序

1. **P3-6D**：Step 零输出 → 最小改动，最大影响
2. **P3-6B**：Reasoning left-border → 核心视觉差异化
3. **P3-6A**：ContextToolGroup → 降噪
4. **P3-6C**：工具 per-type 格式化 → 精细化展示
5. **P3-6E**：配置项与降级 → 可控性
6. **P3-6F**：端到端验收

---

## 5. 验收标准

### 5.1 Step 零输出（P3-6D）

- [x] `EventStepStarted` 和 `EventStepEnded` 不产生任何终端输出
- [x] `[step]` 文字完全消失
- [x] 仅 `EventSessionIdle` 后显示一行汇总统计
- [x] 汇总行格式：`── answered in {duration} · ${cost} · {tokens} tokens ──`
- [x] `step_style` 三种模式均可用（line/minimal/none）
- [x] Golden test 覆盖三种 step_style

### 5.2 Reasoning 展示（P3-6B）

- [x] reasoning 使用 `│ ` left-border 前缀 + glamour Markdown 渲染
- [x] 首行 `_Thinking:_` 标识
- [x] 暗色文字（lipgloss Faint）
- [x] reasoning 走独立渲染通道，不干扰 text delta 管线
- [x] show / minimal / hide 三种模式 work
- [x] `show_reasoning = "hide"` 时完全不输出
- [x] Golden test 覆盖三种模式

### 5.3 上下文工具分组（P3-6A）

- [x] 连续 read/grep/glob/list 合并为一行 `🔍 context  N reads, M searches, K lists`
- [x] 遇到非上下文工具时自动 flush
- [x] Step 结束时自动 flush
- [x] `group_context_tools = false` 时降级为逐个展示
- [x] Golden test 覆盖分组与降级场景

### 5.4 工具调用展示（P3-6C）

- [x] bash/read/write/edit/task/skill 各有独立格式化
- [x] 3 态展示：running (◌)、completed (✓绿)、error (✗红)
- [x] 工具输出 10 行截断
- [x] callID 不显示
- [x] todowrite/todoread 永不显示
- [x] question pending/running 期间隐藏
- [x] Golden test 覆盖所有工具类型的 3 种状态

### 5.5 配置项与降级（P3-6E）

- [x] `display.show_reasoning` 正常生效
- [x] `display.group_context_tools` 正常生效
- [x] `display.step_style` 正常生效
- [x] 非 TTY 自动降级（去除 ANSI + Unicode）
- [x] `todowrite`/`todoread` 不产生 AppEvent

### 5.6 端到端验收（P3-6F）

- [x] 思考过程、工具调用、最终回答三者视觉清晰分离
- [x] 上下文工具合并，视觉噪音大幅降低
- [x] `witty ask` 在 openEuler PTY 下交互流畅
- [x] `go test -count=1 ./...` 通过
- [x] `golangci-lint run ./...` 通过
- [x] openEuler PTY 测试通过
- [x] Golden test 覆盖完整事件流

---

## 6. 关键参考源码位置

| 文件 | 内容 | 行数参考 |
| ---- | ---- | ------- |
| `message-v2.ts` | Part schema、ToolPart 状态机、toModelMessages 过滤逻辑 | Part section, toModelMessagesEffect |
| `session/index.tsx` | TUI PART_MAPPING、ReasoningPart、TextPart、ToolPart 渲染 | ~L700-900 Reasoning, ~L900+ TextPart, InlineTool |
| `message-part.tsx` | Web UIPART_MAPPING、HIDDEN_TOOLS、CONTEXT_GROUP_TOOLS、renderable()、ContextToolGroup、ToolRegistry | ~L1-500 |
| `types.gen.ts` | SDK Part/Event 类型定义 | TextPart, ReasoningPart, ToolPart, EventSessionIdle |
| `context/thinking.ts` | 思考模式状态管理（show/hide toggle） | ThinkingMode |

---

## 附录 A：OpenCode 完整工具列表

```typescript
// 来源: ToolRegistry 注册（message-part.tsx + session/index.tsx）

| 工具名         | TUI 渲染              | Web UI 渲染           | 显示规则                |
| ------------- | -------------------- | -------------------- | ---------------------- |
| bash          | Shell (BlockTool)    | bash (ToolRegistry)  | 始终显示                |
| read          | Read (InlineRow)     | read (ToolRegistry)  | 归入 context group (Web) |
| write         | Write (BlockTool)    | write (ToolRegistry) | 始终显示                |
| edit          | Edit (BlockTool)     | edit (ToolRegistry)  | 始终显示                |
| glob          | Glob (InlineRow)     | glob (ToolRegistry)  | 归入 context group (Web) |
| grep          | Grep (InlineRow)     | grep (ToolRegistry)  | 归入 context group (Web) |
| list          | (GenericTool)        | list (ToolRegistry)  | 归入 context group (Web) |
| task          | Task (InlineRow)     | task (ToolRegistry)  | 始终显示                |
| webfetch      | WebFetch (InlineRow) | webfetch (ToolRegistry)| 始终显示              |
| websearch     | WebSearch (InlineRow)| websearch (ToolRegistry)| 始终显示             |
| skill         | Skill (InlineRow)    | skill (ToolRegistry) | 始终显示                |
| question      | Question (BlockTool) | question (ToolRegistry)| pending/running 时隐藏  |
| todowrite     | TodoWrite (InlineRow)| — (HIDDEN_TOOLS)     | TUI 显示，Web 隐藏       |
| apply_patch   | ApplyPatch (BlockTool)| apply_patch (ToolRegistry)| 始终显示            |
| plan_enter    | (内部切换)            | —                     | 不渲染                  |
| plan_exit     | (内部切换)            | —                     | 不渲染                  |
```

## 附录 B：Witty 与 OpenCode 的术语映射

| Witty AppEvent | OpenCode Event/Part | 关系 |
| ------------- | ----------------- | --- |
| `EventTextDelta` | `message.part.delta` → TextPart | 直接对应 |
| `EventReasoningDelta` | `message.part.delta` → ReasoningPart | 直接对应 |
| `EventToolCalled` | ToolPart (status: "pending"/"running") | Witty 合并了 pending+running |
| `EventToolSucceeded` | ToolPart (status: "completed") | 直接对应 |
| `EventToolFailed` | ToolPart (status: "error") | 直接对应 |
| `EventStepStarted` | StepStartPart | **不应渲染** |
| `EventStepEnded` | StepFinishPart | **不应渲染** |
| `EventPermissionAsked` | `permission.asked` 事件 | 独立交互 |
| `EventQuestionAsked` | `question.asked` 事件 | 独立交互 |
| `EventSessionIdle` | `session.idle` 事件 | 直接对应 |
| `EventAgentSwitched` | AssistantMessage.agent | 消息属性 |
| `EventModelSwitched` | AssistantMessage.modelID | 消息属性 |
