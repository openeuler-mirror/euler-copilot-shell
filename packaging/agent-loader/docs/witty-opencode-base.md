# witty-agent-loader 使用说明

`witty-agent-loader` 是 `euler-copilot-shell` 软件包内与 `opencode` CLI 配套的 loader 子包，负责把 **RPM 安装的 Agent / Skill / Plugin 套组** 和 OpenCode 的托管配置衔接起来。

它不提供 OpenCode CLI 本体，而是提供：

- `/etc/opencode/opencode.json` 的托管生成逻辑
- 标准 `opencode.json` 配置片段聚合器
- RPM 事务钩子（`%posttrans` / `%transfiletrigger*`）

## 安装关系

典型安装方式：

- `opencode`：CLI 本体
- `witty-agent-loader`：托管配置 loader
- `witty-opencode-agent-*` / `witty-opencode-skill-*`：各个功能套组子包

`witty-agent-loader` 应与 `opencode` 一起安装；后续 Agent / Skill 子包可以按需增删。

## Loader 包安装后的目录

Loader 包安装后会提供并拥有以下目录与文件：

- `/usr/libexec/witty-opencode/rebuild-managed-config.mjs`
- `/usr/libexec/witty-opencode/run-managed-config-hook.sh`
- `/usr/share/witty/opencode/config.d/`
- `/usr/share/witty/opencode/agents/`
- `/usr/share/witty/opencode/skills/`
- `/usr/share/witty/opencode/plugins/`
- `/etc/opencode/opencode.json`（生成文件）

其中 `/etc/opencode/opencode.json` 为**生成产物**，不建议手工维护。若管理员需要追加自定义配置，建议通过用户级或项目级 OpenCode 配置覆盖，而不是直接编辑托管生成文件。

## 子包如何接入

### Skill 子包

Skill 子包只需要把内容安装到：

- `/usr/share/witty/opencode/skills/<rpm-name>/...`

因为 loader 包生成的 `opencode.json` 会固定包含：

- `skills.paths = ["/usr/share/witty/opencode/skills"]`

所以下次启动 OpenCode 时，新安装或卸载的 Skill 目录会自动进入或退出可见集合。

### Agent / 配置子包

每个子包都可以提供一个或多个**标准 `opencode.json` 片段**，安装到：

1. 配置片段：
   - `/usr/share/witty/opencode/config.d/<rpm-name>.json`
2. 若配置中使用文件引用，例如 Agent 的 Prompt 文件，须提供对应资源文件，例如：
   - `/usr/share/witty/opencode/agents/<rpm-name>/...`

配置片段示例：

```json
{
  "$schema": "https://opencode.ai/config.json",
  "agent": {
    "witty/example": {
      "description": "Example agent shipped by a sub-RPM.",
      "mode": "subagent",
      "prompt": "{file:../agents/witty-example/prompt.md}",
      "color": "#00AFFF"
    }
  },
  "mcp": {
    "witty-example": {
      "enabled": false
    }
  }
}
```

子包可以附带标准 schema 中的多种配置，例如：

- `agent`
- `mcp`
- `provider`
- `permission`
- `command`
- `plugin`
- 以及其它允许出现在 `opencode.json` 中的字段

生成器会把片段中的相对 `{file:...}` 引用按 **drop-in 文件所在目录** 解析并改写为绝对路径，然后再合成最终的 `/etc/opencode/opencode.json`。

### Plugin 子包

子包可以通过 config.d 碎片的 `plugin` 字段声明需要加载的 OpenCode Plugin。`plugin` 是一个字符串数组，支持 `file://` 形式的本地文件路径或 npm 包名。生成器会将多个子包的 `plugin` 条目去重合并到 `/etc/opencode/opencode.json`。

Plugin 文件本身可安装到 `/usr/share/witty/opencode/plugins/<rpm-name>/`，也可放在子包自有路径（如 `/usr/lib/<rpm-name>/vendor/`）。

配置片段示例：

```json
{
  "plugin": [
    "file:///usr/lib/witty-opencode-agent-example/vendor/dist/index.js",
    "file:///usr/share/witty/opencode/plugins/witty-opencode-agent-example/bootstrap.js"
  ]
}
```

`plugin` 字段不在冲突命名空间中（冲突命名空间为 `agent`、`command`、`mode`、`mcp`），多个子包可以各自声明自己的 plugin 条目。

## 安装、升级、卸载时发生什么

Loader 包在 spec 中使用两类 RPM 钩子：

- `%posttrans`
- `%transfiletriggerin`
- `%transfiletriggerpostun`

行为如下：

1. **安装/升级 loader 包本身**时，`%posttrans` 会重建托管配置。
2. **安装新的 Agent / Skill / Plugin / 配置子包**时，只要事务中有文件落到受监控目录下，`%transfiletriggerin` 就会在事务结束后统一重建一次配置。
3. **卸载 Agent / Skill / Plugin / 配置子包**时，`%transfiletriggerpostun` 会在事务结束后统一重建一次配置。

这样可以避免每个子包在 `%post` / `%postun` 里各自修改 JSON，减少文件冲突和卸载残留。

对于放在**其他仓库**、由其他维护者单独发布的子包，推荐把 spec 编写约定视为一份稳定的"打包契约"，而不是复用本仓库里的 spec 片段。请直接参考：

- `packaging/docs/witty-agent-loader-addon-packaging.md`

这份文档说明了子包应该安装哪些路径、需要依赖哪些基座能力、何时保持 data-only、何时才添加可选的 `%posttrans` 回退逻辑。

## 冲突处理

如果两个子包声明了相同的受管理命名空间条目（当前包括 `agent`、`command`、`mode`、`mcp`），生成器会直接报错并拒绝覆盖。对 agent 名称，建议子包使用带命名空间的名称，例如：

- `vendor/name`
- `suite:name`

`plugin` 字段不受冲突检测约束，多个子包声明的 plugin 条目会被去重合并。

## 打包说明（Loader 包维护者）

`witty-agent-loader` 的源码位于 `euler-copilot-shell` 仓库的 `packaging/agent-loader/` 下。发布准备由 `packaging/scripts/prepare-release.sh` 负责生成 Source4 tarball：

```bash
bash packaging/scripts/prepare-release.sh <version>
```

该脚本会把 `packaging/agent-loader/`（排除 `examples/`）和仓库根 `LICENSE` 打包为 `witty-agent-loader-<version>.tar.gz`，放入 `build/release/`。

然后由 `packaging/euler-copilot-shell.spec` 在 `%prep` 阶段解包到独立目录，并在 `%install` 阶段安装：

- Loader 包 license（来自项目根目录 `LICENSE`）
- libexec 脚本
- 受管目录（config.d、agents、skills、plugins）
- 文档

对于 Skill / Agent 子包，请参考 [Agent / Skill / 配置子包打包指南](witty-agent-loader-addon-packaging.md)，以及示例 `packaging/agent-loader/examples/`。
