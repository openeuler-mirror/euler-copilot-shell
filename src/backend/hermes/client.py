"""Hermes Chat API 客户端"""

from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING, Any, Self
from urllib.parse import urljoin

import httpx

from backend.base import LLMClientBase
from i18n.manager import _, get_locale
from log.manager import get_logger, log_exception

from .constants import HTTP_OK
from .exceptions import HermesAPIError
from .models import HermesApp, HermesChatRequest
from .services import (
    HermesAgentManager,
    HermesConversationManager,
    HermesHttpManager,
    HermesMCPManager,
    HermesModelManager,
    HermesUserManager,
)
from .stream import HermesStreamEvent, HermesStreamProcessor

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator
    from types import TracebackType

    from backend.mcp_handler import MCPEventHandler
    from backend.models import ModelInfo
    from config.manager import ConfigManager

    from .models import HermesAgent


class HermesChatClient(LLMClientBase):
    """Hermes Chat API 客户端 - 重构版本"""

    def __init__(self, base_url: str, auth_token: str = "", config_manager: ConfigManager | None = None) -> None:
        """
        初始化 Hermes Chat API 客户端

        Args:
            base_url: API 基础 URL
            auth_token: 认证令牌
            config_manager: 配置管理器（用于动态获取 llm_id）

        """
        self.logger = get_logger(__name__)

        self.current_agent_id: str = ""  # 当前选择的智能体 ID
        self.config_manager = config_manager  # 配置管理器，用于动态获取 llm_id

        # HTTP 管理器 - 立即初始化
        self.http_manager = HermesHttpManager(base_url, auth_token)

        # 延迟初始化的管理器
        self._user_manager: HermesUserManager | None = None
        self._model_manager: HermesModelManager | None = None
        self._agent_manager: HermesAgentManager | None = None
        self._conversation_manager: HermesConversationManager | None = None
        self._mcp_manager: HermesMCPManager | None = None
        self._stream_processor: HermesStreamProcessor | None = None

        # MCP 事件处理器（可选）
        self._mcp_handler: MCPEventHandler | None = None

        # 用户信息缓存（在初始化时加载）
        self._user_info: dict[str, Any] | None = None

        self.logger.info("Hermes 客户端初始化成功 - URL: %s", base_url)

    @property
    def user_manager(self) -> HermesUserManager:
        """获取用户管理器（延迟初始化）"""
        if self._user_manager is None:
            self._user_manager = HermesUserManager(self.http_manager, self.config_manager)
        return self._user_manager

    @property
    def model_manager(self) -> HermesModelManager:
        """获取模型管理器（延迟初始化）"""
        if self._model_manager is None:
            self._model_manager = HermesModelManager(
                self.http_manager,
                admin_checker=self.is_admin,
            )
        return self._model_manager

    @property
    def agent_manager(self) -> HermesAgentManager:
        """获取智能体管理器（延迟初始化）"""
        if self._agent_manager is None:
            self._agent_manager = HermesAgentManager(self.http_manager)
        return self._agent_manager

    @property
    def conversation_manager(self) -> HermesConversationManager:
        """获取会话管理器（延迟初始化）"""
        if self._conversation_manager is None:
            self._conversation_manager = HermesConversationManager(self.http_manager)
        return self._conversation_manager

    @property
    def mcp_manager(self) -> HermesMCPManager:
        """获取 MCP 管理器（延迟初始化）"""
        if self._mcp_manager is None:
            self._mcp_manager = HermesMCPManager(self.http_manager)
        return self._mcp_manager

    @property
    def stream_processor(self) -> HermesStreamProcessor:
        """获取流处理器（延迟初始化）"""
        if self._stream_processor is None:
            self._stream_processor = HermesStreamProcessor()
        return self._stream_processor

    def set_mcp_handler(self, handler: MCPEventHandler | None) -> None:
        """设置 MCP 事件处理器"""
        self._mcp_handler = handler

    def set_current_agent(self, agent_id: str) -> None:
        """
        设置当前使用的智能体

        Args:
            agent_id: 智能体ID，空字符串表示不使用智能体

        """
        self.current_agent_id = agent_id
        self.logger.info("设置当前智能体ID: %s", agent_id or "无智能体")

    async def ensure_user_info_loaded(self) -> bool:
        """
        确保用户信息已加载

        在 Hermes 后端初始化时调用，加载并缓存用户信息。
        后续可以直接通过 get_user_xxx 方法从内存获取，无需重复请求。

        Returns:
            bool: 是否成功加载用户信息

        """
        if self._user_info is not None:
            return True

        self.logger.info("开始加载用户信息...")
        self._user_info = await self.user_manager.get_user_info()

        if self._user_info is not None:
            self.logger.info(
                "用户信息加载成功 - ID: %s, 用户名: %s",
                self._user_info.get("userId"),
                self._user_info.get("userName"),
            )
            return True

        self.logger.warning("用户信息加载失败")
        return False

    def get_personal_token(self) -> str:
        """
        获取个人令牌（从内存缓存）

        Returns:
            str: 个人令牌，如果未加载则返回空字符串

        """
        if self._user_info is None:
            return ""
        return self._user_info.get("personalToken", "")

    def get_user_id(self) -> str | None:
        """获取用户ID（从内存缓存）"""
        if self._user_info is None:
            return None
        return self._user_info.get("userId")

    def get_user_name(self) -> str:
        """获取用户名（从内存缓存）"""
        if self._user_info is None:
            return ""
        return self._user_info.get("userName", "")

    def get_auto_execute_status(self) -> bool:
        """获取自动执行状态（从内存缓存）"""
        if self._user_info is None:
            return False
        return self._user_info.get("autoExecute", False)

    def is_admin(self) -> bool:
        """获取管理员状态（从内存缓存）"""
        if self._user_info is None:
            return False
        return self._user_info.get("isAdmin", False)

    async def update_user_info(self, *, auto_execute: bool) -> bool:
        """
        更新用户信息

        更新成功后会自动更新内存中的缓存。

        Args:
            auto_execute: 是否启用自动执行

        Returns:
            bool: 更新是否成功

        """
        success = await self.user_manager.update_user_info(
            auto_execute=auto_execute,
        )

        if success and self._user_info is not None:
            # 更新内存缓存
            self._user_info["autoExecute"] = auto_execute
            self.logger.info("已更新内存中的用户信息缓存")

        return success

    def reset_conversation(self) -> None:
        """重置会话，下次聊天时会创建新的会话"""
        if self._conversation_manager is not None:
            self._conversation_manager.reset_conversation()

    def clear_user_info_cache(self) -> None:
        """清除用户信息缓存，强制下次重新获取"""
        self._user_info = None
        self.logger.debug("用户信息缓存已清除")

    async def get_llm_response(self, prompt: str) -> AsyncGenerator[str, None]:
        """
        生成命令建议

        为了兼容现有的 OpenAI 客户端接口，提供简化的聊天接口。

        Args:
            prompt: 用户输入的提示语

        Yields:
            str: 流式响应的文本内容

        Raises:
            HermesAPIError: 当 API 调用失败时或 llm_id 未配置时

        """
        # 验证 llm_id 是否已配置
        self._validate_llm_id()

        # 不在这里重置状态跟踪，让进度状态能够跨流保持
        # 只有在真正的新对话开始时才重置（由上层调用方决定）

        self.logger.info("开始 Hermes 流式聊天请求")
        self.logger.debug("提示内容长度: %d", len(prompt))
        start_time = time.time()

        try:
            # 获取当前会话ID（可能为空）
            conversation_id = self.conversation_manager.get_conversation_id()
            if conversation_id:
                self.logger.info("使用现有会话ID: %s", conversation_id)
            else:
                self.logger.info("没有会话ID，后端将自动创建新会话")

            # 创建聊天请求
            app = HermesApp(self.current_agent_id)

            # 根据当前语言环境设置语言参数
            current_locale = get_locale()
            language = "zh" if current_locale.startswith("zh") else "en"

            request = HermesChatRequest(
                app=app,
                question=prompt,
                conversation_id=conversation_id,
                language=language,
                llm_id=self._get_llm_id(),
            )

            # 直接传递异常，不在这里处理
            async for text in self._chat_stream(request):
                yield text

            duration = time.time() - start_time
            self.logger.info("Hermes 流式聊天请求完成 - 耗时: %.3fs", duration)

        except Exception as e:
            duration = time.time() - start_time
            log_exception(self.logger, "Hermes 流式聊天请求失败", e)
            raise

    async def get_available_models(self) -> list[ModelInfo]:
        """
        获取当前 LLM 服务中可用的模型，返回模型信息列表

        通过调用 /api/llm/provider 接口获取可用的大模型列表。
        如果调用失败或没有返回，使用空列表，后端接口会自动使用默认模型。
        """
        return await self.model_manager.get_available_models()

    async def get_available_agents(self) -> list[HermesAgent]:
        """
        获取当前用户可用的智能体列表

        通过调用 /api/app 接口获取当前用户可用的智能体列表。
        支持分页获取所有智能体，每页最多16项，会自动请求所有页面。
        这些智能体可以在聊天中使用，选择的智能体 ID 需要在 chat 接口中填入 appId 字段。
        如果调用失败或没有返回，使用空列表。

        Returns:
            list[HermesAgent]: 可用的智能体列表（仅包含已发布的智能体）

        """
        return await self.agent_manager.get_available_agents()

    async def send_mcp_response(self, *, params: dict) -> AsyncGenerator[str, None]:
        """
        发送 MCP 响应并获取流式回复

        Args:
            params: 响应参数
                - 对于 MCP 确认消息: {"confirm": true/false}
                - 对于参数补全: 包含补全参数的字典

        Yields:
            str: 流式响应的文本内容

        Raises:
            HermesAPIError: 当 API 调用失败时

        """
        # 始终使用会话管理器中记录的最新 ID
        conversation_id = self.conversation_manager.get_conversation_id()
        if not conversation_id:
            raise HermesAPIError(400, _("无法确定会话 ID，请重试当前请求"))

        # 不在 MCP 响应时重置状态跟踪，保持去重机制有效
        self.logger.info("发送 MCP 响应 - 会话ID: %s, 参数类型: %s", conversation_id, type(params).__name__)
        start_time = time.time()

        try:
            # 构建 MCP 响应请求
            app = HermesApp(self.current_agent_id, params=params)

            current_locale = get_locale()
            language = "zh" if current_locale.startswith("zh") else "en"

            request = HermesChatRequest(
                app=app,
                question="",
                conversation_id=conversation_id,
                language=language,
                llm_id=self._get_llm_id(),
            )

            self.logger.debug("MCP 响应请求数据: %s", request.to_dict())

            async for text in self._chat_stream(request):
                yield text

            duration = time.time() - start_time
            self.logger.info("MCP 响应请求完成 - 耗时: %.3fs", duration)

        except Exception as e:
            duration = time.time() - start_time
            log_exception(self.logger, "MCP 响应请求失败", e)
            raise

    async def interrupt(self) -> None:
        """
        中断当前正在进行的请求

        调用后端的 stop 能力来中断当前会话。
        """
        self.logger.info("中断 Hermes 客户端当前请求")
        await self._stop()

    async def close(self) -> None:
        """关闭 HTTP 客户端"""
        # 如果有未完成的会话，先停止它
        await self._stop()
        try:
            await self.http_manager.close()
            self.logger.info("Hermes 客户端已关闭")
        except Exception as e:
            log_exception(self.logger, "关闭 Hermes 客户端失败", e)
            raise

    def _get_llm_id(self) -> str:
        """
        从配置管理器获取当前的 llm_id

        Returns:
            str: 当前配置的 llm_id，如果未配置则返回空字符串

        """
        if self.config_manager is None:
            return ""
        return self.config_manager.get_llm_chat_model()

    def _validate_llm_id(self) -> None:
        """
        验证 llm_id 是否已配置

        Raises:
            HermesAPIError: 当 llm_id 未配置时

        """
        llm_id = self._get_llm_id()
        if not llm_id:
            main_message = _("未配置 Chat 模型")
            hint_prefix = _("配置步骤")
            step1 = _("按 Ctrl+S 打开设置")
            step2 = _("确认后端为 sysAgent")
            step3 = _('点击 "更改用户设置" 按钮')
            step4 = _('切换到 "大模型设置" 标签页')
            step5 = _("使用 ↑↓ 键选择模型，空格激活，回车保存")
            error_message = (
                f"{main_message}\n\n"
                f"{hint_prefix}:\n"
                f"  1. {step1}\n"
                f"  2. {step2}\n"
                f"  3. {step3}\n"
                f"  4. {step4}\n"
                f"  5. {step5}"
            )
            raise HermesAPIError(400, error_message)

    async def _chat_stream(
        self,
        request: HermesChatRequest,
    ) -> AsyncGenerator[str, None]:
        """
        发送聊天请求并返回流式响应

        Args:
            request: Hermes 聊天请求对象

        Yields:
            str: 流式响应的文本内容

        Raises:
            HermesAPIError: 当 API 调用失败时

        """
        client = await self.http_manager.get_client()
        chat_url = urljoin(self.http_manager.base_url, "/api/chat")
        headers = self.http_manager.build_headers()

        self.logger.info("准备发送聊天请求 - URL: %s, 会话ID: %s", chat_url, request.conversation_id)
        self.logger.debug("请求头: %s", headers)
        self.logger.debug("请求内容: %s", request.to_dict())

        try:
            async with client.stream(
                "POST",
                chat_url,
                json=request.to_dict(),
                headers=headers,
            ) as response:
                self.logger.info("收到聊天响应 - 状态码: %d", response.status_code)
                await self._validate_chat_response(response)
                async for text in self._process_stream_events(response):
                    yield text

        except httpx.RequestError as e:
            raise HermesAPIError(500, f"Network error: {e!s}") from e
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            raise HermesAPIError(500, f"Data parsing error: {e!s}") from e

    async def _validate_chat_response(self, response: httpx.Response) -> None:
        """验证聊天响应状态"""
        if response.status_code != HTTP_OK:
            error_text = await response.aread()
            raise HermesAPIError(
                response.status_code,
                error_text.decode("utf-8"),
            )

    async def _process_stream_events(self, response: httpx.Response) -> AsyncGenerator[str, None]:
        """处理流式响应事件"""
        has_content = False
        event_count = 0
        has_error_message = False

        self.logger.info("开始处理流式响应事件")

        try:
            async for line in response.aiter_lines():
                event = self._parse_stream_line(line)
                if event is None:
                    continue

                event_count += 1
                self.logger.info("解析到事件 #%d - 类型: %s", event_count, event.event_type)

                # 处理会话ID
                self._handle_conversation_id(event)

                # 处理特殊事件类型
                should_break, break_message = self.stream_processor.handle_special_events(event)
                if should_break:
                    if break_message:
                        has_error_message = True
                        yield break_message
                    break

                # 处理事件内容
                content_yielded = False
                async for content in self._handle_event_content(event):
                    has_content = True
                    content_yielded = True
                    yield content

                if not content_yielded:
                    self.logger.info("事件无文本内容")

            self.logger.info("流式响应处理完成 - 事件数量: %d, 有内容: %s", event_count, has_content)

        except Exception:
            self.logger.exception("处理流式响应事件时出错")
            raise

        # 只有在没有内容且没有错误消息的情况下才显示无内容消息
        if not has_content and not has_error_message:
            yield self.stream_processor.get_no_content_message(event_count)

    def _parse_stream_line(self, line: str) -> HermesStreamEvent | None:
        """解析单行流式响应"""
        stripped_line = line.strip()
        if not stripped_line:
            return None

        self.logger.debug("收到 SSE 行: %s", stripped_line)
        event = HermesStreamEvent.from_line(stripped_line)
        if event is None:
            self.logger.warning("无法解析 SSE 事件")
        return event

    def _handle_conversation_id(self, event: HermesStreamEvent) -> None:
        """处理事件中的会话ID"""
        conversation_id = event.get_conversation_id()
        if conversation_id:
            # 通过 conversation_manager 存储会话ID
            self.conversation_manager.set_conversation_id(conversation_id)

    async def _handle_event_content(self, event: HermesStreamEvent) -> AsyncGenerator[str, None]:
        """处理单个事件的内容"""
        # 处理 MCP 状态信息
        mcp_status = self.stream_processor.format_mcp_status(event)
        if mcp_status:
            yield mcp_status

        # 处理 MCP 交互事件
        if self._mcp_handler is not None:
            if event.event_type == "step.waiting_for_start":
                # 通知 TUI 切换到确认界面
                await self._mcp_handler.handle_waiting_for_start(event)
            elif event.event_type == "step.waiting_for_param":
                # 通知 TUI 切换到参数输入界面
                await self._mcp_handler.handle_waiting_for_param(event)

        # 处理 LLM 最终输出的统计信息
        llm_stats_marker = self.stream_processor.format_llm_stats_marker(event)
        if llm_stats_marker:
            yield llm_stats_marker

        # 处理文本内容：只有当不是 MCP 步骤事件时才输出文本内容
        # 这避免了 MCP 状态消息和文本内容的重复输出
        if not event.is_mcp_step_event():
            text_content = event.get_text_content()
            if text_content:
                self.stream_processor.log_text_content(text_content)
                yield text_content

    async def _stop(self) -> None:
        """停止当前会话"""
        if self._conversation_manager is None:
            return

        try:
            await self._conversation_manager.stop_conversation()
        except HermesAPIError as exc:
            self.logger.warning("Failed to stop Hermes conversation gracefully: %s", exc)

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
