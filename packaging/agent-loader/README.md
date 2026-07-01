# witty-agent-loader

本目录是 **`witty-agent-loader`** RPM 子包的源码（位于 `euler-copilot-shell` 仓库的 `packaging/agent-loader/` 下），该包负责将与 `opencode` CLI 配套的托管资源以系统方式部署。

## 特性

- `/etc/opencode/opencode.json` 和 `/etc/opencode/tui.json` 始终只由一个包负责
- 多个 Agent / Skill 子 RPM 可以干净地安装和卸载，互不干扰
- 安装或卸载子包时无需在脚本里逐包修改 JSON
- 首页 logo 只由 loader 包管理

## RPM 目录布局

- `/usr/share/witty/opencode/skills/<rpm-name>/...` —— 子 RPM 的 skill 资源
- `/usr/share/witty/opencode/agents/<rpm-name>/...` —— 子 RPM 的 prompt Markdown 及其他文件资源
- `/usr/share/witty/opencode/config.d/<rpm-name>.json` —— 子 RPM 提供的配置碎片（需符合 `opencode.json` schema）
- `/usr/share/witty/opencode/plugins/logo/witty-logo.tsx` —— loader 包持有的 logo 插件
- `/usr/libexec/witty-opencode/rebuild-managed-config.mjs` —— loader 包持有的配置生成器
- `/etc/opencode/opencode.json` —— 生成的托管主配置
- `/etc/opencode/tui.json` —— 生成的托管 TUI 配置

## 生成器工作原理

`bin/rebuild-managed-config.mjs` 扫描 `config.d/*.json`，将每个文件当作一份 `opencode.json` 配置碎片处理，把碎片中的相对路径 `{file:...}` 引用改写为绝对路径，最终写出：

- `opencode.json`：包含指向共享 skills 根目录的固定 `skills.paths` 条目，以及所有合并后的配置段（如 `agent`、`mcp`、`provider`、`permission`）
- `tui.json`：指向基础 RPM 的 logo 插件

生成器专为 `%posttrans` 或文件触发器设计，保证每次 RPM 事务只重建一次托管配置。

## RPM hook 脚本

Loader 包还附带两个辅助组件：

- `bin/run-managed-config-hook.sh` —— 供 RPM scriptlet 和文件触发器共用的 shell 封装脚本
- `../docs/witty-opencode-addon-packaging.md` —— 面向 Agent / Skill / 配置子 RPM 维护者的打包规范与 spec 编写指引，说明子包何时应保持纯数据包，何时可以加 `%posttrans` 兜底

### 为什么同时需要 `%posttrans` 和文件触发器？

- **Loader 包自身**安装或升级时，`%posttrans` 负责创建或刷新 `/etc/opencode/*.json`。
- **子 RPM 的安装与卸载**应使用 `%transfiletriggerin` 和 `%transfiletriggerpostun`：这两个触发器会在受管目录下的文件发生变动时自动触发，即使该次事务中并未涉及 loader 包。

这样子 RPM 只需打包数据文件，配置生成始终由 loader 包独自负责。

### 失败策略

共享 hook 默认是 **fail-open** 的：遇到错误时只记录日志、仍然返回成功，不会因为配置重建失败就让整个 RPM 事务中断。

如果更倾向于严格失败，请在调用 hook 之前设置 `WITTY_OPENCODE_RPM_HOOK_STRICT=1`。

## Drop-in 格式

格式示例见 `examples/config.d/witty-example.json`。

每个 drop-in 须是合法的 `opencode.json` 配置碎片：

- `$schema` 可省略，合并时会被忽略
- 可直接包含 `agent`、`mcp`、`provider`、`permission`、`command` 等顶层配置段
- 相对路径形式的 `{file:...}` token 按该 drop-in 文件所在目录解析，输出到 `/etc/opencode/opencode.json` 时会被改写为绝对路径

如果 `agent`、`command`、`mode`、`mcp` 等受管命名空间出现重名，生成器会在任何原子重命名操作发生前直接报错退出，保留原有配置不变。

## 本目录包含的文件

- `bin/rebuild-managed-config.mjs` —— 配置生成脚本
- `bin/run-managed-config-hook.sh` —— RPM hook 封装脚本
- `plugins/logo/witty-logo.tsx` —— logo 插件资源
- `docs/witty-opencode-base.md` —— 用户使用文档（打包时进 tarball）
- `examples/` —— 示例 drop-in 与 prompt 布局（不进 tarball）

子 RPM 打包规范见仓库中的 `packaging/docs/witty-agent-loader-addon-packaging.md`。
