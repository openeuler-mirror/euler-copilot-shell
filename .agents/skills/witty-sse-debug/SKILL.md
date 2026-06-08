---
name: witty-sse-debug
description: 调试 SSE 传输层问题。包括事件解析错误、连接断开、归一化异常、session.idle 信号缺失。用于排查 transport/event 模块运行时问题。
---

# SSE 传输调试

## 常用调试命令

```bash
# 监听原始 SSE 事件流
curl -N -H "Accept: text/event-stream" http://127.0.0.1:4096/event

# 检查 opencode server 健康状态
curl http://127.0.0.1:4096/health

# 查看已建立的 session
curl http://127.0.0.1:4096/session
```

## 常见问题诊断

### 1. 事件解析错误

- 检查文件: `internal/transport/event_stream.go`
- 关键函数: `ParseStream` — 确保正确处理 `data:` 行、空行分隔、多行事件
- 测试: `go test -v -run TestParseStream ./internal/transport/`

### 2. 归一化异常

- 检查文件: `internal/event/normalize.go`
- 注意: 归一化层有状态设计，Router 跟踪 part 的上一次状态（如 tool state 转换）
- 测试: `go test -v -run TestNormalize ./internal/event/`

### 3. session.idle 信号缺失

- **唯一可靠**的流结束信号，不能用 `io.EOF` 判断流结束
- 检查 `internal/event/router.go` 中的 sessionID 过滤逻辑
- 如果长时间未收到 `session.idle`，检查 opencode server 是否仍在处理请求

### 4. HTTP 连接失败

- 检查 `internal/transport/client.go` 中的超时设置
- SSE 连接使用专用 `http.Client`，不设响应超时
- 连接超时和 TLS 握手超时需合理设置

## 架构要点

- SSE 解析**必须**手写 `bufio.Reader`，禁止使用 `ClientWithResponses`（会 buffer 整个响应体）
- 归一化层有状态（Router 跟踪 part 状态，处理增量更新）
- sessionID 过滤在 `internal/event/router.go` 的 `Subscribe` 中处理

## 相关测试

```bash
go test -v -run TestParseStream ./internal/transport/
go test -v -run TestNormalize ./internal/event/
go test -v -run TestEventRouter ./internal/event/
```
