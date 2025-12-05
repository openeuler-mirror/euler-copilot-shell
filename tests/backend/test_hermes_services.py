"""
Hermes 服务模块测试

测试 model.py, conversation.py, agent.py 等服务模块。
"""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import httpx
import pytest

from backend.hermes.constants import HTTP_OK
from backend.hermes.exceptions import HermesPermissionError
from backend.hermes.services.agent import HermesAgentManager
from backend.hermes.services.conversation import HermesConversationManager
from backend.hermes.services.http import HermesHttpManager
from backend.hermes.services.model import HermesModelManager
from backend.models import LLMConfig, LLMProvider, LLMType


class TestHermesHttpManager:
    """测试 HermesHttpManager"""

    def test_init(self) -> None:
        """测试初始化"""
        manager = HermesHttpManager("https://api.example.com/", "test-token")
        assert manager.base_url == "https://api.example.com"
        assert manager.auth_token == "test-token"  # noqa: S105
        assert manager.client is None

    def test_get_host_header(self) -> None:
        """测试获取 Host 头"""
        manager = HermesHttpManager("https://api.example.com:8080/v1")
        assert manager.get_host_header() == "api.example.com:8080"

    def test_get_host_header_simple(self) -> None:
        """测试简单 URL 的 Host 头"""
        manager = HermesHttpManager("http://localhost")
        assert manager.get_host_header() == "localhost"

    def test_build_headers_with_token(self) -> None:
        """测试构建带令牌的请求头"""
        manager = HermesHttpManager("https://api.example.com", "my-token")
        headers = manager.build_headers()
        assert headers["Host"] == "api.example.com"
        assert headers["Authorization"] == "Bearer my-token"

    def test_build_headers_without_token(self) -> None:
        """测试构建不带令牌的请求头"""
        manager = HermesHttpManager("https://api.example.com", "")
        headers = manager.build_headers()
        assert headers["Host"] == "api.example.com"
        assert "Authorization" not in headers

    def test_build_headers_with_extra(self) -> None:
        """测试构建带额外头的请求头"""
        manager = HermesHttpManager("https://api.example.com", "token")
        headers = manager.build_headers({"X-Custom": "value"})
        assert headers["X-Custom"] == "value"
        assert headers["Authorization"] == "Bearer token"

    @pytest.mark.asyncio
    async def test_get_client_creates_new(self) -> None:
        """测试获取客户端会创建新客户端"""
        manager = HermesHttpManager("https://api.example.com", "token")
        client = await manager.get_client()
        assert client is not None
        assert manager.client is client
        await manager.close()

    @pytest.mark.asyncio
    async def test_get_client_reuses_existing(self) -> None:
        """测试获取客户端会复用已有客户端"""
        manager = HermesHttpManager("https://api.example.com", "token")
        client1 = await manager.get_client()
        client2 = await manager.get_client()
        assert client1 is client2
        await manager.close()

    @pytest.mark.asyncio
    async def test_close(self) -> None:
        """测试关闭客户端"""
        manager = HermesHttpManager("https://api.example.com", "token")
        await manager.get_client()
        await manager.close()
        assert manager.client.is_closed # pyright: ignore[reportOptionalMemberAccess]


