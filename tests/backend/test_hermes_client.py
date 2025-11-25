"""HermesChatClient 单元测试"""

from __future__ import annotations

from collections.abc import AsyncGenerator, Awaitable, Callable
from typing import TYPE_CHECKING, Any, cast

import pytest

from backend.hermes.client import HermesChatClient
from backend.hermes.exceptions import HermesAPIError
from backend.hermes.services import HermesConversationManager, HermesModelManager
from backend.models import ModelInfo

if TYPE_CHECKING:
    from config.manager import ConfigManager

ChatStreamCallable = Callable[[Any], AsyncGenerator[str, None]]
StopCallable = Callable[[], Awaitable[None]]

NON_OK_STATUS = 500


class _TestConversationManager(HermesConversationManager):
    """仅跟踪最新的会话 ID"""

    def __init__(self, http_manager) -> None:  # noqa: ANN001
        super().__init__(http_manager)
        self.seen_ids: list[str] = []

    def set_conversation_id(self, conversation_id: str) -> None:
        super().set_conversation_id(conversation_id)
        self.seen_ids.append(conversation_id)


class _FakeStreamResponse:
    """模拟 httpx.Response 的迭代行为"""

    def __init__(self, lines: list[str]) -> None:
        self.status_code = 200
        self._lines = lines

    async def aiter_lines(self) -> AsyncGenerator[str, None]:
        for line in self._lines:
            yield line


class _FakeErrorResponse:
    """简化的错误响应对象"""

    def __init__(self, status_code: int, payload: bytes) -> None:
        self.status_code = status_code
        self._payload = payload

    async def aread(self) -> bytes:
        return self._payload


class _StubConfigManager:
    """仅暴露 get_llm_chat_model 的配置桩对象"""

    def __init__(self, llm_id: str = "stub-llm") -> None:
        self._llm_id = llm_id

    def get_llm_chat_model(self) -> str:
        return self._llm_id


class _OverrideHermesChatClient(HermesChatClient):
    """允许注入自定义流和 stop 行为的 Hermes 客户端"""

    def __init__(
        self,
        base_url: str,
        *,
        chat_stream: ChatStreamCallable,
        stop_impl: StopCallable,
        auth_token: str = "",
        config_manager: ConfigManager | None = None,
    ) -> None:
        super().__init__(base_url, auth_token=auth_token, config_manager=config_manager)
        self._chat_stream_override = chat_stream
        self._stop_override = stop_impl

    async def _chat_stream(self, request: Any) -> AsyncGenerator[str, None]:
        async for chunk in self._chat_stream_override(request):
            yield chunk

    async def _stop(self) -> None:
        await self._stop_override()


FAIL_STOP_MESSAGE = "stop should not be invoked before follow-up questions"


@pytest.mark.asyncio
async def test_process_stream_events_yields_text_and_sets_conversation() -> None:
    """文本事件应被解析并写入会话管理器"""
    client = HermesChatClient("https://api.example")
    client._conversation_manager = _TestConversationManager(client.http_manager)  # noqa: SLF001

    response = _FakeStreamResponse(
        [
            'data: {"event":"text.add","content":{"text":"hello"},"conversationId":"conv-1"}',
            "data: [DONE]",
        ],
    )

    fake_response: Any = response
    chunks = [chunk async for chunk in client._process_stream_events(fake_response)]  # noqa: SLF001

    assert chunks == ["hello"]
    assert client._conversation_manager.seen_ids == ["conv-1"]  # noqa: SLF001


@pytest.mark.asyncio
async def test_process_stream_events_emits_error_message() -> None:
    """ERROR 事件会被转换为用户可见信息"""
    client = HermesChatClient("https://api.example")
    client._conversation_manager = _TestConversationManager(client.http_manager)  # noqa: SLF001

    response = _FakeStreamResponse([
        "data: [ERROR]",
    ])

    fake_response: Any = response
    chunks = [chunk async for chunk in client._process_stream_events(fake_response)]  # noqa: SLF001

    assert chunks == ["后端服务出现错误，请稍后重试。"]


@pytest.mark.asyncio
async def test_validate_chat_response_raises_on_non_ok() -> None:
    """非 200 响应会抛出 HermesAPIError"""
    client = HermesChatClient("https://api.example")
    response = _FakeErrorResponse(NON_OK_STATUS, b"boom")

    fake_response: Any = response
    with pytest.raises(HermesAPIError) as exc:
        await client._validate_chat_response(fake_response)  # noqa: SLF001

    assert exc.value.status_code == NON_OK_STATUS
    assert "boom" in str(exc.value)


@pytest.mark.asyncio
async def test_get_available_models_delegates_to_model_manager() -> None:
    """模型列表直接透传 HermesModelManager 的结果"""
    client = HermesChatClient("https://api.example")

    class _StubModelManager(HermesModelManager):
        async def get_available_models(self) -> list[ModelInfo]:
            return [ModelInfo(model_name="m1", llm_id="llm-1")]

    client._model_manager = _StubModelManager(client.http_manager)  # noqa: SLF001

    models = await client.get_available_models()

    assert [model.model_name for model in models] == ["m1"]


@pytest.mark.asyncio
async def test_get_llm_response_reuses_existing_conversation_id(monkeypatch: pytest.MonkeyPatch) -> None:
    """后续提问应携带已存在的 conversationId"""
    monkeypatch.setattr("backend.hermes.client.get_locale", lambda: "zh")

    stub_config = cast("ConfigManager", _StubConfigManager())
    requested_ids: list[str] = []

    async def fake_chat_stream(request: Any) -> AsyncGenerator[str, None]:
        requested_ids.append(request.conversation_id or "")
        yield "ok"

    async def fail_stop() -> None:
        raise AssertionError(FAIL_STOP_MESSAGE)

    client = _OverrideHermesChatClient(
        "https://api.example",
        chat_stream=fake_chat_stream,
        stop_impl=fail_stop,
        config_manager=stub_config,
    )
    conversation_manager = HermesConversationManager(client.http_manager)
    conversation_manager._conversation_id = "conv-keep"  # noqa: SLF001
    client._conversation_manager = conversation_manager  # noqa: SLF001

    chunks = [chunk async for chunk in client.get_llm_response("hello")]

    assert chunks == ["ok"]
    assert requested_ids == ["conv-keep"]
    assert conversation_manager.get_conversation_id() == "conv-keep"
