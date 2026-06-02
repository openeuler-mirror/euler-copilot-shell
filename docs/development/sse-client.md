# SSE 客户端实现参考

> **适用模块**：`internal/transport`、`internal/event`
>
> **版本基准**：opencode v1.15.13，OpenAPI 3.1.0，2026-06 实测

---

## 1. SSE 协议格式与 opencode 实际格式

### 1.1 opencode serve 的实际格式

**opencode serve 不使用 `event:` 字段。** 所有事件均以单行 `data: <json>` 发出，后跟空行：

```text
data: {"id":"evt_e865d4b2f001QJja01dpR17agN","type":"server.connected","properties":{}}

data: {"id":"evt_e865d4f6d001UJaMUWVNzTrGMU","type":"session.next.agent.switched","properties":{"sessionID":"ses_...","agent":"build"}}

data: {"id":"evt_e865d59be001vpEOF6IvvCQLx2","type":"message.part.delta","properties":{"sessionID":"ses_...","messageID":"msg_...","partID":"prt_...","field":"text","delta":"Hello"}}

data: {"id":"evt_e865d5b90002JGiAI3SEKCzyE3","type":"session.idle","properties":{"sessionID":"ses_..."}}

data: {"id":"evt_e865d7245001htbnoLhz9qdnCl","type":"server.heartbeat","properties":{}}
```

**事件类型在 JSON 内部的 `type` 字段**，不在 SSE `event:` 行。SSE 解析器读取 `data:` 行，然后解析 JSON 中的 `type` 字段作为事件类型。

### 1.2 事件 JSON 通用结构

所有事件共享三字段结构：

```json
{
  "id": "evt_<nanoid>",
  "type": "<event-type-string>",
  "properties": { ... }
}
```

`properties` 的 schema 因 `type` 而异。

