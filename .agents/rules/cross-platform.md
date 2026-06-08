# 跨平台开发约束

## 核心原则

**开发环境自由，交付平台唯一。**

- 开发可在 macOS / Windows 进行
- 所有测试**最终必须在 openEuler 上通过**

## 典型工作流

1. 本地编写 Go 代码 → 本地 `go build`, `go test`（快速反馈）
2. 推送到 openEuler 环境进行最终验证
3. PTY 测试、RPM 验证必须在 openEuler 环境中运行

Agent 通过 `.agents/config.yaml` 获知如何连接 openEuler 环境（OrbStack / WSL / SSH）。

## 禁止

- 依赖 macOS 特定 API（如 `syscall.Mkfifo` 行为差异）
- 假设 `/tmp` 可执行（openEuler 可能挂载 noexec）
- 使用 openEuler 不支持的 kernel 特性
