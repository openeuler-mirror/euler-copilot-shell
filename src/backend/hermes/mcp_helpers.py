"""
MCP (Model Context Protocol) 相关常量定义

统一管理所有 MCP 状态消息、指示符和标记，确保代码的一致性和可维护性。
"""

from __future__ import annotations

import re
from typing import ClassVar, NamedTuple

from i18n.manager import _


# MCP 状态标记
class MCPTags:
    """MCP 消息标记常量"""

    MCP_PREFIX = "[MCP:"
    REPLACE_PREFIX = "[REPLACE:"
    TAG_SUFFIX = "]"


# LLM 统计信息标记
LLM_STATS_PREFIX = "[LLM_STATS]"


class MCPTagInfo(NamedTuple):
    """封装 MCP 标记的元信息"""

    identifier: str
    tool_name: str | None = None

    @property
    def display_name(self) -> str:
        """返回用于展示的名称"""
        return self.tool_name or self.identifier


# MCP 状态表情符号
class MCPEmojis:
    """MCP 状态表情符号常量"""

    INIT = "🔧"
    INPUT = "📥"
    OUTPUT = "✅"
    CANCEL = "⏹️"
    ERROR = "❌"
    WAITING_START = "⏸️"
    WAITING_PARAM = "📝"


# MCP 状态文本片段
class MCPTextFragments:
    """MCP 状态文本片段常量"""

    @staticmethod
    def init_tool() -> str:
        """正在初始化工具"""
        return _("正在初始化工具")

    @staticmethod
    def tool_word() -> str:
        """工具"""
        return _("工具")

    @staticmethod
    def executing() -> str:
        """正在执行..."""
        return _("正在执行...")

    @staticmethod
    def completed() -> str:
        """执行完成"""
        return _("执行完成")

    @staticmethod
    def cancelled() -> str:
        """已取消"""
        return _("已取消")

    @staticmethod
    def failed() -> str:
        """执行失败"""
        return _("执行失败")

    @staticmethod
    def waiting_confirm() -> str:
        """等待用户确认执行工具"""
        return _("**等待用户确认执行工具**")

    @staticmethod
    def waiting_param() -> str:
        """等待用户输入参数"""
        return _("**等待用户输入参数**")


# MCP 完整状态消息模板
class MCPMessageTemplates:
    """MCP 状态消息模板常量"""

    # 基础状态指示符（用于识别）- 使用函数动态生成
    @staticmethod
    def init_indicator() -> str:
        """初始化指示符"""
        return f"{MCPEmojis.INIT} {MCPTextFragments.init_tool()}"

    @staticmethod
    def input_indicator() -> str:
        """输入指示符"""
        return f"{MCPEmojis.INPUT} {MCPTextFragments.tool_word()}"

    @staticmethod
    def executing_indicator() -> str:
        """执行中指示符"""
        return MCPTextFragments.executing()

    @staticmethod
    def output_indicator() -> str:
        """输出指示符"""
        return f"{MCPEmojis.OUTPUT} {MCPTextFragments.tool_word()}"

    @staticmethod
    def completed_indicator() -> str:
        """完成指示符"""
        return MCPTextFragments.completed()

    @staticmethod
    def cancel_indicator() -> str:
        """取消指示符"""
        return f"{MCPEmojis.CANCEL} {MCPTextFragments.tool_word()}"

    @staticmethod
    def cancelled_indicator() -> str:
        """已取消指示符"""
        return MCPTextFragments.cancelled()

    @staticmethod
    def error_indicator() -> str:
        """错误指示符"""
        return f"{MCPEmojis.ERROR} {MCPTextFragments.tool_word()}"

    @staticmethod
    def failed_indicator() -> str:
        """失败指示符"""
        return MCPTextFragments.failed()

    @staticmethod
    def waiting_start_indicator() -> str:
        """等待确认指示符"""
        return f"{MCPEmojis.WAITING_START} {MCPTextFragments.waiting_confirm()}"

    @staticmethod
    def waiting_param_indicator() -> str:
        """等待参数指示符"""
        return f"{MCPEmojis.WAITING_PARAM} {MCPTextFragments.waiting_param()}"

    # 完整状态消息模板（用于生成）
    @staticmethod
    def init_message(tool_name: str) -> str:
        """生成工具初始化消息"""
        return f"\n{MCPEmojis.INIT} {MCPTextFragments.init_tool()}: `{tool_name}`\n"

    @staticmethod
    def input_message(tool_name: str) -> str:
        """生成工具执行中消息"""
        return f"\n{MCPEmojis.INPUT} {MCPTextFragments.tool_word()} `{tool_name}` {MCPTextFragments.executing()}\n"

    @staticmethod
    def output_message(tool_name: str) -> str:
        """生成工具执行完成消息"""
        return f"\n{MCPEmojis.OUTPUT} {MCPTextFragments.tool_word()} `{tool_name}` {MCPTextFragments.completed()}\n"

    @staticmethod
    def cancel_message(tool_name: str) -> str:
        """生成工具取消消息"""
        return f"\n{MCPEmojis.CANCEL} {MCPTextFragments.tool_word()} `{tool_name}` {MCPTextFragments.cancelled()}\n"

    @staticmethod
    def error_message(tool_name: str) -> str:
        """生成工具执行失败消息"""
        return f"\n{MCPEmojis.ERROR} {MCPTextFragments.tool_word()} `{tool_name}` {MCPTextFragments.failed()}\n"

    @staticmethod
    def waiting_start_message(tool_name: str, risk_info: str, reason: str) -> str:
        """生成等待用户确认消息"""
        tool_name_label = _("名称")
        explanation_label = _("说明")
        return (
            f"\n{MCPEmojis.WAITING_START} {MCPTextFragments.waiting_confirm()}\n\n"
            f"{MCPEmojis.INIT} {MCPTextFragments.tool_word()}{tool_name_label}: "
            f"`{tool_name}` {risk_info}\n\n💭 {explanation_label}: {reason}\n"
        )

    @staticmethod
    def waiting_param_message(tool_name: str, message_content: str) -> str:
        """生成等待参数输入消息"""
        tool_name_label = _("名称")
        explanation_label = _("说明")
        return (
            f"\n{MCPEmojis.WAITING_PARAM} {MCPTextFragments.waiting_param()}\n\n"
            f"{MCPEmojis.INIT} {MCPTextFragments.tool_word()}{tool_name_label}: "
            f"`{tool_name}`\n\n💭 {explanation_label}: {message_content}\n"
        )


