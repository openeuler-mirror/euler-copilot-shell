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
    AppConfig,
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
    - mcpServers 内部键名为 "mcp_server_mcp"
    - URL 为 http://127.0.0.1:12555/sse
    """
    return {
        "mcpServers": {
            "mcp_server_mcp": {
                "headers": {},
                "autoApprove": [],
                "autoInstall": True,
                "timeout": 60,
                "url": "http://127.0.0.1:12555/sse",
            },
        },
        "name": "oe-智能运维工具",
        "overview": "文件管理，文件操作，软件包管理，系统信息查询，进程管理，网络修复，ssh修复",
        "description": "文件管理，文件操作，软件包管理，系统信息查询，进程管理，网络修复，ssh修复",
        "mcpType": "sse",
    }


@pytest.fixture
def sample_rag_config() -> dict[str, Any]:
    """
    模拟 rag_mcp/config.json 的配置数据

    基于真实配置:
    - mcpServers 内部键名为 "rag_mcp"
    - URL 为 http://127.0.0.1:12311/sse
    """
    return {
        "mcpServers": {
            "rag_mcp": {
                "headers": {},
                "autoApprove": [],
                "autoInstall": True,
                "timeout": 60,
                "url": "http://127.0.0.1:12311/sse",
            },
        },
        "name": "轻量化知识库",
        "overview": "轻量化知识库",
        "description": "基于 SQLite 的检索增强生成（RAG）知识库，提供知识库全生命周期管理。支持 TXT、DOCX、DOC、PDF 格式，采用 FTS5 全文检索与 sqlite-vec 向量检索的混合搜索策略，结合关键词与语义检索，提升检索准确性。支持异步批量向量化处理、多知识库管理、文档导入导出，并提供命令行工具与 MCP 服务接口，适配中英文环境，适用于轻量级知识库构建与智能检索场景。",
        "mcpType": "sse",
    }


@pytest.fixture
def sample_app_config_toml() -> str:
    """
    模拟 mcp_to_app_config.toml 的内容

    基于真实配置:
    - mcpPath 使用目录名 ["rag_mcp", "mcp_server_mcp"]
    """
    return """\
