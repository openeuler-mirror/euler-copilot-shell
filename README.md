# Witty Assistant 命令行客户端

Witty Assistant 是 openEuler Intelligence 旗下的一款 OS 智能助手。Witty Assistant 的命令行客户端提供 AI 驱动的命令行交互体验，支持多种 LLM 后端，集成 MCP 协议，提供现代化的 TUI 界面。

## 核心特性

- **智能终端界面**: 基于 Textual 的现代化 TUI 界面
- **流式响应**: 实时显示 AI 回复内容
- **部署助手**: 内置 Witty Assistant 后端服务（sysAgent）自动部署功能
- **配置管理**: 内置设置界面（`Ctrl+S`）与本地配置文件，便于切换后端/更新连接信息

## 安装说明

### 方式一：从源码安装（推荐开发者）

1. 克隆仓库:

   ```sh
   git clone https://atomgit.com/openeuler/euler-copilot-shell.git -b dev
   cd euler-copilot-shell
   ```

2. 安装依赖（建议使用 Python 虚拟环境）:

   ```sh
   uv venv --python 3.11 .venv
   source .venv/bin/activate
   uv pip install -e '.[dev]'
   ```

### 方式二：通过 RPM 包安装

注意：*仅适用于 openEuler 24.03 LTS SP3*

```sh
sudo dnf install witty-assistant
```

安装完成后，可以使用 `witty` 命令启动应用程序（RPM 会安装 `witty-assistant` 可执行文件，并提供 `witty` 快捷命令）。

## 使用方法

安装 RPM 包后:

```sh
witty
```

查看最新的日志内容:

```sh
witty logs
```

设置日志级别并验证:

```sh
witty set-default log-level INFO
```

初始化 sysAgent（仅支持 openEuler 操作系统）:

```sh
witty init
```

选择和设置默认智能体（仅适用于 sysAgent）:

```sh
witty set-default agent
```

应用启动后，您可以直接在输入框中输入命令。如果命令无效或无法执行，应用程序将基于您的输入提供智能建议。

### 界面操作快捷键

- **Ctrl+S**: 打开设置屏幕，方便切换后端、更新 API Key 或配置默认模型
- **Ctrl+R**: 重置当前对话历史并回到欢迎界面
- **Ctrl+T**: 弹出智能体选择界面（仅在后端为 sysAgent 且已连接时启用）
- **Tab**: 在命令输入框和输出区域之间切换焦点，方便查看历史输出并复制文本
- **Ctrl+C**: 取消当前正在执行的任务（中断 LLM 请求或停止执行命令）
- **Ctrl+Q**: 退出程序并关闭 TUI

### MCP 工具交互

当使用支持 MCP (Model Context Protocol) 的后端时，应用程序会在需要工具确认或参数输入时：

1. **工具执行确认**: 显示工具名称、风险级别和执行原因，用户可选择确认或取消
2. **参数补全**: 动态生成参数输入表单，用户填写必要信息后提交

应用程序使用内联交互模式，不会打开模态对话框，确保流畅的用户体验。

### `witty init` 命令说明

`witty init` 会启动“部署助手”TUI，用于在 openEuler 系统上引导式安装/配置 sysAgent（以及相关组件）。
命令本身会先检查并自动补全本地配置文件，然后进入部署界面。

**使用要求**:

- 面向 openEuler 场景（部署流程会做系统/环境检查）
- 部署过程中需要管理员权限（sudo）
- 部署/拉取依赖时需要网络连接

**注意**:

1. 此命令会自动安装系统服务，请在生产环境使用前仔细评估；
2. 如果需要重启或卸载 sysAgent，请以管理员身份运行 `witty-manager` 并根据指引操作；
3. `witty-manager` 的卸载功能会清空机器上 PostgreSQL 的全部数据并重置 nginx 服务，请谨慎操作。

### `witty set-default agent` 命令说明

`witty set-default agent` 命令用于在命令行中选择并设置默认智能体，它提供一个 TUI 界面来管理智能体配置：

1. **智能体列表**: 自动获取并显示所有可用的智能体
2. **可视化选择**: 通过图形化界面选择要设置为默认的智能体
3. **配置保存**: 自动将选择保存到配置文件中的 `witty.default_app` 字段
4. **即时反馈**: 设置完成后显示确认信息

**使用要求**:

- 仅在后端为 sysAgent 时可用（否则会提示先启动 `witty` 并在设置界面切换后端）
- 需要能连接到 sysAgent 才能拉取智能体列表

**功能特点**:

- 包含"智能问答"选项（无智能体）作为默认选择
- 支持取消操作，不会更改现有配置
- 自动处理网络错误和异常情况

### `witty llm` 命令说明

