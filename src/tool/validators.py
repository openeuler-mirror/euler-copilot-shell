"""
配置验证器

提供实际 API 调用验证配置的有效性。
支持通过环境变量 OI_SKIP_SSL_VERIFY / OI_SSL_VERIFY 控制 SSL 校验。
"""

from __future__ import annotations

import json
import os
from typing import Any

import httpx
from openai import APIError, AsyncOpenAI, AuthenticationError, OpenAIError

from i18n.manager import _
from log.manager import get_logger

# 常量定义
MAX_MODEL_DISPLAY = 5
HTTP_OK = 200
HTTP_UNAUTHORIZED = 401
HTTP_FORBIDDEN = 403
HTTP_NOT_FOUND = 404

TRUTHY_VALUES = {"1", "true", "yes", "on"}
FALSY_VALUES = {"0", "false", "no", "off"}
SSL_VERIFY_ENV_VAR = "OI_SSL_VERIFY"
SSL_SKIP_ENV_VAR = "OI_SKIP_SSL_VERIFY"

# 令牌格式常量
TOKEN_HEX_LENGTH = 32  # UUID4 hex 格式的长度
TOKEN_LONG_TERM_PREFIX = "sk-"  # noqa: S105
TOKEN_LONG_TERM_LENGTH = 35  # sk- (3) + 32 hex chars
TOKEN_PREVIEW_LENGTH = 5  # 日志中显示的令牌预览长度


def _parse_env_flag(value: str | None) -> bool | None:
    """解析环境变量中的布尔标志值"""
    if value is None:
        return None

    normalized = value.strip().lower()
    if normalized in TRUTHY_VALUES:
        return True
    if normalized in FALSY_VALUES:
        return False

    return None


def _resolve_verify_ssl(*, verify_ssl: bool | None = None) -> bool:
    """根据参数和环境变量确定是否启用 SSL 校验"""
    if verify_ssl is not None:
        return verify_ssl

    skip_flag = _parse_env_flag(os.getenv(SSL_SKIP_ENV_VAR))
    if skip_flag is True:
        return False
    if skip_flag is False:
        return True

    verify_flag = _parse_env_flag(os.getenv(SSL_VERIFY_ENV_VAR))
    if verify_flag is not None:
        return verify_flag

    return True


def should_verify_ssl(*, verify_ssl: bool | None = None) -> bool:
    """公开的 SSL 校验决策入口，供其他模块复用"""
    return _resolve_verify_ssl(verify_ssl=verify_ssl)


