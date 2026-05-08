"""
LLM 配置管理工具

允许管理员通过 TUI 界面管理后端的 LLM 模型配置。
支持模型的新增、修改、删除操作。
"""

from __future__ import annotations

import contextlib
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from typing import Any, ClassVar

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, ScrollableContainer, Vertical
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Checkbox,
    Input,
    Label,
    ListItem,
    ListView,
    Select,
    Static,
    TextArea,
)

from app.tui_header import OIHeader
from backend.hermes import HermesChatClient
from backend.models import LLMConfig as HermesLLMConfig
from backend.models import LLMGlobalSetting, LLMProvider, LLMType, ModelInfo
from config.manager import ConfigManager
from i18n.manager import _
from log.manager import get_logger

logger = get_logger(__name__)

# 常量定义
DEFAULT_LLM_CTX_LENGTH = 128000
DEFAULT_EMBEDDING_CTX_LENGTH = 8192
DEFAULT_MAX_TOKENS = 8192


def restart_sysagent_service() -> tuple[bool, str]:
    """
    重启后端服务使配置生效。

    说明：
        - 仅在系统存在 systemctl 时尝试重启。
        - 重启失败不会抛异常，返回 (False, message) 便于上层输出。

    Returns:
        tuple[bool, str]: (是否成功, 说明/错误信息)

    """
    systemctl = shutil.which("systemctl")
    if not systemctl:
        return False, _("未找到 systemctl，跳过重启后端服务")

    try:
        result = subprocess.run(  # noqa: S603
            [systemctl, "restart", "sysagent"],
            check=False,
            capture_output=True,
            text=True,
        )
    except Exception as e:
        logger.exception("重启后端服务失败")
        return False, _("重启后端失败: {error}").format(error=str(e))

    if result.returncode == 0:
        return True, _("已重启后端服务")

    stderr = (result.stderr or "").strip()
    stdout = (result.stdout or "").strip()
    details = stderr or stdout or str(result.returncode)
    logger.warning("systemctl restart sysagent 失败: %s", details)
    return False, _("重启后端失败: {details}").format(details=details)


# ============================================================================
# 数据模型
# ============================================================================


@dataclass
class EditableModelConfig:
    """
    可编辑的模型配置

    用于 TUI 编辑界面的数据模型，支持所有可编辑字段。
    """

    # 基本信息
    llm_id: str = ""
    """模型唯一标识符"""

    llm_description: str = ""
    """模型描述"""

    # LLM 类型选项（可任意组合）
    has_chat: bool = True
    """是否支持 Chat（聊天对话）"""

    has_function: bool = False
    """是否支持 Function Call"""

    has_embedding: bool = False
    """是否支持 Embedding（向量嵌入）"""

    has_vision: bool = False
    """是否支持图片理解"""

    has_thinking: bool = False
    """是否支持思考推理"""

    # API 配置
    provider: LLMProvider = LLMProvider.OPENAI
    """模型提供商"""

    base_url: str = ""
    """API 端点 URL"""

    api_key: str = ""
    """API 密钥"""

    model_name: str = ""
    """模型名称（用于调用 API）"""

    # 模型参数
    ctx_length: int = DEFAULT_LLM_CTX_LENGTH
    """上下文长度"""

    max_tokens: int = DEFAULT_MAX_TOKENS
    """最大输出令牌数"""

    # 扩展配置
    extra_data_json: str = "{}"
    """额外配置数据（JSON 字符串）"""

    # 编辑状态
    is_new: bool = True
    """是否为新建模型"""

    def get_llm_types(self) -> list[LLMType]:
        """获取 LLM 类型列表"""
        types: list[LLMType] = []
        if self.has_chat:
            types.append(LLMType.CHAT)
        if self.has_function:
            types.append(LLMType.FUNCTION)
        if self.has_embedding:
            types.append(LLMType.EMBEDDING)
        if self.has_vision:
            types.append(LLMType.VISION)
        if self.has_thinking:
            types.append(LLMType.THINKING)
        return types

    def get_extra_data(self) -> dict[str, Any] | None:
        """解析额外配置数据"""
        try:
            data = json.loads(self.extra_data_json)
        except json.JSONDecodeError:
            return None
        else:
            return data if data else None

    def validate_extra_data_json(self) -> tuple[bool, str]:
        """
        验证 JSON 格式

        Returns:
            tuple[bool, str]: (是否有效, 错误消息)

        """
        if not self.extra_data_json.strip():
            return True, ""

        try:
            json.loads(self.extra_data_json)
        except json.JSONDecodeError as e:
            return False, str(e)
        else:
            return True, ""

    def to_hermes_config(self) -> HermesLLMConfig:
        """转换为 Hermes API 配置对象"""
        return HermesLLMConfig(
            provider=self.provider,
            ctx_length=self.ctx_length,
            id=self.llm_id if self.llm_id else None,
            base_url=self.base_url,
            api_key=self.api_key,
            model_name=self.model_name if self.model_name else None,
            max_tokens=self.max_tokens,
            llm_description=self.llm_description,
            llm_type=self.get_llm_types(),
            extra_data=self.get_extra_data(),
        )

    @classmethod
    def from_model_info(cls, model: ModelInfo, config: HermesLLMConfig | None = None) -> EditableModelConfig:
        """
        从 ModelInfo 和 LLMConfig 创建可编辑配置

        Args:
            model: 模型基本信息
            config: 模型详细配置（可选）

        """
        # 解析 LLM 类型
        has_chat = LLMType.CHAT in model.llm_type
        has_function = LLMType.FUNCTION in model.llm_type
        has_embedding = LLMType.EMBEDDING in model.llm_type
        has_vision = LLMType.VISION in model.llm_type
        has_thinking = LLMType.THINKING in model.llm_type

        # 从详细配置中获取更多信息
        provider = LLMProvider.OPENAI
        base_url = ""
        api_key = ""
        model_name = model.model_name
        ctx_length = DEFAULT_LLM_CTX_LENGTH
        max_tokens = model.max_tokens or DEFAULT_MAX_TOKENS
        extra_data_json = "{}"

        if config:
            provider = config.provider
            base_url = config.base_url
            api_key = config.api_key
            model_name = config.model_name or model.model_name
            ctx_length = config.ctx_length
            max_tokens = config.max_tokens
            if config.extra_data:
                extra_data_json = json.dumps(config.extra_data, indent=2, ensure_ascii=False)

        return cls(
            llm_id=model.llm_id or "",
            llm_description=model.llm_description or "",
            has_chat=has_chat,
            has_function=has_function,
            has_embedding=has_embedding,
            has_vision=has_vision,
            has_thinking=has_thinking,
            provider=provider,
            base_url=base_url,
            api_key=api_key,
            model_name=model_name,
            ctx_length=ctx_length,
            max_tokens=max_tokens,
            extra_data_json=extra_data_json,
            is_new=False,
        )


