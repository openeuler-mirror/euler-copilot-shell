"""Hermes MCP 服务管理器"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from urllib.parse import urljoin

import httpx

from backend.hermes.constants import HTTP_OK, ITEMS_PER_PAGE
from backend.hermes.exceptions import HermesAPIError
from log.manager import get_logger, log_api_request, log_exception

if TYPE_CHECKING:
    from .http import HermesHttpManager


@dataclass
class MCPService:
    """MCP 服务信息对象"""

    mcp_service_id: str
    name: str
    description: str
    author: str
    is_active: bool
    status: str

    @staticmethod
    def from_dict(data: dict[str, Any]) -> MCPService:
        """从字典创建 MCPService 对象"""
        return MCPService(
            mcp_service_id=data.get("mcpserviceId", ""),
            name=data.get("name", ""),
            description=data.get("description", ""),
            author=data.get("author", ""),
            is_active=data.get("isActive", False),
            status=data.get("status", ""),
        )


class HermesMCPManager:
    """Hermes MCP 管理器"""

    def __init__(self, http_manager: HermesHttpManager) -> None:
        """
        初始化 MCP 管理器

        Args:
            http_manager: HTTP 管理器

        """
        self.logger = get_logger(__name__)
        self.http_manager = http_manager

    async def activate_all_mcp(self) -> None:
        """
        激活所有可用的 MCP 服务

        获取所有 MCP 服务列表，筛选 is_active=False 且 status="ready" 的服务，
        并分别调用 activate_mcp 方法将它们全部激活。

        Raises:
            HermesAPIError: 当获取服务列表或激活服务失败时抛出

        """
        start_time = time.time()
        self.logger.info("开始激活所有可用的 MCP 服务")

        try:
            # 获取所有 MCP 服务
            all_services = await self.get_mcp_services()
            self.logger.info("获取到 %d 个 MCP 服务", len(all_services))

            # 筛选需要激活的服务（未激活且状态为 ready）
            services_to_activate = [
                service for service in all_services if not service.is_active and service.status == "ready"
            ]

            self.logger.info("筛选出 %d 个需要激活的 MCP 服务", len(services_to_activate))

            if not services_to_activate:
                self.logger.info("没有需要激活的 MCP 服务")
                return

            # 逐个激活服务
            activated_count = 0
            for service in services_to_activate:
                try:
                    service_id = await self.activate_mcp(
                        service.mcp_service_id,
                        active=True,
                    )
                    activated_count += 1
                    self.logger.info(
                        "成功激活 MCP 服务 - %s (serviceId: %s)",
                        service.name,
                        service_id,
                    )
                except HermesAPIError:
                    self.logger.exception(
                        "激活 MCP 服务失败 - %s (%s)",
                        service.name,
                        service.mcp_service_id,
                    )
                    raise

            total_duration = time.time() - start_time
            self.logger.info(
                "激活所有可用 MCP 服务完成 - 激活数: %d, 耗时: %.3fs",
                activated_count,
                total_duration,
            )

        except HermesAPIError:
            raise
        except Exception as e:
            log_exception(self.logger, "激活所有 MCP 服务异常", e)
            raise HermesAPIError(500, f"Activate all MCP error: {e!s}") from e

    async def activate_mcp(self, mcp_id: str, *, active: bool, mcp_env: dict[str, Any] | None = None) -> str:
        """
        激活或停用 MCP 服务

        通过调用 POST /api/mcp/{mcpId} 接口激活或停用指定的 MCP 服务。

        Args:
            mcp_id: MCP 服务 ID
            active: 是否激活
            mcp_env: MCP 环境变量字典，默认为空字典

        Returns:
            str: 返回的服务 ID (serviceId)

        Raises:
            HermesAPIError: 当 API 调用失败时抛出

        """
        if mcp_env is None:
            mcp_env = {}

        start_time = time.time()
        self.logger.info("开始激活/停用 MCP 服务 - mcpId: %s, active: %s", mcp_id, active)

        try:
            client = await self.http_manager.get_client()
            mcp_url = urljoin(self.http_manager.base_url, f"/api/mcp/{mcp_id}")

            headers = self.http_manager.build_headers()

            # 构建请求数据
            request_data = {
                "active": active,
                "mcpEnv": mcp_env,
            }

            self.logger.debug("MCP 激活请求数据: %s", request_data)

            response = await client.post(mcp_url, json=request_data, headers=headers)

            duration = time.time() - start_time

            if response.status_code != HTTP_OK:
                error_text = response.text
                log_api_request(
                    self.logger,
                    "POST",
                    mcp_url,
                    response.status_code,
                    duration,
                    error=error_text,
                )
                raise HermesAPIError(response.status_code, error_text)

            service_id = response.json()["result"]["serviceId"]

            log_api_request(
                self.logger,
                "POST",
                mcp_url,
                response.status_code,
                duration,
                service_id=service_id,
            )

        except httpx.HTTPError as e:
            duration = time.time() - start_time
            log_exception(self.logger, "MCP 激活 API 请求异常", e)
            log_api_request(
                self.logger,
                "POST",
                f"{self.http_manager.base_url}/api/mcp/{mcp_id}",
                500,
                duration,
                error=str(e),
            )
            raise HermesAPIError(500, f"Network error: {e!s}") from e
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            duration = time.time() - start_time
            log_exception(self.logger, "MCP 激活响应解析异常", e)
            log_api_request(
                self.logger,
                "POST",
                f"{self.http_manager.base_url}/api/mcp/{mcp_id}",
                500,
                duration,
                error=str(e),
            )
            raise HermesAPIError(500, f"Data parsing error: {e!s}") from e

        else:
            self.logger.info("MCP 服务激活/停用成功 - serviceId: %s", service_id)
            return service_id

    async def get_mcp_services(self) -> list[MCPService]:
        """
        获取所有 MCP 服务列表

        通过调用 GET /api/mcp 接口获取当前用户可用的所有 MCP 服务列表。
        函数会自动处理分页，每页最多 16 项，直到获取所有页面。

        Returns:
            list[MCPService]: 所有 MCP 服务的列表

        Raises:
            HermesAPIError: 当 API 调用失败时抛出

        """
        start_time = time.time()
        self.logger.info("开始请求所有 MCP 服务列表（自动分页）")

        all_services = []
        current_page = 1

        try:
            client = await self.http_manager.get_client()
            mcp_url = urljoin(self.http_manager.base_url, "/api/mcp")
            headers = self.http_manager.build_headers()

            while True:
                page_start_time = time.time()
                self.logger.info("请求第 %d 页 MCP 服务列表", current_page)

                # 添加分页参数
                params = {"page": current_page}
                response = await client.get(mcp_url, headers=headers, params=params)

                page_duration = time.time() - page_start_time

                if response.status_code != HTTP_OK:
                    error_text = response.text
                    log_api_request(
                        self.logger,
                        "GET",
                        mcp_url,
                        response.status_code,
                        page_duration,
                        error=error_text,
                    )
                    raise HermesAPIError(response.status_code, error_text)

                services_data = response.json()["result"].get("services", [])

                page_services = []
                for service_data in services_data:
                    service = MCPService.from_dict(service_data)
                    page_services.append(service)

                all_services.extend(page_services)

                log_api_request(
                    self.logger,
                    "GET",
                    mcp_url,
                    response.status_code,
                    page_duration,
                    page=current_page,
                    service_count=len(page_services),
                )

                self.logger.info("第 %d 页获取 %d 个服务", current_page, len(page_services))

                # 如果本页服务数少于 16，说明是最后一页
                if len(page_services) < ITEMS_PER_PAGE:
                    self.logger.info("已到达最后一页")
                    break

                current_page += 1

            total_duration = time.time() - start_time

        except httpx.HTTPError as e:
            duration = time.time() - start_time
            log_exception(self.logger, "MCP 列表 API 请求异常", e)
            log_api_request(
                self.logger,
                "GET",
                f"{self.http_manager.base_url}/api/mcp",
                500,
                duration,
                error=str(e),
            )
            raise HermesAPIError(500, f"Network error: {e!s}") from e
        except (json.JSONDecodeError, KeyError, ValueError, AttributeError, TypeError) as e:
            duration = time.time() - start_time
            log_exception(self.logger, "MCP 列表响应解析异常", e)
            log_api_request(
                self.logger,
                "GET",
                f"{self.http_manager.base_url}/api/mcp",
                500,
                duration,
                error=str(e),
            )
            raise HermesAPIError(500, f"Data parsing error: {e!s}") from e

        else:
            self.logger.info(
                "获取所有 MCP 服务列表完成 - 总页数: %d, 总服务数: %d, 耗时: %.3fs",
                current_page,
                len(all_services),
                total_duration,
            )

            return all_services
