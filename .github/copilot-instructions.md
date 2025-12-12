# Project Overview

Witty Assistant 是一个基于 Python 的智能命令行助手项目，用于提供 AI 驱动的终端交互体验。项目采用模块化架构设计，使用 Textual 构建 TUI 界面，支持多种 AI 后端集成。

## Folder Structure

- `/src`: 包含所有源代码
  - `/src/main.py`: 应用程序主入口点
  - `/src/app/`: TUI 应用模块，包含界面和设置
  - `/src/backend/`: AI 后端集成模块，支持 OpenAI 和 Hermes 等
  - `/src/config/`: 配置管理模块
  - `/src/log/`: 日志管理模块
  - `/src/tool/`: 工具和命令处理模块
- `/docs`: 项目文档
  - `/docs/development/`: 开发相关文档
  - `/docs/development/api/`: API 规范文档（仅供参考，请勿修改）
- `/.venv`: Python 虚拟环境
- `/pyproject.toml`: Python 依赖与项目配置（使用 uv 管理）
- `/uv.lock`: uv 生成的锁定文件

## Libraries and Frameworks

- Python 3.9 ~ 3.11 作为主要开发语言
- Textual 用于构建终端用户界面 (TUI)
- OpenAI API 和 Hermes API 用于 AI 后端集成
- 自定义配置管理和日志系统

## Development Environment

**重要：开发与测试必须使用 `.venv` 虚拟环境**

```bash
# 创建虚拟环境（仅首次）
uv venv --python 3.11 .venv

# 激活虚拟环境
source .venv/bin/activate

# 安装依赖（包含可编辑模式安装项目本身和开发工具）
uv pip install -e '.[dev]'

# 运行项目
python src/main.py
```

## Coding Standards

- 遵循 Python PEP 8 编码规范
- 使用相对导入在模块内部进行导入
- 每个 Python 包必须包含 `__init__.py` 文件
- 保持模块结构清晰，按功能划分
- 请注意类方法的排序：
  - `__init__`
  - 公共方法
  - 私有方法（以单下划线 `_` 开头）
- 使用类型提示提高代码可读性
- 添加适当的文档字符串和注释

## Documentation Guidelines

- 项目主要文档维护在 `README.md` 中
- 开发相关文档在 `docs/development/` 目录中编写与更新
- 功能变更时必须同步更新相关文档
- 代码变更时确保注释和文档字符串的准确性

## Testing and Quality

- 测试脚本位于 `tests/` 目录
- `tests/` 目录下的文件应与 `src/` 目录结构相对应
- 可以使用简单的测试方法或其他测试框架
- 所有测试必须在 `.venv` 虚拟环境中运行
- 如果用到测试框架，测试前确保依赖包已正确安装
- 提交代码前检查 VS Code 中报告的所有问题
- 保持代码质量和一致性

## File Organization

- 使用标准 Python 包结构
- 模块文件应具有清晰的职责分工
- 配置文件集中在 `src/config/` 模块中管理
- 日志功能统一通过 `src/log/` 模块处理
