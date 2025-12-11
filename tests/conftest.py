"""
Pytest 配置文件

定义全局 fixtures 和测试配置
"""

from pathlib import Path
from unittest.mock import Mock

import pytest

from config.manager import ConfigManager
from config.model import ConfigModel


@pytest.fixture
def mock_config_manager() -> Mock:
    """模拟的配置管理器"""
    mock = Mock()
    mock.get_llm_chat_model.return_value = ""
    mock.get_witty_url.return_value = "http://localhost:8080"
    mock.get_witty_key.return_value = ""
    return mock


@pytest.fixture
def mock_config_manager_with_llm() -> Mock:
    """模拟的配置管理器（已配置 LLM）"""
    mock = Mock()
    mock.get_llm_chat_model.return_value = "test-model-id"
    mock.get_witty_url.return_value = "http://localhost:8080"
    mock.get_witty_key.return_value = "test-token"
    return mock


@pytest.fixture
def valid_token_samples() -> list[str]:
    """有效的令牌样本"""
    return [
        "",  # 空令牌（兼容旧版本）
        "a1b2c3d4e5f6789012345678abcdef90",  # 短期令牌
        "sk-a1b2c3d4e5f6789012345678abcdef90",  # 长期令牌
    ]


@pytest.fixture
def invalid_token_samples() -> list[str]:
    """无效的令牌样本"""
    return [
        "invalid_token",  # 无效格式
        "12345",  # 太短
        "a1b2c3d4e5f6789012345678abcdef9",  # 31个字符
        "sk-invalid",  # sk- 前缀但长度不对
        "Bearer a1b2c3d4e5f6789012345678abcdef90",  # 带 Bearer 前缀
    ]


@pytest.fixture
def temp_config_env(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, Path]:
    """为配置相关测试提供隔离的用户/全局配置路径。"""
    user_dir = tmp_path / "user-config"
    global_dir = tmp_path / "global-config"
    user_dir.mkdir()
    global_dir.mkdir()

    user_path = user_dir / "witty-assistant.json"
    global_path = global_dir / "witty-assistant-template.json"

    monkeypatch.setattr(ConfigManager, "USER_CONFIG_DIR", user_dir)
    monkeypatch.setattr(ConfigManager, "USER_CONFIG_PATH", user_path)
    monkeypatch.setattr(ConfigManager, "GLOBAL_CONFIG_DIR", global_dir)
    monkeypatch.setattr(ConfigManager, "GLOBAL_CONFIG_PATH", global_path)

    ConfigManager.data = ConfigModel()

    return {
        "user_path": user_path,
        "global_path": global_path,
    }