`witty llm` 会启动一个管理员用的 TUI 配置工具，用于**管理 sysAgent 的模型配置**（增/删/改/查）。
它通过 sysAgent 的模型管理接口生效，并在保存变更后尝试重启服务。

支持配置项（以界面字段为准）：

1. **模型基础信息**：`llm_id`、描述（`llm_description`）
2. **能力开关**：Chat / Function Call / Embedding / Vision / Thinking
3. **提供商与连接信息**：Provider、`base_url`、`api_key`、`model_name`
4. **推理参数**：`ctx_length`、`max_tokens`
5. **扩展参数**：`extra_data`（JSON）

保存变更后：

- 若系统存在 `systemctl`，会尝试执行 `systemctl restart sysagent` 使配置生效
- 若未找到 `systemctl`，会跳过重启并给出提示（不影响保存结果）

**使用要求**:

- 仅适用于已部署的 sysAgent
- 需要管理员权限运行（会检查 `euid`，非 root 会提示使用 `sudo witty llm`）
- 需要能与 sysAgent 通信（以便读取/写入模型配置）

**功能特点**:

- 支持新增/编辑/删除模型配置
- 支持用复选框组合模型能力标签（Chat/Function/Embedding/Vision/Thinking）
- 支持额外参数 JSON（便于扩展 provider 特有参数）

**注意**:

1. 保存后可能会触发重启 `sysagent` 服务，可能影响正在运行的请求；
2. 若以非 root 用户运行会直接退出并提示使用 `sudo witty llm`；
3. 建议在生产环境变更前做好变更评审与回滚预案。

## Shell Completion

Witty Assistant 支持为 Bash / Zsh / Fish 安装补全脚本：

- Bash：

  ```sh
  witty completion bash
  ```

- Zsh：

  ```sh
  witty completion zsh
  ```

- Fish：

  ```sh
  witty completion fish
  ```

这会将补全脚本安装到用户级的默认目录（遵循 XDG 规范）。安装完成后，您可能需要重新启动 shell 或重新加载配置以使补全生效。

如果未指定 shell，Witty 会尝试自动检测当前 shell。

对于系统级安装（RPM 包），补全脚本会自动安装到标准位置。

## 国际化支持

应用程序内置多语言支持，提供英文和中文界面。

### 支持的语言

- **English (en_US)** - 默认语言
- **简体中文 (zh_CN)**

### 切换语言

```sh
# 切换到中文
witty set-default locale zh_CN

# 切换到英文
witty set-default locale en_US
```

语言设置会自动保存，下次启动时生效。

### 语言自动检测

应用启动时会按以下优先级确定显示语言：

1. 用户配置文件中的语言设置
2. 系统环境变量（`LANG`, `LC_ALL` 等）
3. 默认语言（英语）

如果系统语言为中文，首次运行时会自动使用中文界面。

### 开发者文档

如需为应用程序添加新的翻译或了解国际化实现细节，请参考：

- [国际化快速入门](./docs/development/国际化快速入门.md)
- [国际化开发指南](./docs/development/国际化开发指南.md)

## 配置说明

应用程序支持两种后端配置，配置文件会自动保存在 `~/.config/witty/config.json`：

### 后端类型

1. **OpenAI 兼容 API** (包括 LM Studio、vLLM、Ollama 等)
2. **sysAgent**

### 配置示例

首次运行时，可通过设置界面 (Ctrl+S) 配置以下参数：

**OpenAI 兼容 API 配置:**

- Base URL: 如 `http://localhost:1234/v1`
- Model: 如 `qwen/qwen3-30b-a3b`
- API Key: 如 `sk-xxxxxx`

**sysAgent 配置:**

- Base URL: 如 `http://your-server:8002`
- API Key: 您的认证令牌

### 智能体管理

对于 sysAgent，应用程序支持多智能体切换：

1. **默认智能问答**: 通用 AI 助手
2. **专业智能体**: 针对特定领域的专门助手

使用 `Ctrl+T` 可以在运行时切换不同的智能体。

#### 默认智能体配置

应用程序支持配置默认启动的智能体：

- **默认智能体配置**: 决定应用启动时激活哪个智能体，持久保存
- **运行时智能体切换**: 在当前会话中临时切换智能体，不影响默认配置

##### 方式一：命令行（修改默认配置）

```sh
witty set-default agent
```

通过图形化界面选择默认智能体，选择会自动保存到配置文件。

##### 方式二：手动修改配置文件（不推荐）

直接编辑配置文件 `~/.config/witty/config.json`，修改 `witty.default_app` 字段的值：

