"""后端工厂"""

from __future__ import annotations

from typing import TYPE_CHECKING

from backend.hermes.client import HermesChatClient
from backend.openai import OpenAIClient
from config.model import Backend

if TYPE_CHECKING:
    from backend.base import LLMClientBase
    from config.manager import ConfigManager


class BackendFactory:
    """后端工厂类"""

    @staticmethod
    def create_client(config_manager: ConfigManager) -> LLMClientBase:
        """
        根据配置创建对应的客户端

        Args:
            config_manager: 配置管理器

        Returns:
            LLMClientBase: 对应的客户端实例

        Raises:
            ValueError: 当后端类型不支持时

        """
        backend = config_manager.get_backend()

        if backend == Backend.OPENAI:
            return OpenAIClient(
                base_url=config_manager.get_base_url(),
                model=config_manager.get_model(),
                api_key=config_manager.get_api_key(),
            )
        if backend == Backend.SYSAGENT:
            return HermesChatClient(
                base_url=config_manager.get_witty_url(),
                auth_token=config_manager.get_witty_key(),
                config_manager=config_manager,
            )
        msg = f"不支持的后端类型: {backend}"
        raise ValueError(msg)
