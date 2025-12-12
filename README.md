# Witty Assistant

Witty Assistant 是 openEuler AI 助手的命令行客户端，提供 AI 驱动的命令行交互体验。支持多种 LLM 后端，集成 MCP 协议，提供现代化的 TUI 界面。

## 核心特性

- **智能终端界面**: 基于 Textual 的现代化 TUI 界面
- **流式响应**: 实时显示 AI 回复内容
- **部署助手**: 内置 Witty Assistant 后端服务（sysAgent）自动部署功能
- **一键认证**: 提供浏览器登录流程，自动获得并保存 API Key

## 安装说明

### 方式一：从源码安装（推荐开发者）

1. 克隆仓库:

   ```sh
   git clone https://gitee.com/openeuler/euler-copilot-shell.git -b dev
   cd euler-copilot-shell
   ```

2. 安装依赖（建议使用 Python 虚拟环境）:

  ```sh
  uv venv --python 3.11 .venv
  source .venv/bin/activate
  uv pip install -e '.[dev]'
  ```

### 方式二：通过 RPM 包安装

注意：*仅适用于 openEuler 24.03 LTS SP2*

```sh
sudo dnf install witty-assistant
```

安装完成后，可以使用 `oi` 命令启动应用程序。

## 使用方法

安装 RPM 包后:

```sh
oi
```

查看最新的日志内容:

```sh
witty --logs
```

设置日志级别并验证:

```sh
witty --log-level INFO
```

初始化 sysAgent（仅支持 openEuler 操作系统）:

```sh
witty --init
```

选择和设置默认智能体（仅适用于 sysAgent）:

```sh
witty --agent
```

通过浏览器登录并自动保存 API Key（需要已配置的 sysAgent）:

```sh
witty --login
```

运行前请确保运行环境具备图形界面并能启动默认浏览器；在无图形界面的场景下可使用 X11 转发或直接在目标服务器上执行该命令。

应用启动后，您可以直接在输入框中输入命令。如果命令无效或无法执行，应用程序将基于您的输入提供智能建议。

### 界面操作快捷键

- **Ctrl+S**: 打开设置界面
- **Ctrl+R**: 重置对话历史
- **Ctrl+T**: 选择智能体
- **Tab**: 在命令输入框和输出区域之间切换焦点
- **Esc**: 退出应用程序

### MCP 工具交互

当使用支持 MCP (Model Context Protocol) 的后端时，应用程序会在需要工具确认或参数输入时：

1. **工具执行确认**: 显示工具名称、风险级别和执行原因，用户可选择确认或取消
2. **参数补全**: 动态生成参数输入表单，用户填写必要信息后提交

应用程序使用内联交互模式，不会打开模态对话框，确保流畅的用户体验。

### `--init` 命令说明

`--init` 命令用于在 openEuler 操作系统上自动安装和配置 sysAgent，它将执行以下步骤：

1. **系统检测**: 检测当前操作系统是否为 openEuler
2. **环境检查**: 验证 dnf 包管理器和管理员权限
3. **包安装**: 通过 dnf 安装 `witty-assistant-installer` RPM 包
4. **服务部署**: 运行部署脚本完成系统初始化

**使用要求**:

- 仅支持 openEuler 操作系统
- 需要管理员权限（sudo）
- 需要网络连接以下载 RPM 包

**注意**:

1. 此命令会自动安装系统服务，请在生产环境使用前仔细评估；
2. 如果需要重启或卸载 sysAgent，请以管理员身份运行 `witty-manager` 并根据指引操作；
3. `witty-manager` 的卸载功能会清空机器上 MongoDB 和 PostgreSQL 的全部数据并重置 nginx 服务，请谨慎操作。

### `--agent` 命令说明

`--agent` 命令用于在命令行中选择和设置默认智能体，它提供了一个 TUI 界面来管理智能体配置：

1. **智能体列表**: 自动获取并显示所有可用的智能体
2. **可视化选择**: 通过图形化界面选择要设置为默认的智能体
3. **配置保存**: 自动将选择保存到配置文件中的 `witty.default_app` 字段
4. **即时反馈**: 设置完成后显示确认信息

**使用要求**:

- 必须配置为 sysAgent
- 需要有效的服务器连接来获取智能体列表
- 如果后端不是 sysAgent，会显示错误提示并引导切换

**功能特点**:

- 包含"智能问答"选项（无智能体）作为默认选择
- 支持取消操作，不会更改现有配置
- 自动处理网络错误和异常情况

### `--llm-config` 命令说明

`--llm-config` 命令用于配置已部署的 sysAgent 的 LLM 和 Embedding 模型参数，它提供了一个简洁的 TUI 界面来管理系统级配置：

1. **系统配置管理**: 直接修改系统配置文件 `/etc/sysagent/config.toml` 和 `/etc/euler-copilot-rag/data_chain/env`
2. **LLM 配置**: 设置大语言模型的端点、API 密钥、模型名称、最大输出令牌数和温度参数
3. **Embedding 配置**: 配置嵌入模型的端点、API 密钥和模型名称
4. **实时验证**: 自动验证 API 连接性和配置有效性
5. **服务重启**: 配置保存后自动重启相关系统服务（`sysagent`）

**使用要求**:

- 仅适用于已部署的 sysAgent
- 需要管理员权限（sudo）运行
- 需要系统配置文件存在且有写入权限
- 需要网络连接以验证 API 配置

**功能特点**:

- **分标签页配置**: LLM 和 Embedding 配置分别在不同标签页中管理
- **自动验证**: 输入配置后自动验证 API 连接性
- **智能检测**: 自动检测 function call 类型和 embedding 类型
- **安全保存**: 配置验证通过后才能保存
- **服务管理**: 自动重启相关系统服务使配置生效