# ============================================================================
# TUI 组件
# ============================================================================


class ModelListItem(ListItem):
    """模型列表项"""

    def __init__(self, model: ModelInfo) -> None:
        """初始化模型列表项"""
        super().__init__()
        self.model = model

    def compose(self) -> ComposeResult:
        """组合界面组件"""
        # 格式化类型标签
        type_labels = [t.value for t in self.model.llm_type]
        type_str = ", ".join(type_labels) if type_labels else "unknown"

        # 创建显示内容
        with Horizontal(classes="model-item-content"):
            yield Static(self.model.llm_id or self.model.model_name, classes="model-item-id")
            yield Static(f"[{type_str}]", classes="model-item-type")


class ModelEditScreen(ModalScreen[EditableModelConfig | None]):
    """模型编辑屏幕"""

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("escape", "cancel", "取消"),
    ]

    CSS = """
    ModelEditScreen {
        align: center middle;
    }

    .edit-container {
        width: 95%;
        max-width: 120;
        height: 95%;
        background: $surface;
        border: solid $primary;
        padding: 1 2;
    }

    .edit-title {
        text-align: center;
        text-style: bold;
        color: $primary;
        padding: 1;
        margin-bottom: 1;
        height: auto;
    }

    .edit-scroll {
        height: 1fr;
        min-height: 10;
        scrollbar-size: 1 1;
    }

    .form-section {
        margin-bottom: 1;
        padding: 1;
        border: solid $primary-darken-2;
        height: auto;
    }

    .section-title {
        text-style: bold;
        color: $primary;
        margin-bottom: 1;
        height: auto;
    }

    .form-row {
        height: auto;
        min-height: 3;
        margin-bottom: 0;
    }

    .form-label {
        width: 16;
        text-align: right;
        content-align: right middle;
        padding-right: 1;
        height: auto;
    }

    .form-input {
        width: 1fr;
        height: auto;
    }

    .form-input-short {
        width: 30;
        height: auto;
    }

    .checkbox-row {
        height: auto;
        min-height: 3;
        margin-bottom: 0;
    }

    .checkbox-label {
        width: 16;
        text-align: right;
        content-align: right middle;
        padding-right: 1;
        height: auto;
    }

    .checkbox-group {
        width: 1fr;
        height: auto;
    }

    .checkbox-item {
        width: auto;
        margin-right: 2;
    }

    .json-editor-container {
        height: 12;
        min-height: 8;
        margin-top: 1;
    }

    .json-editor {
        height: 100%;
        width: 1fr;
    }

    .json-status {
        height: auto;
        color: $text-muted;
        text-style: italic;
        padding: 0 1;
    }

    .json-error {
        color: $error;
    }

    .button-row {
        height: auto;
        min-height: 3;
        align: center middle;
        margin-top: 1;
        padding: 1 0;
    }

    .button-row > Button {
        margin: 0 1;
        min-width: 12;
    }

    #delete-btn {
        background: $error;
    }
    """

    def __init__(self, config: EditableModelConfig) -> None:
        """初始化编辑屏幕"""
        super().__init__()
        self.config = config
        self._delete_requested = False

    def compose(self) -> ComposeResult:
        """组合界面组件"""
        title = _("新建模型") if self.config.is_new else _("编辑模型: {id}").format(id=self.config.llm_id)

        with Container(classes="edit-container"):
            yield OIHeader()
            yield Static(title, classes="edit-title")

            with ScrollableContainer(classes="edit-scroll"):
                yield from self._compose_basic_info_section()
                yield from self._compose_model_type_section()
                yield from self._compose_api_config_section()
                yield from self._compose_params_section()
                yield from self._compose_extra_data_section()

            yield from self._compose_button_row()

    def _compose_basic_info_section(self) -> ComposeResult:
        """组合基本信息区域"""
        with Vertical(classes="form-section"):
            yield Static(_("基本信息"), classes="section-title")

            with Horizontal(classes="form-row"):
                yield Label(_("模型 ID:"), classes="form-label")
                yield Input(
                    value=self.config.llm_id,
                    placeholder=_("唯一标识符，如 gpt-4o"),
                    id="llm_id",
                    classes="form-input",
                )

            with Horizontal(classes="form-row"):
                yield Label(_("描述:"), classes="form-label")
                yield Input(
                    value=self.config.llm_description,
                    placeholder=_("模型描述信息"),
                    id="llm_description",
                    classes="form-input",
                )

    def _compose_model_type_section(self) -> ComposeResult:
        """组合模型类型区域"""
        with Vertical(classes="form-section"):
            yield Static(_("模型能力"), classes="section-title")

            with Horizontal(classes="checkbox-row"):
                yield Label(_("类型:"), classes="checkbox-label")
                with Horizontal(classes="checkbox-group"):
                    yield Checkbox("Chat", self.config.has_chat, id="has_chat")
                    yield Checkbox("Function", self.config.has_function, id="has_function")
                    yield Checkbox("Embedding", self.config.has_embedding, id="has_embedding")
                    yield Checkbox("Vision", self.config.has_vision, id="has_vision")
                    yield Checkbox("Thinking", self.config.has_thinking, id="has_thinking")

    def _compose_api_config_section(self) -> ComposeResult:
        """组合 API 配置区域"""
        with Vertical(classes="form-section"):
            yield Static(_("API 配置"), classes="section-title")

            with Horizontal(classes="form-row"):
                yield Label(_("提供商:"), classes="form-label")
                yield Select(
                    [
                        ("OpenAI", LLMProvider.OPENAI.value),
                        ("Ollama", LLMProvider.OLLAMA.value),
                        ("TEI", LLMProvider.TEI.value),
                    ],
                    value=self.config.provider.value,
                    id="provider",
                    classes="form-input-short",
                )

            with Horizontal(classes="form-row"):
                yield Label(_("API 端点:"), classes="form-label")
                yield Input(
                    value=self.config.base_url,
                    placeholder=_("如 {url}").format(url="http://localhost:11434/v1"),
                    id="base_url",
                    classes="form-input",
                )

            with Horizontal(classes="form-row"):
                yield Label(_("API 密钥:"), classes="form-label")
                yield Input(
                    value=self.config.api_key,
                    placeholder=_("可选"),
                    password=True,
                    id="api_key",
                    classes="form-input",
                )

            with Horizontal(classes="form-row"):
                yield Label(_("模型名称:"), classes="form-label")
                yield Input(
                    value=self.config.model_name,
                    placeholder=_("用于调用 API 的模型名称"),
                    id="model_name",
                    classes="form-input",
                )

    def _compose_params_section(self) -> ComposeResult:
        """组合参数配置区域"""
        with Vertical(classes="form-section"):
            yield Static(_("参数配置"), classes="section-title")

            with Horizontal(classes="form-row"):
                yield Label(_("上下文长度:"), classes="form-label")
                yield Input(
                    value=str(self.config.ctx_length),
                    placeholder=str(DEFAULT_LLM_CTX_LENGTH),
                    id="ctx_length",
                    classes="form-input-short",
                )

            with Horizontal(classes="form-row"):
                yield Label(_("最大输出:"), classes="form-label")
                yield Input(
                    value=str(self.config.max_tokens),
                    placeholder=str(DEFAULT_MAX_TOKENS),
                    id="max_tokens",
                    classes="form-input-short",
                )

    def _compose_extra_data_section(self) -> ComposeResult:
        """组合扩展配置区域"""
        with Vertical(classes="form-section"):
            yield Static(_("扩展配置 (JSON)"), classes="section-title")
            yield Static(_("有效的 JSON"), id="json_status", classes="json-status")
            with Container(classes="json-editor-container"):
                yield TextArea(
                    self.config.extra_data_json,
                    language="json",
                    id="extra_data",
                    classes="json-editor",
                )

    def _compose_button_row(self) -> ComposeResult:
        """组合按钮区域"""
        with Horizontal(classes="button-row"):
            yield Button(_("保存"), id="save-btn", variant="primary")
            if not self.config.is_new:
                yield Button(_("删除"), id="delete-btn", variant="error")
            yield Button(_("取消"), id="cancel-btn")

    def on_mount(self) -> None:
        """界面挂载时的初始化"""
        # 验证初始 JSON
        self._validate_json()

    @on(TextArea.Changed, "#extra_data")
    def on_json_changed(self, event: TextArea.Changed) -> None:
        """处理 JSON 内容变更"""
        self._validate_json()

    @on(Button.Pressed, "#save-btn")
    def on_save_pressed(self) -> None:
        """处理保存按钮"""
        if self._collect_config():
            self.dismiss(self.config)

    @on(Button.Pressed, "#delete-btn")
    def on_delete_pressed(self) -> None:
        """处理删除按钮"""
        self._delete_requested = True
        # 设置一个特殊标记表示删除
        self.config.llm_id = f"__DELETE__{self.config.llm_id}"
        self.dismiss(self.config)

    @on(Button.Pressed, "#cancel-btn")
    def action_cancel(self) -> None:
        """处理取消按钮"""
        self.dismiss(None)

    def _validate_json(self) -> None:
        """验证 JSON 格式"""
        try:
            text_area = self.query_one("#extra_data", TextArea)
            status = self.query_one("#json_status", Static)

            json_text = text_area.text.strip()
            if not json_text:
                status.update(_("空（将使用 null）"))
                status.remove_class("json-error")
                return

            try:
                json.loads(json_text)
                status.update(_("✓ JSON 格式正确"))
                status.remove_class("json-error")
            except json.JSONDecodeError as e:
                status.update(_("✗ JSON 错误: {error}").format(error=str(e)))
                status.add_class("json-error")
        except LookupError:
            logger.debug("无法查询 JSON 编辑器组件")

    def _collect_config(self) -> bool:
        """收集配置数据"""
        try:
            # 基本信息
            self.config.llm_id = self.query_one("#llm_id", Input).value.strip()
            self.config.llm_description = self.query_one("#llm_description", Input).value.strip()

            # LLM 能力
            self.config.has_chat = self.query_one("#has_chat", Checkbox).value
            self.config.has_function = self.query_one("#has_function", Checkbox).value
            self.config.has_embedding = self.query_one("#has_embedding", Checkbox).value
            self.config.has_vision = self.query_one("#has_vision", Checkbox).value
            self.config.has_thinking = self.query_one("#has_thinking", Checkbox).value

            # API 配置
            provider_value = self.query_one("#provider", Select).value
            self.config.provider = LLMProvider(provider_value)
            self.config.base_url = self.query_one("#base_url", Input).value.strip()
            self.config.api_key = self.query_one("#api_key", Input).value.strip()
            self.config.model_name = self.query_one("#model_name", Input).value.strip()

            # 参数配置
            try:
                self.config.ctx_length = int(self.query_one("#ctx_length", Input).value or "128000")
            except ValueError:
                self.config.ctx_length = 128000

            try:
                self.config.max_tokens = int(self.query_one("#max_tokens", Input).value or "8192")
            except ValueError:
                self.config.max_tokens = 8192

            # 扩展配置
            self.config.extra_data_json = self.query_one("#extra_data", TextArea).text.strip() or "{}"

            # 验证必填字段
            if not self.config.llm_id:
                self.notify(_("模型 ID 不能为空"), severity="error")
                return False

            # 验证 JSON
            is_valid, error_msg = self.config.validate_extra_data_json()
            if not is_valid:
                self.notify(_("JSON 格式错误: {error}").format(error=error_msg), severity="error")
                return False

        except Exception as e:
            self.notify(_("收集配置失败: {error}").format(error=str(e)), severity="error")
            logger.exception("收集配置失败")
            return False
        else:
            return True