> 具体事件类型及归一化映射见 [§4.3 服务端事件对照表](#43-服务端事件对照表)。

---

## 2. 手写 SSE 解析器

witty **不引入外部 SSE 库**（避免依赖传递，手写 100 行以内可覆盖完整规范）。

### 2.1 核心类型定义

```go
// internal/transport/sse/parser.go
package sse

// Event 代表一个完整的 SSE 帧。
// 注：opencode serve 不使用 event: 字段，Type 始终为空。
// 实际事件类型从 Data 字段解析 JSON 的 "type" 获得。
type Event struct {
    ID    string
    Type  string        // 通常为空（opencode 不使用 event: 字段）
    Data  string        // 完整 JSON 字符串
    Retry time.Duration
}
```

### 2.2 ParseStream 实现

```go
func ParseStream(ctx context.Context, r io.Reader, out chan<- Event) error {
    br := bufio.NewReaderSize(r, 32*1024)

    var (
        eventType string
        dataLines []string
        lastID    string
        retryMs   int
    )

    reset := func() {
        eventType = ""
        dataLines = dataLines[:0]
    }

    for {
        select {
        case <-ctx.Done():
            return ctx.Err()
        default:
        }

        line, err := br.ReadString('\n')
        if err != nil {
            if err == io.EOF && line == "" {
                return nil
            }
            if line != "" {
                // 处理最后一行无换行符的情况
            } else {
                return err
            }
        }
        line = strings.TrimRight(line, "\r\n")

        switch {
        case line == "":
            // 空行：dispatch 事件
            if len(dataLines) == 0 {
                reset()
                continue
            }
            data := strings.Join(dataLines, "\n")
            evt := Event{
                ID:   lastID,
                Type: eventType,
                Data: data,
            }
            if retryMs > 0 {
                evt.Retry = time.Duration(retryMs) * time.Millisecond
            }
            select {
            case <-ctx.Done():
                return ctx.Err()
            case out <- evt:
            }
            reset()

        case strings.HasPrefix(line, ":"):
            // 注释行（心跳），忽略

        case strings.HasPrefix(line, "data:"):
            val := strings.TrimPrefix(line, "data:")
            if strings.HasPrefix(val, " ") {
                val = val[1:]
            }
            dataLines = append(dataLines, val)

        case strings.HasPrefix(line, "event:"):
            val := strings.TrimPrefix(line, "event:")
            if strings.HasPrefix(val, " ") {
                val = val[1:]
            }
            eventType = val // opencode 通常不发送此行

        case strings.HasPrefix(line, "id:"):
            val := strings.TrimPrefix(line, "id:")
            if strings.HasPrefix(val, " ") {
                val = val[1:]
            }
            lastID = val

        case strings.HasPrefix(line, "retry:"):
            val := strings.TrimPrefix(line, "retry:")
            if strings.HasPrefix(val, " ") {
                val = val[1:]
            }
            if n, err := strconv.Atoi(val); err == nil {
                retryMs = n
            }
        }
    }
}
```

---

## 3. HTTP SSE 连接建立

### 3.1 超时隔离

SSE 连接不能设置响应读取超时，但连接建立阶段需要超时：

```go
func newSSEHTTPClient() *http.Client {
    transport := &http.Transport{
        DialContext: (&net.Dialer{
            Timeout:   10 * time.Second,
            KeepAlive: 30 * time.Second,
        }).DialContext,
        TLSHandshakeTimeout:   10 * time.Second,
        ResponseHeaderTimeout: 0, // SSE 不限制响应体读取时间
    }
    return &http.Client{Transport: transport}
}
```

### 3.2 SubscribeEvents 实现

```go
type RawEvent struct {
    Type string // 从 JSON 解析的 "type" 字段
    Data []byte // 完整 JSON
    ID   string // SSE event id（opencode 不使用，保留）
}

// sseEnvelope 用于从 JSON 中提取事件类型
type sseEnvelope struct {
    ID         string          `json:"id"`
    Type       string          `json:"type"`
    Properties json.RawMessage `json:"properties"`
}

func (c *Client) SubscribeEvents(ctx context.Context) (<-chan RawEvent, <-chan error) {
    events := make(chan RawEvent, 64)
    errs := make(chan error, 1)

    go func() {
        defer close(events)
        defer close(errs)

        var lastEventID string

        for {
            if err := c.connectAndStream(ctx, lastEventID, events, &lastEventID); err != nil {
                if ctx.Err() != nil {
                    return // context 取消，静默退出
                }
                errs <- err
                return // Phase 1：出错直接退出；Phase 3 改为重连
            }
            return
        }
    }()

    return events, errs
}

func (c *Client) connectAndStream(
    ctx context.Context,
    lastEventID string,
    out chan<- RawEvent,
    lastIDOut *string,
) error {
    // /event 支持 directory 参数做服务端初步过滤
    url := c.baseURL + "/event"
    if c.directory != "" {
        url += "?directory=" + url.QueryEscape(c.directory)
    }

    req, err := http.NewRequestWithContext(ctx, "GET", url, nil)
    if err != nil {
        return err
    }
    req.Header.Set("Accept", "text/event-stream")
    req.Header.Set("Cache-Control", "no-cache")
    req.Header.Set("Connection", "keep-alive")
    if lastEventID != "" {
        req.Header.Set("Last-Event-ID", lastEventID)
    }

    resp, err := c.sseClient.Do(req)
    if err != nil {
        return fmt.Errorf("sse connect: %w", err)
    }
    defer resp.Body.Close()

    if resp.StatusCode != http.StatusOK {
        return &HTTPError{StatusCode: resp.StatusCode, Endpoint: "/event"}
    }

    rawCh := make(chan sse.Event, 32)
    go func() {
        defer close(rawCh)
        sse.ParseStream(ctx, resp.Body, rawCh)
    }()

    for evt := range rawCh {
        if evt.ID != "" {
            *lastIDOut = evt.ID
        }
        if evt.Data == "" {
            continue
        }

        // 从 JSON 提取实际事件类型
        var env sseEnvelope
        if err := json.Unmarshal([]byte(evt.Data), &env); err != nil {
            slog.Warn("sse: failed to parse event JSON", "data", evt.Data, "err", err)
            continue
        }

        select {
        case <-ctx.Done():
            return ctx.Err()
        case out <- RawEvent{
            Type: env.Type,
            Data: []byte(evt.Data),
            ID:   evt.ID,
        }:
        }
    }
    return nil
}
```

---

## 4. RawEvent → AppEvent 归一化

### 4.1 归一化层的有状态设计

`message.part.delta` 事件只携带 `{partID, field, delta}`，不包含 part 类型。要区分 `text` delta 和 `reasoning` delta，Router 必须维护 `partID → partType` 内存映射：

```go
type Router struct {
    transport  transport.Client
    partTypes  map[string]string // partID -> "text" | "reasoning" | "tool" | ...
}
```

`message.part.updated` 事件先到，记录映射；`message.part.delta` 事件后到，查映射来决定产出哪种 AppEvent。

### 4.2 AppEvent 类型定义

```go
// internal/event/types.go
type AppEventKind string

const (
    EventTextDelta       AppEventKind = "text.delta"       // AI 回复文本增量
    EventReasoningDelta  AppEventKind = "reasoning.delta"  // 推理思考增量（Phase 1 可忽略展示）
    EventStepStarted     AppEventKind = "step.started"     // 执行 step 开始
    EventStepEnded       AppEventKind = "step.ended"       // 执行 step 结束
    EventToolCalled      AppEventKind = "tool.called"      // 工具调用开始
    EventToolSucceeded   AppEventKind = "tool.succeeded"   // 工具调用成功
    EventToolFailed      AppEventKind = "tool.failed"      // 工具调用失败
    EventPermissionAsked AppEventKind = "permission.asked" // 需要用户授权
    EventQuestionAsked   AppEventKind = "question.asked"   // AI 向用户提问
    EventSessionIdle     AppEventKind = "session.idle"     // 本轮回答结束
    EventUnknown         AppEventKind = "unknown"
)

type AppEvent struct {
    Kind      AppEventKind
    SessionID string
    Payload   interface{}
}

// Payload 类型
type TextDeltaPayload struct {
    Delta     string
    PartID    string
    MessageID string
}

type ToolCalledPayload struct {
    ToolName string
    CallID   string
    Input    json.RawMessage
    PartID   string
}

type ToolResultPayload struct {
    CallID string
    PartID string
    Output string
    Error  string
}

type StepEndedPayload struct {
    Cost   float64
    Tokens struct {
        Input     int
        Output    int
        Reasoning int
    }
}

type PermissionAskedPayload struct {
    RequestID  string
    Permission string
    Patterns   []string
}

type QuestionAskedPayload struct {
    RequestID string
    Questions []QuestionInfo
}

type QuestionInfo struct {
    Question string
    Header   string
    Options  []QuestionOption
    Multiple bool
    Custom   bool
}

type QuestionOption struct {
    Label       string `json:"label"`
    Description string `json:"description"`
}

type QuestionAnswers [][]string // each inner slice is the selected labels for one question
```

### 4.3 服务端事件对照表

归一化实现见 [§4.4 归一化函数](#44-归一化函数实现草案)。

| 服务端 `type` | 归一化为 |
| --- | --- |
| `message.part.delta`（text） | EventTextDelta |
| `message.part.delta`（reasoning） | EventReasoningDelta |
| `message.part.updated`（step-start） | EventStepStarted |
| `message.part.updated`（step-finish） | EventStepEnded |
| `message.part.updated`（tool, running） | EventToolCalled |
| `message.part.updated`（tool, completed） | EventToolSucceeded |
| `message.part.updated`（tool, error） | EventToolFailed |
| `permission.asked` | EventPermissionAsked |
| `question.asked` | EventQuestionAsked |
| `session.idle` | EventSessionIdle |
| `session.next.text.delta`（ACP 兼容） | EventTextDelta |
| `session.next.tool.called`（ACP 兼容） | EventToolCalled |
| `server.connected` / `server.heartbeat` | 丢弃 |
| `session.status` / `session.updated` 等 | 丢弃 |
| 其他 | EventUnknown |

> Schema 中还定义了 `session.next.*` 等 ACP 协议事件，实现时应兼容但以 `message.part.*` 为主路径。`server.heartbeat` 不在 OpenAPI Event schema 中定义但实际 SSE 流中会发送。

### 4.4 归一化函数实现草案

```go
// internal/event/router.go

type rawEnvelope struct {
    ID         string          `json:"id"`
    Type       string          `json:"type"`
    Properties json.RawMessage `json:"properties"`
}

// part.updated properties
type partUpdatedProps struct {
    SessionID string          `json:"sessionID"`
    Part      json.RawMessage `json:"part"`
    Time      int64           `json:"time"`
}

// part（通用 discriminated union，只读 type + state）
type partBase struct {
    ID     string     `json:"id"`
    Type   string     `json:"type"` // "text","reasoning","tool","step-start","step-finish"
    Tool   string     `json:"tool,omitempty"`
    CallID string     `json:"callID,omitempty"`
    State  *toolState `json:"state,omitempty"`
    Cost   float64    `json:"cost,omitempty"`
    Tokens *stepTokens `json:"tokens,omitempty"`
}

type toolState struct {
    Status string          `json:"status"` // "pending","running","completed","error"
    Input  json.RawMessage `json:"input,omitempty"`
    Output string          `json:"output,omitempty"`
    Error  string          `json:"error,omitempty"`
}

type stepTokens struct {
    Input     int `json:"input"`
    Output    int `json:"output"`
    Reasoning int `json:"reasoning"`
}

// part.delta properties
type partDeltaProps struct {
    SessionID string `json:"sessionID"`
    MessageID string `json:"messageID"`
    PartID    string `json:"partID"`
    Field     string `json:"field"`
    Delta     string `json:"delta"`
}

// permission.asked properties == PermissionRequest schema
type permissionAskedProps struct {
    ID         string   `json:"id"`
    SessionID  string   `json:"sessionID"`
    Permission string   `json:"permission"`
    Patterns   []string `json:"patterns"`
}

// question.asked properties == QuestionRequest schema
type questionAskedProps struct {
    ID        string         `json:"id"`
    SessionID string         `json:"sessionID"`
    Questions []QuestionInfo `json:"questions"`
}

func (r *Router) normalize(raw transport.RawEvent) (AppEvent, bool) {
    var env rawEnvelope
    if err := json.Unmarshal(raw.Data, &env); err != nil {
        slog.Warn("event: normalize: bad json", "err", err)
        return AppEvent{}, false
    }

    switch env.Type {
    // ── 主要流式路径 ──────────────────────────────────────────────

    case "message.part.updated":
        var props partUpdatedProps
        if err := json.Unmarshal(env.Properties, &props); err != nil {
            return AppEvent{}, false
        }
        var part partBase
        if err := json.Unmarshal(props.Part, &part); err != nil {
            return AppEvent{}, false
        }
        // 更新 partID → partType 缓存
        if part.ID != "" && part.Type != "" {
            r.partTypes[part.ID] = part.Type
        }
        return r.normalizePartUpdated(props.SessionID, &part)

    case "message.part.delta":
        var props partDeltaProps
        if err := json.Unmarshal(env.Properties, &props); err != nil {
            return AppEvent{}, false
        }
        return r.normalizePartDelta(props)

    case "session.idle":
        var props struct {
            SessionID string `json:"sessionID"`
        }
        if err := json.Unmarshal(env.Properties, &props); err != nil {
            return AppEvent{}, false
        }
        return AppEvent{Kind: EventSessionIdle, SessionID: props.SessionID}, true

    case "permission.asked":
        var props permissionAskedProps
        if err := json.Unmarshal(env.Properties, &props); err != nil {
            return AppEvent{}, false
        }
        return AppEvent{
            Kind:      EventPermissionAsked,
            SessionID: props.SessionID,
            Payload: PermissionAskedPayload{
                RequestID:  props.ID,
                Permission: props.Permission,
                Patterns:   props.Patterns,
            },
        }, true

    case "question.asked":
        var props questionAskedProps
        if err := json.Unmarshal(env.Properties, &props); err != nil {
            return AppEvent{}, false
        }
        return AppEvent{
            Kind:      EventQuestionAsked,
            SessionID: props.SessionID,
            Payload: QuestionAskedPayload{
                RequestID: props.ID,
                Questions: props.Questions,
            },
        }, true

    // ── ACP 兼容路径（session.next.* 事件）─────────────────────────

    case "session.next.text.delta":
        var props struct {
            SessionID string `json:"sessionID"`
            Delta     string `json:"delta"`
        }
        if err := json.Unmarshal(env.Properties, &props); err != nil {
            return AppEvent{}, false
        }
        return AppEvent{
            Kind:      EventTextDelta,
            SessionID: props.SessionID,
            Payload:   TextDeltaPayload{Delta: props.Delta},
        }, true

    case "session.next.tool.called":
        var props struct {
            SessionID string          `json:"sessionID"`
            CallID    string          `json:"callID"`
            Tool      string          `json:"tool"`
            Input     json.RawMessage `json:"input"`
        }
        if err := json.Unmarshal(env.Properties, &props); err != nil {
            return AppEvent{}, false
        }
        return AppEvent{
            Kind:      EventToolCalled,
            SessionID: props.SessionID,
            Payload: ToolCalledPayload{
                ToolName: props.Tool,
                CallID:   props.CallID,
                Input:    props.Input,
            },
        }, true

    // ── 静默忽略（不需要展示）────────────────────────────────────

    case "server.connected", "server.heartbeat",
        "message.updated", "message.removed",
        "message.part.removed",
        "session.status", "session.updated", "session.diff",
        "session.created", "session.deleted",
        "session.next.agent.switched", "session.next.model.switched",
        "session.next.step.started", "session.next.step.ended",
        "session.next.reasoning.delta",
        "session.next.prompted":
        return AppEvent{}, false

    default:
        slog.Debug("event: unknown type", "type", env.Type)
        return AppEvent{Kind: EventUnknown}, false
    }
}

func (r *Router) normalizePartDelta(props partDeltaProps) (AppEvent, bool) {
    if props.Field != "text" {
        return AppEvent{}, false // 忽略非 text 字段的 delta
    }
    partType := r.partTypes[props.PartID] // 查缓存
    kind := EventUnknown
    switch partType {
    case "text":
        kind = EventTextDelta
    case "reasoning":
        kind = EventReasoningDelta
    default:
        // partType 未知（可能 part.updated 还没到），保守处理为 text
        kind = EventTextDelta
    }
    return AppEvent{
        Kind:      kind,
        SessionID: props.SessionID,
        Payload: TextDeltaPayload{
            Delta:     props.Delta,
            PartID:    props.PartID,
            MessageID: props.MessageID,
        },
    }, true
}

func (r *Router) normalizePartUpdated(sessionID string, part *partBase) (AppEvent, bool) {
    switch part.Type {
    case "step-start":
        return AppEvent{Kind: EventStepStarted, SessionID: sessionID}, true

    case "step-finish":
        payload := StepEndedPayload{Cost: part.Cost}
        if part.Tokens != nil {
            payload.Tokens.Input = part.Tokens.Input
            payload.Tokens.Output = part.Tokens.Output
            payload.Tokens.Reasoning = part.Tokens.Reasoning
        }
        return AppEvent{Kind: EventStepEnded, SessionID: sessionID, Payload: payload}, true

    case "tool":
        if part.State == nil {
            return AppEvent{}, false
        }
        switch part.State.Status {
        case "running":
            return AppEvent{
                Kind:      EventToolCalled,
                SessionID: sessionID,
                Payload: ToolCalledPayload{
                    ToolName: part.Tool,
                    CallID:   part.CallID,
                    Input:    part.State.Input,
                    PartID:   part.ID,
                },
            }, true
        case "completed":
            return AppEvent{
                Kind:      EventToolSucceeded,
                SessionID: sessionID,
                Payload: ToolResultPayload{
                    CallID: part.CallID,
                    PartID: part.ID,
                    Output: part.State.Output,
                },
            }, true
        case "error":
            return AppEvent{
                Kind:      EventToolFailed,
                SessionID: sessionID,
                Payload: ToolResultPayload{
                    CallID: part.CallID,
                    PartID: part.ID,
                    Error:  part.State.Error,
                },
            }, true
        }
        return AppEvent{}, false

    default:
        // "text"、"reasoning" 的 part.updated 只更新缓存，不产出 AppEvent
        return AppEvent{}, false
    }
}
```

### 4.5 sessionID 过滤

`/event` 是全局事件总线，Router 层强制过滤：

```go
func (r *Router) Subscribe(ctx context.Context, targetSessionID string) (<-chan AppEvent, <-chan error) {
    rawEvents, rawErrs := r.transport.SubscribeEvents(ctx)
    out := make(chan AppEvent, 32)
    errs := make(chan error, 1)

    go func() {
        defer close(out)
        defer close(errs)

        for {
            select {
            case <-ctx.Done():
                return
            case err, ok := <-rawErrs:
                if !ok {
                    return
                }
                errs <- err
                return
            case raw, ok := <-rawEvents:
                if !ok {
                    return
                }
                evt, ok := r.normalize(raw)
                if !ok {
                    continue
                }
                // 丢弃非目标 session 的事件
                if evt.SessionID != "" && evt.SessionID != targetSessionID {
                    continue
                }
                select {
                case <-ctx.Done():
                    return
                case out <- evt:
                }
            }
        }
    }()

    return out, errs
}
```

---

## 5. 并发模型

```text
GET /event SSE 连接 goroutine
    → sse.ParseStream（按行读取 bufio.Reader）
    → chan sse.Event (buf=32)
    → transport.connectAndStream（JSON 解析提取 type）
    → chan transport.RawEvent (buf=64)
    → event.Router goroutine（有状态归一化 + sessionID 过滤）
    → chan event.AppEvent (buf=32)
    → core.AskRunner.Run（消费，驱动 renderer/presenter/permission）
```

**通道关闭规则**（只有写入者关闭）：

| 通道 | 关闭者 |
| ---- | ------ |
| `chan sse.Event` | ParseStream goroutine（EOF 或 ctx 取消后） |
| `chan transport.RawEvent` | SubscribeEvents goroutine |
| `chan event.AppEvent` | Router goroutine |
| `chan error` | 同写入者（发送唯一值后关闭） |

---

## 6. session.idle 检测

### 6.1 为什么 session.idle 是唯一可靠信号

- `message.part.delta` 流结束不代表回答结束（可能有后续工具调用）
- `session.status` 的 `{type:"idle"}` 与 `session.idle` 都会发出，但 `session.idle` 是专用事件
- SSE 连接不会主动断开（持续保持）
- `[DONE]` 是 OpenAI 兼容服务可选约定，opencode 不使用

### 6.2 在 AskRunner 中消费

```go
func (r *AskRunner) Run(ctx context.Context, sessionID string, prompt string) error {
    events, errs := r.Router.Subscribe(ctx, sessionID)

    idleTimeout := 5 * time.Minute
    timeoutCtx, cancel := context.WithTimeout(ctx, idleTimeout)
    defer cancel()

    for {
        select {
        case <-timeoutCtx.Done():
            return fmt.Errorf("session timed out waiting for idle: %w", timeoutCtx.Err())

        case err := <-errs:
            return err

        case evt, ok := <-events:
            if !ok {
                return ErrStreamEndedWithoutIdle
            }
            switch evt.Kind {
            case EventTextDelta:
                p := evt.Payload.(TextDeltaPayload)
                if err := r.Renderer.WriteDelta(p.Delta); err != nil {
                    return err
                }
            case EventReasoningDelta:

            case EventStepStarted, EventStepEnded,
                EventToolCalled, EventToolSucceeded, EventToolFailed:
                r.Presenter.Handle(evt)

            case EventPermissionAsked:
                p := evt.Payload.(PermissionAskedPayload)
                decision, err := r.Permission.Ask(ctx, p)
                if err != nil {
                    return err
                }
                if err := r.Transport.ReplyPermission(ctx, p.RequestID, decision); err != nil {
                    return err
                }

            case EventQuestionAsked:
                p := evt.Payload.(QuestionAskedPayload)
                answers, err := r.Permission.AskQuestion(ctx, p)
                if err != nil {
                    if err := r.Transport.RejectQuestion(ctx, p.RequestID); err != nil {
                        slog.Warn("failed to reject question", "err", err)
                    }
                    continue
                }
                if err := r.Transport.ReplyQuestion(ctx, p.RequestID, answers); err != nil {
                    return err
                }

            case EventSessionIdle:
                return r.Renderer.Flush()
            }
        }
    }
}

var ErrStreamEndedWithoutIdle = fmt.Errorf("sse stream closed before session.idle")
```

---

## 7. 错误处理

### 7.1 结构化错误类型

```go
type HTTPError struct {
    StatusCode int
    Endpoint   string
    Message    string
}

func (e *HTTPError) Error() string {
    return fmt.Sprintf("http %d from %s: %s", e.StatusCode, e.Endpoint, e.Message)
}

var ErrStreamEndedWithoutIdle = fmt.Errorf("sse stream closed before session.idle")
```

### 7.2 错误分类与处理策略

| 错误类型 | 处理策略 |
| -------- | -------- |
| context 取消 | 立即退出，不打印错误 |
| 网络错误 | Phase 3 重连；Phase 1 打印错误退出 |
| HTTP 4xx | 不重试，向用户展示说明 |
| HTTP 5xx | 可重试 |
| JSON 解析失败 | 跳过该事件，记录 warn 日志，继续 |
| 无 idle 超时 | 触发 context 超时，打印诊断 |
| 流提前关闭 | Phase 3 重连；Phase 1 返回 ErrStreamEndedWithoutIdle |

### 7.3 错误向上传递

每层只用 `fmt.Errorf("context: %w", err)` 包装，最终由 `cmd/witty` 区分：

- `context.Canceled` → 静默退出（用户 Ctrl+C）
- 其他 → 打印并以非零状态码退出

### 7.4 Doctor 检查点

```go
func CheckSSEEndpoint(ctx context.Context, client transport.Client) CheckResult {
    // 建立 SSE 连接，等待 server.connected 事件或超时（最多 5s）
    // 收到 server.connected → 连接正常
    // 超时但无 err → 连接正常（只是 heartbeat 周期未到）
    // 收到 err → 连接失败
}
```

---

## 8. 断线重连策略（Phase 3）

- 重连时携带 `Last-Event-ID`（opencode 分配 evt_xxx ID；因无法在无 live server 环境下验证服务端去重行为，Phase 3 实现时需以实际 SSE 重连测试为准，Fallback 为不带 ID 重连）
- 指数退避：初始 1s，每次翻倍，上限 30s
- context 取消立即中止

```go
const reconnectInitialDelay = 1 * time.Second
const reconnectMaxDelay     = 30 * time.Second

// HTTP 4xx → 不重试（认证失败、资源不存在等）
// HTTP 5xx / 网络错误 → 退避后重试
// context 取消 → 立即退出
```

---

## 附录：目录结构参考

```text
internal/
├── transport/
│   ├── sse/
│   │   └── parser.go       — 纯 SSE 帧解析
│   ├── client.go           — HTTP client 实现
│   ├── event_stream.go     — SSE 连接管理 + JSON envelope 解析
│   └── errors.go
├── event/
│   ├── types.go            — AppEventKind + Payload 类型
│   ├── normalize.go        — 有状态归一化（partID 缓存）
│   └── router.go           — sessionID 过滤 + goroutine 管理
└── core/
    └── runner.go           — AskRunner.Run 事件消费循环
```
