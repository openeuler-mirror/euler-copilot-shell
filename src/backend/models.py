"""后端模型数据结构定义"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class LLMType(str, Enum):
    """
    LLM 类型枚举

    定义了 Hermes 后端支持的 LLM 能力类型。
    """

    CHAT = "chat"
    """模型支持 Chat（聊天对话）"""

    FUNCTION = "function"
    """模型支持 Function Call（函数调用）"""

    EMBEDDING = "embedding"
    """模型支持 Embedding（向量嵌入）"""

    VISION = "vision"
    """模型支持图片理解（视觉能力）"""

    THINKING = "thinking"
    """模型支持思考推理（推理能力）"""


class LLMProvider(str, Enum):
    """
    LLM 提供商枚举

    定义了 Hermes 后端支持的大模型提供商。
    """

    OLLAMA = "ollama"
    """Ollama"""

    OPENAI = "openai"
    """OpenAI"""

    TEI = "tei"
    """TEI"""


@dataclass
class ModelInfo:
    """
    模型信息数据类

    该类用于统一表示不同后端（OpenAI、Hermes）返回的模型信息。

    注意：
    - model_name: 仅用于后端调用大模型 API 时使用，CLI 前端不需要关心
    - llm_id: CLI 前端使用的模型标识符，用于显示和配置保存
    """

    # 通用字段（所有后端都支持）
    model_name: str
    """模型名称，仅用于后端调用大模型 API"""

    # Hermes 特有字段
    llm_id: str | None = None
    """LLM ID，CLI 前端使用的模型唯一标识符（用于显示和配置）"""

    llm_description: str | None = None
    """LLM 描述，Hermes 后端的模型说明"""

    llm_type: list[LLMType] = field(default_factory=list)
    """LLM 类型列表，如 [LLMType.CHAT, LLMType.FUNCTION]，Hermes 后端特有"""

    max_tokens: int | None = None
    """模型支持的最大 token 数，Hermes 后端提供"""

    def __str__(self) -> str:
        """返回模型的字符串表示（优先使用 llm_id）"""
        return self.llm_id or self.model_name

    def __repr__(self) -> str:
        """返回模型的详细表示"""
        return f"ModelInfo(model_name={self.model_name!r}, llm_id={self.llm_id!r})"

    @staticmethod
    def parse_llm_types(llm_types: list[str] | None) -> list[LLMType]:
        """
        解析 LLM 类型字符串列表，过滤掉不合法的值

        Args:
            llm_types: LLM 类型字符串列表

        Returns:
            list[LLMType]: 合法的 LLM 类型枚举列表

        """
        if not llm_types:
            return []

        valid_values = {t.value for t in LLMType}
        return [LLMType(llm_type_str) for llm_type_str in llm_types if llm_type_str in valid_values]


@dataclass
class LLMConfig:
    """
    大模型配置数据类

    用于创建/更新大模型时的请求参数，以及获取模型详细配置时的响应数据。
    对应后端 UpdateLLMReq 数据结构。
    """

    # 必填字段
    provider: LLMProvider
    """模型提供商"""

    ctx_length: int
    """模型支持的上下文长度"""

    # 可选字段（有默认值）
    id: str | None = None
    """模型唯一标识符（llmId），创建时可为空"""

    base_url: str = ""
    """模型 API 基础 URL"""

    api_key: str = ""
    """模型 API 密钥"""

    model_name: str | None = None
    """模型名称，用于调用 API"""

    max_tokens: int = 8192
    """模型支持的最大 token 数，默认 8192"""

    llm_description: str = ""
    """模型描述"""

    extra_data: dict[str, Any] | None = None
    """额外配置数据"""

    def to_api_dict(self) -> dict[str, Any]:
        """
        转换为 API 请求所需的字典格式

        Returns:
            dict[str, Any]: API 请求参数字典

        """
        data: dict[str, Any] = {
            "provider": self.provider.value,
            "ctxLength": self.ctx_length,
            "baseUrl": self.base_url,
            "apiKey": self.api_key,
            "maxTokens": self.max_tokens,
            "llmDescription": self.llm_description,
        }

        if self.id is not None:
            data["id"] = self.id
        if self.model_name is not None:
            data["modelName"] = self.model_name
        if self.extra_data is not None:
            data["extraData"] = self.extra_data

        return data

    @classmethod
    def from_api_response(cls, data: dict[str, Any]) -> LLMConfig:
        """
        从 API 响应数据构建 LLMConfig 对象

        Args:
            data: API 响应中的模型配置数据

        Returns:
            LLMConfig: 模型配置对象

        """
        # 解析 provider，默认使用 OPENAI
        provider_str = data.get("provider", "openai")
        try:
            provider = LLMProvider(provider_str)
        except ValueError:
            provider = LLMProvider.OPENAI

        return cls(
            provider=provider,
            ctx_length=data.get("ctxLength", 0),
            id=data.get("llmId"),
            base_url=data.get("baseUrl", ""),
            api_key=data.get("apiKey", ""),
            model_name=data.get("modelName"),
            max_tokens=data.get("maxTokens", 8192),
            llm_description=data.get("llmDescription", ""),
            extra_data=data.get("extraConfig") or data.get("extraData"),
        )


@dataclass
class LLMGlobalSetting:
    """
    大模型全局设置数据类

    用于配置系统级别的 LLM 设置。
    """

    function_llm: str | None = None
    """用于函数调用的 LLM ID"""

    embedding_llm: str | None = None
    """用于向量嵌入的 LLM ID"""

    def to_api_dict(self) -> dict[str, Any]:
        """
        转换为 API 请求所需的字典格式

        Returns:
            dict[str, Any]: API 请求参数字典

        """
        data: dict[str, Any] = {}

        if self.function_llm is not None:
            data["functionLLM"] = self.function_llm
        if self.embedding_llm is not None:
            data["embeddingLLM"] = self.embedding_llm

        return data
