"""Hermes 用户管理器"""

from __future__ import annotations

import getpass
import json
import time
from typing import TYPE_CHECKING
from urllib.parse import urljoin

import httpx

from backend.hermes.constants import HTTP_FORBIDDEN, HTTP_OK, HTTP_UNAUTHORIZED
from log.manager import get_logger, log_api_request, log_exception

if TYPE_CHECKING:
    from typing import Any

    from config.manager import ConfigManager

    from .http import HermesHttpManager


class HermesUserManager:
    """Hermes 用户管理器"""

    def __init__(
        self,
        http_manager: HermesHttpManager,
        config_manager: ConfigManager | None = None,
    ) -> None:
        """
        初始化用户管理器

        Args:
            http_manager: HTTP 管理器
            config_manager: 配置管理器（用于保存登录后获取的 token）

        """
        self.logger = get_logger(__name__)
        self.http_manager = http_manager
        self.config_manager = config_manager

    async def get_user_info(self) -> dict[str, Any] | None:
        """
        获取用户信息

        通过调用 GET /api/user 接口获取当前用户信息，
        包括用户标识、用户名、权限、个人令牌、自动执行设置等。

        如果请求返回认证失败（401/403），会自动调用登录接口获取 token 并重试。

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
        # 第一次尝试获取用户信息
        result = await self._fetch_user_info()

        if result is not None:
            return result

        # 如果是认证失败，尝试登录后重试
        if self._last_status_code in (HTTP_UNAUTHORIZED, HTTP_FORBIDDEN):
            self.logger.info("用户信息请求认证失败，尝试自动登录")
            login_success = await self._login()
            if login_success:
                # 登录成功后重新获取用户信息
                self.logger.info("登录成功，重新获取用户信息")
                return await self._fetch_user_info()
            self.logger.warning("自动登录失败，无法获取用户信息")
            return None

        # 其他错误（后端配置错误等）
        return None

    async def _fetch_user_info(self) -> dict[str, Any] | None:
        """
        实际执行获取用户信息的请求

        Returns:
            dict[str, Any] | None: 用户信息字典，如果请求失败返回 None

        """
        self._last_status_code: int = 0
        start_time = time.time()
        self.logger.info("开始请求 Hermes 用户信息 API")

        try:
            client = await self.http_manager.get_client()
            user_url = urljoin(self.http_manager.base_url, "/api/user")
            headers = self.http_manager.build_headers()

            response = await client.get(user_url, headers=headers)

            duration = time.time() - start_time
            self._last_status_code = response.status_code
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

    async def _login(self) -> bool:
        """
        调用登录接口获取 token

        通过调用 GET /api/auth/login 接口获取认证 token，
        并将 token 保存到配置和 HTTP 管理器中。

        Returns:
            bool: 登录是否成功

        """
        start_time = time.time()
        self.logger.info("开始请求 Hermes 登录 API")

        try:
            client = await self.http_manager.get_client()
            login_url = urljoin(self.http_manager.base_url, "/api/auth/login")
            headers = self.http_manager.build_headers(self._build_remote_user_header())

            response = await client.get(login_url, headers=headers)

            duration = time.time() - start_time
            log_api_request(
                self.logger,
                "GET",
                login_url,
                response.status_code,
                duration,
            )

            # 处理HTTP错误状态
            if response.status_code != HTTP_OK:
                error_msg = f"登录 API 调用失败，状态码: {response.status_code}"
                self.logger.warning("登录失败: %s", error_msg)
                return False

            # 解析响应数据
            try:
                data = response.json()
            except json.JSONDecodeError:
                self.logger.warning("登录响应 JSON 格式无效")
                return False

            # 验证响应结构并提取 token
            if not self._validate_login_response(data):
                return False

            token = data["result"]["token"]
            self.logger.info("登录成功，获取到 token")

            # 保存 token 到配置
            self._save_token(token)

            # 更新 HTTP 管理器中的 token
            self._update_http_manager_token(token)

        except (httpx.HTTPError, httpx.InvalidURL) as e:
            duration = time.time() - start_time
            log_exception(self.logger, "Hermes 登录 API 请求异常", e)
            log_api_request(
                self.logger,
                "GET",
                f"{self.http_manager.base_url}/api/auth/login",
                500,
                duration,
                error=str(e),
            )
            return False
        else:
            return True

    def _validate_login_response(self, data: dict[str, Any]) -> bool:
        """验证登录 API 响应结构"""
        if not isinstance(data, dict):
            self.logger.warning("登录响应格式无效：不是字典")
            return False

        code = int(data.get("code", 400))
        if code != HTTP_OK:
            self.logger.warning("登录 API 返回错误代码: %s", code)
            return False

        result = data.get("result")
        if not isinstance(result, dict):
            self.logger.warning("登录响应 result 字段不是对象")
            return False

        if "token" not in result:
            self.logger.warning("登录响应缺少 token 字段")
            return False

        return True

    def _save_token(self, token: str) -> None:
        """保存 token 到配置"""
        if self.config_manager is None:
            self.logger.warning("配置管理器未设置，无法保存 token")
            return

        self.config_manager.set_witty_key(token)
        self.logger.info("token 已保存到配置")

    def _update_http_manager_token(self, token: str) -> None:
        """更新 HTTP 管理器中的 token"""
        self.http_manager.auth_token = token
        # 关闭现有客户端，下次请求时会使用新的 token 创建新客户端
        if self.http_manager.client is not None and not self.http_manager.client.is_closed:
            # 使用同步方式标记客户端需要重建
            # 实际关闭会在下次 get_client 时处理
            self.http_manager.client = None
        self.logger.info("HTTP 管理器 token 已更新")

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
        """构建带有当前 Linux 用户名的请求头"""
        remote_user = self._get_remote_user_name()
        if remote_user is None:
            return {}
        return {
            "X-Remote-User": remote_user,
        }

    def _get_remote_user_name(self) -> str | None:
        """获取当前 Linux 用户名"""
        # 尝试多种方法获取用户名，按优先级排序
        username = None

        try:
            username = getpass.getuser()
            if username:
                self.logger.debug("从 getpass 模块获取到用户名: %s", username)
                return username
        except (ImportError, OSError):
            pass

        self.logger.warning("无法通过任何方法获取当前用户名，无法设置 X-Remote-User 请求头")
        return None
