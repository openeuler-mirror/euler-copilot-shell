"""HermesConversationManager 行为测试"""

from __future__ import annotations

import pytest

from backend.hermes.services import HermesConversationManager, HermesHttpManager


class _StubResponse:
    status_code = 200

    async def aread(self) -> bytes:
        return b""


class _StubClient:
    def __init__(self) -> None:
        self.is_closed = False
        self.calls: list[tuple[str, dict[str, str]]] = []

    async def post(self, url: str, *, headers: dict[str, str]) -> _StubResponse:
        self.calls.append((url, headers))
        return _StubResponse()


@pytest.mark.asyncio
async def test_stop_conversation_keeps_id_when_client_missing() -> None:
    """HTTP 客户端缺失时不应清理会话 ID"""
    http_manager = HermesHttpManager("https://api.example")
    manager = HermesConversationManager(http_manager)
    manager._conversation_id = "conv-1"  # noqa: SLF001

    await manager.stop_conversation()

    assert manager.get_conversation_id() == "conv-1"


@pytest.mark.asyncio
async def test_stop_conversation_keeps_id_after_successful_request() -> None:
    """调用 /api/stop 成功时保留会话 ID"""
    http_manager = HermesHttpManager("https://api.example")
    http_manager.client = _StubClient()  # type: ignore[assignment]
    manager = HermesConversationManager(http_manager)
    manager._conversation_id = "conv-2"  # noqa: SLF001

    await manager.stop_conversation()

    assert manager.get_conversation_id() == "conv-2"
    assert len(http_manager.client.calls) == 1  # type: ignore[union-attr]
    stop_url, _ = http_manager.client.calls[0]  # type: ignore[union-attr]
    assert stop_url.endswith("/api/stop")