class DefaultModelScreen(ModalScreen[LLMGlobalSetting | None]):
    """默认模型设置屏幕"""

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("escape", "cancel", "取消"),
    ]

    CSS = """
    DefaultModelScreen {
        align: center middle;
    }

    .default-container {
        width: 80;
        height: auto;
        max-height: 30;
        background: $surface;
        border: solid $primary;
        padding: 1 2;
    }

    .default-title {
        text-align: center;
        text-style: bold;
        color: $primary;
        padding: 1;
        margin-bottom: 1;
        height: auto;
    }

    .default-form-row {
        height: auto;
        min-height: 3;
        margin-bottom: 1;
    }

    .default-label {
        width: 20;
        text-align: right;
        content-align: right middle;
        padding-right: 1;
        height: auto;
    }

    .default-select {
        width: 1fr;
        height: auto;
    }

    .default-hint {
        color: $text-muted;
        text-style: italic;
        padding: 1;
        height: auto;
    }

    .default-button-row {
        height: auto;
        min-height: 3;
        align: center middle;
        margin-top: 1;
        padding: 1 0;
    }

    .default-button-row > Button {
        margin: 0 1;
        min-width: 12;
    }
    """

    def __init__(
        self,
        models: list[ModelInfo],
        current_function_llm: str | None = None,
        current_embedding_llm: str | None = None,
    ) -> None:
        """初始化默认模型设置屏幕"""
        super().__init__()
        self._models = models
        self._current_function_llm = current_function_llm
        self._current_embedding_llm = current_embedding_llm

    def compose(self) -> ComposeResult:
        """组合界面组件"""
        # 筛选支持 Function 的模型
        function_models = [m for m in self._models if LLMType.FUNCTION in m.llm_type or LLMType.CHAT in m.llm_type]
        # 筛选支持 Embedding 的模型
        embedding_models = [m for m in self._models if LLMType.EMBEDDING in m.llm_type]

        # 构建选择列表
        function_options: list[tuple[str, str]] = [(_("（不设置）"), "")]
        for m in function_models:
            llm_id = m.llm_id or m.model_name
            function_options.append((llm_id, llm_id))

        embedding_options: list[tuple[str, str]] = [(_("（不设置）"), "")]
        for m in embedding_models:
            llm_id = m.llm_id or m.model_name
            embedding_options.append((llm_id, llm_id))

        # 确定当前选中值
        function_value = self._current_function_llm or ""
        embedding_value = self._current_embedding_llm or ""

        with Container(classes="default-container"):
            yield OIHeader()
            yield Static(_("设置默认模型"), classes="default-title")

            with Horizontal(classes="default-form-row"):
                yield Label(_("Function 模型:"), classes="default-label")
                yield Select(
                    function_options,
                    value=function_value,
                    id="function_llm",
                    classes="default-select",
                    allow_blank=True,
                )

            with Horizontal(classes="default-form-row"):
                yield Label(_("Embedding 模型:"), classes="default-label")
                yield Select(
                    embedding_options,
                    value=embedding_value,
                    id="embedding_llm",
                    classes="default-select",
                    allow_blank=True,
                )

            yield Static(
                _("Function 模型用于智能体的函数调用，Embedding 模型用于向量嵌入。"),
                classes="default-hint",
            )

            with Horizontal(classes="default-button-row"):
                yield Button(_("保存"), id="save-default-btn", variant="primary")
                yield Button(_("取消"), id="cancel-default-btn")

    @on(Button.Pressed, "#save-default-btn")
    def on_save_pressed(self) -> None:
        """处理保存按钮"""
        try:
            function_llm_value = self.query_one("#function_llm", Select).value
            embedding_llm_value = self.query_one("#embedding_llm", Select).value

            # 处理空值和 NoSelection 类型
            function_llm: str | None = None
            if isinstance(function_llm_value, str) and function_llm_value:
                function_llm = function_llm_value

            embedding_llm: str | None = None
            if isinstance(embedding_llm_value, str) and embedding_llm_value:
                embedding_llm = embedding_llm_value

            setting = LLMGlobalSetting(
                function_llm=function_llm,
                embedding_llm=embedding_llm,
            )
            self.dismiss(setting)

        except Exception as e:
            self.notify(_("获取配置失败: {error}").format(error=str(e)), severity="error")
            logger.exception("获取默认模型配置失败")

    @on(Button.Pressed, "#cancel-default-btn")
    def action_cancel(self) -> None:
        """处理取消按钮"""
        self.dismiss(None)