**配置项说明**:

- **LLM 配置**:

  - **端点地址**: LLM API 的基础 URL
  - **API 密钥**: 访问 LLM 服务的认证密钥
  - **模型名称**: 要使用的具体模型名称
  - **最大输出令牌数**: 单次请求的最多输出的令牌数（默认 8192）
  - **温度参数**: 控制生成随机性的参数（默认 0.7）

- **Embedding 配置**:

  - **端点地址**: Embedding API 的基础 URL
  - **API 密钥**: 访问 Embedding 服务的认证密钥
  - **模型名称**: 要使用的 Embedding 模型名称

**注意**:

1. 此命令直接修改系统配置文件，请在生产环境使用前仔细评估；
2. 配置保存后会自动重启 `sysagent` 服务，可能会影响正在运行的服务；
3. 如果系统配置文件不存在或权限不足，工具会显示相应错误信息并退出；
4. 建议在修改配置前备份原有的配置文件。

## 国际化支持

应用程序内置多语言支持，提供英文和中文界面。

### 支持的语言

- **English (en_US)** - 默认语言
- **简体中文 (zh_CN)**

### 切换语言

```sh
# 切换到中文
witty --locale zh_CN

# 切换到英文
witty --locale en_US
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
witty --agent
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
- **命令行查看**: 使用 `python src/main.py --logs` 查看最新日志内容
- **记录内容**:
  - 程序启动和退出
  - API请求详情（URL、状态码、耗时等）
  - 异常和错误信息
  - 模块级别的操作日志

## 系统要求

### 基本要求

- **Python**: 3.11 或更高版本
- **操作系统**: openEuler 24.03 LTS 或更高版本
- **网络**: 访问配置的 LLM API 服务

### 依赖包

核心依赖：

- **textual**: 5.3.0 - TUI 界面框架
- **rich**: 14.1.0 - 富文本渲染
- **httpx**: 0.28.1 - HTTP 客户端
- **openai**: 1.99.6 - OpenAI API 客户端

开发依赖：

- **ruff**: *Latest* - 代码检查器

### 特殊功能要求

**自动部署功能（`--init` 命令）**:

- 仅支持 openEuler 操作系统
- 需要管理员权限（sudo）
- 需要 dnf 包管理器
- 需要网络连接

## 在 openEuler 系统下的 RPM 打包

以下步骤演示如何在 openEuler 24.03 LTS 或更高版本上，使用自带脚本打包生成 RPM 包。

前提条件：

- 操作系统：openEuler 24.03 LTS 或更高版本
- 工具依赖：rpmdevtools、git、bash
- 具有管理员权限（sudo）

构建步骤：

1. 克隆仓库并切换到对应分支：

   ```sh
   git clone https://gitee.com/openeuler/euler-copilot-shell.git -b dev
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
├── README.md                     # 项目说明文档
├── pyproject.toml                # 项目配置与依赖（由 uv 管理）
├── requirements.txt              # pip 兼容依赖列表（使用 uv export 生成）
├── uv.lock                       # uv 生成的锁定文件
├── LICENSE                       # 开源许可证
├── distribution/                 # 发布相关文件
├── docs/                         # 项目文档目录
│   └── development/              # 开发设计文档
│       └── server-side/          # 服务端相关文档
├── scripts/                      # 部署脚本目录
│   └── build/                    # RPM 包构建脚本
│   └── deploy/                   # 自动化部署脚本
├── tests/                        # 测试文件目录
└── src/                          # 源代码目录
    ├── main.py                   # 应用程序入口点
    ├── app/                      # TUI 应用模块
    │   ├── tui.py                # 主界面应用类
    │   ├── mcp_widgets.py        # MCP 交互组件
    │   ├── tui_mcp_handler.py    # MCP 事件处理器
    │   ├── settings.py           # 设置界面
    │   ├── css/
    │   │   └── styles.tcss       # TUI 样式文件
    │   ├── deployment/           # 部署助手模块
    │   │   ├── agent.py          # 智能体部署管理
    │   │   ├── models.py         # 部署配置模型
    │   │   ├── service.py        # 部署服务逻辑
    │   │   ├── ui.py             # 部署界面组件
    │   │   └── components/       # 部署组件模块
    │   └── dialogs/              # 对话框组件
    │       ├── agent.py          # 智能体选择对话框
    │       └── common.py         # 通用对话框组件
    ├── backend/                  # 后端适配模块
    │   ├── base.py               # 后端客户端基类
    │   ├── factory.py            # 后端工厂类
    │   ├── mcp_handler.py        # MCP 事件处理接口
    │   ├── openai.py             # OpenAI 兼容客户端
    │   └── hermes/               # sysAgent 客户端
    │       ├── client.py         # sysAgent API 客户端
    │       ├── constants.py      # 常量定义
    │       ├── exceptions.py     # 异常类定义
    │       ├── mcp_helpers.py    # MCP 事件辅助工具
    │       ├── models.py         # 数据模型
    │       ├── stream.py         # 流式响应处理
    │       └── services/         # 服务层组件
    ├── config/                   # 配置管理模块
    │   ├── manager.py            # 配置管理器
    │   └── model.py              # 配置数据模型
    ├── log/                      # 日志管理模块
    │   └── manager.py            # 日志管理器
    └── tool/                     # 工具模块
        ├── command_processor.py  # 命令处理器
        ├── oi_backend_init.py    # 后端初始化工具
        ├── oi_llm_config.py      # LLM 配置管理工具
        ├── oi_select_agent.py    # 智能体选择工具
        └── validators.py         # 配置验证器
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
