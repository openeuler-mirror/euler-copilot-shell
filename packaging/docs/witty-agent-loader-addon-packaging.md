# witty-agent-loader Agent / Skill / 配置子包打包指南

这份文档面向**在其他仓库中维护自己 RPM 子包**的作者。

目标很简单：

- 子包只负责安装自己的 Agent / Skill / 配置资源
- `witty-agent-loader` 负责统一重建 `/etc/opencode/opencode.json` 与 `/etc/opencode/tui.json`
- 子包之间不要直接改写托管配置文件，也不要互相抢 ownership

一句话版本：**把资源放到约定目录，剩下的交给 loader 包。**

## 你应当依赖什么

建议子包至少依赖：

- `witty-agent-loader`

如果你的子包本身也要求 OpenCode CLI 一定存在，再额外依赖：

- `opencode`

常见做法：

- 纯数据子包（只放 Agent / Skill / config）：`Requires: witty-agent-loader`
- 功能强绑定 CLI 的子包：`Requires: witty-agent-loader`，必要时再加 `Requires: opencode`

## 子包允许写入的目录

请把内容安装到以下目录：

- `/usr/share/witty/opencode/config.d/<rpm-name>.json`
- `/usr/share/witty/opencode/agents/<rpm-name>/...`
- `/usr/share/witty/opencode/skills/<rpm-name>/...`

其中：

- `config.d` 存放**标准 `opencode.json` 片段**
- `agents/` 存放 Prompt Markdown 或其它被 `{file:...}` 引用的资源
- `skills/` 存放 Skill 目录树

## 子包不应该做什么

请不要在子包里做下面这些事：

- 不要拥有或直接安装 `/etc/opencode/opencode.json`
- 不要拥有或直接安装 `/etc/opencode/tui.json`
- 不要在 `%post` / `%postun` 里自己改 JSON
- 不要覆盖 `/usr/share/witty/opencode/plugins/logo/witty-logo.tsx`
- 不要假设自己是唯一的 Agent / Skill 提供者

这些操作会导致多包并存、升级和卸载时产生文件冲突或配置残留。

## 配置片段格式

`config.d/*.json` 必须是**标准 schema 兼容的 `opencode.json` 片段**。

示例：

```json
{
  "$schema": "https://opencode.ai/config.json",
  "agent": {
    "vendor/example": {
      "description": "Example agent shipped by an external RPM.",
      "mode": "subagent",
      "prompt": "{file:../agents/vendor-example/prompt.md}",
      "color": "#00AFFF"
    }
  },
  "mcp": {
    "vendor-example": {
      "enabled": false
    }
  }
}
```

注意事项：

- 相对 `{file:...}` 路径会以**当前 drop-in 文件所在目录**为基准解析
- 生成器会把这些路径改写成绝对路径再写入最终的 `/etc/opencode/opencode.json`
- 可以提供 `agent`、`mcp`、`provider`、`permission`、`command` 等标准字段
- 当前受保护的重复命名空间包括：`agent`、`command`、`mode`、`mcp`

建议始终使用带前缀的唯一名称，例如：

- `vendor/example`
- `suite:reviewer`

## 推荐的子包 spec 结构

大多数子包应该保持 **data-only**，也就是：

- 不写任何 `%post`
- 不写任何 `%postun`
- 不写任何 trigger
- 只在 `%install` 里安装资源文件

因为 `witty-agent-loader` 已经通过文件触发器监控这些目录；只要你的文件落到约定路径，事务结束后它就会自动重建托管配置。

一个最小化示例：

```spec
Name:           witty-opencode-agent-example
Version:        1.0.0
Release:        1
Summary:        Example Agent bundle for witty-opencode
License:        MIT
BuildArch:      noarch

Requires:       witty-agent-loader

%description
Example Agent / config bundle for witty-opencode.

%install
install -d %{buildroot}/usr/share/witty/opencode/config.d
install -d %{buildroot}/usr/share/witty/opencode/agents/%{name}
install -d %{buildroot}/usr/share/witty/opencode/skills/%{name}

install -m 0644 packaging/%{name}.json \
  %{buildroot}/usr/share/witty/opencode/config.d/%{name}.json

cp -a agents/. %{buildroot}/usr/share/witty/opencode/agents/%{name}/
cp -a skills/. %{buildroot}/usr/share/witty/opencode/skills/%{name}/

%files
/usr/share/witty/opencode/config.d/%{name}.json
/usr/share/witty/opencode/agents/%{name}
/usr/share/witty/opencode/skills/%{name}
```

## 什么时候才需要在子包里加 `%posttrans`

默认情况下，**不需要**。

只有在下面这种场景下，才考虑在子包里加入一个很薄的 `%posttrans` 回退：

- 目标发行版/策略不允许或不依赖 loader 包的 `transfiletrigger`
- 你的部署环境明确要求“每个子包自己确保事务完成后重建一次配置”

推荐的可选回退写法：

```spec
Requires(posttrans): witty-agent-loader

%posttrans
if [ -x /usr/libexec/witty-opencode/run-managed-config-hook.sh ]; then
  /usr/libexec/witty-opencode/run-managed-config-hook.sh addon-posttrans || :
fi
```

注意：

- 这是**回退方案**，不是默认方案
- 即便用了它，也不要自己写 JSON 合并逻辑
- 多个子包同时这样写时，通常也只是多次调用同一个共享 hook，而不是各自篡改配置

## 卸载语义

一个合格的子包应当做到：

- 安装时只增加自己的文件
- 卸载时只删除自己的文件
- 不留下对 `/etc/opencode/*.json` 的残留修改

也就是说，子包应尽量表现得像“声明式资源包”，而不是“事务脚本包”。

## 与 loader 包的契约边界

当你在外部仓库维护子包时，可以把下面这些看作稳定契约：

- 由 `witty-agent-loader` 负责托管 `/etc/opencode/opencode.json`
- 由 `witty-agent-loader` 负责托管 `/etc/opencode/tui.json`
- `skills.paths` 会指向 `/usr/share/witty/opencode/skills`
- `config.d` 片段会被聚合成标准 `opencode.json`
- 相对 `{file:...}` 会被改写为绝对路径

## 发布前自查清单

在发布自己的子包前，至少检查：

- 配置片段是否是合法 JSON
- 顶层字段是否符合 `opencode.json` schema
- `{file:...}` 是否都能在安装后解析到真实文件
- agent / mcp / command / mode 名称是否带唯一前缀
- spec 是否没有直接修改 `/etc/opencode/*.json`
- spec 是否没有覆盖 logo 插件

如果这些都满足，你的子包通常就能和其他维护者的包和平共处。