class LLMConfigScreen(ModalScreen[bool]):
    """
    LLM 配置管理屏幕

    显示模型列表，支持新增、编辑、删除操作。
    """

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("n", "new_model", "新建"),
        Binding("enter", "edit_model", "编辑"),
        Binding("d", "delete_model", "删除"),
        Binding("r", "refresh", "刷新"),
        Binding("escape", "quit", "退出"),
    ]

    CSS = """
    LLMConfigScreen {
        align: center middle;
    }

    .main-container {
        width: 95%;
        max-width: 130;
        height: 95%;
        background: $surface;
        border: solid $primary;
        padding: 0 1;
    }

    .title {
        text-align: center;
        text-style: bold;
        color: $primary;
        padding: 1;
    }

    .model-list-container {
        height: 1fr;
        border: solid $primary-darken-2;
        margin: 1 0;
    }

    .model-list {
        height: 1fr;
        scrollbar-size: 1 1;
    }

    .model-item-content {
        width: 100%;
        height: 3;
        padding: 1;
    }

    .model-item-id {
        width: 1fr;
        content-align: left middle;
        text-style: bold;
    }

    .model-item-type {
        width: auto;
        content-align: right middle;
        color: $text-muted;
    }

    .status-bar {
        height: 1;
        color: $text-muted;
        text-style: italic;
        padding: 0 1;
    }

    .help-text {
        height: auto;
        color: $text-muted;
        text-align: center;
        padding: 1;
    }

    .button-row {
        height: 3;
        align: center middle;
        margin-top: 1;
        dock: bottom;
    }

    .button-row > Button {
        margin: 0 1;
        min-width: 12;
    }

    .loading {
        text-align: center;
        color: $warning;
        padding: 2;
    }

    .error {
        text-align: center;
        color: $error;
        padding: 2;
    }

    .empty {
        text-align: center;
        color: $text-muted;
        padding: 2;
    }
    """

    class ModelsLoaded(Message):
        """模型加载完成消息"""

        def __init__(self, models: list[ModelInfo]) -> None:
            """初始化模型加载完成消息"""
            super().__init__()
            self.models = models

    class LoadError(Message):
        """加载错误消息"""

        def __init__(self, error: str) -> None:
            """初始化加载错误消息"""
            super().__init__()
            self.error = error

    def __init__(self) -> None:
        """初始化配置屏幕"""
        super().__init__()
        self._client: HermesChatClient | None = None
        self._models: list[ModelInfo] = []
        self._is_loading = True
        self._changed = False

    def compose(self) -> ComposeResult:
        """组合界面组件"""
        with Container(classes="main-container"):
            yield OIHeader()
            yield Static(_("大模型配置管理"), classes="title")

            with Container(classes="model-list-container"):
                yield Static(_("正在加载模型列表..."), id="loading-status", classes="loading")
                yield ListView(id="model-list", classes="model-list")

            yield Static("", id="status-bar", classes="status-bar")
            yield Static(
                _("快捷键: [N] 新建  [Enter] 编辑  [D] 删除  [R] 刷新  [Esc] 退出"),
                classes="help-text",
                markup=False,
            )

            with Horizontal(classes="button-row"):
                yield Button(_("新建模型"), id="new-btn", variant="primary")
                yield Button(_("刷新列表"), id="refresh-btn")
                yield Button(_("退出"), id="quit-btn", variant="error")
                yield Button(_("设置默认"), id="default-btn", variant="warning")

    async def on_mount(self) -> None:
        """界面挂载时初始化"""
        # 初始化后端客户端
        await self._init_client()
        # 加载模型列表
        self._load_models()

    async def _init_client(self) -> None:
        """初始化后端客户端"""
        try:
            config_manager = ConfigManager()
            base_url = config_manager.get_witty_url()

            if not base_url:
                self.post_message(self.LoadError(_("未配置后端服务地址")))
                return

            self._client = HermesChatClient(base_url, config_manager=config_manager)

            # 登录获取管理员权限
            if not await self._client.ensure_user_info_loaded():
                self.post_message(self.LoadError(_("登录失败，无法获取用户信息")))
                return

            if not self._client.is_admin():
                self.post_message(self.LoadError(_("当前用户不是管理员，无法管理模型")))
                return

            logger.info("后端客户端初始化成功（管理员权限）")

        except Exception as e:
            logger.exception("初始化后端客户端失败")
            self.post_message(self.LoadError(_("初始化失败: {error}").format(error=str(e))))

    @work(exclusive=True)
    async def _load_models(self) -> None:
        """加载模型列表"""
        if not self._client:
            return

        try:
            models = await self._client.model_manager.get_available_models()
            self.post_message(self.ModelsLoaded(models))
        except Exception as e:
            logger.exception("加载模型列表失败")
            self.post_message(self.LoadError(_("加载模型列表失败: {error}").format(error=str(e))))

    @on(ModelsLoaded)
    def on_models_loaded(self, event: ModelsLoaded) -> None:
        """处理模型加载完成"""
        self._models = event.models
        self._is_loading = False
        self._update_model_list()

    @on(LoadError)
    def on_load_error(self, event: LoadError) -> None:
        """处理加载错误"""
        self._is_loading = False
        try:
            loading_status = self.query_one("#loading-status", Static)
            loading_status.update(f"[red]{event.error}[/red]")
            loading_status.remove_class("loading")
            loading_status.add_class("error")
        except LookupError:
            logger.warning("无法查询加载状态标签")

    def _update_model_list(self) -> None:
        """更新模型列表显示"""
        try:
            loading_status = self.query_one("#loading-status", Static)
            model_list = self.query_one("#model-list", ListView)
            status_bar = self.query_one("#status-bar", Static)

            # 清空列表
            model_list.clear()

            if not self._models:
                loading_status.update(_("暂无模型，点击「新建模型」添加"))
                loading_status.remove_class("loading")
                loading_status.add_class("empty")
                loading_status.display = True
                model_list.display = False
            else:
                loading_status.display = False
                model_list.display = True

                # 添加模型项
                for model in self._models:
                    model_list.append(ModelListItem(model))

            # 更新状态栏
            status_bar.update(_("共 {count} 个模型").format(count=len(self._models)))

        except LookupError:
            logger.warning("无法查询模型列表组件")

    @on(Button.Pressed, "#new-btn")
    def action_new_model(self) -> None:
        """新建模型"""
        config = EditableModelConfig(is_new=True)
        self.app.push_screen(ModelEditScreen(config), self._handle_edit_result)

    @on(Button.Pressed, "#refresh-btn")
    def action_refresh(self) -> None:
        """刷新列表"""
        self._is_loading = True
        try:
            loading_status = self.query_one("#loading-status", Static)
            loading_status.update(_("正在刷新..."))
            loading_status.remove_class("error", "empty")
            loading_status.add_class("loading")
            loading_status.display = True
        except LookupError:
            logger.debug("无法查询加载状态标签")
        self._load_models()

    @on(Button.Pressed, "#default-btn")
    def on_default_btn_pressed(self) -> None:
        """打开设置默认模型界面"""
        if not self._models:
            self.notify(_("暂无可用模型"), severity="warning")
            return

        # TODO: 未来可从后端获取当前默认设置
        self.app.push_screen(
            DefaultModelScreen(self._models),
            self._handle_default_setting_result,
        )

    def _handle_default_setting_result(self, result: LLMGlobalSetting | None) -> None:
        """处理默认模型设置结果"""
        if result is None:
            return
        self._save_default_setting(result)

    @work(exclusive=True)
    async def _save_default_setting(self, setting: LLMGlobalSetting) -> None:
        """保存默认模型设置"""
        if not self._client:
            return

        try:
            await self._client.model_manager.update_global_setting(setting)
            self.notify(_("默认模型设置已保存"), severity="information")
        except Exception as e:
            logger.exception("保存默认模型设置失败")
            self.notify(_("保存默认模型设置失败: {error}").format(error=str(e)), severity="error")

    @on(Button.Pressed, "#quit-btn")
    def action_quit(self) -> None:
        """退出"""
        self.dismiss(result=self._changed)

    @on(ListView.Selected, "#model-list")
    def action_edit_model(self, event: ListView.Selected | None = None) -> None:
        """编辑选中的模型"""
        self._edit_selected_model()

    def _edit_selected_model(self) -> None:
        """编辑当前选中的模型"""
        try:
            model_list = self.query_one("#model-list", ListView)
            if model_list.highlighted_child is None:
                self.notify(_("请先选择一个模型"), severity="warning")
                return

            selected_item = model_list.highlighted_child
            if not isinstance(selected_item, ModelListItem):
                return

            model = selected_item.model
            self._open_edit_screen(model)

        except Exception as e:
            logger.exception("编辑模型失败")
            self.notify(_("编辑模型失败: {error}").format(error=str(e)), severity="error")

    @work(exclusive=True)
    async def _open_edit_screen(self, model: ModelInfo) -> None:
        """打开编辑屏幕"""
        if not self._client:
            return

        try:
            # 获取模型详细配置
            llm_config = await self._client.model_manager.get_model_config(model.llm_id or model.model_name)
            config = EditableModelConfig.from_model_info(model, llm_config)
            self.app.push_screen(ModelEditScreen(config), self._handle_edit_result)
        except Exception as e:
            logger.exception("获取模型配置失败")
            self.notify(_("获取模型配置失败: {error}").format(error=str(e)), severity="error")

    def _handle_edit_result(self, result: EditableModelConfig | None) -> None:
        """处理编辑结果"""
        if result is None:
            return

        # 检查是否为删除操作
        if result.llm_id.startswith("__DELETE__"):
            llm_id = result.llm_id[len("__DELETE__") :]
            self._delete_model(llm_id)
            return

        # 保存模型
        self._save_model(result)

    @work(exclusive=True)
    async def _save_model(self, config: EditableModelConfig) -> None:
        """保存模型配置"""
        if not self._client:
            return

        try:
            hermes_config = config.to_hermes_config()
            await self._client.model_manager.create_or_update_model(hermes_config)

            self.notify(_("模型保存成功"), severity="information")
            self._changed = True
            self.action_refresh()

        except Exception as e:
            logger.exception("保存模型失败")
            self.notify(_("保存模型失败: {error}").format(error=str(e)), severity="error")

    def action_delete_model(self) -> None:
        """删除选中的模型"""
        try:
            model_list = self.query_one("#model-list", ListView)
            if model_list.highlighted_child is None:
                self.notify(_("请先选择一个模型"), severity="warning")
                return

            selected_item = model_list.highlighted_child
            if not isinstance(selected_item, ModelListItem):
                return

            model = selected_item.model
            llm_id = model.llm_id or model.model_name
            self._delete_model(llm_id)

        except Exception as e:
            logger.exception("删除模型失败")
            self.notify(_("删除模型失败: {error}").format(error=str(e)), severity="error")

    @work(exclusive=True)
    async def _delete_model(self, llm_id: str) -> None:
        """删除模型"""
        if not self._client:
            return

        try:
            await self._client.model_manager.delete_model(llm_id)
            self.notify(_("模型已删除: {id}").format(id=llm_id), severity="information")
            self._changed = True
            self.action_refresh()

        except Exception as e:
            logger.exception("删除模型失败")
            self.notify(_("删除模型失败: {error}").format(error=str(e)), severity="error")

    async def on_unmount(self) -> None:
        """界面卸载时清理"""
        if self._client:
            with contextlib.suppress(Exception):
                await self._client.close()


