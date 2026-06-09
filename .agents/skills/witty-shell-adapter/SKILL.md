---
name: witty-shell-adapter
description: 开发 Shell Adapter 的 Bash 模板和 Go 桥接层。包括 witty init bash 模板、路由分类、history 管理、Readline 绑定。用于修改 Shell 接入行为时。
---

# Shell Adapter 开发

## 关键文件

- `internal/shellinit/bash.go` — Go 侧模板渲染入口
- `internal/shellinit/templates/witty.bash.tmpl` — Bash 模板（分隔符 `[[ ]]`）
- `internal/shellbridge/control.go` — Shell 路由分类逻辑
- `internal/shellbridge/history.go` — History 命令管理

## 开发流程

1. **修改 Bash 模板** (`witty.bash.tmpl`)
   - 模板分隔符必须使用 `[[ ]]`（不是 `{{ }}`）
   - Go 模板层通过 `Delims("[[", "]]")` 设置自定义分隔符
   - 修改后立即格式化：`shfmt -w -i 2 internal/shellinit/templates/*.bash.tmpl`

2. **验证格式化与静态检查**:

   ```bash
   shfmt -d -i 2 internal/shellinit/templates/*.bash.tmpl
   shellcheck internal/shellinit/templates/*.bash.tmpl
   ```

3. **运行 Golden Test**:

   ```bash
   go test -v -run TestBashInitGolden ./internal/shellinit/
   ```

   若模板变更需要更新 golden file:

   ```bash
   go test -v -run TestBashInitGolden -update ./internal/shellinit/
   ```

4. **运行 PTY 测试** (必须在 openEuler 环境中执行):

   在进入 openEuler 远程环境前，先直接读取 `shell/.agents/config.yaml`；不要先依赖 `find_path` 或目录扫描判断文件是否存在。该文件可能被 `.gitignore` 隐藏，但仍然真实存在。若直接读取失败，再回退参考 `shell/.agents/config.template.yaml`。

   ```bash
   go test -v -tags=pty ./test/pty/
   ```

## Bash 模板函数约定

模板中至少拆出以下函数:

- `__witty_should_enable` — 判断是否启用 witty
- `__witty_classify` — 分类输入（shell / agent / control）
- `__witty_pre_accept` — Enter 前 Hook
- `__witty_shell_dispatch` — Shell 命令分发
- `__witty_debug` — 调试输出
- `__witty_install_bindings` — 安装 Readline 绑定

## 强制约束

- 模板分隔符 `[[ ]]`
- Bash 函数前缀 `__witty_`
- 所有模板和脚本变更后 `shfmt -w -i 2`（2 空格缩进）
- 不在 Bash Hook 中执行长时间 AI 调用
- 不将 wrapper 命令暴露到 history

## 明确禁止

- 在 Go 中接管 Bash 交互式输入循环
- 将自然语言翻译为 shell 命令后偷偷执行
- 修改非 Bash Shell 的初始化（首版仅支持 Bash）
