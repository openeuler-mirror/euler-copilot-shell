"""OpenAI 大模型客户端"""

from __future__ import annotations

import asyncio
import time
from importlib import import_module
from typing import TYPE_CHECKING

import httpx
from openai import AsyncOpenAI, OpenAIError

from backend.base import LLMClientBase
from log.manager import get_logger, log_api_request, log_exception

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from openai.types.chat import ChatCompletionMessageParam


def _should_verify_ssl(*, verify_ssl: bool | None = None) -> bool:
    """延迟导入工具模块以决定 SSL 校验策略"""
    module = import_module("tool.validators")
    return module.should_verify_ssl(verify_ssl=verify_ssl)


class OpenAIClient(LLMClientBase):
    """OpenAI 大模型客户端"""

    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str = "",
        *,
        verify_ssl: bool | None = None,
    ) -> None:
        """初始化 OpenAI 大模型客户端"""
        self.logger = get_logger(__name__)

        self.model = model
        self.base_url = base_url
        self.verify_ssl = _should_verify_ssl(verify_ssl=verify_ssl)
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            http_client=httpx.AsyncClient(verify=self.verify_ssl),
        )
        self.logger.debug("OpenAIClient SSL 验证状态: %s", self.verify_ssl)

        # 添加历史记录管理
        self._conversation_history: list[ChatCompletionMessageParam] = []

        # 用于中断的任务跟踪
        self._current_task: asyncio.Task | None = None

        self.logger.info("OpenAI 客户端初始化成功 - URL: %s, Model: %s", base_url, model)

    async def get_llm_response(self, prompt: str) -> AsyncGenerator[str, None]:
        """
        生成命令建议

        异步调用 OpenAI 或兼容接口的大模型生成命令建议，支持流式输出。
        保持对话历史记录，支持多轮对话上下文。
        """
        start_time = time.time()
        self.logger.info("开始请求 OpenAI 流式聊天 API - Model: %s", self.model)

        # 添加用户消息到历史记录
        user_message: ChatCompletionMessageParam = {"role": "user", "content": prompt}
        self._conversation_history.append(user_message)

        try:
            # 使用完整的对话历史记录
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=self._conversation_history,
                stream=True,
            )

            # 记录成功的API请求
            duration = time.time() - start_time
            log_api_request(
                self.logger,
                "POST",
                f"{self.base_url}/chat/completions",
                200,
                duration,
                model=self.model,
                stream=True,
                history_length=len(self._conversation_history),
            )

            # 收集助手的完整回复
            assistant_response = ""
            try:
                async for chunk in response:
                    content = chunk.choices[0].delta.content
                    if content:
                        assistant_response += content
                        yield content
            except asyncio.CancelledError:
                self.logger.info("OpenAI 流式响应被中断")
                # 如果被中断，移除刚添加的用户消息
                if (
                    self._conversation_history
                    and len(self._conversation_history) > 0
                    and self._conversation_history[-1].get("content") == prompt
                ):
                    self._conversation_history.pop()
                raise

            # 将助手回复添加到历史记录
            if assistant_response:
                assistant_message: ChatCompletionMessageParam = {
                    "role": "assistant",
                    "content": assistant_response,
                }
                self._conversation_history.append(assistant_message)
                self.logger.info("对话历史记录已更新，当前消息数: %d", len(self._conversation_history))

        except asyncio.CancelledError:
            # 重新抛出取消异常
            raise
        except OpenAIError as e:
            # 如果请求失败，移除刚添加的用户消息
            if (
                self._conversation_history
                and len(self._conversation_history) > 0
                and self._conversation_history[-1].get("content") == prompt
            ):
                self._conversation_history.pop()

            duration = time.time() - start_time
            log_exception(self.logger, "OpenAI 流式聊天 API 请求失败", e)
            # 记录失败的API请求
            log_api_request(
                self.logger,
                "POST",
                f"{self.base_url}/chat/completions",
                500,
                duration,
                model=self.model,
                stream=True,
                error=str(e),
            )
            raise
        finally:
            # 清理当前任务引用
            self._current_task = None

    async def interrupt(self) -> None:
        """
        中断当前正在进行的请求

        取消当前正在进行的流式请求。
        """
        if self._current_task is not None and not self._current_task.done():
            self.logger.info("中断 OpenAI 客户端当前请求")
            self._current_task.cancel()
            try:
                await self._current_task
            except asyncio.CancelledError:
                self.logger.info("OpenAI 客户端请求已成功中断")
            except (OSError, TimeoutError) as e:
                self.logger.warning("中断 OpenAI 客户端请求时出错: %s", e)
            finally:
                self._current_task = None
        else:
            self.logger.debug("OpenAI 客户端当前无正在进行的请求")

    def reset_conversation(self) -> None:
        """
        重置对话上下文

        清空历史记录，开始新的对话会话。
        """
        self._conversation_history.clear()
        self.logger.info("OpenAI 客户端对话历史记录已重置")

    async def get_available_models(self) -> list[str]:
        """
        获取当前 LLM 服务中可用的模型，返回名称列表

        调用 LLM 服务的模型列表接口，并解析返回结果提取模型名称。
        如果服务不支持模型列表接口，返回空列表。
        """
        start_time = time.time()
        self.logger.info("开始请求 OpenAI 模型列表 API")

        try:
            models_response = await self.client.models.list()
            models = [model.id async for model in models_response]
            # 记录成功的API请求
            duration = time.time() - start_time
            log_api_request(
                self.logger,
                "GET",
                f"{self.base_url}/models",
                200,
                duration,
                model_count=len(models),
            )
        except OpenAIError as e:
            duration = time.time() - start_time
            log_exception(self.logger, "OpenAI 模型列表 API 请求失败", e)
            log_api_request(
                self.logger,
                "GET",
                f"{self.base_url}/models",
                500,
                duration,
                error=str(e),
            )
            return []
        else:
            self.logger.info("获取到 %d 个可用模型", len(models))
            return models

    async def close(self) -> None:
        """关闭 OpenAI 客户端"""
        try:
            await self.client.close()
            self.logger.info("OpenAI 客户端已关闭")
        except OpenAIError as e:
            log_exception(self.logger, "关闭 OpenAI 客户端失败", e)
            raise
