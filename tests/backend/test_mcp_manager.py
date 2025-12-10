"""
MCP 服务模块测试

测试 mcp.py 模块中的 HermesMCPManager 和 MCPService。
"""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import httpx
import pytest

from backend.hermes.constants import HTTP_OK
from backend.hermes.exceptions import HermesAPIError
from backend.hermes.services.http import HermesHttpManager
from backend.hermes.services.mcp import HermesMCPManager, MCPService


class TestMCPService:
    """测试 MCPService 数据模型"""

    def test_init(self) -> None:
        """测试初始化"""
        service = MCPService(
            mcp_service_id="rag-mcp",
            name="RAG MCP",
            description="测试描述",
            author="root",
            is_active=True,
            status="ready",
        )

        assert service.mcp_service_id == "rag-mcp"
        assert service.name == "RAG MCP"
        assert service.description == "测试描述"
        assert service.author == "root"
        assert service.is_active is True
        assert service.status == "ready"

    def test_to_dict(self) -> None:
        """测试转换为字典"""
        service = MCPService(
            mcp_service_id="rag-mcp",
            name="RAG MCP",
            description="测试描述",
            author="root",
            is_active=True,
            status="ready",
        )

        # dataclass 自动支持转换为 dict
        result = service.__dict__
        assert result["mcp_service_id"] == "rag-mcp"
        assert result["name"] == "RAG MCP"
        assert result["description"] == "测试描述"
        assert result["author"] == "root"
        assert result["is_active"] is True
        assert result["status"] == "ready"

    def test_from_dict(self) -> None:
        """测试从字典创建对象"""
        data = {
            "mcpserviceId": "rag-mcp",
            "name": "RAG MCP",
            "description": "测试描述",
            "author": "root",
            "isActive": True,
            "status": "ready",
        }

        service = MCPService.from_dict(data)
        assert service.mcp_service_id == "rag-mcp"
        assert service.name == "RAG MCP"
        assert service.description == "测试描述"
        assert service.author == "root"
        assert service.is_active is True
        assert service.status == "ready"

    def test_from_dict_with_missing_fields(self) -> None:
        """测试从不完整字典创建对象"""
        data = {
            "mcpserviceId": "rag-mcp",
            "name": "RAG MCP",
        }

        service = MCPService.from_dict(data)
        assert service.mcp_service_id == "rag-mcp"
        assert service.name == "RAG MCP"
        assert service.description == ""
        assert service.author == ""
        assert service.is_active is False
        assert service.status == ""


