"""测试真实的部署配置数据模型"""

from __future__ import annotations

from typing import Any

import pytest

from app.deployment.models import DeploymentConfig, EmbeddingConfig, LLMConfig

LLM_DEFAULT_MAX_TOKENS = 8192
LLM_DEFAULT_TEMPERATURE = 0.7
LLM_DEFAULT_TIMEOUT = 300
LLM_CUSTOM_MAX_TOKENS = 1024
LLM_CUSTOM_TEMPERATURE = 0.1
LLM_CUSTOM_TIMEOUT = 10


@pytest.mark.unit
class TestLLMConfig:
    """验证 LLMConfig dataclass 行为"""

    def test_defaults(self) -> None:
        """LLMConfig 的初始值应与产品约定一致"""
        config = LLMConfig()

        assert config.endpoint == ""
        assert config.api_key == ""
        assert config.model == ""
        assert config.max_tokens == LLM_DEFAULT_MAX_TOKENS
        assert config.temperature == LLM_DEFAULT_TEMPERATURE
        assert config.request_timeout == LLM_DEFAULT_TIMEOUT

    def test_custom_values(self) -> None:
        """自定义构造参数应被正确保存"""
        config = LLMConfig(
            endpoint="http://127.0.0.1:9000/v1",
            api_key="demo-key",
            model="demo-model",
            max_tokens=LLM_CUSTOM_MAX_TOKENS,
            temperature=LLM_CUSTOM_TEMPERATURE,
            request_timeout=LLM_CUSTOM_TIMEOUT,
        )

        assert config.endpoint == "http://127.0.0.1:9000/v1"
        assert config.api_key == "demo-key"
        assert config.model == "demo-model"
        assert config.max_tokens == LLM_CUSTOM_MAX_TOKENS
        assert config.temperature == LLM_CUSTOM_TEMPERATURE
        assert config.request_timeout == LLM_CUSTOM_TIMEOUT


@pytest.mark.unit
class TestEmbeddingConfig:
    """验证 EmbeddingConfig dataclass 行为"""

    def test_defaults(self) -> None:
        """默认值应为空字符串"""
        config = EmbeddingConfig()
        assert config.type == ""
        assert config.endpoint == ""
        assert config.api_key == ""
        assert config.model == ""

    def test_custom_values(self) -> None:
        """自定义参数应被持久化"""
        config = EmbeddingConfig(
            type="mindie",
            endpoint="http://localhost:5100/embed",
            api_key="token",
            model="embed-model",
        )

        assert config.type == "mindie"
        assert config.endpoint == "http://localhost:5100/embed"
        assert config.api_key == "token"
        assert config.model == "embed-model"


@pytest.mark.unit
class TestDeploymentConfigValidation:
    """验证 DeploymentConfig.validate 的核心规则"""

    def test_llm_endpoint_required(self) -> None:
        """LLM 端点是最基本的必填项"""
        config = DeploymentConfig()
        valid, errors = config.validate()
        assert not valid
        assert any("LLM" in error for error in errors)

        config.llm.endpoint = "http://127.0.0.1:8000/v1"
        valid, errors = config.validate()
        assert valid is True
        assert errors == []

    def test_light_mode_embedding_optional(self) -> None:
        """轻量模式下 embedding 可以缺省"""
        config = DeploymentConfig()
        config.llm.endpoint = "http://127.0.0.1:8000/v1"

        # light 模式下不填写 embedding 也合法
        valid, errors = config.validate()
        assert valid
        assert not errors

        # 但只填写部分 embedding 字段时需要 endpoint
        config.embedding.api_key = "token"
        valid, errors = config.validate()
        assert not valid
        assert any("Embedding" in error for error in errors)

        config.embedding.endpoint = "http://localhost:5100/embed"
        valid, errors = config.validate()
        assert valid
        assert not errors

    def test_numeric_fields_validation(self) -> None:
        """数值字段应遵守上/下限"""
        config = DeploymentConfig(
            llm=LLMConfig(
                endpoint="http://127.0.0.1:8000/v1",
                max_tokens=0,
                temperature=99,
                request_timeout=-1,
            ),
            embedding=EmbeddingConfig(endpoint="http://localhost:5100/embed"),
        )

        valid, errors = config.validate()
        assert not valid
        assert any("max_tokens" in error for error in errors)
        assert any("temperature" in error for error in errors)
        assert any("超时" in error or "timeout" in error.lower() for error in errors)


@pytest.mark.asyncio
class TestDeploymentConnectivity:
    """验证异步连接性方法依赖 APIValidator 的行为"""

    async def test_validate_llm_connectivity_updates_backend_type(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """LLM 验证成功应写入 backend 类型"""
        config = DeploymentConfig()
        config.llm.endpoint = "http://127.0.0.1:8000/v1"

        called = {}

        async def fake_validate_llm_config(*_args: Any, **_kwargs: Any) -> tuple[bool, str, dict[str, bool | str]]:
            called["run"] = True
            return (True, "ok", {"supports_function_call": True, "detected_function_call_type": "structured_output"})

        monkeypatch.setattr("app.deployment.models.APIValidator.validate_llm_config", fake_validate_llm_config)

        success, message, info = await config.validate_llm_connectivity()

        assert success is True
        assert message == "ok"
        assert info["supports_function_call"] is True
        assert config.detected_backend_type == "structured_output"
        assert called["run"] is True

    async def test_validate_llm_connectivity_requires_endpoint(self) -> None:
        """无 endpoint 时直接返回错误"""
        config = DeploymentConfig()
        success, message, info = await config.validate_llm_connectivity()
        assert success is False
        assert "端点" in message
        assert info == {}

    async def test_validate_embedding_connectivity_updates_type(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Embedding 验证应更新类型信息"""
        config = DeploymentConfig()
        config.embedding.endpoint = "http://localhost:5100/embed"

        async def fake_validate_embedding_config(*_args: Any, **_kwargs: Any) -> tuple[bool, str, dict[str, str]]:
            return (True, "ok", {"type": "mindie"})

        monkeypatch.setattr(
            "app.deployment.models.APIValidator.validate_embedding_config",
            fake_validate_embedding_config,
        )

        success, message, info = await config.validate_embedding_connectivity()

        assert success is True
        assert message == "ok"
        assert info == {"type": "mindie"}
        assert config.embedding.type == "mindie"

    async def test_validate_embedding_connectivity_requires_endpoint(self) -> None:
        """缺少 embedding endpoint 时返回错误"""
        config = DeploymentConfig()
        success, message, info = await config.validate_embedding_connectivity()
        assert success is False
        assert "端点" in message
        assert info == {}