- 设置为空字符串 `""` 或删除该字段：使用"智能问答"（没有调用工具的能力）
- 设置为有效的智能体ID：使用指定的智能体作为默认
- 设置为无效的智能体ID：应用启动时会自动清理并回退到"智能问答"

##### 配置详情

- **配置位置**: `~/.config/witty/config.json` 中的 `witty.default_app` 字段
- **默认行为**: 如果未设置或为空，将默认使用"智能问答"（通用助手）
- **自动应用**: 应用启动时会自动加载配置的默认智能体
- **自动清理**: 如果配置的智能体ID不存在（如服务器数据更改），会自动清理配置并回退到"智能问答"

**配置示例**:

```json
{
  "backend": "witty",
  "witty": {
    "base_url": "http://your-server:8002",
    "api_key": "your-api-key",
    "default_app": "your-preferred-agent-id"
  }
}
```

### 日志配置

应用程序提供多级日志记录：

- **DEBUG**: 详细调试信息（默认）
- **INFO**: 基本信息
- **WARNING**: 警告信息
- **ERROR**: 仅错误信息

## 日志功能

应用程序提供完整的日志记录功能：

- **日志位置**: `~/.cache/witty/logs/`
- **日志格式**: `witty-assistant-YYYYMMDD-HHMMSS.log`（使用本地时区时间）
- **自动清理**: 每次启动时自动删除7天前的旧日志和空日志文件
- **命令行查看**: 使用 `witty logs` 查看最新日志内容（可通过 `-n/--lines` 控制行数）
- **记录内容**:
  - 程序启动和退出
  - API请求详情（URL、状态码、耗时等）
  - 异常和错误信息
  - 模块级别的操作日志

## 系统要求

### 基本要求

- **Python**: 3.11 或更高版本
- **操作系统**: openEuler 24.03 LTS SP3 或更高版本
- **网络**: 访问配置的 LLM API 服务

### 依赖包

核心依赖：

- **textual**: 6.6.0 - TUI 界面框架
- **rich**: 14.2.0 - 富文本渲染
- **httpx**: 0.28.1 - HTTP 客户端
- **openai**: 2.8.0 - OpenAI API 客户端
- **pyyaml**: 6.0.3 - YAML 解析
- **toml**: 0.10.2 - TOML 解析

开发依赖：

- **ruff**: *Latest* - 代码检查器
- **textual-dev**: *Latest* - Textual 开发工具
- **pytest**: *Latest* - 测试框架
- **pytest-asyncio**: *Latest* - 异步测试支持
- **pytest-cov**: *Latest* - 覆盖率检查工具

### 特殊功能要求

**自动部署功能（`witty init` 命令）**:

- 仅支持 openEuler 操作系统
- 需要管理员权限（sudo）
- 需要 dnf 包管理器
- 需要网络连接

## 在 openEuler 系统下的 RPM 打包

以下步骤演示如何在 openEuler 24.03 LTS SP3 或更高版本上，使用自带脚本打包生成 RPM 包。

前提条件：

- 操作系统：openEuler 24.03 LTS SP3 或更高版本
- 工具依赖：rpmdevtools、git、bash
- 具有管理员权限（sudo）

构建步骤：

1. 克隆仓库并切换到对应分支：

   ```sh
   git clone https://atomgit.com/openeuler/euler-copilot-shell.git -b dev
   cd euler-copilot-shell
   ```

2. 为构建脚本添加可执行权限：

   ```sh
   chmod +x scripts/build/create_tarball.sh scripts/build/build_rpm.sh
   ```

3. 运行 RPM 构建脚本：

   ```sh
   ./scripts/build/build_rpm.sh
   ```

   脚本执行完成后，会在临时构建目录下的 `RPMS` 和 `SRPMS` 子目录中生成相应的二进制包和源码包，并在终端输出具体路径。

## 项目结构

