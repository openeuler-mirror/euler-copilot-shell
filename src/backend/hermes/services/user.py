"""Hermes 用户管理器"""

from __future__ import annotations

import json
import os
import time
from typing import TYPE_CHECKING
from urllib.parse import urljoin

import httpx

from backend.hermes.constants import HTTP_OK
from log.manager import get_logger, log_api_request, log_exception

if TYPE_CHECKING:
    from typing import Any

    from .http import HermesHttpManager


class HermesUserManager:
    """Hermes 用户管理器"""

    def __init__(self, http_manager: HermesHttpManager) -> None:
        """初始化用户管理器"""
        self.logger = get_logger(__name__)
        self.http_manager = http_manager

    async def get_user_info(self) -> dict[str, Any] | None:
        """
        获取用户信息

        通过调用 GET /api/user 接口获取当前用户信息，
        包括用户标识、用户名、权限、个人令牌、自动执行设置等。

        Returns:
            dict[str, Any] | None: 用户信息字典，如果请求失败返回 None
                返回数据格式:
                {
                    "userId": str,         # 用户ID
                    "userName": str,       # 用户名
                    "isAdmin": bool,       # 是否管理员
                    "personalToken": str,  # 个人令牌
                    "autoExecute": bool    # 是否自动执行
                }

        """
        start_time = time.time()
        self.logger.info("开始请求 Hermes 用户信息 API")

        try:
            client = await self.http_manager.get_client()
            user_url = urljoin(self.http_manager.base_url, "/api/user")
            headers = self.http_manager.build_headers(self._build_remote_user_header())

            response = await client.get(user_url, headers=headers)

            duration = time.time() - start_time
            log_api_request(
                self.logger,
                "GET",
                user_url,
                response.status_code,
                duration,
            )

            # 处理HTTP错误状态
            if response.status_code != HTTP_OK:
                error_msg = f"API 调用失败，状态码: {response.status_code}"
                self.logger.warning("获取用户信息失败: %s", error_msg)
                return None

            # 解析响应数据
            try:
                data = response.json()
            except json.JSONDecodeError:
                error_msg = "响应 JSON 格式无效"
                self.logger.warning("获取用户信息失败: %s", error_msg)
                return None

            # 验证响应结构
            if not self._validate_user_response(data):
                return None

            user_info = data["result"]
            self.logger.info(
                "获取用户信息成功 - 用户ID: %s, 用户名: %s, 自动执行: %s, 管理员: %s",
                user_info.get("userId", "未知"),
                user_info.get("userName", "未知"),
                user_info.get("autoExecute", False),
                user_info.get("isAdmin", False),
            )

        except (httpx.HTTPError, httpx.InvalidURL) as e:
            # 网络请求异常
            duration = time.time() - start_time
            log_exception(self.logger, "Hermes 用户信息 API 请求异常", e)
            log_api_request(
                self.logger,
                "GET",
                f"{self.http_manager.base_url}/api/user",
                500,
                duration,
                error=str(e),
            )
            self.logger.warning("Hermes 用户信息 API 请求异常，返回 None")
            return None
        else:
            return user_info

    async def update_user_info(self, *, auto_execute: bool = False) -> bool:
        """
        更新用户信息

        通过调用 POST /api/user 接口更新当前用户的自动执行设置。

        Args:
            auto_execute: 是否启用自动执行

        Returns:
            bool: 更新是否成功

        """
        start_time = time.time()
        self.logger.info(
            "开始请求 Hermes 用户信息更新 API - auto_execute: %s",
            auto_execute,
        )

        try:
            client = await self.http_manager.get_client()
            user_url = urljoin(self.http_manager.base_url, "/api/user")
            headers = self.http_manager.build_headers(
                {
                    "Content-Type": "application/json",
                },
            )

            # 构建请求体
            request_data: dict[str, Any] = {
                "autoExecute": auto_execute,
            }

            response = await client.post(user_url, headers=headers, json=request_data)

            duration = time.time() - start_time
            log_api_request(
                self.logger,
                "POST",
                user_url,
                response.status_code,
                duration,
            )

            # 处理HTTP错误状态
            if response.status_code != HTTP_OK:
                error_msg = f"API 调用失败，状态码: {response.status_code}"
                self.logger.warning("更新用户信息失败: %s", error_msg)
                return False

        except (httpx.HTTPError, httpx.InvalidURL) as e:
            # 网络请求异常
            duration = time.time() - start_time
            log_exception(self.logger, "Hermes 用户信息更新 API 请求异常", e)
            log_api_request(
                self.logger,
                "POST",
                f"{self.http_manager.base_url}/api/user",
                500,
                duration,
                error=str(e),
            )
            self.logger.warning("Hermes 用户信息更新 API 请求异常")
            return False
        else:
            self.logger.info("更新用户信息成功")
            return True

    def _validate_user_response(self, data: dict[str, Any]) -> bool:
        """验证用户信息 API 响应结构"""
        if not isinstance(data, dict):
            self.logger.warning("用户信息响应格式无效：不是字典")
            return False

        # 检查基本响应结构
        code = int(data.get("code", 400))
        if code != HTTP_OK:
            self.logger.warning("用户信息 API 返回错误代码: %s", code)
            return False

        # 检查 result 字段
        result = data.get("result")
        if not isinstance(result, dict):
            self.logger.warning("用户信息 result 字段不是对象")
            return False

        # 检查必要字段是否存在
        required_fields = ["userId", "userName", "isAdmin", "autoExecute"]
        for field in required_fields:
            if field not in result:
                self.logger.warning("用户信息缺少必要字段: %s", field)
                return False

        return True

    def _build_remote_user_header(self) -> dict[str, str]:
        """构建带有当前 Linux 用户 UID 的请求头"""
        remote_uid = self._get_remote_user_id()
        if remote_uid is None:
            return {}
        return {
            "X-Remote-User": remote_uid,
        }

    def _get_remote_user_id(self) -> str | None:
        """获取当前 Linux 用户的 UID"""
        try:
            uid = os.getuid()
        except AttributeError:
            self.logger.warning("当前系统不支持 os.getuid()，无法设置 X-Remote-User 请求头")
            return None
        except OSError as error:  # pragma: no cover - 仅在异常系统状态下触发
            self.logger.warning("获取当前用户 UID 失败: %s", error)
            return None

        return str(uid)
