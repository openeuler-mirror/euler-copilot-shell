# EulerCopilot Shell

这是一个基于 Python Textual 库开发的 TUI（文本用户界面）应用程序。它允许用户输入命令，验证并执行这些命令。如果命令无法执行，应用程序会与大型语言模型交互，生成建议或纠正方案。

## 功能特点

- 用户友好的命令输入和输出显示界面
- 命令验证和执行支持
- 集成大型语言模型提供智能命令建议
- 提供本地或在线模型服务集成选项

## 项目结构

```text
euler-copilot-shell/
├── README.md                     # 项目文档
├── requirements.txt              # 项目依赖
└── src
    ├── app
    |   ├── css
    │   │   └── styles.tcss       # TUI 样式配置
    │   ├── __init__.py
    │   ├── settings.py           # 设置界面逻辑
    │   └── tui.py                # 主界面布局和组件定义
    ├── backend
    │   ├── __init__.py
    │   └── openai.py             # 与 OpenAI API 交互的逻辑
    ├── config
    │   ├── __init__.py
    │   ├── manager.py            # 配置管理
    │   └── model.py              # 配置模型定义
    ├── main.py                   # TUI 应用程序入口点
    └── tool
        ├── __init__.py
        └── command_processor.py  # 命令验证和执行逻辑
```

## 安装说明

1. 克隆仓库:

   ```sh
   git clone https://gitee.com/openeuler/euler-copilot-shell.git -b dev
   cd euler-copilot-shell
   ```

2. 安装依赖:

   ```sh
   pip install -r requirements.txt
   ```

## 使用方法

直接运行应用程序:

```sh
python src/main.py
```

应用启动后，您可以直接在输入框中输入命令。如果命令无效或无法执行，应用程序将基于您的输入提供智能建议。

## 大型语言模型集成

该应用程序利用大型语言模型（LLM）增强用户体验，提供智能命令建议。集成在 `backend/openai.py` 文件中处理，该文件与 OpenAI 兼容的 API 通信以获取基于用户输入的建议。应用支持配置不同的后端和模型。

## 配置设置

您可以通过应用内的设置界面（按 Ctrl+S）配置以下选项:

- 后端类型: OpenAI 或 EulerCopilot
- API 基础 URL
- API 密钥
- 模型选择（OpenAI 后端）

配置会保存在`~/.config/eulercopilot/smart-shell.json`。

## RPM打包

我们提供了一个 spec 文件，可以使用 PyInstaller 打包并生成 RPM 包:

```sh
# 创建源代码归档
tar czf euler-copilot-shell-0.9.6.tar.gz --transform 's,^smart-shell,euler-copilot-shell-0.9.6,' smart-shell

# 构建RPM包(需要已安装rpm-build工具)
rpmbuild -ba euler-copilot-shell.spec
```

## 贡献

欢迎贡献代码！请随时提交 PR 或开启问题讨论任何功能增强或错误修复建议。

## 许可证

本项目采用木兰宽松许可证第2版（MulanPSL-2.0）。详情请参阅 LICENSE 文件。
