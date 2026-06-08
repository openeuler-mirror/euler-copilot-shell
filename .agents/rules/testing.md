# 测试规则

## 测试类型

| 类型 | 命令 | 位置 |
| ---- | ---- | ---- |
| 单元测试 | `go test ./internal/<package>/` | `*_test.go` 与源文件同目录 |
| Golden Test | `go test -update` 更新快照 | `test/golden/` |
| PTY 集成测试 | `go test -v -tags=pty ./test/pty/` | `test/pty/` |
| 接口回归测试 | OpenAPI spec 更新后执行 | `internal/event/`, `internal/transport/` |

## 关键规则

- PTY 测试强制 `TERM=xterm-256color`
- PTY 测试**必须**在 openEuler 环境中运行（不能在 macOS 上跑，依赖 Bash 5.x + readline）
- 测试数据放在 `test/testdata/` 目录
- 覆盖率目标: 核心模块 > 80%
- 每次代码修改后运行: `go test -count=1 ./...`
- Golden Test 快照更新需人工确认变更合理性

## 测试编写约定

- 测试函数命名: `Test<Function>_<Scenario>`
- 优先使用 table-driven tests
- 外部依赖（网络、文件系统）必须 mock
- 并发测试必须使用 `-race` flag 验证
