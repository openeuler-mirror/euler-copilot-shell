---
name: witty-integration-test
description: 在真实 opencode 后端上运行 Witty 集成测试与端到端联调。当用户要验证或调试 live opencode server 下的 transport、SSE 订阅、事件归一化、session 管理行为，新增或修改 `test/integration/` 测试，或怀疑单元测试与真实后端行为不一致时，务必使用这个 skill。默认场景是 `127.0.0.1:4096` 可达并执行 `go test -tags=integration ./test/integration/`。
---

# opencode 真实后端集成测试

## 适用场景

这个 skill 用于 **真实后端联调**，不是普通单元测试：

- 运行现有 `test/integration/` 集成测试套件
- 新增或修改真实 opencode server 驱动的集成测试
- 验证 `internal/transport`、SSE 订阅、`internal/event`、`internal/session` 在 live backend 下的协作行为
- 排查“单元测试通过，但真实后端行为不同”的问题

如果问题是 **SSE 行级语法**、**单个函数逻辑**、**纯本地 fake transport 行为**，优先写/改单元测试；如果问题是“真实 opencode 流里到底发了什么、客户端在 live backend 下怎么表现”，再用这个 skill。

## 前置条件

如果这次集成测试需要在 openEuler 远程环境中执行，先直接读取 `shell/.agents/config.yaml` 获取连接方式；不要先依赖 `find_path` 或目录扫描判断该文件是否存在。该文件可能被 `.gitignore` 隐藏，但仍然真实存在。若直接读取失败，再回退参考 `shell/.agents/config.template.yaml`。

如果使用 OrbStack / WSL 跑远程命令，必须显式经 shell 执行；不要把整段 `cd ... && ...` 直接当成 `orb` / `wsl` 的命令名。

```bash
# OrbStack
orb run -m <vm> -u <user> sh -lc 'cd <work_dir> && go test -v -tags=integration -count=1 -timeout 300s ./test/integration/'

# WSL
wsl -d <distro> -u <user> -- sh -lc 'cd <work_dir> && go test -v -tags=integration -count=1 -timeout 300s ./test/integration/'
```

opencode server 必须在 **与测试进程同一个运行环境可达的** `127.0.0.1:4096` 上运行。

验证流程是：

1. 先检查 health：

   ```bash
   curl -s http://127.0.0.1:4096/global/health
   ```

2. 如果不可达，**不要直接停止**；先在同一环境里尝试启动：

   ```bash
   opencode serve --port 4096
   ```

   实际执行时应以 detached 方式启动，并等待数秒后重试 health check。

3. 只有在“启动失败”或“二次 health check 仍失败”时，才报告 server 不可达。

健康检查成功后，预期输出示例：

```bash
curl -s http://127.0.0.1:4096/global/health
# → {"healthy":true,"version":"1.x.x"}
```

> 如果你是在 openEuler VM / OrbStack / SSH 远程环境里跑测试，`127.0.0.1` 指的是 **该环境自身**，不是宿主机。需要在同一环境内启动 opencode，或确保该地址从测试环境里确实可达。

## 运行现有集成测试

```bash
go test -v -tags=integration -count=1 -timeout 300s ./test/integration/
```

当前测试文件：`test/integration/opencode_integration_test.go`

当前同包辅助函数：

- `newTransport(t)`
- `skipIfServerDown(t, client)`

server 不可达时，测试应 **skip** 而不是 fail。

## 当前测试覆盖（按现有代码而非理想覆盖描述）

### Transport HTTP Client

| 测试 | 当前实际验证点 |
| ---- | ------ |
| `TestTransport_Health` | `GET /global/health` 返回 `healthy=true` 且 `version` 非空 |
| `TestTransport_SessionCreateListGet` | `CreateSession` 成功；`GetSession` 返回相同 ID；`ListSessions` 能查到刚创建的 session |
| `TestTransport_SendPromptAsyncAndSubscribe` | 先订阅 `/event`，再发送 `prompt_async`；真实流里能观察到文本增量路径（`message.part.delta` 或 `session.next.text.delta`）以及 `session.idle` |

### SSE Parser / Streaming Path

当前 integration suite **只在真实后端上验证 streaming 主路径**，包括：

- 能建立 `/event` SSE 连接
- 能持续消费 live event stream
- 能把 `data:` 中的 JSON envelope 提取为 `transport.RawEvent`
- 业务完成以 `session.idle` 为准，而不是把连接 EOF 当作完成信号

以下内容 **不应宣称由当前 integration test 完整覆盖**：

- `event:` / `id:` / `retry:` 每种字段的显式分支
- 多行 `data:` 拼接
- 注释行 `:`
- malformed `retry`
- EOF 前残留事件 dispatch

