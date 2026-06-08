---
name: witty-module
description: 在 internal/ 下创建新的 Go 模块。遵循标准模块结构，包含接口定义、构造函数和 wiring 注入。用于新增 internal 子包时。
---

# 模块创建与脚手架

## 标准模块结构

每个 internal 模块必须包含:

- `<module>.go` — 核心接口定义与实现
- `<module>_test.go` — 单元测试（与源文件同目录）
- 可选: `errors.go` — 模块专属错误类型

## 创建步骤

1. 在 `internal/<module>/` 下创建包目录
2. 定义导出接口（从消费方视角设计）
3. 实现接口，构造函数 `New<Type>` 返回接口类型
4. 在 `internal/app/wiring.go` 中注册依赖
5. 编写 `_test.go`（覆盖核心路径和错误路径）

## 命名约定

- 包名: 小写单词（如 `shellbridge`，不是 `shell_bridge`）
- 构造函数: `New<Type>`
- 接口命名: 单方法接口用 `-er` 后缀（如 `Renderer`），多方法接口用名词（如 `Client`）

## 检查清单

- [ ] 包名与目录名一致（小写单词）
- [ ] 构造函数 `New<Type>` 返回接口类型而非具体类型
- [ ] 接口定义在消费方包中
- [ ] 无循环依赖（`go vet ./...` 通过）
- [ ] `go build ./cmd/witty` 通过
- [ ] `go test ./internal/<module>/` 通过（覆盖率 > 80%）
- [ ] wiring.go 已更新
