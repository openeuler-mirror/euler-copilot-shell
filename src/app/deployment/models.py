"""
部署配置数据模型

定义部署过程中需要的配置项数据结构。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum

from i18n.manager import _
from tool.validators import APIValidator

# 常量定义
MAX_TEMPERATURE = 10.0
MIN_TEMPERATURE = 0.0


class AgentInitStatus(Enum):
    """智能体初始化状态"""

    SUCCESS = "success"  # 成功完成
    SKIPPED = "skipped"  # 跳过（RPM包不可用）
    FAILED = "failed"  # 失败（其他错误）


@dataclass
class LLMConfig:
    """
    LLM 配置

    包含大语言模型的配置信息。
    """

    endpoint: str = ""
    api_key: str = ""
    model: str = ""
    max_tokens: int = 8192
    ctx_length: int = 128000
    temperature: float = 0.7
    request_timeout: int = 300


@dataclass
class EmbeddingConfig:
    """
    Embedding 配置

    包含嵌入模型的配置信息。
    """

    type: str = ""  # 可选值: "openai", "mindie"
    endpoint: str = ""
    api_key: str = ""
    model: str = ""
    ctx_length: int = 8192


@dataclass
class DeploymentConfig:
    """
    部署配置

    包含完整的部署配置信息。
    """

    # LLM 配置
    llm: LLMConfig = field(default_factory=LLMConfig)

    # Embedding 配置
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)

    # 检测到的后端类型（从 API 验证中获得）
    detected_backend_type: str = "function_call"  # 默认值

    def validate(self) -> tuple[bool, list[str]]:
        """
        验证配置的有效性

        Returns:
            tuple[bool, list[str]]: (是否有效, 错误消息列表)

        """
        errors = []

        # 验证 LLM 字段
        errors.extend(self._validate_llm_fields())

        # 验证 Embedding 字段
        errors.extend(self._validate_embedding_fields())

        # 验证数值范围
        errors.extend(self._validate_numeric_fields())

        return len(errors) == 0, errors

    async def validate_llm_connectivity(self) -> tuple[bool, str, dict]:
        """
        验证 LLM API 连接性和功能

        单独验证 LLM 配置的有效性，包括模型可用性和 function_call 支持。
        当 LLM 的端点填写后调用，API Key 和模型名称允许为空。

        Returns:
            tuple[bool, str, dict]: (是否验证成功, 消息, 验证详细信息)

        """
        # 检查必要字段是否完整（只要求端点）
        if not self.llm.endpoint.strip():
            return False, _("LLM API 端点不能为空"), {}

        validator = APIValidator()
        llm_valid, llm_msg, llm_info = await validator.validate_llm_config(
            self.llm.endpoint,
            self.llm.api_key,  # 允许为空
            self.llm.model,  # 允许为空
            self.llm.request_timeout,
        )

        # 如果验证成功，保存检测到的后端类型
        if llm_valid and llm_info.get("supports_function_call", False):
            self.detected_backend_type = llm_info.get("detected_function_call_type", "function_call")

        return llm_valid, llm_msg, llm_info

    async def validate_embedding_connectivity(self) -> tuple[bool, str, dict]:
        """
        验证 Embedding API 连接性和功能

        单独验证 Embedding 配置的有效性。
        当 Embedding 的端点填写后调用，API Key 和模型名称允许为空。

        Returns:
            tuple[bool, str, dict]: (是否验证成功, 消息, 验证详细信息)

        """
        # 检查必要字段是否完整（只要求端点）
        if not self.embedding.endpoint.strip():
            return False, _("Embedding API 端点不能为空"), {}

        validator = APIValidator()
        embed_valid, embed_msg, embed_info = await validator.validate_embedding_config(
            self.embedding.endpoint,
            self.embedding.api_key,  # 允许为空
            self.embedding.model,  # 允许为空
            self.llm.request_timeout,  # 使用相同的超时设置
        )

        # 如果验证成功，保存检测到的 embedding 类型
        if embed_valid and embed_info.get("type"):
            detected_type = embed_info.get("type")
            if detected_type in ("openai", "mindie"):
                self.embedding.type = detected_type

        return embed_valid, embed_msg, embed_info

    def _validate_llm_fields(self) -> list[str]:
        """验证 LLM 配置字段"""
        errors = []
        if not self.llm.endpoint.strip():
            errors.append(_("LLM API 端点不能为空"))
        return errors

    def _validate_embedding_fields(self) -> list[str]:
        """验证 Embedding 配置字段"""
        errors = []

        has_embedding_config = any(
            [
                self.embedding.endpoint.strip(),
                self.embedding.api_key.strip(),
                self.embedding.model.strip(),
            ],
        )

        # Embedding 配置为可选项，仅在用户填写部分字段时要求端点必填
        if has_embedding_config and not self.embedding.endpoint.strip():
            errors.append(_("Embedding API 端点不能为空"))

        return errors

    def _validate_numeric_fields(self) -> list[str]:
        """验证数值字段"""
        errors = []
        if self.llm.max_tokens <= 0:
            errors.append(_("LLM max_tokens 必须大于 0"))
        if not (MIN_TEMPERATURE <= self.llm.temperature <= MAX_TEMPERATURE):
            errors.append(
                _("LLM temperature 必须在 {min} 到 {max} 之间").format(
                    min=MIN_TEMPERATURE,
                    max=MAX_TEMPERATURE,
                ),
            )
        if self.llm.request_timeout <= 0:
            errors.append(_("LLM 请求超时时间必须大于 0"))
        return errors


@dataclass
class DeploymentState:
    """
    部署状态

    跟踪部署过程的状态信息。
    """

    current_step: int = 0
    total_steps: int = 0
    current_step_name: str = ""
    is_running: bool = False
    is_completed: bool = False
    is_failed: bool = False
    error_message: str = ""
    output_log: list[str] = field(default_factory=list)

    def add_log(self, message: str) -> None:
        """
        添加日志消息

        避免输出重复内容，只有当新消息与最后一条消息不同时才添加

        Args:
            message: 日志消息

        """
        # 转换 ANSI 颜色标记为 Textual 富文本标记
        rich_message = self._convert_shell_colors_to_rich(message)

        # 如果日志为空，或者新消息与最后一条消息不同，则添加
        if not self.output_log or self.output_log[-1] != rich_message:
            self.output_log.append(rich_message)

    def _convert_shell_colors_to_rich(self, text: str) -> str:
        r"""
        将 Shell ANSI 颜色码转换为 Textual Rich 标记

        基于脚本中实际使用的颜色标记进行转换:
        - COLOR_INFO='\033[34m'    # 蓝色信息 -> [blue]
        - COLOR_SUCCESS='\033[32m' # 绿色成功 -> [green]
        - COLOR_ERROR='\033[31m'   # 红色错误 -> [red]
        - COLOR_WARNING='\033[33m' # 黄色警告 -> [yellow]
        - COLOR_RESET='\033[0m'    # 重置颜色 -> [/]

        处理跨行颜色标记，确保 Rich 标记的完整性，避免 MarkupError。

        Args:
            text: 包含 ANSI 颜色码的文本

        Returns:
            转换后的 Rich 标记文本

        """
        # ANSI 颜色码到 Rich 标记的映射
        color_map = {
            r"\033\[34m": "[blue]",  # 蓝色信息
            r"\033\[32m": "[green]",  # 绿色成功
            r"\033\[31m": "[red]",  # 红色错误
            r"\033\[33m": "[yellow]",  # 黄色警告
            r"\033\[0;32m": "[green]",  # 绿色 (GREEN 变量)
            r"\033\[0;33m": "[yellow]",  # 黄色 (YELLOW 变量)
            r"\033\[0;34m": "[blue]",  # 蓝色 (BLUE 变量)
            r"\033\[0m": "[/]",  # 重置颜色
        }

        # 应用颜色转换
        result = text
        for ansi_code, rich_markup in color_map.items():
            result = re.sub(ansi_code, rich_markup, result)

        # 检查是否存在未配对的Rich标记，避免MarkupError
        return self._ensure_balanced_rich_tags(result)

    def _ensure_balanced_rich_tags(self, text: str) -> str:
        """
        确保 Rich 标记的平衡性，避免跨行导致的 MarkupError

        处理以下情况：
        1. 只有开始标记没有结束标记：自动添加结束标记
        2. 只有结束标记没有开始标记：移除孤立的结束标记
        3. 嵌套不当的标记：进行修复

        Args:
            text: 包含 Rich 标记的文本

        Returns:
            平衡的 Rich 标记文本

        """
        close_pattern = r"\[/\]"
        color_pattern = r"\[(blue|green|red|yellow)\]"

        # 找到所有开始标记和结束标记，包含结束位置
        open_matches = [
            {"pos": match.start(), "end": match.end(), "type": "open", "tag": match.group(1)}
            for match in re.finditer(color_pattern, text)
        ]

        close_matches = [
            {"pos": match.start(), "end": match.end(), "type": "close", "tag": "close"}
            for match in re.finditer(close_pattern, text)
        ]

        # 合并并按位置排序
        all_matches = open_matches + close_matches
        all_matches.sort(key=lambda x: x["pos"])

        # 使用栈来跟踪标记平衡
        open_stack = []
        balanced_text = ""
        last_pos = 0

        for match in all_matches:
            # 添加匹配前的文本
            balanced_text += text[last_pos : match["pos"]]

            if match["type"] == "open":
                # 开始标记：入栈并添加到结果
                open_stack.append(match["tag"])
                balanced_text += f"[{match['tag']}]"
            elif match["type"] == "close":
                if open_stack:
                    # 有匹配的开始标记：出栈并添加结束标记
                    open_stack.pop()
                    balanced_text += "[/]"
                # 如果没有匹配的开始标记，忽略这个结束标记（不添加到结果中）

            last_pos = match["end"]

        # 添加剩余的文本
        balanced_text += text[last_pos:]

        # 为未闭合的开始标记添加结束标记
        while open_stack:
            balanced_text += "[/]"
            open_stack.pop()

        return balanced_text

    def clear_log(self) -> None:
        """清空日志"""
        self.output_log.clear()

    def reset(self) -> None:
        """重置状态"""
        self.current_step = 0
        self.current_step_name = ""
        self.is_running = False
        self.is_completed = False
        self.is_failed = False
        self.error_message = ""
        self.clear_log()