class APIValidator:
    """API 配置验证器"""

    def __init__(self, *, verify_ssl: bool | None = None) -> None:
        """初始化验证器"""
        self.logger = get_logger(__name__)
        self.verify_ssl = should_verify_ssl(verify_ssl=verify_ssl)
        self.logger.debug("SSL 验证状态: %s", self.verify_ssl)

    async def validate_llm_config(  # noqa: PLR0913
        self,
        endpoint: str,
        api_key: str,
        model: str,
        timeout: int = 30,  # noqa: ASYNC109
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> tuple[bool, str, dict[str, Any]]:
        """
        验证 LLM 配置

        Args:
            endpoint: API 端点
            api_key: API 密钥
            model: 模型名称
            timeout: 超时时间（秒）
            max_tokens: 最大令牌数，如果为 None 则使用默认值
            temperature: 温度参数，如果为 None 则使用默认值

        Returns:
            tuple[bool, str, dict]: (是否验证成功, 错误/成功消息, 额外信息)

        """
        self.logger.info("开始验证 LLM 配置 - 端点: %s, 模型: %s", endpoint, model)

        try:
            client = self._create_openai_client(
                endpoint=endpoint,
                api_key=api_key,
                timeout=timeout,
            )

            # 测试基本对话功能
            chat_valid, chat_msg = await self._test_basic_chat(client, model, max_tokens, temperature)
            if not chat_valid:
                await client.close()
                return False, chat_msg, {}

            # 测试 function_call 支持并检测类型
            func_valid, _func_msg, func_type = await self._detect_function_call_type(
                client,
                model,
                max_tokens,
                temperature,
            )

            await client.close()

        except TimeoutError:
            return False, _("连接超时 - 无法在 {timeout} 秒内连接到 {endpoint}").format(
                timeout=timeout,
                endpoint=endpoint,
            ), {}
        except (AuthenticationError, APIError, OpenAIError) as e:
            error_msg = _("LLM 配置验证失败: {error}").format(error=str(e))
            self.logger.exception(error_msg)
            return False, error_msg, {}
        else:
            success_msg = _("LLM 配置验证成功")
            if func_valid:
                success_msg += _(" - 支持工具调用，类型: {func_type}").format(func_type=func_type)
            else:
                success_msg += _(" - 不支持工具调用")

            return (
                True,
                success_msg,
                {
                    "supports_function_call": func_valid,
                    "detected_function_call_type": func_type,
                },
            )

    async def validate_embedding_config(
        self,
        endpoint: str,
        api_key: str,
        model: str,
        timeout: int = 30,  # noqa: ASYNC109
    ) -> tuple[bool, str, dict[str, Any]]:
        """
        验证 Embedding 配置

        Args:
            endpoint: API 端点
            api_key: API 密钥
            model: 模型名称
            timeout: 超时时间（秒）

        Returns:
            tuple[bool, str, dict]: (是否验证成功, 错误/成功消息, 额外信息)

        """
        self.logger.info("开始验证 Embedding 配置 - 端点: %s", endpoint)

        # 首先尝试 OpenAI 格式
        openai_success, openai_msg, openai_info = await self._validate_openai_embedding(
            endpoint,
            api_key,
            model,
            timeout,
        )
        if openai_success:
            return True, openai_msg, openai_info

        # 如果 OpenAI 格式失败，尝试 MindIE 格式
        mindie_success, mindie_msg, mindie_info = await self._validate_mindie_embedding(
            endpoint,
            api_key,
            timeout,
        )
        if mindie_success:
            return True, mindie_msg, mindie_info

        # 两种格式都失败
        return False, _("无法连接到 Embedding 模型服务。"), {}

    def _create_openai_client(
        self,
        *,
        endpoint: str,
        api_key: str,
        timeout: int,
    ) -> AsyncOpenAI:
        """构造 AsyncOpenAI 客户端，应用统一的 SSL 校验设置"""
        http_client = httpx.AsyncClient(timeout=timeout, verify=self.verify_ssl)
        return AsyncOpenAI(
            api_key=api_key,
            base_url=endpoint,
            timeout=timeout,
            http_client=http_client,
        )

    async def _test_basic_chat(
        self,
        client: AsyncOpenAI,
        model: str,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> tuple[bool, str]:
        """测试基本对话功能"""
        try:
            # 使用传入的参数或默认值
            call_kwargs = {
                "model": model,
                "messages": [{"role": "user", "content": "请回复'测试成功'"}],
                "max_tokens": max_tokens if max_tokens is not None else 10,
            }

            # 只有当 temperature 不为 None 时才添加到参数中
            if temperature is not None:
                call_kwargs["temperature"] = temperature

            response = await client.chat.completions.create(**call_kwargs)
        except (AuthenticationError, APIError, OpenAIError):
            return False, _("基本对话测试失败")
        else:
            if response.choices and len(response.choices) > 0:
                return True, _("基本对话功能正常")

            return False, _("对话响应为空")

    async def _detect_function_call_type(
        self,
        client: AsyncOpenAI,
        model: str,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> tuple[bool, str, str]:
        """
        检测并测试不同类型的 function_call 支持

        按照以下顺序尝试：
        1. OpenAI 标准 function_call 格式
        2. OpenAI tools 格式
        3. vLLM 特有格式
        4. Ollama 特有格式

        Returns:
            tuple[bool, str, str]: (是否支持, 详细消息, 格式类型)

        """
        # 尝试 OpenAI tools 格式
        tools_valid, tools_msg = await self._test_tools_format(
            client,
            model,
            max_tokens,
            temperature,
        )
        if tools_valid:
            return True, tools_msg, "function_call"

        # 尝试 structured_output 格式
        structured_valid, structured_msg = await self._test_structured_output(
            client,
            model,
            max_tokens,
            temperature,
        )
        if structured_valid:
            return True, structured_msg, "structured_output"

        # 尝试 json_mode 格式
        json_mode_valid, json_mode_msg = await self._test_json_mode(
            client,
            model,
            max_tokens,
            temperature,
        )
        if json_mode_valid:
            return True, json_mode_msg, "json_mode"

        # 尝试 vLLM 格式
        vllm_valid, vllm_msg = await self._test_vllm_function_call(
            client,
            model,
            max_tokens,
            temperature,
        )
        if vllm_valid:
            return True, vllm_msg, "vllm"

        # 尝试 Ollama 格式
        ollama_valid, ollama_msg = await self._test_ollama_function_call(
            client,
            model,
            max_tokens,
            temperature,
        )
        if ollama_valid:
            return True, ollama_msg, "ollama"

        return False, _("不支持任何 function_call 格式"), "none"

    async def _test_tools_format(
        self,
        client: AsyncOpenAI,
        model: str,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> tuple[bool, str]:
        """测试新版 tools 格式的 function calling"""
        try:
            test_tool = {
                "type": "function",
                "function": {
                    "name": "get_current_time",
                    "description": "获取当前时间",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            }

            # 构建请求参数
            call_kwargs = {
                "model": model,
                "messages": [{"role": "user", "content": "请调用函数获取当前时间"}],
                "tools": [test_tool],  # type: ignore[arg-type]
                "tool_choice": "auto",
                "max_tokens": max_tokens if max_tokens is not None else 50,
            }

            # 只有当 temperature 不为 None 时才添加到参数中
            if temperature is not None:
                call_kwargs["temperature"] = temperature

            response = await client.chat.completions.create(**call_kwargs)
        except (AuthenticationError, APIError, OpenAIError) as e:
            return False, _("tools 格式测试失败: {error}").format(error=str(e))
        else:
            if response.choices and len(response.choices) > 0:
                choice = response.choices[0]
                if hasattr(choice.message, "tool_calls") and choice.message.tool_calls:
                    return True, _("支持 tools 格式的 function_call")

            return False, _("不支持工具调用功能")

    async def _test_structured_output(
        self,
        client: AsyncOpenAI,
        model: str,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> tuple[bool, str]:
        """测试 structured_output 格式的 JSON 输出"""
        try:
            test_schema = {
                "type": "object",
                "properties": {
                    "status": {"type": "string"},
                    "timestamp": {"type": "string"},
                },
                "required": ["status"],
                "additionalProperties": False,
            }

            call_kwargs = {
                "model": model,
                "messages": [{"role": "user", "content": "请返回状态信息的JSON"}],
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "status_response",
                        "description": "Status response in JSON format",
                        "schema": test_schema,
                        "strict": True,
                    },
                },
                "max_tokens": max_tokens if max_tokens is not None else 50,
            }

            if temperature is not None:
                call_kwargs["temperature"] = temperature

            response = await client.chat.completions.create(**call_kwargs)
        except (AuthenticationError, APIError, OpenAIError) as e:
            return False, _("structured_output 格式测试失败: {error}").format(error=str(e))
        else:
            if response.choices and len(response.choices) > 0:
                choice = response.choices[0]
                if hasattr(choice.message, "content") and choice.message.content:
                    try:
                        json.loads(choice.message.content)
                    except (json.JSONDecodeError, ValueError):
                        return False, _("structured_output 响应不是有效 JSON")
                    else:
                        return True, _("支持 structured_output 格式")

            return False, _("structured_output 响应为空")

    async def _test_json_mode(
        self,
        client: AsyncOpenAI,
        model: str,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> tuple[bool, str]:
        """测试 json_mode 格式的 JSON 输出"""
        try:
            call_kwargs = {
                "model": model,
                "messages": [
                    {"role": "system", "content": "你必须返回有效的JSON格式"},
                    {"role": "user", "content": "请返回包含status字段的JSON对象"},
                ],
                "response_format": {"type": "json_object"},
                "max_tokens": max_tokens if max_tokens is not None else 50,
            }

            if temperature is not None:
                call_kwargs["temperature"] = temperature

            response = await client.chat.completions.create(**call_kwargs)
        except (AuthenticationError, APIError, OpenAIError) as e:
            return False, _("json_mode 格式测试失败: {error}").format(error=str(e))
        else:
            if response.choices and len(response.choices) > 0:
                choice = response.choices[0]
                if hasattr(choice.message, "content") and choice.message.content:
                    try:
                        json.loads(choice.message.content)
                    except (json.JSONDecodeError, ValueError):
                        return False, _("json_mode 响应不是有效 JSON")
                    else:
                        return True, _("支持 json_mode 格式")

            return False, _("json_mode 响应为空")

    async def _test_vllm_function_call(
        self,
        client: AsyncOpenAI,
        model: str,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> tuple[bool, str]:
        """测试 vLLM 特有的 guided_json 格式"""
        try:
            # vLLM 支持 guided_json 参数来强制 JSON 输出
            test_schema = {
                "type": "object",
                "properties": {
                    "status": {"type": "string"},
                    "message": {"type": "string"},
                },
                "required": ["status"],
            }

            call_kwargs = {
                "model": model,
                "messages": [{"role": "user", "content": "请返回状态信息的JSON"}],
                "max_tokens": max_tokens if max_tokens is not None else 50,
                "extra_body": {"guided_json": test_schema},
            }

            if temperature is not None:
                call_kwargs["temperature"] = temperature

            response = await client.chat.completions.create(**call_kwargs)

            if response.choices and len(response.choices) > 0:
                choice = response.choices[0]
                content = getattr(choice.message, "content", "")

                if content:
                    try:
                        json.loads(content)
                    except (json.JSONDecodeError, ValueError):
                        # 如果不是有效 JSON，可能不支持 guided_json
                        pass
                    else:
                        return True, "支持 vLLM guided_json 格式"

                # 检查是否包含结构化输出的迹象
                if content and any(keyword in content.lower() for keyword in ["json", "{", "}"]):
                    return True, _("支持 vLLM 结构化输出（部分支持）")

        except (AuthenticationError, APIError, OpenAIError) as e:
            error_str = str(e).lower()
            if any(keyword in error_str for keyword in ["extra_body", "guided_json", "not supported"]):
                return False, _("不支持 vLLM guided_json 格式: {error}").format(error=str(e))
            raise

        else:
            return False, _("vLLM guided_json 响应无效")

    async def _test_ollama_function_call(
        self,
        client: AsyncOpenAI,
        model: str,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> tuple[bool, str]:
        """测试 Ollama 特有的 function calling 格式"""
        try:
            # Ollama 对 function calling 的支持可能有限
            # 通常通过特殊的 prompt 格式来实现

            # 尝试使用结构化 prompt 来测试 function calling
            structured_prompt = """
你是一个助手，可以调用函数。当需要调用函数时，请按以下格式回复：
FUNCTION_CALL: get_current_time()

现在请调用 get_current_time 函数获取当前时间。
"""

            call_kwargs = {
                "model": model,
                "messages": [{"role": "user", "content": structured_prompt}],
                "max_tokens": max_tokens if max_tokens is not None else 100,
            }

            if temperature is not None:
                call_kwargs["temperature"] = temperature

            response = await client.chat.completions.create(**call_kwargs)

            if response.choices and len(response.choices) > 0:
                choice = response.choices[0]
                content = getattr(choice.message, "content", "")

                # 检查 Ollama 可能的函数调用响应格式
                if content and any(
                    keyword in content
                    for keyword in [
                        "FUNCTION_CALL:",
                        "get_current_time",
                        "function",
                        "call",
                    ]
                ):
                    return True, _("支持 Ollama function_call 格式")

        except (AuthenticationError, APIError, OpenAIError) as e:
            return False, _("不支持 Ollama function_call 格式: {error}").format(error=str(e))

        else:
            return False, _("Ollama function_call 响应无效")

    async def _validate_openai_embedding(
        self,
        endpoint: str,
        api_key: str,
        model: str,
        timeout: int = 30,  # noqa: ASYNC109
    ) -> tuple[bool, str, dict[str, Any]]:
        """验证 OpenAI 格式的 embedding 配置"""
        try:
            client = self._create_openai_client(
                endpoint=endpoint,
                api_key=api_key,
                timeout=timeout,
            )

            # 测试 embedding 功能
            test_text = "这是一个测试文本"
            response = await client.embeddings.create(input=test_text, model=model)

            await client.close()
        except TimeoutError:
            return False, _("连接超时 - 无法在 {timeout} 秒内连接到 {endpoint}").format(
                timeout=timeout,
                endpoint=endpoint,
            ), {}
        except (AuthenticationError, APIError, OpenAIError) as e:
            error_msg = _("OpenAI Embedding 配置验证失败: {error}").format(error=str(e))
            self.logger.exception(error_msg)
            return False, error_msg, {}
        else:
            if response.data and len(response.data) > 0:
                embedding = response.data[0].embedding
                dimension = len(embedding)
                return (
                    True,
                    _("OpenAI Embedding 配置验证成功 - 维度: {dimension}").format(dimension=dimension),
                    {
                        "type": "openai",
                        "dimension": dimension,
                        "sample_embedding_length": len(embedding),
                    },
                )

            return False, _("OpenAI Embedding 响应为空"), {}

    async def _validate_mindie_embedding(
        self,
        endpoint: str,
        api_key: str,
        timeout: int = 30,  # noqa: ASYNC109
    ) -> tuple[bool, str, dict[str, Any]]:
        """验证 MindIE (TEI) 格式的 embedding 配置"""
        try:
            embed_endpoint = endpoint.rstrip("/") + "/embed"
            headers = {"Content-Type": "application/json"}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"

            data = {"inputs": "这是一个测试文本", "normalize": True}

            async with httpx.AsyncClient(timeout=timeout, verify=self.verify_ssl) as client:
                response = await client.post(embed_endpoint, json=data, headers=headers)

                if response.status_code == HTTP_OK:
                    json_response = response.json()
                    if isinstance(json_response, list) and len(json_response) > 0:
                        embedding = json_response[0]
                        if isinstance(embedding, list) and len(embedding) > 0:
                            dimension = len(embedding)
                            return (
                                True,
                                _("MindIE Embedding 配置验证成功 - 维度: {dimension}").format(
                                    dimension=dimension,
                                ),
                                {
                                    "type": "mindie",
                                    "dimension": dimension,
                                    "sample_embedding_length": len(embedding),
                                },
                            )

                return False, _("MindIE Embedding 响应格式不正确"), {}

        except httpx.TimeoutException:
            return False, _("连接超时 - 无法在 {timeout} 秒内连接到 {endpoint}").format(
                timeout=timeout,
                endpoint=endpoint,
            ), {}
        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            error_msg = _("MindIE Embedding 配置验证失败: {error}").format(error=str(e))
            self.logger.exception(error_msg)
            return False, error_msg, {}


async def validate_oi_connection(base_url: str, access_token: str) -> tuple[bool, str]:  # noqa: PLR0911
    """
    验证 openEuler Intelligence 服务连接

    Args:
        base_url: 服务 URL
        access_token: 访问令牌（可为空）

    Returns:
        tuple[bool, str]: (连接是否成功, 消息)

    """
    logger = get_logger(__name__)

    try:
        # 确保 URL 格式正确
        if not base_url.startswith(("http://", "https://")):
            return False, _("服务 URL 必须以 http:// 或 https:// 开头")

        # 验证令牌格式
        if not _is_valid_token_format(access_token):
            # 记录令牌的前几个字符用于调试
            token_preview = (
                access_token[:TOKEN_PREVIEW_LENGTH] + "..."
                if len(access_token) > TOKEN_PREVIEW_LENGTH
                else access_token
            )
            logger.warning("访问令牌格式无效: %s", token_preview)
            return False, _("访问令牌格式无效")

        # 移除尾部的斜杠
        base_url = base_url.rstrip("/")

        # 构造用户信息 API URL
        api_url = f"{base_url}/api/user"

        # 准备请求头
        headers = {}
        if access_token and access_token.strip():
            headers["Authorization"] = f"Bearer {access_token}"

        async with httpx.AsyncClient(timeout=10) as client:
            # 发送请求
            response = await client.get(api_url, headers=headers)

            # 检查 HTTP 状态码
            if response.status_code != HTTP_OK:
                return _handle_http_error(response.status_code)

            # 检查响应内容
            try:
                response_data = response.json()
            except (ValueError, TypeError, KeyError):
                return False, _("服务返回的数据格式不正确")

            # 检查 code 字段
            code = response_data.get("code")
            if code == HTTP_OK:
                logger.info("openEuler Intelligence 服务连接成功")
                return True, _("连接成功")

            return False, _("服务返回错误代码: {code}").format(code=code)

    except httpx.ConnectError:
        return False, _("无法连接到服务，请检查 URL 和网络连接")
    except httpx.TimeoutException:
        return False, _("连接超时，请检查网络连接或服务状态")
    except Exception as e:
        logger.exception("验证 openEuler Intelligence 连接时发生异常")
        return False, _("连接验证失败: {error}").format(error=str(e))


def _handle_http_error(status_code: int) -> tuple[bool, str]:
    """处理 HTTP 错误状态码"""
    error_messages = {
        HTTP_UNAUTHORIZED: _("访问令牌无效或已过期"),
        HTTP_FORBIDDEN: _("访问权限不足"),
        HTTP_NOT_FOUND: _("API 接口不存在，请检查服务版本"),
    }

    message = error_messages.get(status_code, _("服务响应异常，状态码: {status_code}").format(status_code=status_code))
    return False, message


def _is_valid_token_format(token: str) -> bool:
    """
    验证令牌格式是否有效

    支持三种格式：
    1. 空字符串（兼容旧版本）
    2. 32字符的十六进制字符串（短期令牌，uuid4().hex格式）
    3. sk- 前缀 + 32字符的十六进制字符串（长期令牌）

    Args:
        token: 访问令牌

    Returns:
        bool: 令牌格式是否有效

    """
    if not token or not token.strip():
        # 空令牌，兼容旧版本
        return True

    token = token.strip()

    # 检查是否为32字符的十六进制字符串（短期令牌）
    if len(token) == TOKEN_HEX_LENGTH and all(c in "0123456789abcdef" for c in token.lower()):
        return True

    # 检查是否为 sk- 前缀的长期令牌
    if token.startswith(TOKEN_LONG_TERM_PREFIX) and len(token) == TOKEN_LONG_TERM_LENGTH:
        hex_part = token[len(TOKEN_LONG_TERM_PREFIX) :]
        if all(c in "0123456789abcdef" for c in hex_part.lower()):
            return True

    return False
