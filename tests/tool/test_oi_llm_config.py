"""
oi_llm_config.py 模块测试

测试 LLM 配置管理工具的数据模型和工具函数。
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from backend.models import LLMConfig as HermesLLMConfig
from backend.models import LLMProvider, LLMType, ModelInfo
from tool.oi_llm_config import (
    DEFAULT_EMBEDDING_CTX_LENGTH,
    DEFAULT_LLM_CTX_LENGTH,
    DEFAULT_MAX_TOKENS,
    EditableModelConfig,
    check_admin_permission,
)


class TestEditableModelConfigDefaults:
    """测试 EditableModelConfig 默认值"""

    def test_default_values(self) -> None:
        """测试默认配置值"""
        config = EditableModelConfig()

        assert config.llm_id == ""
        assert config.llm_description == ""
        assert config.has_chat is True
        assert config.has_function is False
        assert config.has_embedding is False
        assert config.has_vision is False
        assert config.has_thinking is False
        assert config.provider == LLMProvider.OPENAI
        assert config.base_url == ""
        assert config.api_key == ""
        assert config.model_name == ""
        assert config.ctx_length == DEFAULT_LLM_CTX_LENGTH
        assert config.max_tokens == DEFAULT_MAX_TOKENS
        assert config.extra_data_json == "{}"
        assert config.is_new is True

    def test_custom_values(self) -> None:
        """测试自定义配置值"""
        config = EditableModelConfig(
            llm_id="test-model",
            llm_description="测试模型",
            has_chat=True,
            has_function=True,
            has_embedding=True,
            has_vision=True,
            has_thinking=True,
            provider=LLMProvider.OLLAMA,
            base_url="http://localhost:11434/v1",
            api_key="test-key",
            model_name="llama3",
            ctx_length=4096,
            max_tokens=2048,
            extra_data_json='{"temperature": 0.7}',
            is_new=False,
        )

        assert config.llm_id == "test-model"
        assert config.llm_description == "测试模型"
        assert config.has_chat is True
        assert config.has_function is True
        assert config.has_embedding is True
        assert config.has_vision is True
        assert config.has_thinking is True
        assert config.provider == LLMProvider.OLLAMA
        assert config.base_url == "http://localhost:11434/v1"
        assert config.api_key == "test-key"
        assert config.model_name == "llama3"
        assert config.ctx_length == 4096
        assert config.max_tokens == 2048
        assert config.extra_data_json == '{"temperature": 0.7}'
        assert config.is_new is False


class TestEditableModelConfigLLMTypes:
    """测试 EditableModelConfig 的 LLM 类型处理"""

    def test_get_llm_types_all_false(self) -> None:
        """测试所有类型都为 False 时"""
        config = EditableModelConfig(
            has_chat=False,
            has_function=False,
            has_embedding=False,
            has_vision=False,
            has_thinking=False,
        )
        assert config.get_llm_types() == []

    def test_get_llm_types_chat_only(self) -> None:
        """测试仅 chat 类型"""
        config = EditableModelConfig(has_chat=True, has_function=False)
        types = config.get_llm_types()
        assert LLMType.CHAT in types
        assert len(types) == 1

    def test_get_llm_types_multiple(self) -> None:
        """测试多个类型"""
        config = EditableModelConfig(
            has_chat=True,
            has_function=True,
            has_embedding=False,
            has_vision=True,
            has_thinking=False,
        )
        types = config.get_llm_types()
        assert LLMType.CHAT in types
        assert LLMType.FUNCTION in types
        assert LLMType.VISION in types
        assert LLMType.EMBEDDING not in types
        assert LLMType.THINKING not in types
        assert len(types) == 3

    def test_get_llm_types_all_true(self) -> None:
        """测试所有类型都为 True"""
        config = EditableModelConfig(
            has_chat=True,
            has_function=True,
            has_embedding=True,
            has_vision=True,
            has_thinking=True,
        )
        types = config.get_llm_types()
        assert len(types) == 5
        assert LLMType.CHAT in types
        assert LLMType.FUNCTION in types
        assert LLMType.EMBEDDING in types
        assert LLMType.VISION in types
        assert LLMType.THINKING in types


class TestEditableModelConfigExtraData:
    """测试 EditableModelConfig 的额外数据处理"""

    def test_get_extra_data_empty_string(self) -> None:
        """测试空字符串"""
        config = EditableModelConfig(extra_data_json="")
        assert config.get_extra_data() is None

    def test_get_extra_data_empty_object(self) -> None:
        """测试空对象"""
        config = EditableModelConfig(extra_data_json="{}")
        assert config.get_extra_data() is None

    def test_get_extra_data_valid_json(self) -> None:
        """测试有效的 JSON"""
        config = EditableModelConfig(extra_data_json='{"temperature": 0.7, "top_p": 0.9}')
        data = config.get_extra_data()
        assert data is not None
        assert data["temperature"] == 0.7
        assert data["top_p"] == 0.9

    def test_get_extra_data_invalid_json(self) -> None:
        """测试无效的 JSON"""
        config = EditableModelConfig(extra_data_json="not valid json")
        assert config.get_extra_data() is None

    def test_get_extra_data_nested_json(self) -> None:
        """测试嵌套的 JSON"""
        json_str = '{"model_options": {"temperature": 0.7}, "features": ["a", "b"]}'
        config = EditableModelConfig(extra_data_json=json_str)
        data = config.get_extra_data()
        assert data is not None
        assert data["model_options"]["temperature"] == 0.7
        assert data["features"] == ["a", "b"]


class TestEditableModelConfigValidateJson:
    """测试 EditableModelConfig 的 JSON 验证"""

    def test_validate_empty_string(self) -> None:
        """测试空字符串验证"""
        config = EditableModelConfig(extra_data_json="")
        is_valid, error = config.validate_extra_data_json()
        assert is_valid is True
        assert error == ""

    def test_validate_whitespace_only(self) -> None:
        """测试只有空白字符"""
        config = EditableModelConfig(extra_data_json="   \n\t  ")
        is_valid, error = config.validate_extra_data_json()
        assert is_valid is True
        assert error == ""

    def test_validate_valid_json(self) -> None:
        """测试有效的 JSON"""
        config = EditableModelConfig(extra_data_json='{"key": "value"}')
        is_valid, error = config.validate_extra_data_json()
        assert is_valid is True
        assert error == ""

    def test_validate_invalid_json(self) -> None:
        """测试无效的 JSON"""
        config = EditableModelConfig(extra_data_json="{invalid}")
        is_valid, error = config.validate_extra_data_json()
        assert is_valid is False
        assert error != ""

    def test_validate_incomplete_json(self) -> None:
        """测试不完整的 JSON"""
        config = EditableModelConfig(extra_data_json='{"key":')
        is_valid, error = config.validate_extra_data_json()
        assert is_valid is False
        assert error != ""


class TestEditableModelConfigToHermesConfig:
    """测试 EditableModelConfig 转换为 HermesLLMConfig"""

    def test_basic_conversion(self) -> None:
        """测试基本转换"""
        config = EditableModelConfig(
            llm_id="test-model",
            llm_description="Test Model",
            has_chat=True,
            has_function=False,
            provider=LLMProvider.OPENAI,
            base_url="https://api.openai.com/v1",
            api_key="sk-test",
            model_name="gpt-4",
            ctx_length=8192,
            max_tokens=4096,
        )

        hermes_config = config.to_hermes_config()

        assert isinstance(hermes_config, HermesLLMConfig)
        assert hermes_config.id == "test-model"
        assert hermes_config.llm_description == "Test Model"
        assert hermes_config.provider == LLMProvider.OPENAI
        assert hermes_config.base_url == "https://api.openai.com/v1"
        assert hermes_config.api_key == "sk-test"
        assert hermes_config.model_name == "gpt-4"
        assert hermes_config.ctx_length == 8192
        assert hermes_config.max_tokens == 4096
        assert LLMType.CHAT in hermes_config.llm_type

    def test_conversion_with_empty_llm_id(self) -> None:
        """测试空 llm_id 的转换"""
        config = EditableModelConfig(llm_id="")
        hermes_config = config.to_hermes_config()
        assert hermes_config.id is None

    def test_conversion_with_empty_model_name(self) -> None:
        """测试空 model_name 的转换"""
        config = EditableModelConfig(model_name="")
        hermes_config = config.to_hermes_config()
        assert hermes_config.model_name is None

    def test_conversion_with_extra_data(self) -> None:
        """测试带额外数据的转换"""
        config = EditableModelConfig(extra_data_json='{"temperature": 0.8}')
        hermes_config = config.to_hermes_config()
        assert hermes_config.extra_data == {"temperature": 0.8}

    def test_conversion_with_invalid_extra_data(self) -> None:
        """测试无效额外数据的转换"""
        config = EditableModelConfig(extra_data_json="invalid json")
        hermes_config = config.to_hermes_config()
        assert hermes_config.extra_data is None


class TestEditableModelConfigFromModelInfo:
    """测试从 ModelInfo 创建 EditableModelConfig"""

    def test_from_model_info_basic(self) -> None:
        """测试基本的 ModelInfo 转换"""
        model = ModelInfo(
            model_name="gpt-4",
            llm_id="gpt-4-turbo",
            llm_description="GPT-4 Turbo",
            llm_type=[LLMType.CHAT, LLMType.FUNCTION],
            max_tokens=8192,
        )

        config = EditableModelConfig.from_model_info(model)

        assert config.llm_id == "gpt-4-turbo"
        assert config.llm_description == "GPT-4 Turbo"
        assert config.model_name == "gpt-4"
        assert config.has_chat is True
        assert config.has_function is True
        assert config.has_embedding is False
        assert config.has_vision is False
        assert config.has_thinking is False
        assert config.max_tokens == 8192
        assert config.is_new is False

    def test_from_model_info_with_config(self) -> None:
        """测试带有 HermesLLMConfig 的转换"""
        model = ModelInfo(
            model_name="llama3",
            llm_id="llama3-70b",
            llm_type=[LLMType.CHAT],
        )

        hermes_config = HermesLLMConfig(
            provider=LLMProvider.OLLAMA,
            ctx_length=4096,
            base_url="http://localhost:11434/v1",
            api_key="",
            model_name="llama3:70b",
            max_tokens=2048,
            extra_data={"temperature": 0.7},
        )

        config = EditableModelConfig.from_model_info(model, hermes_config)

        assert config.provider == LLMProvider.OLLAMA
        assert config.base_url == "http://localhost:11434/v1"
        assert config.api_key == ""
        assert config.model_name == "llama3:70b"
        assert config.ctx_length == 4096
        assert config.max_tokens == 2048
        assert config.extra_data_json == '{\n  "temperature": 0.7\n}'

    def test_from_model_info_empty_llm_id(self) -> None:
        """测试空 llm_id 的转换"""
        model = ModelInfo(model_name="test-model", llm_id=None)
        config = EditableModelConfig.from_model_info(model)
        assert config.llm_id == ""

    def test_from_model_info_empty_description(self) -> None:
        """测试空描述的转换"""
        model = ModelInfo(model_name="test-model", llm_description=None)
        config = EditableModelConfig.from_model_info(model)
        assert config.llm_description == ""

    def test_from_model_info_all_llm_types(self) -> None:
        """测试所有 LLM 类型"""
        model = ModelInfo(
            model_name="multimodal",
            llm_type=[
                LLMType.CHAT,
                LLMType.FUNCTION,
                LLMType.EMBEDDING,
                LLMType.VISION,
                LLMType.THINKING,
            ],
        )

        config = EditableModelConfig.from_model_info(model)

        assert config.has_chat is True
        assert config.has_function is True
        assert config.has_embedding is True
        assert config.has_vision is True
        assert config.has_thinking is True

    def test_from_model_info_no_llm_types(self) -> None:
        """测试无 LLM 类型"""
        model = ModelInfo(model_name="unknown", llm_type=[])
        config = EditableModelConfig.from_model_info(model)

        assert config.has_chat is False
        assert config.has_function is False
        assert config.has_embedding is False
        assert config.has_vision is False
        assert config.has_thinking is False

    def test_from_model_info_null_max_tokens(self) -> None:
        """测试 max_tokens 为 None 时使用默认值"""
        model = ModelInfo(model_name="test", max_tokens=None)
        config = EditableModelConfig.from_model_info(model)
        assert config.max_tokens == DEFAULT_MAX_TOKENS


class TestCheckAdminPermission:
    """测试管理员权限检查"""

    def test_root_user_has_permission(self) -> None:
        """测试 root 用户有权限"""
        with patch("os.geteuid", return_value=0):
            ok, errors = check_admin_permission()
            assert ok is True
            assert errors == []

    def test_non_root_user_no_permission(self) -> None:
        """测试非 root 用户无权限"""
        with patch("os.geteuid", return_value=1000):
            ok, errors = check_admin_permission()
            assert ok is False
            assert len(errors) == 2


class TestConstants:
    """测试常量定义"""

    def test_default_llm_ctx_length(self) -> None:
        """测试默认 LLM 上下文长度"""
        assert DEFAULT_LLM_CTX_LENGTH == 128000

    def test_default_embedding_ctx_length(self) -> None:
        """测试默认 Embedding 上下文长度"""
        assert DEFAULT_EMBEDDING_CTX_LENGTH == 8192

    def test_default_max_tokens(self) -> None:
        """测试默认最大令牌数"""
        assert DEFAULT_MAX_TOKENS == 8192