class TestHermesConversationManager:
    """测试 HermesConversationManager"""

    def test_init(self) -> None:
        """测试初始化"""
        http_manager = Mock()
        manager = HermesConversationManager(http_manager)
        assert manager._conversation_id is None  # noqa: SLF001

    def test_reset_conversation(self) -> None:
        """测试重置会话"""
        http_manager = Mock()
        manager = HermesConversationManager(http_manager)
        manager._conversation_id = "test-id"  # noqa: SLF001
        manager.reset_conversation()
        assert manager._conversation_id is None  # noqa: SLF001

    def test_get_conversation_id_empty(self) -> None:
        """测试获取空会话 ID"""
        http_manager = Mock()
        manager = HermesConversationManager(http_manager)
        assert manager.get_conversation_id() == ""

    def test_get_conversation_id_with_value(self) -> None:
        """测试获取会话 ID"""
        http_manager = Mock()
        manager = HermesConversationManager(http_manager)
        manager._conversation_id = "test-conv-id"  # noqa: SLF001
        assert manager.get_conversation_id() == "test-conv-id"

    def test_set_conversation_id(self) -> None:
        """测试设置会话 ID"""
        http_manager = Mock()
        manager = HermesConversationManager(http_manager)
        manager.set_conversation_id("new-id")
        assert manager._conversation_id == "new-id"  # noqa: SLF001

    def test_set_conversation_id_empty(self) -> None:
        """测试设置空会话 ID 不会覆盖"""
        http_manager = Mock()
        manager = HermesConversationManager(http_manager)
        manager._conversation_id = "existing-id"  # noqa: SLF001
        manager.set_conversation_id("")
        assert manager._conversation_id == "existing-id"  # noqa: SLF001

    def test_set_conversation_id_same_value(self) -> None:
        """测试设置相同会话 ID"""
        http_manager = Mock()
        manager = HermesConversationManager(http_manager)
        manager._conversation_id = "same-id"  # noqa: SLF001
        manager.set_conversation_id("same-id")
        assert manager._conversation_id == "same-id"  # noqa: SLF001

    @pytest.mark.asyncio
    async def test_stop_conversation_no_id(self) -> None:
        """测试停止没有会话 ID 的会话"""
        http_manager = Mock()
        manager = HermesConversationManager(http_manager)
        # 不应该抛出异常
        await manager.stop_conversation()

    @pytest.mark.asyncio
    async def test_stop_conversation_closed_client(self) -> None:
        """测试客户端已关闭时停止会话"""
        http_manager = Mock()
        http_manager.client = None
        manager = HermesConversationManager(http_manager)
        manager._conversation_id = "test-id"  # noqa: SLF001
        # 不应该抛出异常
        await manager.stop_conversation()