```text
witty-assistant/
├── LICENSE                       # 开源许可证
├── MANIFEST.in                   # Python 包清单文件
├── README.md                     # 项目说明文档
├── pyproject.toml                # 项目配置与依赖（由 uv 管理）
├── pytest.ini                    # pytest 配置文件
├── requirements.txt              # pip 兼容依赖列表（使用 uv export 生成）
├── uv.lock                       # uv 生成的锁定文件
├── witty-assistant.spec          # RPM 打包规格文件
├── build/                        # 构建输出目录
├── distribution/                 # 发布相关文件
├── docs/                         # 项目文档目录
│   ├── development/              # 开发设计文档
│   │   ├── design/               # 设计文档
│   │   └── i18n/                 # 国际化文档
│   └── resource/                 # 文档资源
├── scripts/                      # 部署脚本目录
│   ├── build/                    # RPM 包构建脚本
│   ├── deploy/                   # 自动化部署脚本
│   │   ├── deploy.sh             # 部署脚本入口
│   │   ├── 0-one-click-deploy/   # 一键部署脚本
│   │   ├── 1-check-env/          # 环境检查脚本
│   │   ├── 2-install-dependency/ # 依赖安装脚本
│   │   ├── 3-install-server/     # 服务安装脚本
│   │   └── resources/            # 部署资源
│   └── tools/                    # 工具脚本
│       ├── coverage_report.py    # 覆盖率报告工具
│       ├── filter_debug_log.py   # 日志过滤工具
│       ├── i18n-manager.sh       # 国际化管理脚本
│       └── uninstaller.sh        # 卸载脚本
├── src/                          # 源代码目录
│   ├── __version__.py            # 版本信息
│   ├── main.py                   # 应用程序入口点
│   ├── app/                      # TUI 应用模块
│   │   ├── logo.py               # 应用 LOGO
│   │   ├── mcp_widgets.py        # MCP 交互组件
│   │   ├── settings.py           # 设置界面
│   │   ├── tui.py                # 主界面应用类
│   │   ├── tui_header.py         # TUI 头部组件
│   │   ├── tui_mcp_handler.py    # MCP 事件处理器
│   │   ├── css/                  # 样式文件
│   │   │   └── styles.tcss       # TUI 样式文件
│   │   ├── deployment/           # 部署助手模块
│   │   │   ├── agent.py          # 智能体部署管理
│   │   │   ├── models.py         # 部署配置模型
│   │   │   ├── service.py        # 部署服务逻辑
│   │   │   ├── ui.py             # 部署界面组件
│   │   │   └── components/       # 部署组件模块
│   │   └── dialogs/              # 对话框组件
│   │       ├── agent.py          # 智能体选择对话框
│   │       └── common.py         # 通用对话框组件
│   ├── backend/                  # 后端适配模块
│   │   ├── base.py               # 后端客户端基类
│   │   ├── factory.py            # 后端工厂类
│   │   ├── mcp_handler.py        # MCP 事件处理接口
│   │   ├── models.py             # 数据模型
│   │   ├── openai.py             # OpenAI 兼容客户端
│   │   └── hermes/               # sysAgent 客户端
│   │       ├── client.py         # sysAgent API 客户端
│   │       ├── constants.py      # 常量定义
│   │       ├── exceptions.py     # 异常类定义
│   │       ├── mcp_helpers.py    # MCP 事件辅助工具
│   │       ├── models.py         # 数据模型
│   │       ├── stream.py         # 流式响应处理
│   │       └── services/         # 服务层组件
│   ├── config/                   # 配置管理模块
│   │   ├── manager.py            # 配置管理器
│   │   └── model.py              # 配置数据模型
│   ├── i18n/                     # 国际化模块
│   │   ├── manager.py            # 国际化管理器
│   │   └── locales/              # 语言包
│   ├── log/                      # 日志管理模块
│   │   └── manager.py            # 日志管理器
│   └── tool/                     # 工具模块
│       ├── command_processor.py  # 命令处理器
│       ├── completion.py         # Shell 补全功能
│       ├── oi_backend_init.py    # 后端初始化工具
│       ├── oi_llm_config.py      # LLM 配置管理工具
│       ├── oi_select_agent.py    # 智能体选择工具
│       └── validators.py         # 配置验证器
└── tests/                        # 测试文件目录
    ├── README.md                 # 测试说明文档
    ├── conftest.py               # pytest 配置
    ├── app/                      # 应用模块测试
    ├── backend/                  # 后端模块测试
    ├── config/                   # 配置模块测试
    ├── i18n/                     # 国际化模块测试
    ├── log/                      # 日志模块测试
    └── tool/                     # 工具模块测试
```

## 贡献

欢迎贡献代码！请随时提交 PR 或开启问题讨论任何功能增强或错误修复建议。

## 相关文档

### 开发文档

- [项目整体设计](docs/development/项目整体设计.md) - 系统架构和整体设计方案
- [TUI应用模块设计](docs/development/TUI应用模块设计.md) - 用户界面模块设计
- [后端适配模块设计](docs/development/后端适配模块设计.md) - 多后端支持架构
- [部署助手模块设计](docs/development/部署助手模块设计.md) - 自动部署功能设计
- [配置管理模块设计](docs/development/配置管理模块设计.md) - 配置管理系统设计
- [日志管理模块设计](docs/development/日志管理模块设计.md) - 日志记录系统设计

### 部署文档

- [安装部署手册](scripts/deploy/安装部署手册.md) - 详细的部署指南

## 开源许可

本项目采用 MulanPSL-2.0 许可证。详细信息请参见 [LICENSE](LICENSE) 文件。
