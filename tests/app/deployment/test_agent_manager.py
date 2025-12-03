"""
AgentManager 测试

包含:
- 单元测试: 测试辅助方法和配置规范化
- 集成测试: 测试完整的 MCP 配置写入和智能体创建流程

所有测试使用内置的测试数据，不依赖外部配置文件。
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import pytest
import yaml

from app.deployment.agent import (
    AgentManager,
    McpConfig,
    McpConfigLoader,
)
from app.deployment.models import DeploymentState

if TYPE_CHECKING:
    from pathlib import Path

# ============================================================================
# 测试数据 Fixtures
# ============================================================================


@pytest.fixture
def sample_mcp_server_config() -> dict[str, Any]:
    """
    模拟 mcp_server_mcp/config.json 的配置数据

    基于真实配置:
    - mcpServers 内部键名为 "mcp_server"
    - URL 为 http://127.0.0.1:12555/sse
    """
    return {
        "mcpServers": {
            "mcp_server": {
                "headers": {},
                "autoApprove": [],
                "autoInstall": False,
                "timeout": 60,
                "url": "http://127.0.0.1:12555/sse",
            },
        },
        "name": "mcptool集成管理工具",
        "overview": "定制化的配置自己tool",
        "description": "定制化的配置自己tool",
        "mcpType": "sse",
    }


@pytest.fixture
def sample_remote_info_config() -> dict[str, Any]:
    """
    模拟 remote_info_mcp/config.json 的配置数据

    基于真实配置:
    - mcpServers 内部键名为 "mcp_server"（与上面相同，这是真实场景）
    - URL 为 http://127.0.0.1:12100/sse
    """
    return {
        "mcpServers": {
            "mcp_server": {
                "headers": {},
                "autoApprove": [],
                "autoInstall": False,
                "timeout": 60,
                "url": "http://127.0.0.1:12100/sse",
            },
        },
        "name": "端侧信息收集工具",
        "overview": "端侧信息收集工具",
        "description": "端侧信息收集工具",
        "mcpType": "sse",
    }


@pytest.fixture
def sample_app_config_toml() -> str:
    """
    模拟 mcp_to_app_config.toml 的内容

    基于真实配置:
    - mcpPath 使用目录名 ["remote_info_mcp", "mcp_server_mcp"]
    """
    return """\