# MCP 状态指示符列表（用于识别和检测）
class MCPIndicators:
    """MCP 状态指示符列表常量"""

    # 所有状态指示符（用于通用检测）- 使用函数动态生成
    @staticmethod
    def all_indicators() -> list[str]:
        """获取所有状态指示符"""
        return [
            MCPMessageTemplates.init_indicator(),
            MCPMessageTemplates.input_indicator(),
            MCPMessageTemplates.executing_indicator(),
            MCPMessageTemplates.waiting_start_indicator(),
            MCPMessageTemplates.waiting_param_indicator(),
            MCPMessageTemplates.output_indicator(),
            MCPMessageTemplates.completed_indicator(),
            MCPMessageTemplates.cancel_indicator(),
            MCPMessageTemplates.cancelled_indicator(),
            MCPMessageTemplates.error_indicator(),
            MCPMessageTemplates.failed_indicator(),
        ]

    # 最终状态指示符（用于检测工具执行结束）
    @staticmethod
    def final_indicators() -> list[str]:
        """获取最终状态指示符"""
        return [
            MCPMessageTemplates.output_indicator(),
            MCPMessageTemplates.completed_indicator(),
            MCPMessageTemplates.cancel_indicator(),
            MCPMessageTemplates.cancelled_indicator(),
            MCPMessageTemplates.error_indicator(),
            MCPMessageTemplates.failed_indicator(),
        ]

    # 进度状态指示符（用于UI快速检测）
    PROGRESS_INDICATORS: ClassVar[list[str]] = [
        MCPEmojis.INIT,
        MCPEmojis.INPUT,
        MCPEmojis.OUTPUT,
        MCPEmojis.CANCEL,
        MCPEmojis.ERROR,
        MCPEmojis.WAITING_START,
        MCPEmojis.WAITING_PARAM,
    ]


# MCP 事件类型映射
class MCPEventTypes:
    """MCP 事件类型常量"""

    STEP_INIT = "step.init"
    STEP_INPUT = "step.input"
    STEP_OUTPUT = "step.output"
    STEP_CANCEL = "step.cancel"
    STEP_ERROR = "step.error"
    STEP_WAITING_FOR_START = "step.waiting_for_start"
    STEP_WAITING_FOR_PARAM = "step.waiting_for_param"

    # 所有步骤事件类型
    ALL_STEP_EVENTS: ClassVar[set[str]] = {
        STEP_INIT,
        STEP_INPUT,
        STEP_OUTPUT,
        STEP_CANCEL,
        STEP_ERROR,
        STEP_WAITING_FOR_START,
        STEP_WAITING_FOR_PARAM,
    }

    # 最终状态事件类型
    FINAL_STATE_EVENTS: ClassVar[set[str]] = {
        STEP_OUTPUT,
        STEP_CANCEL,
        STEP_ERROR,
    }

    # 进度消息事件类型
    PROGRESS_MESSAGE_EVENTS: ClassVar[set[str]] = ALL_STEP_EVENTS