class LLMConfigApp(App[bool]):
    """LLM 配置应用"""

    TITLE = "LLM Configurator"

    def __init__(self) -> None:
        """初始化应用"""
        super().__init__()
        self.config_result: bool = False

    def on_mount(self) -> None:
        """应用启动时显示配置屏幕"""
        self.push_screen(LLMConfigScreen(), self._on_config_screen_dismissed)

    def _on_config_screen_dismissed(self, result: bool | None) -> None:  # noqa: FBT001
        """配置屏幕关闭时的回调"""
        self.config_result = result or False
        self.exit()


# ============================================================================
# 入口函数
# ============================================================================


def check_admin_permission() -> tuple[bool, list[str]]:
    """
    检查管理员权限

    Returns:
        tuple[bool, list[str]]: (是否有权限, 错误消息列表)

    """
    errors = []

    # 检查是否以管理员权限运行
    if os.geteuid() != 0:
        errors.append(_("需要管理员权限才能管理 LLM 配置"))
        errors.append(_("请使用 'sudo witty llm' 运行"))

    return len(errors) == 0, errors


def llm_config() -> None:
    """
    LLM 配置主函数

    witty llm 子命令的入口点。
    """
    logger.info("启动 LLM 配置工具")

    try:
        # 检查管理员权限
        ok, errors = check_admin_permission()
        if not ok:
            sys.stderr.write(_("错误：无法启动 LLM 配置工具") + "\n")
            for error in errors:
                sys.stderr.write(f"  - {error}\n")
            sys.exit(1)

        # 启动 TUI 应用
        app = LLMConfigApp()
        app.run()

        # 输出结果
        if app.config_result:
            # 变更已发生：重启 sysagent 使配置生效
            ok_restart, message = restart_sysagent_service()
            if ok_restart:
                sys.stdout.write(f"{message}\n")
            else:
                # 不阻断正常退出，但要提示用户
                sys.stderr.write(f"{message}\n")
            sys.stdout.write(_("✓ LLM 配置管理完成") + "\n")
        else:
            sys.stdout.write(_("LLM 配置管理已退出") + "\n")

    except KeyboardInterrupt:
        sys.stderr.write("\n" + _("配置已取消") + "\n")
        sys.exit(1)
    except (OSError, ValueError, RuntimeError) as e:
        logger.exception("LLM 配置工具发生异常")
        sys.stderr.write(_("错误：{error}").format(error=str(e)) + "\n")
        sys.exit(1)


if __name__ == "__main__":
    llm_config()
