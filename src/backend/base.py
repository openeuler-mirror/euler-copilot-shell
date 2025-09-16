"""后端客户端基类和工厂"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from typing_extensions import Self

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator
    from types import TracebackType


class LLMClientBase(ABC):
    """LLM 客户端基类"""

    @abstractmethod
    def get_llm_response(self, prompt: str) -> AsyncGenerator[str, None]:
        """
        生成命令建议

        Args:
            prompt: 用户输入的提示

        Yields:
            str: 流式响应的文本内容

        """

    @abstractmethod
    async def interrupt(self) -> None:
        """
        中断当前正在进行的请求

        子类应该实现具体的中断逻辑，例如取消 HTTP 请求、停止流式响应等。
        """

    @abstractmethod
    async def get_available_models(self) -> list[str]:
        """
        获取当前 LLM 服务中可用的模型，返回名称列表

        Returns:
            list[str]: 可用的模型名称列表

        """

    @abstractmethod
    def reset_conversation(self) -> None:
        """
        重置对话上下文

        此方法作为模板方法，子类可以重写以实现具体的会话重置逻辑。
        默认实现不执行任何操作，适用于无状态的客户端。
        """

    @abstractmethod
    async def close(self) -> None:
        """关闭客户端连接"""

    async def __aenter__(self) -> Self:
        """异步上下文管理器入口"""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """异步上下文管理器出口"""
        await self.close()