[[applications]]
appType = "agent"
name = "OE-智能运维助手"
description = "提供通用系统运维能力，含网络监控、性能分析、硬件信息查询、存储管理等功能"
mcpPath = [
    "remote_info_mcp",
    "mcp_server_mcp",
]
published = true
"""


@pytest.fixture
def temp_mcp_config_dir(
    tmp_path: Path,
    sample_mcp_server_config: dict[str, Any],
    sample_remote_info_config: dict[str, Any],
    sample_app_config_toml: str,
) -> Path:
    """
    创建临时的 MCP 配置目录结构

    目录结构:
        tmp_path/mcp_config/
            mcp_server_mcp/config.json
            remote_info_mcp/config.json
            mcp_to_app_config.toml
    """
    config_dir = tmp_path / "mcp_config"
    config_dir.mkdir()

    # 创建 mcp_server_mcp 配置
    mcp_server_dir = config_dir / "mcp_server_mcp"
    mcp_server_dir.mkdir()
    with (mcp_server_dir / "config.json").open("w", encoding="utf-8") as f:
        json.dump(sample_mcp_server_config, f, ensure_ascii=False, indent=4)

    # 创建 remote_info_mcp 配置
    remote_info_dir = config_dir / "remote_info_mcp"
    remote_info_dir.mkdir()
    with (remote_info_dir / "config.json").open("w", encoding="utf-8") as f:
        json.dump(sample_remote_info_config, f, ensure_ascii=False, indent=4)

    # 创建应用配置 TOML
    with (config_dir / "mcp_to_app_config.toml").open("w", encoding="utf-8") as f:
        f.write(sample_app_config_toml)

    return config_dir


@pytest.fixture
def temp_semantics_dir(tmp_path: Path) -> Path:
    """创建临时 semantics 目录结构"""
    semantics_dir = tmp_path / "semantics"
    (semantics_dir / "mcp" / "template").mkdir(parents=True)
    (semantics_dir / "app").mkdir(parents=True)
    return semantics_dir


@pytest.fixture
def configured_agent_manager(
    temp_semantics_dir: Path,
    temp_mcp_config_dir: Path,
) -> AgentManager:
    """创建使用临时路径的 AgentManager"""
    manager = AgentManager()

    # 覆盖路径为临时目录
    manager.semantics_dir = temp_semantics_dir
    manager.mcp_template_dir = temp_semantics_dir / "mcp" / "template"
    manager.app_dir = temp_semantics_dir / "app"
    manager.mcp_config_dir = temp_mcp_config_dir
    manager.app_config_path = temp_mcp_config_dir / "mcp_to_app_config.toml"

    return manager


# ============================================================================
# 单元测试: AgentManager 辅助方法
# ============================================================================


@pytest.mark.unit
class TestNormalizeMcpConfig:
    """测试 _normalize_mcp_config 方法"""

    def test_empty_config_returns_defaults(self) -> None:
        """空配置应返回所有默认值"""
        manager = AgentManager()
        normalized = manager._normalize_mcp_config({})  # noqa: SLF001

        assert normalized == {
            "env": {},
            "autoApprove": [],
            "disabled": False,
            "autoInstall": True,
            "timeout": 60,
            "description": "",
            "headers": {},
            "url": "",
        }

    def test_preserves_valid_values(self) -> None:
        """有效值应被保留"""
        manager = AgentManager()
        raw_config = {
            "url": "http://127.0.0.1:12555/sse",
            "timeout": 120,
            "autoInstall": False,
            "disabled": True,
        }

        normalized = manager._normalize_mcp_config(raw_config)  # noqa: SLF001

        assert normalized["url"] == "http://127.0.0.1:12555/sse"
        assert normalized["timeout"] == 120  # noqa: PLR2004
        assert normalized["autoInstall"] is False
        assert normalized["disabled"] is True

    def test_fixes_invalid_types(self) -> None:
        """非法类型应被修正为默认值"""
        manager = AgentManager()
        raw_config = {
            "autoApprove": "should_be_list",  # 应为 list
            "headers": ["should_be_dict"],  # 应为 dict
            "env": "should_be_dict",  # 应为 dict
        }

        normalized = manager._normalize_mcp_config(raw_config)  # noqa: SLF001

        assert normalized["autoApprove"] == []
        assert normalized["headers"] == {}
        assert normalized["env"] == {}

    def test_converts_legacy_auto_install_field(self) -> None:
        """兼容旧字段名 auto_install"""
        manager = AgentManager()
        raw_config = {"auto_install": False}

        normalized = manager._normalize_mcp_config(raw_config)  # noqa: SLF001

        assert normalized["autoInstall"] is False
        assert "auto_install" not in normalized

    def test_handles_invalid_timeout(self) -> None:
        """非法的 timeout 值应使用默认值"""
        manager = AgentManager()
        raw_config = {"timeout": "invalid"}

        normalized = manager._normalize_mcp_config(raw_config)  # noqa: SLF001

        assert normalized["timeout"] == 60  # noqa: PLR2004


@pytest.mark.unit
class TestResolveMcpServices:
    """测试 _resolve_mcp_services 方法"""

    def test_resolves_existing_services(self) -> None:
        """存在的服务应被正确解析"""
        manager = AgentManager()
        mapping = {
            "remote_info_mcp": "remote_info_mcp",
            "mcp_server_mcp": "mcp_server_mcp",
        }
        mcp_paths = ["remote_info_mcp", "mcp_server_mcp"]

        resolved, missing = manager._resolve_mcp_services(mcp_paths, mapping)  # noqa: SLF001

        assert resolved == ["remote_info_mcp", "mcp_server_mcp"]
        assert missing == []

    def test_identifies_missing_services(self) -> None:
        """缺失的服务应被识别出来"""
        manager = AgentManager()
        mapping = {"remote_info_mcp": "remote_info_mcp"}
        mcp_paths = ["remote_info_mcp", "non_existent_mcp"]

        resolved, missing = manager._resolve_mcp_services(mcp_paths, mapping)  # noqa: SLF001

        assert resolved == ["remote_info_mcp"]
        assert missing == ["non_existent_mcp"]

    def test_handles_empty_mapping(self) -> None:
        """空映射应导致所有服务都缺失"""
        manager = AgentManager()
        mapping: dict[str, str] = {}
        mcp_paths = ["remote_info_mcp"]

        resolved, missing = manager._resolve_mcp_services(mcp_paths, mapping)  # noqa: SLF001

        assert resolved == []
        assert missing == ["remote_info_mcp"]

    def test_preserves_order(self) -> None:
        """解析结果应保持原始顺序"""
        manager = AgentManager()
        mapping = {
            "svc_a": "svc_a",
            "svc_b": "svc_b",
            "svc_c": "svc_c",
        }
        mcp_paths = ["svc_c", "svc_a", "svc_b"]

        resolved, _ = manager._resolve_mcp_services(mcp_paths, mapping)  # noqa: SLF001

        assert resolved == ["svc_c", "svc_a", "svc_b"]


@pytest.mark.unit
class TestNormalizeHelpers:
    """测试其他规范化辅助方法"""

    def test_normalize_links_filters_invalid(self) -> None:
        """无效的 links 应被过滤"""
        raw_links = [
            {"title": "Valid", "url": "https://example.com"},
            {"title": "", "url": "https://example.com"},  # 空标题
            {"title": "No URL"},  # 缺少 url
            "not_a_dict",  # 非字典
        ]

        result = AgentManager._normalize_links(raw_links)  # noqa: SLF001

        assert len(result) == 1
        assert result[0] == {"title": "Valid", "url": "https://example.com"}

    def test_normalize_first_questions_limits_count(self) -> None:
        """first_questions 应限制数量"""
        raw_questions = ["Q1", "Q2", "Q3", "Q4", "Q5"]

        result = AgentManager._normalize_first_questions(raw_questions)  # noqa: SLF001

        assert len(result) == 3  # noqa: PLR2004
        assert result == ["Q1", "Q2", "Q3"]

    def test_normalize_permission_data_with_defaults(self) -> None:
        """权限数据应有默认值"""
        result = AgentManager._normalize_permission_data(None)  # noqa: SLF001

        assert result == {"type": "public", "users": []}

    def test_normalize_hashes_filters_non_strings(self) -> None:
        """hashes 应只保留字符串值"""  # noqa: D403
        raw_hashes = {
            "valid": "hash123",
            "invalid": 123,  # 非字符串
            "also_valid": "hash456",
        }

        result = AgentManager._normalize_hashes(raw_hashes)  # noqa: SLF001

        assert result == {"valid": "hash123", "also_valid": "hash456"}


# ============================================================================
# 集成测试: McpConfigLoader  # noqa: ERA001
# ============================================================================


class TestMcpConfigLoader:
    """测试 McpConfigLoader 加载配置"""

    def test_loads_all_configs(self, temp_mcp_config_dir: Path) -> None:
        """应加载所有 MCP 配置"""
        loader = McpConfigLoader(temp_mcp_config_dir)
        configs = loader.load_all_configs()

        assert len(configs) == 2  # noqa: PLR2004

        dir_names = {dir_name for dir_name, _ in configs}
        assert dir_names == {"mcp_server_mcp", "remote_info_mcp"}

    def test_parses_config_structure(self, temp_mcp_config_dir: Path) -> None:
        """配置结构应被正确解析"""
        loader = McpConfigLoader(temp_mcp_config_dir)
        configs = loader.load_all_configs()

        for _dir_name, config in configs:
            assert isinstance(config, McpConfig)
            assert config.name
            assert config.description
            assert config.mcp_servers
            assert config.mcp_type in ("sse", "stdio")

    def test_mcp_servers_contain_correct_keys(
        self,
        temp_mcp_config_dir: Path,
    ) -> None:
        """
        mcpServers 应包含正确的键名

        真实场景: 两个不同的 MCP 配置都使用 "mcp_server" 作为内部键名
        """  # noqa: D403
        loader = McpConfigLoader(temp_mcp_config_dir)
        configs = loader.load_all_configs()

        for _dir_name, config in configs:
            # 两个配置都使用 "mcp_server" 作为键名
            assert "mcp_server" in config.mcp_servers
            server_config = config.mcp_servers["mcp_server"]
            assert "url" in server_config
            assert "timeout" in server_config

    def test_raises_error_for_nonexistent_dir(self, tmp_path: Path) -> None:
        """不存在的目录应抛出异常"""
        from app.deployment.agent import ConfigError  # noqa: PLC0415

        loader = McpConfigLoader(tmp_path / "nonexistent")

        with pytest.raises(ConfigError):
            loader.load_all_configs()

    def test_skips_invalid_json(self, tmp_path: Path) -> None:
        """无效的 JSON 文件应被跳过"""
        config_dir = tmp_path / "config"
        config_dir.mkdir()

        # 创建有效配置
        valid_dir = config_dir / "valid_mcp"
        valid_dir.mkdir()
        with (valid_dir / "config.json").open("w") as f:
            json.dump(
                {
                    "mcpServers": {"svc": {"url": "http://localhost"}},
                    "name": "Valid",
                    "description": "Valid",
                    "mcpType": "sse",
                },
                f,
            )

        # 创建无效配置
        invalid_dir = config_dir / "invalid_mcp"
        invalid_dir.mkdir()
        with (invalid_dir / "config.json").open("w") as f:
            f.write("{ invalid json }")

        loader = McpConfigLoader(config_dir)
        configs = loader.load_all_configs()

        # 应该只加载有效的配置
        assert len(configs) == 1
        assert configs[0][0] == "valid_mcp"


# ============================================================================
# 集成测试: MCP 配置写入
# ============================================================================


@pytest.mark.asyncio
class TestWriteMcpConfigs:
    """测试 MCP 配置写入到文件系统"""

    async def test_creates_correct_directory_structure(
        self,
        configured_agent_manager: AgentManager,
        temp_semantics_dir: Path,
    ) -> None:
        """应创建正确的目录结构"""
        manager = configured_agent_manager
        state = DeploymentState()

        mcp_mapping = await manager._write_mcp_configs_to_filesystem(state, None)  # noqa: SLF001

        # 验证创建了两个目录
        assert len(mcp_mapping) == 2  # noqa: PLR2004

        for dir_name in mcp_mapping:
            target_dir = temp_semantics_dir / "mcp" / "template" / dir_name
            assert target_dir.exists()
            assert (target_dir / "config.json").exists()

    async def test_mapping_uses_directory_names(
        self,
        configured_agent_manager: AgentManager,
    ) -> None:
        """
        映射应使用目录名作为键和值

        这是关键测试: 确保 mcp_service 使用目录名而非 mcpServers 内部键名
        """
        manager = configured_agent_manager
        state = DeploymentState()

        mcp_mapping = await manager._write_mcp_configs_to_filesystem(state, None)  # noqa: SLF001

        # 映射的键和值都应该是目录名
        assert "remote_info_mcp" in mcp_mapping
        assert "mcp_server_mcp" in mcp_mapping
        assert mcp_mapping["remote_info_mcp"] == "remote_info_mcp"
        assert mcp_mapping["mcp_server_mcp"] == "mcp_server_mcp"

        # 不应该出现 mcpServers 内部的键名
        assert "mcp_server" not in mcp_mapping

    async def test_normalizes_server_config(
        self,
        configured_agent_manager: AgentManager,
        temp_semantics_dir: Path,
    ) -> None:
        """写入的配置应经过规范化"""
        manager = configured_agent_manager
        state = DeploymentState()

        await manager._write_mcp_configs_to_filesystem(state, None)  # noqa: SLF001

        # 读取写入的配置
        config_file = (
            temp_semantics_dir / "mcp" / "template" / "mcp_server_mcp" / "config.json"
        )
        with config_file.open(encoding="utf-8") as f:
            config_data = json.load(f)

        server_config = config_data["mcpServers"]["mcp_server"]

        # 验证规范化后添加了默认字段
        assert "env" in server_config
        assert "disabled" in server_config
        assert "description" in server_config
        assert isinstance(server_config["env"], dict)

    async def test_preserves_original_values(
        self,
        configured_agent_manager: AgentManager,
        temp_semantics_dir: Path,
    ) -> None:
        """原始配置值应被保留"""
        manager = configured_agent_manager
        state = DeploymentState()

        await manager._write_mcp_configs_to_filesystem(state, None)  # noqa: SLF001

        # 读取写入的配置
        config_file = (
            temp_semantics_dir / "mcp" / "template" / "remote_info_mcp" / "config.json"
        )
        with config_file.open(encoding="utf-8") as f:
            config_data = json.load(f)

        # 验证原始值被保留
        assert config_data["name"] == "端侧信息收集工具"
        assert config_data["mcpType"] == "sse"

        server_config = config_data["mcpServers"]["mcp_server"]
        assert server_config["url"] == "http://127.0.0.1:12100/sse"
        assert server_config["timeout"] == 60  # noqa: PLR2004


# ============================================================================
# 集成测试: App 元数据写入
# ============================================================================


@pytest.mark.asyncio
class TestWriteAppMetadata:
    """测试智能体元数据写入"""

    async def test_creates_app_directory(
        self,
        configured_agent_manager: AgentManager,
        temp_semantics_dir: Path,
    ) -> None:
        """应创建 app 目录和 metadata.yaml"""
        manager = configured_agent_manager
        state = DeploymentState()

        # 先写入 MCP 配置
        mcp_mapping = await manager._write_mcp_configs_to_filesystem(state, None)  # noqa: SLF001

        # 写入 App 元数据
        app_id = await manager._write_app_metadata_to_filesystem(  # noqa: SLF001
            mcp_mapping,
            state,
            None,
        )

        assert app_id is not None

        app_dir = temp_semantics_dir / "app" / app_id
        assert app_dir.exists()
        assert (app_dir / "metadata.yaml").exists()

    async def test_metadata_has_correct_structure(
        self,
        configured_agent_manager: AgentManager,
        temp_semantics_dir: Path,
    ) -> None:
        """元数据应包含正确的字段"""
        manager = configured_agent_manager
        state = DeploymentState()

        mcp_mapping = await manager._write_mcp_configs_to_filesystem(state, None)  # noqa: SLF001
        app_id = await manager._write_app_metadata_to_filesystem(  # noqa: SLF001
            mcp_mapping,
            state,
            None,
        )

        # 读取元数据
        metadata_file = temp_semantics_dir / "app" / app_id / "metadata.yaml"
        with metadata_file.open(encoding="utf-8") as f:
            metadata = yaml.safe_load(f)

        # 验证必要字段
        assert metadata["type"] == "app"
        assert metadata["id"] == app_id
        assert metadata["name"] == "OE-智能运维助手"
        assert "提供通用系统运维能力" in metadata["description"]
        assert metadata["app_type"] == "agent"
        assert metadata["published"] is True

    async def test_mcp_service_uses_directory_names(
        self,
        configured_agent_manager: AgentManager,
        temp_semantics_dir: Path,
    ) -> None:
        """
        mcp_service 应使用目录名而非 mcpServers 内部键名

        这是最关键的测试:
        - mcpPath 配置: ["remote_info_mcp", "mcp_server_mcp"]
        - mcpServers 内部键名: "mcp_server" (两个配置相同)
        - 期望结果: mcp_service = ["remote_info_mcp", "mcp_server_mcp"]
        - 错误结果: mcp_service = ["mcp_server", "mcp_server"]
        """
        manager = configured_agent_manager
        state = DeploymentState()

        mcp_mapping = await manager._write_mcp_configs_to_filesystem(state, None)  # noqa: SLF001
        app_id = await manager._write_app_metadata_to_filesystem(  # noqa: SLF001
            mcp_mapping,
            state,
            None,
        )

        # 读取元数据
        metadata_file = temp_semantics_dir / "app" / app_id / "metadata.yaml"
        with metadata_file.open(encoding="utf-8") as f:
            metadata = yaml.safe_load(f)

        mcp_services = metadata["mcp_service"]

        # 应该使用目录名
        assert "remote_info_mcp" in mcp_services
        assert "mcp_server_mcp" in mcp_services

        # 不应该使用 mcpServers 内部键名
        # 如果只有 ["mcp_server", "mcp_server"]，说明逻辑错误
        assert mcp_services != ["mcp_server", "mcp_server"], (
            "mcp_service 错误地使用了 mcpServers 内部键名 'mcp_server'，"
            "应该使用目录名 'remote_info_mcp' 和 'mcp_server_mcp'"
        )

    async def test_handles_missing_mcp_services(
        self,
        configured_agent_manager: AgentManager,
    ) -> None:
        """缺失的 MCP 服务应被识别但不阻止创建"""
        manager = configured_agent_manager
        state = DeploymentState()

        # 只提供部分映射
        partial_mapping = {"remote_info_mcp": "remote_info_mcp"}

        app_id = await manager._write_app_metadata_to_filesystem(  # noqa: SLF001
            partial_mapping,
            state,
            None,
        )

        # 应该仍然创建智能体（使用可用的服务）
        assert app_id is not None


# ============================================================================
# 集成测试: 完整流程  # noqa: ERA001
# ============================================================================


@pytest.mark.asyncio
class TestFullIntegrationFlow:
    """完整流程集成测试"""

    async def test_end_to_end_agent_creation(
        self,
        configured_agent_manager: AgentManager,
        temp_semantics_dir: Path,
    ) -> None:
        """端到端测试: 从配置加载到智能体创建"""
        manager = configured_agent_manager
        state = DeploymentState()
        progress_logs: list[str] = []

        def progress_callback(s: DeploymentState) -> None:
            if s.output_log:
                progress_logs.append(s.output_log[-1])

        # Step 1: 写入 MCP 配置
        mcp_mapping = await manager._write_mcp_configs_to_filesystem(  # noqa: SLF001
            state,
            progress_callback,
        )

        assert len(mcp_mapping) == 2  # noqa: PLR2004
        assert "remote_info_mcp" in mcp_mapping
        assert "mcp_server_mcp" in mcp_mapping

        # Step 2: 写入 App 元数据
        app_id = await manager._write_app_metadata_to_filesystem(  # noqa: SLF001
            mcp_mapping,
            state,
            progress_callback,
        )

        assert app_id is not None

        # Step 3: 验证最终结构
        # MCP 配置目录
        mcp_template_dir = temp_semantics_dir / "mcp" / "template"
        assert (mcp_template_dir / "remote_info_mcp" / "config.json").exists()
        assert (mcp_template_dir / "mcp_server_mcp" / "config.json").exists()

        # App 目录
        app_dir = temp_semantics_dir / "app" / app_id
        assert (app_dir / "metadata.yaml").exists()

        # 验证元数据内容
        with (app_dir / "metadata.yaml").open(encoding="utf-8") as f:
            metadata = yaml.safe_load(f)

        assert metadata["name"] == "OE-智能运维助手"
        assert set(metadata["mcp_service"]) == {"remote_info_mcp", "mcp_server_mcp"}

        # 验证有进度日志
        assert len(progress_logs) > 0

    async def test_multiple_apps_creation(
        self,
        temp_semantics_dir: Path,
        temp_mcp_config_dir: Path,
    ) -> None:
        """测试创建多个智能体"""
        # 创建包含多个应用的配置
        multi_app_toml = """\
