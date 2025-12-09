"""Hermes 模型管理器"""

from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING
from urllib.parse import urljoin

import httpx

from backend.hermes.constants import HTTP_OK
from backend.hermes.exceptions import HermesAPIError, HermesPermissionError
from backend.models import LLMConfig, LLMGlobalSetting, ModelInfo
from log.manager import get_logger, log_api_request, log_exception

if TYPE_CHECKING:
    from collections.abc import Callable

    from .http import HermesHttpManager


class HermesModelManager:
    """Hermes 模型管理器"""

    def __init__(
        self,
        http_manager: HermesHttpManager,
        admin_checker: Callable[[], bool] | None = None,
    ) -> None:
        """
        初始化模型管理器

        Args:
            http_manager: HTTP 管理器
            admin_checker: 管理员权限检查回调函数，返回 True 表示是管理员

        """
        self.logger = get_logger(__name__)
        self.http_manager = http_manager
        self._admin_checker = admin_checker

    def _require_admin(self) -> None:
        """
        检查当前用户是否为管理员

        Raises:
            HermesPermissionError: 当用户不是管理员时抛出

        """
        if self._admin_checker is None:
            self.logger.warning("未设置管理员检查器，拒绝访问管理员接口")
            msg = "未配置权限检查，无法访问管理员接口"
            raise HermesPermissionError(msg)

        if not self._admin_checker():
            self.logger.warning("非管理员用户尝试访问管理员接口")
            msg = "需要管理员权限才能执行此操作"
            raise HermesPermissionError(msg)

    async def get_available_models(self) -> list[ModelInfo]:
        """
        获取当前 LLM 服务中可用的模型，返回模型信息列表

        通过调用 /api/llm/provider 接口获取可用的大模型列表。
        如果调用失败或没有返回，使用空列表，后端接口会自动使用默认模型。

        返回的 ModelInfo 包含以下字段：
        - model_name: 模型名称
        - llm_id: LLM ID
        - llm_description: LLM 描述
        - llm_type: LLM 类型列表
        - max_tokens: 最大 token 数
        """
        start_time = time.time()
        self.logger.info("开始请求 Hermes 模型列表 API")

        try:
            client = await self.http_manager.get_client()
            llm_url = urljoin(self.http_manager.base_url, "/api/llm/provider")

            headers = self.http_manager.build_headers()
            response = await client.get(llm_url, headers=headers)

            duration = time.time() - start_time

            if response.status_code != HTTP_OK:
                # 如果接口调用失败，返回空列表
                log_api_request(
                    self.logger,
                    "GET",
                    llm_url,
                    response.status_code,
                    duration,
                    error="API 调用失败",
                )
                self.logger.warning("Hermes 模型列表 API 调用失败，返回空列表")
                return []

            data = response.json()

            # 检查响应格式
            if not isinstance(data, dict) or "result" not in data:
                log_api_request(
                    self.logger,
                    "GET",
                    llm_url,
                    response.status_code,
                    duration,
                    error="响应格式无效",
                )
                self.logger.warning("Hermes 模型列表 API 响应格式无效，返回空列表")
                return []

            result = data["result"]
            if not isinstance(result, list):
                log_api_request(
                    self.logger,
                    "GET",
                    llm_url,
                    response.status_code,
                    duration,
                    error="result字段不是数组",
                )
                self.logger.warning("Hermes 模型列表 API result字段不是数组，返回空列表")
                return []

            # 解析模型信息
            models = []
            for llm_info in result:
                if not isinstance(llm_info, dict):
                    continue

                llm_id = llm_info.get("llmId")
                if not llm_id:
                    continue

                # 解析并验证 llmType 字段
                llm_types = ModelInfo.parse_llm_types(llm_info.get("llmType"))

                # 构建 ModelInfo 对象
                model_info = ModelInfo(
                    model_name=llm_info.get("modelName") or llm_id,
                    llm_id=llm_id,
                    llm_description=llm_info.get("llmDescription"),
                    llm_type=llm_types,
                    max_tokens=llm_info.get("maxTokens"),
                )
                models.append(model_info)

            # 记录成功的API请求
            log_api_request(
                self.logger,
                "GET",
                llm_url,
                response.status_code,
                duration,
                model_count=len(models),
            )

            self.logger.info("获取到 %d 个可用模型", len(models))

        except (
            httpx.HTTPError,
            httpx.InvalidURL,
            json.JSONDecodeError,
            KeyError,
            ValueError,
        ) as e:
            # 如果发生网络错误、JSON解析错误或其他预期错误，返回空列表
            duration = time.time() - start_time
            log_exception(self.logger, "Hermes 模型列表 API 请求异常", e)
            log_api_request(
                self.logger,
                "GET",
                f"{self.http_manager.base_url}/api/llm",
                500,
                duration,
                error=str(e),
            )
            self.logger.warning("Hermes 模型列表 API 请求异常，返回空列表")
            return []
        else:
            return models

    async def create_or_update_model(self, config: LLMConfig) -> bool:
        """
        创建或更新大模型配置（管理员接口）

        通过调用 PUT /api/llm 接口创建或更新大模型。

        Args:
            config: 大模型配置对象

        Returns:
            bool: 操作是否成功

        Raises:
            HermesPermissionError: 当用户不是管理员时抛出
            HermesAPIError: 当 API 调用失败时抛出

        """
        self._require_admin()

        start_time = time.time()
        self.logger.info("开始创建/更新大模型: %s", config.id)

        try:
            client = await self.http_manager.get_client()
            llm_url = urljoin(self.http_manager.base_url, "/api/llm")

            headers = self.http_manager.build_headers()
            request_data = config.to_api_dict()
            response = await client.put(llm_url, headers=headers, json=request_data)

            duration = time.time() - start_time

            if response.status_code != HTTP_OK:
                log_api_request(
                    self.logger,
                    "PUT",
                    llm_url,
                    response.status_code,
                    duration,
                    error="API 调用失败",
                )
                error_msg = f"创建/更新大模型失败: HTTP {response.status_code}"
                self.logger.error(error_msg)
                raise HermesAPIError(response.status_code, error_msg)

            log_api_request(
                self.logger,
                "PUT",
                llm_url,
                response.status_code,
                duration,
                llm_id=config.id,
            )
            self.logger.info("成功创建/更新大模型: %s", config.id)

        except httpx.HTTPError as e:
            duration = time.time() - start_time
            log_exception(self.logger, "创建/更新大模型 API 请求异常", e)
            log_api_request(
                self.logger,
                "PUT",
                f"{self.http_manager.base_url}/api/llm",
                500,
                duration,
                error=str(e),
            )
            raise HermesAPIError(500, f"请求异常: {e}") from e
        else:
            return True

    async def delete_model(self, llm_id: str) -> bool:
        """
        删除大模型（管理员接口）

        通过调用 DELETE /api/llm?llmId=xxxx 接口删除大模型。

        Args:
            llm_id: 要删除的大模型 ID

        Returns:
            bool: 操作是否成功

        Raises:
            HermesPermissionError: 当用户不是管理员时抛出
            HermesAPIError: 当 API 调用失败时抛出

        """
        self._require_admin()

        start_time = time.time()
        self.logger.info("开始删除大模型: %s", llm_id)

        try:
            client = await self.http_manager.get_client()
            llm_url = urljoin(self.http_manager.base_url, f"/api/llm?llmId={llm_id}")

            headers = self.http_manager.build_headers()
            response = await client.delete(llm_url, headers=headers)

            duration = time.time() - start_time

            if response.status_code != HTTP_OK:
                log_api_request(
                    self.logger,
                    "DELETE",
                    llm_url,
                    response.status_code,
                    duration,
                    error="API 调用失败",
                )
                error_msg = f"删除大模型失败: HTTP {response.status_code}"
                self.logger.error(error_msg)
                raise HermesAPIError(response.status_code, error_msg)

            log_api_request(
                self.logger,
                "DELETE",
                llm_url,
                response.status_code,
                duration,
                llm_id=llm_id,
            )
            self.logger.info("成功删除大模型: %s", llm_id)

        except httpx.HTTPError as e:
            duration = time.time() - start_time
            log_exception(self.logger, "删除大模型 API 请求异常", e)
            log_api_request(
                self.logger,
                "DELETE",
                f"{self.http_manager.base_url}/api/llm",
                500,
                duration,
                error=str(e),
            )
            raise HermesAPIError(500, f"请求异常: {e}") from e
        else:
            return True

    async def get_model_config(self, llm_id: str) -> LLMConfig | None:
        """
        获取大模型详细配置（管理员接口）

        通过调用 GET /api/llm/config?llmId=xxxx 接口获取模型详细信息。

        Args:
            llm_id: 大模型 ID

        Returns:
            LLMConfig | None: 模型配置对象，获取失败时返回 None

        Raises:
            HermesPermissionError: 当用户不是管理员时抛出

        """
        self._require_admin()

        start_time = time.time()
        self.logger.info("开始获取大模型配置: %s", llm_id)

        try:
            client = await self.http_manager.get_client()
            llm_url = urljoin(self.http_manager.base_url, f"/api/llm/config?llmId={llm_id}")

            headers = self.http_manager.build_headers()
            response = await client.get(llm_url, headers=headers)

            duration = time.time() - start_time

            if response.status_code != HTTP_OK:
                log_api_request(
                    self.logger,
                    "GET",
                    llm_url,
                    response.status_code,
                    duration,
                    error="API 调用失败",
                )
                self.logger.warning("获取大模型配置失败: %s", llm_id)
                return None

            data = response.json()

            # 检查响应格式
            if not isinstance(data, dict) or "result" not in data:
                log_api_request(
                    self.logger,
                    "GET",
                    llm_url,
                    response.status_code,
                    duration,
                    error="响应格式无效",
                )
                self.logger.warning("获取大模型配置响应格式无效: %s", llm_id)
                return None

            result = data["result"]
            if not isinstance(result, dict):
                log_api_request(
                    self.logger,
                    "GET",
                    llm_url,
                    response.status_code,
                    duration,
                    error="result字段不是对象",
                )
                self.logger.warning("获取大模型配置 result 字段不是对象: %s", llm_id)
                return None

            # 解析配置
            config = LLMConfig.from_api_response(result)

            log_api_request(
                self.logger,
                "GET",
                llm_url,
                response.status_code,
                duration,
                llm_id=llm_id,
            )
            self.logger.info("成功获取大模型配置: %s", llm_id)

        except (
            httpx.HTTPError,
            httpx.InvalidURL,
            json.JSONDecodeError,
            KeyError,
            ValueError,
        ) as e:
            duration = time.time() - start_time
            log_exception(self.logger, "获取大模型配置 API 请求异常", e)
            log_api_request(
                self.logger,
                "GET",
                f"{self.http_manager.base_url}/api/llm/config",
                500,
                duration,
                error=str(e),
            )
            self.logger.warning("获取大模型配置请求异常: %s", llm_id)
            return None
        else:
            return config

    async def update_global_setting(self, setting: LLMGlobalSetting) -> bool:
        """
        修改全局 LLM 设置（管理员接口）

        通过调用 PUT /api/llm/setting 接口修改全局设置。

        Args:
            setting: 全局设置对象

        Returns:
            bool: 操作是否成功

        Raises:
            HermesPermissionError: 当用户不是管理员时抛出
            HermesAPIError: 当 API 调用失败时抛出

        """
        self._require_admin()

        start_time = time.time()
        self.logger.info("开始修改全局 LLM 设置")

        try:
            client = await self.http_manager.get_client()
            setting_url = urljoin(self.http_manager.base_url, "/api/llm/setting")

            headers = self.http_manager.build_headers()
            request_data = setting.to_api_dict()

            # 记录请求数据以便调试
            self.logger.debug("全局设置请求 URL: %s", setting_url)
            self.logger.debug("全局设置请求数据: %s", json.dumps(request_data, ensure_ascii=False))

            response = await client.put(setting_url, headers=headers, json=request_data)

            duration = time.time() - start_time

            if response.status_code != HTTP_OK:
                # 尝试获取响应内容以便调试
                try:
                    response_text = response.text
                    self.logger.error("全局设置 API 响应内容: %s", response_text)
                except Exception:
                    self.logger.exception("无法读取全局设置 API 响应内容")
                    response_text = "无法读取响应内容"

                # 记录完整的请求信息以便调试
                self.logger.error(
                    "全局设置 API 调用失败 - URL: %s, 请求数据: %s, 响应状态: %d",
                    setting_url,
                    json.dumps(request_data, ensure_ascii=False),
                    response.status_code,
                )

                log_api_request(
                    self.logger,
                    "PUT",
                    setting_url,
                    response.status_code,
                    duration,
                    error="API 调用失败",
                )
                error_msg = f"修改全局设置失败: HTTP {response.status_code}"
                self.logger.error(error_msg)
                raise HermesAPIError(response.status_code, error_msg)

            log_api_request(
                self.logger,
                "PUT",
                setting_url,
                response.status_code,
                duration,
            )
            self.logger.info("成功修改全局 LLM 设置")

        except httpx.HTTPError as e:
            duration = time.time() - start_time
            log_exception(self.logger, "修改全局设置 API 请求异常", e)
            log_api_request(
                self.logger,
                "PUT",
                f"{self.http_manager.base_url}/api/llm/setting",
                500,
                duration,
                error=str(e),
            )
            raise HermesAPIError(500, f"请求异常: {e}") from e
        else:
            return True
