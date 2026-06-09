# Git 工作流规则

## 分支命名

- `feat/<描述>` — 新功能
- `fix/<描述>` — 修复
- `chore/<描述>` — 杂务（构建、依赖更新、文档）

## 提交信息格式

```text
<module>: <简短描述>
```

示例:

- `transport: fix SSE reconnect race condition`
- `renderer: handle CJK character width in block boundary detection`
- `shellinit: update bash template for openEuler 24.03`
- `config: add koanf loader for TOML files`

## PR 规范

- 一个 PR 一个逻辑变更，不捆绑无关修复
- 必须包含对应的测试更新
- 通过所有质量门禁后合并（见 `witty-build` Skill）
- PR 标题与提交信息格式一致

## 禁止

- Force push 到 main 或 protected branches
- 提交包含 secrets、token、credentials 的文件
- 提交 `.agents/config.yaml`
- 提交未格式化的代码（先运行 `go fmt ./...` 和 `shfmt -w -i 2` 对 shell 脚本）
