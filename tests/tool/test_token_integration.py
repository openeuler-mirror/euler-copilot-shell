"""
测试令牌验证与 OI 连接集成

运行方法：
    pytest tests/tool/test_token_integration.py -v
"""

from collections.abc import Sequence
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from i18n.manager import _
from tool.validators import validate_oi_connection


@pytest.mark.asyncio
@pytest.mark.integration
class TestTokenIntegration:
    """测试令牌验证与 OI 连接集成"""

    async def test_invalid_token_no_request(self, invalid_token_samples: Sequence[str]) -> None:
        """测试无效令牌不会发送 HTTP 请求"""
        base_url = "http://localhost:8080"

        # Mock httpx.AsyncClient 来验证是否发送了请求
        with patch("tool.validators.httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_client_instance

            for token in invalid_token_samples:
                valid, message = await validate_oi_connection(base_url, token)

                # 验证结果
                assert valid is False, f"应该拒绝无效令牌: {token}"
                assert _("访问令牌格式无效") in message, f"错误消息应该提示格式无效: {message}"

                # 验证没有发送 HTTP 请求
                mock_client_instance.get.assert_not_called()

                # 重置 mock 以便下一次测试
                mock_client_instance.reset_mock()

    async def test_valid_token_sends_request(self, valid_token_samples: Sequence[str]) -> None:
        """测试有效令牌会发送 HTTP 请求"""
        base_url = "http://localhost:8080"

        for token in valid_token_samples:
            # Mock httpx.AsyncClient
            with patch("tool.validators.httpx.AsyncClient") as mock_client:
                mock_response = AsyncMock()
                mock_response.status_code = 200
                # response.json() 是同步方法
                mock_response.json = lambda: {"code": 200, "data": {}}

                mock_client_instance = AsyncMock()
                mock_client_instance.get = AsyncMock(return_value=mock_response)
                mock_client.return_value.__aenter__.return_value = mock_client_instance

                # 执行验证
                _valid, _message = await validate_oi_connection(base_url, token)

                # 验证发送了 HTTP 请求
                mock_client_instance.get.assert_called_once()

    @pytest.mark.parametrize(
        "invalid_url",
        [
            "localhost:8080",  # 缺少协议
            "ftp://localhost:8080",  # 错误的协议
            "localhost",  # 无端口无协议
        ],
    )
    async def test_url_validation_priority(self, invalid_url: str) -> None:
        """测试 URL 格式验证优先于令牌验证"""
        # 使用有效令牌
        valid_token = "a1b2c3d4e5f6789012345678abcdef90"  # noqa: S105

        with patch("tool.validators.httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_client_instance

            valid, message = await validate_oi_connection(invalid_url, valid_token)

            # 验证结果
            assert valid is False, f"应该拒绝无效 URL: {invalid_url}"
            assert "http://" in message or "https://" in message, f"错误消息应该提示协议错误: {message}"

            # 验证没有发送 HTTP 请求
            mock_client_instance.get.assert_not_called()

    async def test_successful_connection(self) -> None:
        """测试成功连接的情况"""
        base_url = "http://localhost:8080"
        valid_token = "a1b2c3d4e5f6789012345678abcdef90"  # noqa: S105

        with patch("tool.validators.httpx.AsyncClient") as mock_client:
            mock_response = AsyncMock()
            mock_response.status_code = 200
            # response.json() 是同步方法，不要使用 AsyncMock
            mock_response.json = lambda: {"code": 200, "data": {}}

            mock_client_instance = AsyncMock()
            mock_client_instance.get = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value = mock_client_instance

            valid, message = await validate_oi_connection(base_url, valid_token)

            assert valid is True
            assert _("连接成功") in message

    async def test_connection_error_handling(self) -> None:
        """测试连接错误处理"""
        base_url = "http://localhost:8080"
        valid_token = "a1b2c3d4e5f6789012345678abcdef90"  # noqa: S105

        with patch("tool.validators.httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client_instance.get.side_effect = httpx.ConnectError("Connection failed")
            mock_client.return_value.__aenter__.return_value = mock_client_instance

            valid, message = await validate_oi_connection(base_url, valid_token)

            assert valid is False
            assert _("无法连接到服务，请检查 URL 和网络连接") in message