class TestHermesModelManager:
    """测试 HermesModelManager"""

    def test_init(self) -> None:
        """测试初始化"""
        http_manager = Mock()
        manager = HermesModelManager(http_manager)
        assert manager._admin_checker is None  # noqa: SLF001

    def test_init_with_admin_checker(self) -> None:
        """测试带管理员检查器的初始化"""
        http_manager = Mock()
        checker = Mock(return_value=True)
        manager = HermesModelManager(http_manager, admin_checker=checker)
        assert manager._admin_checker is checker  # noqa: SLF001

    def test_require_admin_no_checker(self) -> None:
        """测试无管理员检查器时拒绝访问"""
        http_manager = Mock()
        manager = HermesModelManager(http_manager)
        with pytest.raises(HermesPermissionError):
            manager._require_admin()  # noqa: SLF001

    def test_require_admin_not_admin(self) -> None:
        """测试非管理员用户"""
        http_manager = Mock()
        checker = Mock(return_value=False)
        manager = HermesModelManager(http_manager, admin_checker=checker)
        with pytest.raises(HermesPermissionError):
            manager._require_admin()  # noqa: SLF001

    def test_require_admin_is_admin(self) -> None:
        """测试管理员用户"""
        http_manager = Mock()
        checker = Mock(return_value=True)
        manager = HermesModelManager(http_manager, admin_checker=checker)
        # 不应该抛出异常
        manager._require_admin()  # noqa: SLF001

    @pytest.mark.asyncio
    async def test_get_available_models_success(self) -> None:
        """测试成功获取模型列表"""
        http_manager = Mock()
        http_manager.base_url = "https://api.example.com"
        http_manager.build_headers.return_value = {}

        mock_response = Mock()
        mock_response.status_code = HTTP_OK
        mock_response.json.return_value = {
            "result": [
                {
                    "llmId": "gpt-4",
                    "modelName": "gpt-4-turbo",
                    "llmDescription": "GPT-4 Turbo",
                    "llmType": ["chat", "function"],
                    "maxTokens": 8192,
                },
            ],
        }

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        http_manager.get_client = AsyncMock(return_value=mock_client)

        manager = HermesModelManager(http_manager)
        models = await manager.get_available_models()

        assert len(models) == 1
        assert models[0].llm_id == "gpt-4"
        assert models[0].model_name == "gpt-4-turbo"
        assert LLMType.CHAT in models[0].llm_type
        assert LLMType.FUNCTION in models[0].llm_type

    @pytest.mark.asyncio
    async def test_get_available_models_empty_result(self) -> None:
        """测试空模型列表"""
        http_manager = Mock()
        http_manager.base_url = "https://api.example.com"
        http_manager.build_headers.return_value = {}

        mock_response = Mock()
        mock_response.status_code = HTTP_OK
        mock_response.json.return_value = {"result": []}

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        http_manager.get_client = AsyncMock(return_value=mock_client)

        manager = HermesModelManager(http_manager)
        models = await manager.get_available_models()

        assert len(models) == 0

    @pytest.mark.asyncio
    async def test_get_available_models_api_error(self) -> None:
        """测试 API 错误返回空列表"""
        http_manager = Mock()
        http_manager.base_url = "https://api.example.com"
        http_manager.build_headers.return_value = {}

        mock_response = Mock()
        mock_response.status_code = 500

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        http_manager.get_client = AsyncMock(return_value=mock_client)

        manager = HermesModelManager(http_manager)
        models = await manager.get_available_models()

        assert len(models) == 0

    @pytest.mark.asyncio
    async def test_get_available_models_invalid_response(self) -> None:
        """测试无效响应格式"""
        http_manager = Mock()
        http_manager.base_url = "https://api.example.com"
        http_manager.build_headers.return_value = {}

        mock_response = Mock()
        mock_response.status_code = HTTP_OK
        mock_response.json.return_value = {"invalid": "data"}

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        http_manager.get_client = AsyncMock(return_value=mock_client)

        manager = HermesModelManager(http_manager)
        models = await manager.get_available_models()

        assert len(models) == 0

    @pytest.mark.asyncio
    async def test_get_available_models_result_not_list(self) -> None:
        """测试 result 字段不是列表"""
        http_manager = Mock()
        http_manager.base_url = "https://api.example.com"
        http_manager.build_headers.return_value = {}

        mock_response = Mock()
        mock_response.status_code = HTTP_OK
        mock_response.json.return_value = {"result": "not a list"}

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        http_manager.get_client = AsyncMock(return_value=mock_client)

        manager = HermesModelManager(http_manager)
        models = await manager.get_available_models()

        assert len(models) == 0

    @pytest.mark.asyncio
    async def test_get_available_models_skips_invalid_items(self) -> None:
        """测试跳过无效项"""
        http_manager = Mock()
        http_manager.base_url = "https://api.example.com"
        http_manager.build_headers.return_value = {}

        mock_response = Mock()
        mock_response.status_code = HTTP_OK
        mock_response.json.return_value = {
            "result": [
                "not a dict",
                {"noLlmId": "missing"},
                {"llmId": "valid-model"},
            ],
        }

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        http_manager.get_client = AsyncMock(return_value=mock_client)

        manager = HermesModelManager(http_manager)
        models = await manager.get_available_models()

        assert len(models) == 1
        assert models[0].llm_id == "valid-model"

    @pytest.mark.asyncio
    async def test_create_or_update_model_requires_admin(self) -> None:
        """测试创建/更新模型需要管理员权限"""
        http_manager = Mock()
        manager = HermesModelManager(http_manager)

        config = LLMConfig(
            provider=LLMProvider.OPENAI,
            ctx_length=8192,
            id="test-model",
        )

        with pytest.raises(HermesPermissionError):
            await manager.create_or_update_model(config)

    @pytest.mark.asyncio
    async def test_delete_model_requires_admin(self) -> None:
        """测试删除模型需要管理员权限"""
        http_manager = Mock()
        manager = HermesModelManager(http_manager)

        with pytest.raises(HermesPermissionError):
            await manager.delete_model("test-model")


class TestHermesAgentManager:
    """测试 HermesAgentManager"""

    def test_init(self) -> None:
        """测试初始化"""
        http_manager = Mock()
        manager = HermesAgentManager(http_manager)
        assert manager.http_manager is http_manager

    @pytest.mark.asyncio
    async def test_get_available_agents_empty(self) -> None:
        """测试获取空智能体列表"""
        http_manager = Mock()
        http_manager.base_url = "https://api.example.com"
        http_manager.build_headers.return_value = {}

        mock_response = Mock()
        mock_response.status_code = HTTP_OK
        mock_response.json.return_value = {
            "result": {
                "list": [],
                "total": 0,
                "pageNum": 1,
            },
        }

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        http_manager.get_client = AsyncMock(return_value=mock_client)

        manager = HermesAgentManager(http_manager)
        agents = await manager.get_available_agents()

        assert len(agents) == 0

    @pytest.mark.asyncio
    async def test_get_available_agents_http_error(self) -> None:
        """测试 HTTP 错误返回空列表"""
        http_manager = Mock()
        http_manager.base_url = "https://api.example.com"
        http_manager.build_headers.return_value = {}

        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.HTTPError("Connection failed")
        http_manager.get_client = AsyncMock(return_value=mock_client)

        manager = HermesAgentManager(http_manager)
        agents = await manager.get_available_agents()

        assert len(agents) == 0
