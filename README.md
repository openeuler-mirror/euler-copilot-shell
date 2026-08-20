# Witty CLI

Witty CLI 是 openEuler 终端场景下的 AI 助手 CLI。单二进制 + Bash Shell Adapter + SSE 流式传输，基于 opencode HTTP Server 提供会话、渲染、权限与展示能力。

目标平台：openEuler 24.03 LTS（x86_64 / aarch64），`CGO_ENABLED=0`。

## 功能

- Shell 直输：在 Bash 提示符直接输入自然语言即可触发 AI 助手
- REPL 交互：运行 `witty` 进入交互式 CLI
- 自动管理 `opencode serve` 生命周期（自动启动、健康检测、闲置超时停止、多用户安全隔离）
- 环境诊断：`witty doctor` 一键检查配置、server、Shell 集成与终端环境

## 环境要求

- Go 1.26+
- OpenCode 1.17+（运行期依赖；未安装时 `witty doctor` 会提示）
- Bash >= 4.0（Shell 直输功能需要）

## 构建

```bash
bash scripts/build.sh
```

产物输出到 `build/<GOOS>-<GOARCH>/witty` 与 `build/<GOOS>-<GOARCH>/wittyd`，具体路径以脚本输出为准。

## 测试

```bash
go test -count=1 ./...

# PTY 集成测试（需在 openEuler 环境执行）
TERM=xterm-256color go test -v -tags=pty ./test/pty/

# 集成测试（需要 127.0.0.1:4096 的 opencode server，不可达时自动跳过）
go test -v -tags=integration ./test/integration/
```

## 快速使用

```bash
witty version            # 验证安装
witty                    # 进入 REPL
witty ask "检查系统内存"  # 单次提问
witty doctor             # 环境诊断
eval "$(witty init bash)"  # 手动启用 Shell 集成
```

## 文档

- 完整使用文档：[docs/usage.md](docs/usage.md)
- 设计文档：[docs/design/](docs/design/)
- 开发文档：[docs/development/](docs/development/)

## RPM 打包

在 openEuler 环境执行：

```bash
rpmbuild -ba packaging/euler-copilot-shell.spec
```