[[applications]]
appType = "agent"
name = "OE-智能运维助手"
description = "提供通用系统运维能力，含网络监控、性能分析、硬件信息查询、存储管理等功能"
mcpPath = [
    "rag_mcp",
    "mcp_server_mcp",
]
published = true
"""


@pytest.fixture
def temp_mcp_config_dir(
    tmp_path: Path,
    sample_mcp_server_config: dict[str, Any],
    sample_rag_config: dict[str, Any],
    sample_app_config_toml: str,
) -> Path:
    """
    创建临时的 MCP 配置目录结构

    目录结构:
        tmp_path/mcp_config/
            mcp_server_mcp/config.json
            rag_mcp/config.json
            mcp_to_app_config.toml
    """
    config_dir = tmp_path / "mcp_config"
    config_dir.mkdir()

    # 创建 mcp_server_mcp 配置
    mcp_server_dir = config_dir / "mcp_server_mcp"
    mcp_server_dir.mkdir()
    with (mcp_server_dir / "config.json").open("w", encoding="utf-8") as f:
        json.dump(sample_mcp_server_config, f, ensure_ascii=False, indent=4)

    # 创建 rag_mcp 配置
    rag_dir = config_dir / "rag_mcp"
    rag_dir.mkdir()
    with (rag_dir / "config.json").open("w", encoding="utf-8") as f:
        json.dump(sample_rag_config, f, ensure_ascii=False, indent=4)

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
            "rag_mcp": "rag_mcp",
            "mcp_server_mcp": "mcp_server_mcp",
        }
        mcp_paths = ["rag_mcp", "mcp_server_mcp"]

        resolved, missing = manager._resolve_mcp_services(mcp_paths, mapping)  # noqa: SLF001

        assert resolved == ["rag_mcp", "mcp_server_mcp"]
        assert missing == []

    def test_identifies_missing_services(self) -> None:
        """缺失的服务应被识别出来"""
        manager = AgentManager()
        mapping = {"rag_mcp": "rag_mcp"}
        mcp_paths = ["rag_mcp", "non_existent_mcp"]

        resolved, missing = manager._resolve_mcp_services(mcp_paths, mapping)  # noqa: SLF001

        assert resolved == ["rag_mcp"]
        assert missing == ["non_existent_mcp"]

    def test_handles_empty_mapping(self) -> None:
        """空映射应导致所有服务都缺失"""
        manager = AgentManager()
        mapping: dict[str, str] = {}
        mcp_paths = ["rag_mcp"]

        resolved, missing = manager._resolve_mcp_services(mcp_paths, mapping)  # noqa: SLF001

        assert resolved == []
        assert missing == ["rag_mcp"]

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
class TestFallbackMcpMapping:
    """测试外部托管 MCP 的回退映射逻辑"""

    def test_build_fallback_mcp_service_mapping_uses_mcp_path_as_service_id(self) -> None:
        """当本地 mcp_config 不存在时，应直接使用 mcpPath 作为 service id。"""
        app_configs = [
            AppConfig(
                app_type="agent",
                name="A",
                description="desc",
                mcp_path=["external_rag", "external_tool"],
            ),
            AppConfig(
                app_type="agent",
                name="B",
                description="desc",
                mcp_path=["external_tool", "external_web"],
            ),
        ]

        mapping = AgentManager._build_fallback_mcp_service_mapping(app_configs)  # noqa: SLF001

        assert mapping == {
            "external_rag": "external_rag",
            "external_tool": "external_tool",
            "external_web": "external_web",
        }


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
        assert dir_names == {"mcp_server_mcp", "rag_mcp"}

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

        真实场景: mcpServers 的内部键名与目录名可能一致，也可能不一致。
        但每个配置必须只包含 1 个内部键名。
        """  # noqa: D403
        loader = McpConfigLoader(temp_mcp_config_dir)
        configs = loader.load_all_configs()

        for _dir_name, config in configs:
            assert isinstance(config.mcp_servers, dict)
            assert len(config.mcp_servers) == 1
            (server_id,) = tuple(config.mcp_servers.keys())
            assert server_id in {"mcp_server_mcp", "rag_mcp"}
            server_config = config.mcp_servers[server_id]
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

        # 目录应使用 mcpServers 内部键名（mapping 的 value），而不是配置目录名
        for server_id in mcp_mapping.values():
            target_dir = temp_semantics_dir / "mcp" / "template" / server_id
            assert target_dir.exists()
            assert (target_dir / "config.json").exists()

    async def test_mapping_uses_internal_server_ids_and_is_unique(
        self,
        configured_agent_manager: AgentManager,
    ) -> None:
        """
        映射应使用目录名作为键，mcpServers 内部键名作为值，并且内部键名不能重复。
        """
        manager = configured_agent_manager
        state = DeploymentState()

        mcp_mapping = await manager._write_mcp_configs_to_filesystem(state, None)  # noqa: SLF001

        # 映射的键是路径目录名（供 mcp_to_app_config.toml 引用）
        assert set(mcp_mapping.keys()) == {"rag_mcp", "mcp_server_mcp"}

        # 映射的值是 mcpServers 内部键名（实际落盘目录/元数据使用）
        assert set(mcp_mapping.values()) == {"rag_mcp", "mcp_server_mcp"}
        assert len(set(mcp_mapping.values())) == len(mcp_mapping)

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

        server_config = config_data["mcpServers"]["mcp_server_mcp"]

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
            temp_semantics_dir / "mcp" / "template" / "rag_mcp" / "config.json"
        )
        with config_file.open(encoding="utf-8") as f:
            config_data = json.load(f)

        # 验证原始值被保留
        assert config_data["name"] == "轻量化知识库"
        assert config_data["mcpType"] == "sse"

        server_config = config_data["mcpServers"]["rag_mcp"]
        assert server_config["url"] == "http://127.0.0.1:12311/sse"
        assert server_config["timeout"] == 60  # noqa: PLR2004

    async def test_raises_error_when_internal_server_id_duplicates(self, tmp_path: Path) -> None:
        """当多个配置复用同一个 mcpServers 内部键名时应报错（防止落盘覆盖）"""
        from app.deployment.agent import ConfigError  # noqa: PLC0415

        # semantics 目录
        semantics_dir = tmp_path / "semantics"
        (semantics_dir / "mcp" / "template").mkdir(parents=True)

        # 构造重复 internal key 的 mcp_config
        config_dir = tmp_path / "mcp_config"
        config_dir.mkdir()

        a_dir = config_dir / "svc_a_path"
        a_dir.mkdir()
        with (a_dir / "config.json").open("w", encoding="utf-8") as f:
            json.dump(
                {
                    "mcpServers": {
                        "mcp_server": {
                            "headers": {},
                            "autoApprove": [],
                            "autoInstall": True,
                            "timeout": 60,
                            "url": "http://127.0.0.1:11111/sse",
                        },
                    },
                    "name": "A",
                    "overview": "A",
                    "description": "A",
                    "mcpType": "sse",
                },
                f,
                ensure_ascii=False,
                indent=4,
            )

        b_dir = config_dir / "svc_b_path"
        b_dir.mkdir()
        with (b_dir / "config.json").open("w", encoding="utf-8") as f:
            json.dump(
                {
                    "mcpServers": {
                        "mcp_server": {
                            "headers": {},
                            "autoApprove": [],
                            "autoInstall": True,
                            "timeout": 60,
                            "url": "http://127.0.0.1:22222/sse",
                        },
                    },
                    "name": "B",
                    "overview": "B",
                    "description": "B",
                    "mcpType": "sse",
                },
                f,
                ensure_ascii=False,
                indent=4,
            )

        manager = AgentManager()
        manager.mcp_config_dir = config_dir
        manager.mcp_template_dir = semantics_dir / "mcp" / "template"

        state = DeploymentState()
        with pytest.raises(ConfigError):
            await manager._write_mcp_configs_to_filesystem(state, None)  # noqa: SLF001


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

    async def test_mcp_service_uses_internal_server_ids(
        self,
        configured_agent_manager: AgentManager,
        temp_semantics_dir: Path,
    ) -> None:
        """
        mcp_to_app_config.toml 中的 mcpPath 一定使用“配置目录名”，
        但最终写入 metadata.yaml 的 mcp_service 应使用 mcpServers 的内部键名。

        在本测试的真实样例中，目录名与内部键名恰好相同：
        - mcpPath: ["rag_mcp", "mcp_server_mcp"]
        - mcpServers 内部键名: "rag_mcp" / "mcp_server_mcp"
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

        assert mcp_services == ["rag_mcp", "mcp_server_mcp"]

    async def test_handles_missing_mcp_services(
        self,
        configured_agent_manager: AgentManager,
    ) -> None:
        """缺失的 MCP 服务应被识别但不阻止创建"""
        manager = configured_agent_manager
        state = DeploymentState()

        # 只提供部分映射
        partial_mapping = {"rag_mcp": "rag_mcp"}

        app_id = await manager._write_app_metadata_to_filesystem(  # noqa: SLF001
            partial_mapping,
            state,
            None,
        )

        # 应该仍然创建智能体（使用可用的服务）
        assert app_id is not None

    async def test_mcp_path_resolves_to_internal_server_id_when_names_differ(self, tmp_path: Path) -> None:
        """当目录名与 mcpServers 内部键名不一致时：toml 用目录名，最终 mcp_service 用内部键名"""
        # semantics 目录
        semantics_dir = tmp_path / "semantics"
        (semantics_dir / "mcp" / "template").mkdir(parents=True)
        (semantics_dir / "app").mkdir(parents=True)

        # mcp_config 目录
        config_dir = tmp_path / "mcp_config"
        config_dir.mkdir()

        # 目录名为 rag_mcp_path，但内部键名为 rag_mcp
        rag_path_dir = config_dir / "rag_mcp_path"
        rag_path_dir.mkdir()
        with (rag_path_dir / "config.json").open("w", encoding="utf-8") as f:
            json.dump(
                {
                    "mcpServers": {
                        "rag_mcp": {
                            "headers": {},
                            "autoApprove": [],
                            "autoInstall": True,
                            "timeout": 60,
                            "url": "http://127.0.0.1:12311/sse",
                        },
                    },
                    "name": "轻量化知识库",
                    "overview": "轻量化知识库",
                    "description": "轻量化知识库",
                    "mcpType": "sse",
                },
                f,
                ensure_ascii=False,
                indent=4,
            )

        # 目录名与内部键名一致
        mcp_server_dir = config_dir / "mcp_server_mcp"
        mcp_server_dir.mkdir()
        with (mcp_server_dir / "config.json").open("w", encoding="utf-8") as f:
            json.dump(
                {
                    "mcpServers": {
                        "mcp_server_mcp": {
                            "headers": {},
                            "autoApprove": [],
                            "autoInstall": True,
                            "timeout": 60,
                            "url": "http://127.0.0.1:12555/sse",
                        },
                    },
                    "name": "oe-智能运维工具",
                    "overview": "oe-智能运维工具",
                    "description": "oe-智能运维工具",
                    "mcpType": "sse",
                },
                f,
                ensure_ascii=False,
                indent=4,
            )

        # app toml：只能写目录名
        app_toml = """\