这些更适合放在 `internal/transport/event_stream_test.go` 这类单元测试中验证。

### Event Router

| 测试 | 当前实际验证点 |
| ---- | ------ |
| `TestEventRouter_WithRealEvents` | 在真实流上跑 `event.Router.Subscribe`；断言能产出 `EventTextDelta` 与 `EventSessionIdle`；并检查发出的非空 `SessionID` 不会绕过目标 session 过滤 |

补充说明：

- 当前测试会 **记录** `step.started`、`reasoning.delta`、`step.ended` 等事件出现情况，但不会把这些 live event 的精确数量/顺序当成硬断言。
- 这是更稳妥的做法，因为真实后端事件组合可能随 server 版本、prompt 内容、agent 行为而变化。

### Session Manager

| 测试 | 当前实际验证点 |
| ---- | ------ |
| `TestSessionResolver_ResolveAndList` | `Resolve(CWD, false)` 返回可用 session；`Resolve(CWD, true)` 创建不同 session；`Continue(ID)` 返回目标 session；`List` 返回非空摘要列表 |
| `TestSessionResolver_ContinueInvalidID` | 无效 session ID 返回非 nil 错误；当前后端通常会给出带 session ID 的 HTTP 404 / `NotFoundError` 信息 |

> 注意：当前第二个测试主要验证“错误清晰且非 nil”，而不是把某一段后端错误文案逐字视为稳定契约。若你后续要收紧断言，优先断言 **status / endpoint / session ID** 这类稳定信息。

## 编写新的集成测试

测试文件位于 `test/integration/`，使用 `//go:build integration` tag 隔离。

### 推荐模板

优先复用同包已有辅助函数，而不是每个测试重复手写 transport 初始化和 health check。

```go
//go:build integration

package integration

import (
    "context"
    "testing"
    "time"

    "atomgit.com/openeuler/witty-cli/internal/transport"
)

func TestMyFeature(t *testing.T) {
    client := newTransport(t)
    skipIfServerDown(t, client)

    ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
    defer cancel()

    // test logic...
    _ = transport.EventFilter{}
}
```

### 编写原则

1. 每个测试保持自包含：自己创建 client、自己创建 session、自己清理上下文。
2. 优先复用 `newTransport(t)` 和 `skipIfServerDown(t, client)`；server 不可达时 skip 而非 fail。
3. 真实流测试必须设置合理 timeout；推荐 `30s` 做 health/list/create，`120-300s` 做 streaming。
4. **订阅类测试先订阅，再发送 prompt**，避免错过前几个事件。
5. 收到 `session.idle` 后应尽快 `cancel()` 或主动结束事件循环；不要无谓等到外层 timeout。
6. 不要把 `io.EOF` 当成业务完成；业务完成以 `session.idle` 为准。
7. session 状态文件放在 `t.TempDir()` 下，不污染用户目录。
8. 不要为了测试添加生产代码专用 export 或测试后门。
9. 对真实后端事件，优先断言 **稳定不变量**（是否出现目标事件、sessionID 是否匹配、错误是否带 endpoint/status），少断言脆弱的完整 payload 文案、精确事件条数或严格顺序。
10. 如果你要验证 parser 边界条件（多行 `data:`、`retry:`、注释行等），优先写 `internal/transport` 单元测试；integration test 只补“真实后端确实走通”这一层。

## 常见问题与已知限制

- **事件循环不退出**：先检查收到 `session.idle` 后是否及时 `cancel()`；否则很容易把测试拖到 timeout。
- **流测试很慢**：当前 `TestTransport_SendPromptAsyncAndSubscribe` 还没有在 `session.idle` 后主动 cancel，运行时可能接近其 timeout。扩展该测试时优先修成“idle 后尽快退出”。
- **sessionID 过滤失效**：`router.Subscribe(ctx, targetSessionID, filter)` 的 `targetSessionID` 不能为空；`/event` 是全局总线，不能默认全量消费。
- **openEuler 环境**：如果在 VM / 远程机里跑测试，要在同一环境内启动 opencode，不能默认宿主机的 `127.0.0.1:4096` 可达。
- **server 不可达时的默认动作**：先尝试启动 `opencode serve --port 4096` 并重试 health check；不要一看到 `curl` 失败就结束任务。
- **并发 session**：`Resolve(..., true)` 的预期是创建新 session；如果当前目录已有活跃 session，新旧 ID 应不同。
- **这不是 PTY / Shell Adapter 测试**：Shell 接入、Readline、交互式终端行为属于 `test/pty/` 范畴，不要把这类验证塞进 integration skill。
