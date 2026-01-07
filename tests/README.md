# 测试文档

本目录包含 Witty Assistant 的所有测试用例。

## 运行测试

```bash
# 激活虚拟环境
source .venv/bin/activate

# 运行所有测试
pytest tests/ -v

# 运行特定模块的测试
pytest tests/backend/ -v
pytest tests/tool/ -v
pytest tests/app/deployment/ -v

# 运行单个测试文件
pytest tests/backend/test_model_info.py -v

# 运行特定的测试类
pytest tests/backend/test_model_info.py::TestModelInfo -v

# 运行特定的测试函数
pytest tests/backend/test_model_info.py::TestModelInfo::test_model_info_creation_openai_style -v
```

## 测试统计

用例数量以本仓库实际运行 `pytest` 的收集结果为准（本仓库当前约 **338** 个用例）。

### Backend 模块概览

- `test_model_info.py`: ModelInfo 与 LLMType 枚举/解析逻辑
- `test_llm_id_validation.py`: HermesChatClient 的 llm_id 校验
- `test_hermes_client.py`: Hermes 流式响应解析、错误处理与模型枚举
- `test_openai_client.py`: OpenAI 客户端的模型列表获取与异常处理

### Tool 模块概览

- `test_browser_availability.py`: 浏览器可用性检测
- `test_token_validation.py`: Token 格式校验
- `test_token_integration.py`: Token 接入与网络交互
- `test_command_processor.py`: CLI 命令执行/回退逻辑
- `test_ssl_flags.py`: SSL 标志解析与 APIValidator 分支

### Config 模块概览

- `test_manager.py`: ConfigManager 的模板复制、默认生成与字段合并

### App 模块概览

- `deployment/test_rpm_availability.py`: 部署资源文件检查
- `deployment/test_validate_llm_config.py`: 部署配置数据模型与连接性校验
- `test_agent_manager.py`: AgentManager 帮助函数（MCP 配置解析）

## 测试结构

```text
tests/
├── README.md
├── conftest.py                  # 全局 fixture 定义
├── app/
│   ├── deployment/
│   │   ├── test_rpm_availability.py
│   │   └── test_validate_llm_config.py
│   └── test_agent_manager.py
├── backend/
│   ├── test_hermes_client.py
│   ├── test_llm_id_validation.py
│   ├── test_model_info.py
│   └── test_openai_client.py
├── config/
│   └── test_manager.py
└── tool/
    ├── test_browser_availability.py
    ├── test_command_processor.py
    ├── test_ssl_flags.py
    ├── test_token_integration.py
    └── test_token_validation.py
```

## 测试类型

项目使用 pytest 标记来区分不同类型的测试：

- `@pytest.mark.unit`: 单元测试 - 测试单个函数或类
- `@pytest.mark.integration`: 集成测试 - 测试多个组件的交互
- `@pytest.mark.asyncio`: 异步测试 - 测试异步函数

使用标记运行特定类型的测试：

```bash
# 只运行单元测试
pytest -m unit tests/ -v

# 只运行集成测试
pytest -m integration tests/ -v

# 只运行异步测试
pytest -m asyncio tests/ -v
```

## Fixture 说明

### 全局 Fixture（在 conftest.py 中定义）

- `mock_config_manager`: 模拟的 ConfigManager 实例，不包含 LLM 配置
- `mock_config_manager_with_llm`: 包含 LLM 配置的 ConfigManager 实例
- `valid_token_samples`: 有效 token 格式示例列表
- `invalid_token_samples`: 无效 token 格式示例列表
- `temp_config_env`: 为配置相关测试提供隔离的用户/全局配置路径

## 测试覆盖范围

### Backend 模块覆盖

- `test_model_info.py`: 覆盖 ModelInfo 构造、字符串表示和 LLMType 解析/验证。
- `test_llm_id_validation.py`: 校验 `llm_id` 的空值、有效值以及 ConfigManager 回退路径。
- `test_hermes_client.py` / `test_openai_client.py`: 验证 Hermes/OpenAI 客户端的流式事件、模型列表代理、成功与异常分支。

### Tool 模块覆盖

- `test_browser_availability.py`: 检查浏览器可用性探测的正常、异常与回退分支。
- `test_token_validation.py` / `test_token_integration.py`: 覆盖短期/长期 token 的解析、空值与格式拒绝，以及网络交互路径。
- `test_command_processor.py` / `test_ssl_flags.py`: 关注命令黑/白名单、子进程回退、流式输出聚合，以及 SSL 标志和 APIValidator 分支。

### App.Deployment 模块覆盖

- `deployment/test_rpm_availability.py`: 验证脚本资源目录、RPM 列表、配置文件和 systemd 服务文件的存在性与格式。
- `deployment/test_validate_llm_config.py`: 检查 LLM/Embedding/部署配置数据结构及端点、数值字段的校验逻辑。

### Config 模块覆盖

- `config/test_manager.py`: 覆盖用户配置缺失时的模板复制、模板缺失时的默认生成，以及 `validate_and_update_config` 字段合并与保存。

## 注意事项

### 循环导入问题

由于 `app.deployment` 模块存在循环导入问题，部署模块的测试采用以下策略：

1. **资源文件测试**: 直接使用 Path 操作验证文件存在性和格式，避免导入 AgentManager
2. **配置验证测试**: 定义简化的数据类进行测试，避免导入会触发循环导入的完整模块

这种方法确保测试的独立性和可靠性，同时覆盖核心功能。

### 异步测试

异步测试使用 `pytest-asyncio` 插件，配置为自动模式（`asyncio_mode = auto`），因此：

- 使用 `@pytest.mark.asyncio` 标记异步测试函数
- 测试函数可以直接使用 `async def` 和 `await`
- 不需要手动管理事件循环

### Mock 使用

测试中大量使用 `unittest.mock` 来隔离外部依赖：

- 使用 `@patch` 装饰器模拟函数调用
- 使用 `AsyncMock` 模拟异步方法
- 使用 `MagicMock` 模拟同步对象
- 注意 `AsyncMock.json()` 等同步方法应使用 `lambda` 或直接赋值

## 持续改进

随着项目的发展，测试也需要持续更新：

1. 新功能必须添加相应的测试用例
2. Bug 修复应该包含回归测试
3. 重构代码后确保所有测试通过
4. 定期审查测试覆盖率

运行测试覆盖率分析：

```bash
pytest tests/ --cov=src --cov-report=html
```
