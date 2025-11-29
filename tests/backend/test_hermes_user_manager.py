"""HermesUserManager 相关单元测试"""

from __future__ import annotations

from typing import Any

import pytest

from backend.hermes.constants import HTTP_OK
from backend.hermes.services.user import HermesUserManager


class _FakeResponse:
    """模拟 httpx.Response 以便测试"""

    def __init__(self) -> None:
        self.status_code = HTTP_OK

    def json(self) -> dict[str, Any]:
        return {
            "code": HTTP_OK,
            "result": {
                "userId": "demo",
                "userName": "Demo User",
                "isAdmin": False,
                "personalToken": "token",
                "autoExecute": True,
            },
        }


class _FakeAsyncClient:
    """记录 GET 请求参数的假 httpx.AsyncClient"""

    def __init__(self) -> None:
        self.request_url: str | None = None
        self.request_headers: dict[str, str] | None = None

    async def get(self, url: str, *, headers: dict[str, str]) -> _FakeResponse:
        self.request_url = url
        self.request_headers = headers
        return _FakeResponse()


class _StubHttpManager:
    """最小化的 HermesHttpManager stub"""

    def __init__(self) -> None:
        self.base_url = "https://api.example"
        self._client = _FakeAsyncClient()

    async def get_client(self) -> _FakeAsyncClient:
        return self._client

    def build_headers(self, extra_headers: dict[str, str] | None = None) -> dict[str, str]:
        headers = {"Host": "api.example"}
        if extra_headers:
            headers.update(extra_headers)
        return headers


@pytest.mark.asyncio
async def test_get_user_info_includes_remote_user_header(monkeypatch: pytest.MonkeyPatch) -> None:
    """GET /api/user 请求应包含当前 Linux UID"""
    remote_uid = 2048
    monkeypatch.setattr("backend.hermes.services.user.os.getuid", lambda: remote_uid)

    http_manager = _StubHttpManager()
    user_manager = HermesUserManager(http_manager)  # type: ignore[arg-type]

    user_info = await user_manager.get_user_info()

    assert user_info is not None
    assert user_info["userId"] == "demo"

    assert http_manager._client.request_url == "https://api.example/api/user"  # noqa: SLF001
    assert http_manager._client.request_headers is not None  # noqa: SLF001
    assert http_manager._client.request_headers["X-Remote-User"] == str(remote_uid)  # noqa: SLF001
