# Bash 模板规则

## 强制约束

1. 模板分隔符必须是 `[[ ]]`，绝不能使用 `{{ }}`
2. 所有模板变更后必须运行 `shellcheck`
3. Bash 函数前缀 `__witty_`

`{{ }}` 分隔符的禁用原因：

- 与 Bash 变量语法 `${}` 的第 2-3 字符相同，容易冲突
- 与 Bash 花括号展开 `{a,b}` 产生歧义
- Go 模板层通过 `Delims("[[", "]]")` 自定义分隔符

## 验证命令

```bash
shellcheck internal/shellinit/templates/*.bash.tmpl
go test -v -run TestBashTemplate ./internal/shellinit/
```

## 禁止

- 在 Bash Hook 中执行长时间 AI 调用
- 暴露 wrapper 命令到 history
- 将自然语言翻译为 shell 命令后偷偷执行
- 修改非 Bash Shell（zsh, fish）的初始化（首版仅 Bash）