class TestHermesMCPManager:
    """测试 HermesMCPManager"""

    def test_init(self) -> None:
        """测试初始化"""
        http_manager = HermesHttpManager("https://api.example.com", "token")
        mcp_manager = HermesMCPManager(http_manager)

        assert mcp_manager.http_manager is http_manager
        assert mcp_manager.logger is not None

    @pytest.mark.asyncio
    async def test_activate_mcp_success(self) -> None:
        """测试成功激活 MCP 服务"""
        http_manager = HermesHttpManager("https://api.example.com", "token")
        mcp_manager = HermesMCPManager(http_manager)

        # Mock 响应
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = HTTP_OK
        mock_response.json.return_value = {
            "code": 200,
            "message": "OK",
            "result": {
                "serviceId": "mcp-service-123456",
            },
        }

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(return_value=mock_response)

        # Mock get_client 方法
        http_manager.get_client = AsyncMock(return_value=mock_client)

        # 调用方法
        service_id = await mcp_manager.activate_mcp(
            mcp_id="rag-mcp",
            active=True,
            mcp_env={},
        )

        assert service_id == "mcp-service-123456"
        mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_activate_mcp_with_env(self) -> None:
        """测试激活 MCP 服务并传递环境变量"""
        http_manager = HermesHttpManager("https://api.example.com", "token")
        mcp_manager = HermesMCPManager(http_manager)

        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = HTTP_OK
        mock_response.json.return_value = {
            "code": 200,
            "message": "OK",
            "result": {
                "serviceId": "mcp-service-789",
            },
        }

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(return_value=mock_response)

        http_manager.get_client = AsyncMock(return_value=mock_client)

        mcp_env = {"KEY": "value"}
        service_id = await mcp_manager.activate_mcp(
            mcp_id="rag-mcp",
            active=False,
            mcp_env=mcp_env,
        )

        assert service_id == "mcp-service-789"

        # 验证调用参数
        call_args = mock_client.post.call_args
        assert call_args is not None
        json_data = call_args[1]["json"]
        assert json_data["active"] is False
        assert json_data["mcpEnv"] == mcp_env

    @pytest.mark.asyncio
    async def test_activate_mcp_api_error(self) -> None:
        """测试激活失败时抛出异常"""
        http_manager = HermesHttpManager("https://api.example.com", "token")
        mcp_manager = HermesMCPManager(http_manager)

        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(return_value=mock_response)

        http_manager.get_client = AsyncMock(return_value=mock_client)

        with pytest.raises(HermesAPIError):
            await mcp_manager.activate_mcp("rag-mcp", active=True)

    @pytest.mark.asyncio
    async def test_activate_mcp_invalid_response(self) -> None:
        """测试响应格式无效时抛出异常"""
        http_manager = HermesHttpManager("https://api.example.com", "token")
        mcp_manager = HermesMCPManager(http_manager)

        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = HTTP_OK
        mock_response.json.return_value = {
            "code": 200,
            "message": "OK",
            # 缺少 result 字段
        }

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(return_value=mock_response)

        http_manager.get_client = AsyncMock(return_value=mock_client)

        with pytest.raises(HermesAPIError):
            await mcp_manager.activate_mcp("rag-mcp", active=True)

    @pytest.mark.asyncio
    async def test_activate_mcp_missing_service_id(self) -> None:
        """测试响应中缺少 serviceId 时抛出异常"""
        http_manager = HermesHttpManager("https://api.example.com", "token")
        mcp_manager = HermesMCPManager(http_manager)

        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = HTTP_OK
        mock_response.json.return_value = {
            "code": 200,
            "message": "OK",
            "result": {
                # 缺少 serviceId
            },
        }

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(return_value=mock_response)

        http_manager.get_client = AsyncMock(return_value=mock_client)

        with pytest.raises(HermesAPIError):
            await mcp_manager.activate_mcp("rag-mcp", active=True)

    @pytest.mark.asyncio
    async def test_get_mcp_services_success(self) -> None:
        """测试成功获取 MCP 服务列表（单页，无需翻页）"""
        http_manager = HermesHttpManager("https://api.example.com", "token")
        mcp_manager = HermesMCPManager(http_manager)

        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = HTTP_OK
        mock_response.json.return_value = {
            "code": 200,
            "message": "OK",
            "result": {
                "currentPage": 1,
                "services": [
                    {
                        "mcpserviceId": "rag-mcp",
                        "name": "RAG MCP",
                        "description": "RAG 服务",
                        "author": "root",
                        "isActive": False,
                        "status": "ready",
                    },
                    {
                        "mcpserviceId": "tool-mcp",
                        "name": "Tool MCP",
                        "description": "工具服务",
                        "author": "admin",
                        "isActive": True,
                        "status": "ready",
                    },
                ],
            },
        }

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=mock_response)

        http_manager.get_client = AsyncMock(return_value=mock_client)

        services = await mcp_manager.get_mcp_services()

        assert len(services) == 2  # noqa: PLR2004
        assert services[0].mcp_service_id == "rag-mcp"
        assert services[1].mcp_service_id == "tool-mcp"

    @pytest.mark.asyncio
    async def test_get_mcp_services_empty(self) -> None:
        """测试获取空服务列表"""
        http_manager = HermesHttpManager("https://api.example.com", "token")
        mcp_manager = HermesMCPManager(http_manager)

        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = HTTP_OK
        mock_response.json.return_value = {
            "code": 200,
            "message": "OK",
            "result": {
                "currentPage": 1,
                "services": [],
            },
        }

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=mock_response)

        http_manager.get_client = AsyncMock(return_value=mock_client)

        services = await mcp_manager.get_mcp_services()

        assert len(services) == 0

    @pytest.mark.asyncio
    async def test_get_mcp_services_api_error(self) -> None:
        """测试获取服务列表失败"""
        http_manager = HermesHttpManager("https://api.example.com", "token")
        mcp_manager = HermesMCPManager(http_manager)

        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=mock_response)

        http_manager.get_client = AsyncMock(return_value=mock_client)

        with pytest.raises(HermesAPIError):
            await mcp_manager.get_mcp_services()

    @pytest.mark.asyncio
    async def test_get_mcp_services_pagination(self) -> None:
        """测试自动分页获取所有服务"""
        http_manager = HermesHttpManager("https://api.example.com", "token")
        mcp_manager = HermesMCPManager(http_manager)

        # 模拟第一页：16个服务（满页）
        mock_response_page1 = Mock(spec=httpx.Response)
        mock_response_page1.status_code = HTTP_OK
        mock_response_page1.json.return_value = {
            "code": 200,
            "message": "OK",
            "result": {
                "currentPage": 1,
                "services": [
                    {
                        "mcpserviceId": f"service-{i}",
                        "name": f"Service {i}",
                        "description": f"Service {i} description",
                        "author": "admin",
                        "isActive": False,
                        "status": "ready",
                    }
                    for i in range(1, 17)  # 16 个服务
                ],
            },
        }

        # 模拟第二页：2个服务（不足16个，为最后一页）
        mock_response_page2 = Mock(spec=httpx.Response)
        mock_response_page2.status_code = HTTP_OK
        mock_response_page2.json.return_value = {
            "code": 200,
            "message": "OK",
            "result": {
                "currentPage": 2,
                "services": [
                    {
                        "mcpserviceId": "service-17",
                        "name": "Service 17",
                        "description": "Service 17 description",
                        "author": "admin",
                        "isActive": False,
                        "status": "ready",
                    },
                    {
                        "mcpserviceId": "service-18",
                        "name": "Service 18",
                        "description": "Service 18 description",
                        "author": "admin",
                        "isActive": False,
                        "status": "ready",
                    },
                ],
            },
        }

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        # 第一次调用返回第一页，第二次调用返回第二页
        mock_client.get = AsyncMock(side_effect=[mock_response_page1, mock_response_page2])

        http_manager.get_client = AsyncMock(return_value=mock_client)

        services = await mcp_manager.get_mcp_services()

        # 应该获取到总共 18 个服务
        assert len(services) == 18  # noqa: PLR2004
        assert services[0].mcp_service_id == "service-1"
        assert services[16].mcp_service_id == "service-17"
        assert services[17].mcp_service_id == "service-18"

        # 验证发送了两次请求
        assert mock_client.get.call_count == 2  # noqa: PLR2004

    @pytest.mark.asyncio
    async def test_get_mcp_services_invalid_response(self) -> None:
        """测试响应格式无效"""
        http_manager = HermesHttpManager("https://api.example.com", "token")
        mcp_manager = HermesMCPManager(http_manager)

        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = HTTP_OK
        mock_response.json.return_value = {
            "code": 200,
            "message": "OK",
            # 缺少 result
        }

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=mock_response)

        http_manager.get_client = AsyncMock(return_value=mock_client)

        with pytest.raises(HermesAPIError):
            await mcp_manager.get_mcp_services()

    @pytest.mark.asyncio
    async def test_get_mcp_services_invalid_services_field(self) -> None:
        """测试 services 字段类型无效"""
        http_manager = HermesHttpManager("https://api.example.com", "token")
        mcp_manager = HermesMCPManager(http_manager)

        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = HTTP_OK
        mock_response.json.return_value = {
            "code": 200,
            "message": "OK",
            "result": {
                "currentPage": 1,
                "services": "not-a-list",  # 无效的类型
            },
        }

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=mock_response)

        http_manager.get_client = AsyncMock(return_value=mock_client)

        with pytest.raises(HermesAPIError):
            await mcp_manager.get_mcp_services()

    @pytest.mark.asyncio
    async def test_activate_all_mcp_success(self) -> None:
        """测试成功激活所有可用的 MCP 服务"""
        http_manager = HermesHttpManager("https://api.example.com", "token")
        mcp_manager = HermesMCPManager(http_manager)

        # Mock get_mcp_services 返回的数据
        services = [
            MCPService(
                mcp_service_id="rag-mcp",
                name="RAG MCP",
                description="RAG 服务",
                author="admin",
                is_active=False,
                status="ready",
            ),
            MCPService(
                mcp_service_id="search-mcp",
                name="Search MCP",
                description="搜索服务",
                author="admin",
                is_active=False,
                status="ready",
            ),
            MCPService(
                mcp_service_id="web-mcp",
                name="Web MCP",
                description="Web 服务",
                author="admin",
                is_active=True,  # 已激活，不应该再激活
                status="ready",
            ),
            MCPService(
                mcp_service_id="test-mcp",
                name="Test MCP",
                description="测试服务",
                author="admin",
                is_active=False,
                status="error",  # 状态不是 ready，不应该激活
            ),
        ]

        # Mock activate_mcp 响应
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = HTTP_OK
        mock_response.json.return_value = {
            "code": 200,
            "message": "OK",
            "result": {"serviceId": "mcp-service-123456"},
        }

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.get = AsyncMock(return_value=mock_response)

        http_manager.get_client = AsyncMock(return_value=mock_client)

        # Mock get_mcp_services
        mcp_manager.get_mcp_services = AsyncMock(return_value=services)

        # 调用方法
        await mcp_manager.activate_all_mcp()

        # 验证只激活了 2 个服务（rag-mcp 和 search-mcp）
        assert mock_client.post.call_count == 2  # noqa: PLR2004

    @pytest.mark.asyncio
    async def test_activate_all_mcp_no_services_to_activate(self) -> None:
        """测试没有需要激活的 MCP 服务"""
        http_manager = HermesHttpManager("https://api.example.com", "token")
        mcp_manager = HermesMCPManager(http_manager)

        # 所有服务都已激活或状态不是 ready
        services = [
            MCPService(
                mcp_service_id="web-mcp",
                name="Web MCP",
                description="Web 服务",
                author="admin",
                is_active=True,
                status="ready",
            ),
            MCPService(
                mcp_service_id="test-mcp",
                name="Test MCP",
                description="测试服务",
                author="admin",
                is_active=False,
                status="error",
            ),
        ]

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock()

        http_manager.get_client = AsyncMock(return_value=mock_client)
        mcp_manager.get_mcp_services = AsyncMock(return_value=services)

        # 调用方法
        await mcp_manager.activate_all_mcp()

        # 验证没有调用 post
        mock_client.post.assert_not_called()

    @pytest.mark.asyncio
    async def test_activate_all_mcp_activation_failure(self) -> None:
        """测试激活过程中某个服务失败"""
        http_manager = HermesHttpManager("https://api.example.com", "token")
        mcp_manager = HermesMCPManager(http_manager)

        services = [
            MCPService(
                mcp_service_id="rag-mcp",
                name="RAG MCP",
                description="RAG 服务",
                author="admin",
                is_active=False,
                status="ready",
            ),
            MCPService(
                mcp_service_id="search-mcp",
                name="Search MCP",
                description="搜索服务",
                author="admin",
                is_active=False,
                status="ready",
            ),
        ]

        http_manager.get_client = AsyncMock()
        mcp_manager.get_mcp_services = AsyncMock(return_value=services)

        # Mock activate_mcp 在第一个服务时成功，第二个时失败
        activate_mcp_mock = AsyncMock()
        activate_mcp_mock.side_effect = [
            "mcp-service-1",
            HermesAPIError(500, "Activation failed"),
        ]
        mcp_manager.activate_mcp = activate_mcp_mock

        # 验证抛出异常
        with pytest.raises(HermesAPIError):
            await mcp_manager.activate_all_mcp()

        # 验证尝试激活了 2 个服务，但第二个失败
        assert activate_mcp_mock.call_count == 2  # noqa: PLR2004