[[applications]]
appType = "agent"
name = "智能体A"
description = "第一个智能体"
mcpPath = ["remote_info_mcp"]
published = true

[[applications]]
appType = "agent"
name = "智能体B"
description = "第二个智能体"
mcpPath = ["mcp_server_mcp"]
published = true
"""
        with (temp_mcp_config_dir / "mcp_to_app_config.toml").open("w") as f:
            f.write(multi_app_toml)

        manager = AgentManager()
        manager.semantics_dir = temp_semantics_dir
        manager.mcp_template_dir = temp_semantics_dir / "mcp" / "template"
        manager.app_dir = temp_semantics_dir / "app"
        manager.mcp_config_dir = temp_mcp_config_dir
        manager.app_config_path = temp_mcp_config_dir / "mcp_to_app_config.toml"

        state = DeploymentState()

        mcp_mapping = await manager._write_mcp_configs_to_filesystem(state, None)  # noqa: SLF001
        default_app_id = await manager._write_app_metadata_to_filesystem(  # noqa: SLF001
            mcp_mapping,
            state,
            None,
        )

        # 应该创建了智能体
        assert default_app_id is not None

        # 验证 app 目录中有多个智能体
        app_dirs = list(temp_semantics_dir.glob("app/*/metadata.yaml"))
        assert len(app_dirs) == 2  # noqa: PLR2004

        # 验证智能体名称
        names = set()
        for metadata_file in app_dirs:
            with metadata_file.open(encoding="utf-8") as f:
                metadata = yaml.safe_load(f)
            names.add(metadata["name"])

        assert names == {"智能体A", "智能体B"}


# ============================================================================
# 边界条件测试
# ============================================================================


@pytest.mark.asyncio
class TestEdgeCases:
    """边界条件测试"""

    async def test_empty_mcp_config_dir(self, tmp_path: Path) -> None:
        """空的 MCP 配置目录应返回空映射"""
        empty_dir = tmp_path / "empty_config"
        empty_dir.mkdir()

        semantics_dir = tmp_path / "semantics"
        (semantics_dir / "mcp" / "template").mkdir(parents=True)

        manager = AgentManager()
        manager.mcp_config_dir = empty_dir
        manager.mcp_template_dir = semantics_dir / "mcp" / "template"

        state = DeploymentState()
        mcp_mapping = await manager._write_mcp_configs_to_filesystem(state, None)  # noqa: SLF001

        assert mcp_mapping == {}

    async def test_missing_app_config_file(
        self,
        temp_semantics_dir: Path,
        temp_mcp_config_dir: Path,
    ) -> None:
        """缺失的应用配置文件应返回 None"""
        # 删除应用配置文件
        (temp_mcp_config_dir / "mcp_to_app_config.toml").unlink()

        manager = AgentManager()
        manager.semantics_dir = temp_semantics_dir
        manager.mcp_template_dir = temp_semantics_dir / "mcp" / "template"
        manager.app_dir = temp_semantics_dir / "app"
        manager.mcp_config_dir = temp_mcp_config_dir
        manager.app_config_path = temp_mcp_config_dir / "mcp_to_app_config.toml"

        state = DeploymentState()
        mcp_mapping = {"remote_info_mcp": "remote_info_mcp"}

        app_id = await manager._write_app_metadata_to_filesystem(  # noqa: SLF001
            mcp_mapping,
            state,
            None,
        )

        assert app_id is None

    async def test_app_with_no_valid_mcp_services(
        self,
        temp_semantics_dir: Path,
        temp_mcp_config_dir: Path,
    ) -> None:
        """没有有效 MCP 服务的应用不应被创建"""
        # 修改配置使 mcpPath 指向不存在的服务
        bad_toml = """\
[[applications]]
appType = "agent"
name = "无效智能体"
description = "没有有效的 MCP 服务"
mcpPath = ["non_existent_mcp"]
published = true
"""
        with (temp_mcp_config_dir / "mcp_to_app_config.toml").open("w") as f:
            f.write(bad_toml)

        manager = AgentManager()
        manager.semantics_dir = temp_semantics_dir
        manager.mcp_template_dir = temp_semantics_dir / "mcp" / "template"
        manager.app_dir = temp_semantics_dir / "app"
        manager.mcp_config_dir = temp_mcp_config_dir
        manager.app_config_path = temp_mcp_config_dir / "mcp_to_app_config.toml"

        state = DeploymentState()

        # 提供一个不匹配的映射
        mcp_mapping = {"other_mcp": "other_mcp"}

        app_id = await manager._write_app_metadata_to_filesystem(  # noqa: SLF001
            mcp_mapping,
            state,
            None,
        )

        # 由于没有有效的 MCP 服务，不应创建智能体
        assert app_id is None
