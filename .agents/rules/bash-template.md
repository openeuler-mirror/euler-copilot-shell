# Bash 模板与 Shell 脚本规则

## 强制约束

1. 模板分隔符必须是 `[[ ]]`，绝不能使用 `{{ }}`
2. 所有模板和 Shell 脚本变更后必须运行 `shfmt -w -i 2`（统一 2 空格缩进）
3. 所有模板变更后必须运行 `shellcheck`
4. Bash 函数前缀 `__witty_`

`{{ }}` 分隔符的禁用原因：

- 与 Bash 变量语法 `${}` 的第 2-3 字符相同，容易冲突
- 与 Bash 花括号展开 `{a,b}` 产生歧义
- Go 模板层通过 `Delims("[[", "]]")` 自定义分隔符

## 格式化

**所有 shell 脚本和脚本模板在提交前必须通过 `shfmt` 格式化。**

```bash
# 格式化所有 shell 脚本和模板（2 空格缩进）
shfmt -w -i 2 internal/shellinit/templates/*.bash.tmpl
git ls-files '*.sh' | xargs shfmt -w -i 2

# 验证无残余差异
shfmt -d -i 2 internal/shellinit/templates/*.bash.tmpl
git ls-files '*.sh' | xargs shfmt -d -i 2
```

## 验证命令

```bash
shfmt -d -i 2 internal/shellinit/templates/*.bash.tmpl
shellcheck internal/shellinit/templates/*.bash.tmpl
go test -v -run TestBashTemplate ./internal/shellinit/
```

## 禁止

- 在 Bash Hook 中执行长时间 AI 调用
- 暴露 wrapper 命令到 history
- 将自然语言翻译为 shell 命令后偷偷执行
- 修改非 Bash Shell（zsh, fish）的初始化（首版仅 Bash）
- 提交未经 `shfmt -w -i 2` 格式化的 shell 脚本或模板