[[applications]]
appType = "agent"
name = "OE-智能运维助手"
description = "desc"
mcpPath = ["rag_mcp_path", "mcp_server_mcp"]
published = true
"""
        with (config_dir / "mcp_to_app_config.toml").open("w", encoding="utf-8") as f:
            f.write(app_toml)

        manager = AgentManager()
        manager.semantics_dir = semantics_dir
        manager.mcp_template_dir = semantics_dir / "mcp" / "template"
        manager.app_dir = semantics_dir / "app"
        manager.mcp_config_dir = config_dir
        manager.app_config_path = config_dir / "mcp_to_app_config.toml"

        state = DeploymentState()
        mapping = await manager._write_mcp_configs_to_filesystem(state, None)  # noqa: SLF001
        assert mapping["rag_mcp_path"] == "rag_mcp"
        assert mapping["mcp_server_mcp"] == "mcp_server_mcp"

        app_id = await manager._write_app_metadata_to_filesystem(mapping, state, None)  # noqa: SLF001
        assert app_id is not None

        metadata_file = semantics_dir / "app" / app_id / "metadata.yaml"
        with metadata_file.open(encoding="utf-8") as f:
            metadata = yaml.safe_load(f)

        assert metadata["mcp_service"] == ["rag_mcp", "mcp_server_mcp"]

        # 落盘目录也应使用内部键名
        assert (semantics_dir / "mcp" / "template" / "rag_mcp" / "config.json").exists()


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
        assert "rag_mcp" in mcp_mapping
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
        assert (mcp_template_dir / "rag_mcp" / "config.json").exists()
        assert (mcp_template_dir / "mcp_server_mcp" / "config.json").exists()

        # App 目录
        app_dir = temp_semantics_dir / "app" / app_id
        assert (app_dir / "metadata.yaml").exists()

        # 验证元数据内容
        with (app_dir / "metadata.yaml").open(encoding="utf-8") as f:
            metadata = yaml.safe_load(f)

        assert metadata["name"] == "OE-智能运维助手"
        assert set(metadata["mcp_service"]) == {"rag_mcp", "mcp_server_mcp"}

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
    mcpPath = ["rag_mcp"]
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

    async def test_prepare_mapping_falls_back_to_app_config_when_local_mcp_missing(
        self,
        temp_semantics_dir: Path,
        temp_mcp_config_dir: Path,
    ) -> None:
        """当本地 mcp_center 缺失时，应使用 mcp_to_app_config.toml 的 mcpPath 继续生成映射。"""
        manager = AgentManager()
        manager.resource_dir = temp_semantics_dir / "missing_mcp_center"
        manager.service_dir = manager.resource_dir / "service"
        manager.run_script_path = manager.resource_dir / "run.sh"
        manager.mcp_config_dir = temp_semantics_dir / "missing_mcp_config"
        manager.app_config_path = temp_mcp_config_dir / "mcp_to_app_config.toml"
        manager.mcp_template_dir = temp_semantics_dir / "mcp" / "template"
        manager.app_dir = temp_semantics_dir / "app"

        state = DeploymentState()
        mapping = await manager._prepare_mcp_service_mapping(state, None)  # noqa: SLF001

        assert mapping == {
            "rag_mcp": "rag_mcp",
            "mcp_server_mcp": "mcp_server_mcp",
        }

        assert not any("未找到本地 MCP 配置" in log for log in state.output_log)
        assert not any("mcp_center" in log for log in state.output_log)

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
        mcp_mapping = {"rag_mcp": "rag_mcp"}

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
