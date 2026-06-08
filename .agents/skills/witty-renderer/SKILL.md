---
name: witty-renderer
description: 开发或调试流式 Markdown 渲染器。包括 Phase 1 块边界渲染和 Phase 2 即时回显。用于修改 internal/renderer 模块时。
---

# 流式渲染器开发

## 关键文件

- `internal/renderer/markdown.go` — 主渲染器 `MarkdownRenderer`
- `internal/renderer/buffer.go` — `BlockBuffer` 块边界缓冲
- `internal/renderer/flush_policy.go` — 刷新策略

## 核心约束

**glamour 是批量渲染器**，不支持流式增量输入。因此流式渲染分两阶段:

- **Phase 1（MVP）**: 块边界渲染
  1. `WriteDelta()` 将增量文本写入 `BlockBuffer`
  2. `BlockBuffer` 按 Markdown 块边界（段落、标题、代码块、列表等）检测完整块
  3. 完整块通过 `glamour.Render()` 渲染后输出
  4. 流结束时 `Flush()` 剩余缓冲区

- **Phase 2**: 即时回显 + ANSI 擦除替换
  1. 先用 `lipgloss` 原样输出原始文本（即时回显）
  2. 当 glamour 渲染出完整块后，用 ANSI 擦除序列替换为格式化版本

## 测试

```bash
# 块边界检测单元测试
go test -v -run TestBlockBoundary ./internal/renderer/

# 行数追踪单元测试（Phase 2）
go test -v -run TestTrackRows ./internal/renderer/

# Glamour 渲染 Golden Test
go test -v -run TestGlamourGolden ./internal/renderer/

# TextRenderer 接口集成测试
go test -v -run TestMarkdownRenderer ./internal/renderer/
```

## 常见陷阱

- **围栏代码块内不检测块边界**: 代码块内容可能包含 `#`、`---` 等字符，在代码围栏内部不触发块边界
- **流结束时 Flush 剩余缓冲区**: `Flush()` 必须将 buffer 中剩余的不完整块也渲染输出
- **CJK 字符宽度**: Phase 2 中用 `go-runewidth` 计算 CJK 字符的实际终端宽度
- **ANSI 擦除序列**: 依赖终端宽度信息，通过 `golang.org/x/term` 获取和监听 SIGWINCH
