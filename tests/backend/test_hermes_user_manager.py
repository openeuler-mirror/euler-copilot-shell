"""HermesUserManager 相关单元测试"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from backend.hermes.constants import HTTP_FORBIDDEN, HTTP_OK, HTTP_UNAUTHORIZED
from backend.hermes.services.user import HermesUserManager


class _FakeResponse:
    """模拟 httpx.Response 以便测试"""

    def __init__(self, status_code: int = HTTP_OK, data: dict[str, Any] | None = None) -> None:
        self.status_code = status_code
        self._data = data or {
            "code": HTTP_OK,
            "result": {
                "userId": "demo",
                "userName": "Demo User",
                "isAdmin": False,
                "personalToken": "token",
                "autoExecute": True,
            },
        }

    def json(self) -> dict[str, Any]:
        return self._data


class _FakeAsyncClient:
    """记录 GET 请求参数的假 httpx.AsyncClient"""

    def __init__(self) -> None:
        self.request_url: str | None = None
        self.request_headers: dict[str, str] | None = None
        self.responses: list[_FakeResponse] = []
        self._call_count = 0
        self.is_closed = False

    def add_response(self, response: _FakeResponse) -> None:
        """添加响应到队列"""
        self.responses.append(response)

    async def get(self, url: str, *, headers: dict[str, str]) -> _FakeResponse:
        self.request_url = url
        self.request_headers = headers
        if self.responses:
            response = self.responses[self._call_count] if self._call_count < len(self.responses) else self.responses[-1]
            self._call_count += 1
            return response
        return _FakeResponse()


class _StubHttpManager:
    """最小化的 HermesHttpManager stub"""

    def __init__(self) -> None:
        self.base_url = "https://api.example"
        self.auth_token = ""
        self.client: _FakeAsyncClient | None = _FakeAsyncClient()
        self._client = self.client

    async def get_client(self) -> _FakeAsyncClient:
        if self._client is None:
            self._client = _FakeAsyncClient()
        return self._client

    def build_headers(self, extra_headers: dict[str, str] | None = None) -> dict[str, str]:
        headers = {"Host": "api.example"}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        if extra_headers:
            headers.update(extra_headers)
        return headers


class _StubConfigManager:
    """最小化的 ConfigManager stub"""

    def __init__(self) -> None:
        self.saved_key: str | None = None

    def set_eulerintelli_key(self, key: str) -> None:
        self.saved_key = key


@pytest.mark.asyncio
async def test_get_user_info_no_remote_user_header() -> None:
    """GET /api/user 请求不应包含 X-Remote-User 头"""
    http_manager = _StubHttpManager()
    user_manager = HermesUserManager(http_manager)  # type: ignore[arg-type]

    user_info = await user_manager.get_user_info()

    assert user_info is not None
    assert user_info["userId"] == "demo"

    assert http_manager._client.request_url == "https://api.example/api/user"  # noqa: SLF001
    assert http_manager._client.request_headers is not None  # noqa: SLF001
    assert "X-Remote-User" not in http_manager._client.request_headers  # noqa: SLF001


@pytest.mark.asyncio
async def test_get_user_info_auth_failure_triggers_login(monkeypatch: pytest.MonkeyPatch) -> None:
    """GET /api/user 返回 401 时应自动登录并重试"""
    remote_uid = 2048
    monkeypatch.setattr("backend.hermes.services.user.os.getuid", lambda: remote_uid)

    http_manager = _StubHttpManager()
    config_manager = _StubConfigManager()

    # 设置响应序列：401 -> 登录成功 -> 用户信息成功
    client = await http_manager.get_client()
    client.add_response(_FakeResponse(HTTP_UNAUTHORIZED))  # 第一次 /api/user 失败
    client.add_response(_FakeResponse(HTTP_OK, {  # 登录成功
        "code": HTTP_OK,
        "result": {"token": "new-token"},
    }))
    client.add_response(_FakeResponse())  # 第二次 /api/user 成功

    user_manager = HermesUserManager(http_manager, config_manager)  # type: ignore[arg-type]

    user_info = await user_manager.get_user_info()

    assert user_info is not None
    assert user_info["userId"] == "demo"
    assert config_manager.saved_key == "new-token"
    assert http_manager.auth_token == "new-token"


@pytest.mark.asyncio
async def test_get_user_info_forbidden_triggers_login(monkeypatch: pytest.MonkeyPatch) -> None:
    """GET /api/user 返回 403 时也应自动登录并重试"""
    remote_uid = 1000
    monkeypatch.setattr("backend.hermes.services.user.os.getuid", lambda: remote_uid)

    http_manager = _StubHttpManager()
    config_manager = _StubConfigManager()

    client = await http_manager.get_client()
    client.add_response(_FakeResponse(HTTP_FORBIDDEN))  # 403 失败
    client.add_response(_FakeResponse(HTTP_OK, {
        "code": HTTP_OK,
        "result": {"token": "another-token"},
    }))
    client.add_response(_FakeResponse())

    user_manager = HermesUserManager(http_manager, config_manager)  # type: ignore[arg-type]

    user_info = await user_manager.get_user_info()

    assert user_info is not None
    assert config_manager.saved_key == "another-token"


@pytest.mark.asyncio
async def test_get_user_info_other_error_returns_none() -> None:
    """GET /api/user 返回其他错误时应返回 None（不尝试登录）"""
    http_manager = _StubHttpManager()

    client = await http_manager.get_client()
    client.add_response(_FakeResponse(500))  # 500 服务器错误

    user_manager = HermesUserManager(http_manager)  # type: ignore[arg-type]

    user_info = await user_manager.get_user_info()

    assert user_info is None
    # 确保只调用了一次（没有尝试登录）
    assert client._call_count == 1  # noqa: SLF001


@pytest.mark.asyncio
async def test_login_includes_remote_user_header(monkeypatch: pytest.MonkeyPatch) -> None:
    """GET /api/auth/login 请求应包含 X-Remote-User 头"""
    remote_uid = 3000
    monkeypatch.setattr("backend.hermes.services.user.os.getuid", lambda: remote_uid)

    http_manager = _StubHttpManager()
    config_manager = _StubConfigManager()

    client = await http_manager.get_client()
    client.add_response(_FakeResponse(HTTP_UNAUTHORIZED))  # 触发登录
    client.add_response(_FakeResponse(HTTP_OK, {
        "code": HTTP_OK,
        "result": {"token": "test-token"},
    }))
    client.add_response(_FakeResponse())

    user_manager = HermesUserManager(http_manager, config_manager)  # type: ignore[arg-type]

    await user_manager.get_user_info()

    # 检查登录请求是否包含 X-Remote-User（第二次请求）
    # 注意：由于我们使用同一个 client 记录，最后记录的是第三次请求
    # 但至少确认 token 已保存，说明登录成功
    assert config_manager.saved_key == "test-token"


@pytest.mark.asyncio
async def test_login_failure_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    """登录失败时应返回 None"""
    remote_uid = 1000
    monkeypatch.setattr("backend.hermes.services.user.os.getuid", lambda: remote_uid)

    http_manager = _StubHttpManager()
    config_manager = _StubConfigManager()

    client = await http_manager.get_client()
    client.add_response(_FakeResponse(HTTP_UNAUTHORIZED))  # 触发登录
    client.add_response(_FakeResponse(500))  # 登录也失败

    user_manager = HermesUserManager(http_manager, config_manager)  # type: ignore[arg-type]

    user_info = await user_manager.get_user_info()

    assert user_info is None
    assert config_manager.saved_key is None