# 风险级别相关常量
class MCPRiskLevels:
    """MCP 工具风险级别常量"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    UNKNOWN = "unknown"

    # 风险级别显示映射 - 使用函数动态生成
    @classmethod
    def get_risk_display(cls, risk_level: str) -> str:
        """获取风险级别的显示文本"""
        risk_display_map = {
            cls.LOW: f"🟢 {_('低风险')}",
            cls.MEDIUM: f"🟡 {_('中等风险')}",
            cls.HIGH: f"🔴 {_('高风险')}",
            cls.UNKNOWN: f"⚪ {_('未知风险')}",
        }
        return risk_display_map.get(risk_level, risk_display_map[cls.UNKNOWN])


# 工具函数
def is_mcp_message(content: str) -> bool:
    """检查内容是否为 MCP 状态消息"""
    # 检查是否包含 MCP 标记
    if MCPTags.MCP_PREFIX in content or MCPTags.REPLACE_PREFIX in content:
        return True

    # 检查是否包含任何 MCP 状态指示符
    return any(indicator in content for indicator in MCPIndicators.all_indicators())


def is_final_mcp_message(content: str) -> bool:
    """检查内容是否为最终状态的 MCP 消息"""
    return any(indicator in content for indicator in MCPIndicators.final_indicators())


def extract_mcp_tag(content: str) -> tuple[MCPTagInfo | None, str]:
    """从内容中提取 MCP 标记并返回清理后的内容"""

    def _extract(pattern: str, text: str) -> tuple[MCPTagInfo | None, str]:
        match = re.search(pattern, text)
        if not match:
            return None, text

        identifier = match.group(1)
        tool_name = match.group(2) or None
        cleaned = re.sub(pattern, "", text).strip()
        if tool_name is None:
            tool_name = identifier
        return MCPTagInfo(identifier=identifier, tool_name=tool_name), cleaned

    replace_prefix = re.escape(MCPTags.REPLACE_PREFIX)
    tag_suffix = re.escape(MCPTags.TAG_SUFFIX)
    value_pattern = "[^|\\]]+"
    replace_pattern = f"{replace_prefix}({value_pattern})(?:\\|({value_pattern}))?{tag_suffix}"

    tag_info, cleaned_content = _extract(replace_pattern, content)
    if tag_info is not None:
        return tag_info, cleaned_content

    mcp_prefix = re.escape(MCPTags.MCP_PREFIX)
    mcp_pattern = f"{mcp_prefix}({value_pattern})(?:\\|({value_pattern}))?{tag_suffix}"

    return _extract(mcp_pattern, content)


def create_mcp_tag(tool_name: str, *, step_id: str | None = None, is_replace: bool = False) -> str:
    """创建 MCP 标记字符串"""

    def _sanitize(value: str) -> str:
        return value.replace("|", "｜").replace("]", "］")

    prefix = MCPTags.REPLACE_PREFIX if is_replace else MCPTags.MCP_PREFIX
    if step_id:
        identifier = _sanitize(step_id)
        sanitized_tool = _sanitize(tool_name)
        return f"{prefix}{identifier}|{sanitized_tool}{MCPTags.TAG_SUFFIX}"

    sanitized_tool = _sanitize(tool_name)
    return f"{prefix}{sanitized_tool}{MCPTags.TAG_SUFFIX}"


def format_error_message(error_text: str) -> str:
    """格式化错误消息"""
    return f"{MCPEmojis.ERROR} {error_text}"


def format_tool_message(tool_name: str, status: str, *, use_emoji: bool = True) -> str:
    """格式化工具状态消息"""
    emoji_map = {
        "init": MCPEmojis.INIT,
        "executing": MCPEmojis.INPUT,
        "completed": MCPEmojis.OUTPUT,
        "cancelled": MCPEmojis.CANCEL,
        "failed": MCPEmojis.ERROR,
    }

    if use_emoji and status in emoji_map:
        return f"{emoji_map[status]} {MCPTextFragments.tool_word()} `{tool_name}` {status}"

    return f"{MCPTextFragments.tool_word()} `{tool_name}` {status}"
