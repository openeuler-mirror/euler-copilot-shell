"""设置页面"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from textual import on
from textual.containers import Container, Horizontal
from textual.css.query import NoMatches
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static

from app.dialogs import ExitDialog
from backend.hermes import HermesChatClient
from backend.openai import OpenAIClient
from config import Backend, ConfigManager
from i18n.manager import _
from log import get_logger
from tool.validators import APIValidator, validate_oi_connection

if TYPE_CHECKING:
    from textual.app import ComposeResult
    from textual.events import Key

    from backend.base import LLMClientBase


class SettingsScreen(ModalScreen):
    """设置页面"""

    CSS_PATH = "css/styles.tcss"

    def __init__(self, config_manager: ConfigManager, llm_client: LLMClientBase) -> None:
        """初始化设置页面"""
        super().__init__()
        self.config_manager = config_manager
        self.llm_client = llm_client
        self.backend = self.config_manager.get_backend()
        self.selected_model = self.config_manager.get_model()
        # 添加保存任务的集合
        self.background_tasks: set[asyncio.Task] = set()

        # MCP 工具授权相关状态
        self.auto_execute_status = False  # 默认为手动确认
        self.mcp_status_loaded = False  # 是否已成功加载状态

        # 验证相关状态
        self.is_validated = False
        self.validation_message = ""
        self.validator = APIValidator()
        self.logger = get_logger(__name__)

        # 防抖和验证任务管理
        self._validation_task: asyncio.Task | None = None
        self._debounce_timer: asyncio.Task | None = None
        self._validation_generation = 0  # 用于标记验证代数，避免旧的验证任务执行

    def compose(self) -> ComposeResult:
        """构建设置页面"""
        yield Container(
            Container(
                Label(_("设置"), id="settings-title"),
                # 后端选择
                Horizontal(
                    Label(_("后端:"), classes="settings-label"),
                    Button(
                        f"{self.backend.get_display_name()}",
                        id="backend-btn",
                        classes="settings-button",
                    ),
                    classes="settings-option",
                ),
                # Base URL 输入
                Horizontal(
                    Label(_("Base URL:"), classes="settings-label"),
                    Input(
                        value=self.config_manager.get_base_url()
                        if self.backend == Backend.OPENAI
                        else self.config_manager.get_eulerintelli_url(),
                        classes="settings-input",
                        id="base-url",
                    ),
                    classes="settings-option",
                ),
                # API Key 输入
                Horizontal(
                    Label(_("API Key:"), classes="settings-label"),
                    Input(
                        value=self.config_manager.get_api_key()
                        if self.backend == Backend.OPENAI
                        else self.config_manager.get_eulerintelli_key(),
                        classes="settings-input",
                        id="api-key",
                        placeholder=_("API 访问密钥，可选"),
                        password=True,
                    ),
                    classes="settings-option",
                ),
                # 模型选择（仅 OpenAI 后端显示）
                *(
                    [
                        Horizontal(
                            Label(_("模型:"), classes="settings-label"),
                            Input(
                                value=self.selected_model,
                                classes="settings-input",
                                id="model-input",
                                placeholder=_("模型名称，可选"),
                            ),
                            id="model-section",
                            classes="settings-option",
                        ),
                    ]
                    if self.backend == Backend.OPENAI
                    else [
                        Horizontal(
                            Label(_("MCP 工具授权:"), classes="settings-label"),
                            Button(
                                _("自动执行") if self.auto_execute_status else _("手动确认"),
                                id="mcp-btn",
                                classes="settings-button",
                                disabled=not self.mcp_status_loaded,
                            ),
                            id="mcp-section",
                            classes="settings-option",
                        ),
                    ]
                ),
                # 添加一个空白区域，确保操作按钮始终可见
                Static("", id="spacer"),
                # 操作按钮
                Horizontal(
                    Button(_("保存"), id="save-btn", variant="primary"),
                    Button(_("取消"), id="cancel-btn", variant="default"),
                    id="action-buttons",
                    classes="settings-option",
                ),
                id="settings-container",
            ),
            id="settings-screen",
        )

    def on_mount(self) -> None:
        """组件挂载时加载可用模型"""
        if self.backend == Backend.EULERINTELLI:
            task = asyncio.create_task(self.load_mcp_status())
            # 保存任务引用
            self.background_tasks.add(task)
            task.add_done_callback(self.background_tasks.discard)

        # 启动配置验证
        self._schedule_validation()

        # 确保操作按钮始终可见
        self._ensure_buttons_visible()

    async def load_mcp_status(self) -> None:
        """异步加载 MCP 工具授权状态"""
        try:
            # 只有 EULERINTELLI 后端才支持 MCP 状态
            if self.backend != Backend.EULERINTELLI:
                return

            # 从 Hermes 客户端获取自动执行状态
            if hasattr(self.llm_client, "get_auto_execute_status"):
                self.auto_execute_status = await self.llm_client.get_auto_execute_status()  # type: ignore[attr-defined]
                self.mcp_status_loaded = True
            else:
                self.auto_execute_status = False
                self.mcp_status_loaded = False

            # 更新 MCP 按钮文本和状态
            mcp_btn = self.query_one("#mcp-btn", Button)
            mcp_btn.label = _("自动执行") if self.auto_execute_status else _("手动确认")
            mcp_btn.disabled = not self.mcp_status_loaded

        except (OSError, ValueError, RuntimeError):
            self.auto_execute_status = False
            self.mcp_status_loaded = False
            mcp_btn = self.query_one("#mcp-btn", Button)
            mcp_btn.label = _("手动确认")
            mcp_btn.disabled = True

    @on(Input.Changed, "#base-url, #api-key, #model-input")
    def on_config_changed(self) -> None:
        """当 Base URL、API Key 或模型改变时更新客户端并验证配置"""
        if self.backend == Backend.OPENAI:
            # 获取当前模型输入值
            try:
                model_input = self.query_one("#model-input", Input)
                self.selected_model = model_input.value
            except NoMatches:
                # 如果模型输入框不存在，跳过
                pass

            self._update_llm_client()
        else:  # EULERINTELLI
            self._update_llm_client()
            # 重新加载 MCP 状态
            task = asyncio.create_task(self.load_mcp_status())
            self.background_tasks.add(task)
            task.add_done_callback(self.background_tasks.discard)

        # 重新验证配置
        self._schedule_validation()

    @on(Button.Pressed, "#backend-btn")
    def toggle_backend(self) -> None:
        """切换后端"""
        current = self.backend
        new = Backend.EULERINTELLI if current == Backend.OPENAI else Backend.OPENAI
        self.backend = new

        # 更新按钮文本
        backend_btn = self.query_one("#backend-btn", Button)
        backend_btn.label = new.get_display_name()

        # 更新 URL 和 API Key
        base_url = self.query_one("#base-url", Input)
        api_key = self.query_one("#api-key", Input)

        if new == Backend.OPENAI:
            base_url.value = self.config_manager.get_base_url()
            api_key.value = self.config_manager.get_api_key()

            # 创建新的 OpenAI 客户端
            self._update_llm_client()

            # 移除 MCP 工具授权部分
            mcp_section = self.query("#mcp-section")
            if mcp_section:
                mcp_section[0].remove()

            # 添加模型选择部分
            if not self.query("#model-section"):
                container = self.query_one("#settings-container")
                spacer = self.query_one("#spacer")
                model_section = Horizontal(
                    Label(_("模型:"), classes="settings-label"),
                    Input(
                        value=self.selected_model,
                        classes="settings-input",
                        id="model-input",
                        placeholder=_("模型名称，可选"),
                    ),
                    id="model-section",
                    classes="settings-option",
                )

                # 在 spacer 前面添加 model_section
                if spacer:
                    container.mount(model_section, before=spacer)
                else:
                    container.mount(model_section)
        else:
            base_url.value = self.config_manager.get_eulerintelli_url()
            api_key.value = self.config_manager.get_eulerintelli_key()

            # 创建新的 Hermes 客户端
            self._update_llm_client()

            # 移除模型选择部分
            model_section = self.query("#model-section")
            if model_section:
                model_section[0].remove()

            # 添加 MCP 工具授权部分
            if not self.query("#mcp-section"):
                container = self.query_one("#settings-container")
                spacer = self.query_one("#spacer")
                mcp_section = Horizontal(
                    Label(_("MCP 工具授权:"), classes="settings-label"),
                    Button(
                        _("自动执行") if self.auto_execute_status else _("手动确认"),
                        id="mcp-btn",
                        classes="settings-button",
                        disabled=not self.mcp_status_loaded,
                    ),
                    id="mcp-section",
                    classes="settings-option",
                )

                # 在spacer前面添加mcp_section
                if spacer:
                    container.mount(mcp_section, before=spacer)
                else:
                    container.mount(mcp_section)

                # 重新加载 MCP 状态
                task = asyncio.create_task(self.load_mcp_status())
                # 保存任务引用
                self.background_tasks.add(task)
                task.add_done_callback(self.background_tasks.discard)

        # 确保按钮可见
        self._ensure_buttons_visible()

        # 切换后端后重新验证配置
        self._schedule_validation()

    @on(Button.Pressed, "#mcp-btn")
    def toggle_mcp_authorization(self) -> None:
        """切换 MCP 工具授权模式"""
        if not self.mcp_status_loaded:
            return

        # 创建切换任务
        task = asyncio.create_task(self._toggle_mcp_authorization_async())
        self.background_tasks.add(task)
        task.add_done_callback(self.background_tasks.discard)

    @on(Button.Pressed, "#save-btn")
    def save_settings(self) -> None:
        """保存设置"""
        # 取消所有后台任务
        for task in self.background_tasks:
            if not task.done():
                task.cancel()
        self.background_tasks.clear()

        # 检查验证状态
        if not self.is_validated:
            return

        self.config_manager.set_backend(self.backend)

        base_url = self.query_one("#base-url", Input).value
        api_key = self.query_one("#api-key", Input).value

        if self.backend == Backend.OPENAI:
            # 获取模型输入值
            try:
                model_input = self.query_one("#model-input", Input)
                self.selected_model = model_input.value.strip()
            except NoMatches:
                # 如果模型输入框不存在，保持当前选择的模型
                pass

            self.config_manager.set_base_url(base_url)
            self.config_manager.set_api_key(api_key)
            self.config_manager.set_model(self.selected_model)
        else:  # eulerintelli
            self.config_manager.set_eulerintelli_url(base_url)
            self.config_manager.set_eulerintelli_key(api_key)

        # 通知主应用刷新客户端
        refresh_method = getattr(self.app, "refresh_llm_client", None)
        if refresh_method:
            refresh_method()

        self.app.pop_screen()

    @on(Button.Pressed, "#cancel-btn")
    def cancel_settings(self) -> None:
        """取消设置"""
        # 取消所有后台任务
        for task in self.background_tasks:
            if not task.done():
                task.cancel()
        self.background_tasks.clear()

        self.app.pop_screen()

    def on_key(self, event: Key) -> None:
        """处理键盘事件"""
        if event.key == "escape":
            # 取消所有后台任务
            for task in self.background_tasks:
                if not task.done():
                    task.cancel()
            self.background_tasks.clear()
            # ESC 键退出设置页面，等效于取消
            self.app.pop_screen()
        if event.key == "ctrl+q":
            self.app.push_screen(ExitDialog())
            event.prevent_default()
            event.stop()

    def _schedule_validation(self) -> None:
        """调度验证任务，带防抖机制"""
        # 增加验证代数，使旧的验证任务失效
        self._validation_generation += 1
        current_generation = self._validation_generation

        # 取消之前的定时器
        if self._debounce_timer and not self._debounce_timer.done():
            self._debounce_timer.cancel()

        # 取消之前的验证任务
        if self._validation_task and not self._validation_task.done():
            self._validation_task.cancel()

        # 创建新的定时器，1秒后启动验证
        async def debounce_and_validate() -> None:
            try:
                await asyncio.sleep(1.0)  # 防抖延迟
                # 检查这个任务是否已经过期（有更新的验证请求）
                if current_generation != self._validation_generation:
                    return  # 已经有更新的验证请求，跳过这个过期的验证
                # 再次检查：如果已经有验证任务在运行，跳过
                if self._validation_task and not self._validation_task.done():
                    return
                self._validation_task = asyncio.create_task(self._validate_configuration())
                self.background_tasks.add(self._validation_task)
                self._validation_task.add_done_callback(self.background_tasks.discard)
            except asyncio.CancelledError:
                # 任务被取消，直接退出
                pass

        self._debounce_timer = asyncio.create_task(debounce_and_validate())
        self.background_tasks.add(self._debounce_timer)
        self._debounce_timer.add_done_callback(self.background_tasks.discard)

    def _ensure_buttons_visible(self) -> None:
        """确保操作按钮始终可见"""

        # 延迟一点执行，确保布局已完成
        async def scroll_to_buttons() -> None:
            await asyncio.sleep(0.1)
            container = self.query_one("#settings-container")
            action_buttons = self.query_one("#action-buttons")
            if action_buttons:
                container.scroll_to_widget(action_buttons)

        task = asyncio.create_task(scroll_to_buttons())
        self.background_tasks.add(task)
        task.add_done_callback(self.background_tasks.discard)

    async def _validate_configuration(self) -> None:
        """验证当前配置"""
        try:
            base_url = self.query_one("#base-url", Input).value.strip()
            api_key = self.query_one("#api-key", Input).value.strip()

            if not base_url:
                self.is_validated = False
                self.validation_message = _("Base URL 不能为空")
                self._update_save_button_state()
                return

            if self.backend == Backend.OPENAI:
                # 获取模型输入值（可以为空）
                try:
                    model_input = self.query_one("#model-input", Input)
                    model = model_input.value.strip()
                except NoMatches:
                    # 如果模型输入框不存在，使用当前选择的模型
                    model = self.selected_model

                # 验证 OpenAI 配置（模型和 API Key 都可以为空）
                valid, message, _additional_info = await self.validator.validate_llm_config(
                    endpoint=base_url,
                    api_key=api_key,
                    model=model,
                    timeout=10,
                )
                self.is_validated = valid
                self.validation_message = message
            else:
                # 验证 Witty Assistant 配置
                valid, message = await validate_oi_connection(base_url, api_key)
                self.is_validated = valid
                self.validation_message = message

            # 将验证结果记录到日志，不显示通知
            if self.is_validated:
                self.logger.info("配置验证成功: %s", self.validation_message)
            else:
                self.logger.warning("配置验证失败: %s", self.validation_message)

            self._update_save_button_state()

        except asyncio.CancelledError:
            # 验证被取消，直接退出，不更新状态
            raise
        except (TimeoutError, ValueError, RuntimeError):
            self.is_validated = False
            self.logger.exception("配置验证异常")
            self._update_save_button_state()

    def _update_save_button_state(self) -> None:
        """根据验证状态更新保存按钮"""
        save_btn = self.query_one("#save-btn", Button)
        if self.is_validated:
            save_btn.disabled = False
        else:
            save_btn.disabled = True

    def _update_llm_client(self) -> None:
        """根据当前UI中的配置更新LLM客户端"""
        base_url_input = self.query_one("#base-url", Input)
        api_key_input = self.query_one("#api-key", Input)

        # 保存当前智能体状态（如果是Hermes客户端）
        current_agent_id = ""
        if isinstance(self.llm_client, HermesChatClient):
            current_agent_id = getattr(self.llm_client, "current_agent_id", "")

        if self.backend == Backend.OPENAI:
            # 获取模型输入值，如果输入框不存在则使用当前选择的模型
            try:
                model_input = self.query_one("#model-input", Input)
                model = model_input.value.strip()
            except NoMatches:
                model = self.selected_model

            self.llm_client = OpenAIClient(
                base_url=base_url_input.value,
                model=model,
                api_key=api_key_input.value,
            )
        else:  # EULERINTELLI
            self.llm_client = HermesChatClient(
                base_url=base_url_input.value,
                auth_token=api_key_input.value,
            )
            # 恢复智能体状态
            if current_agent_id:
                self.llm_client.set_current_agent(current_agent_id)

    async def _toggle_mcp_authorization_async(self) -> None:
        """异步切换 MCP 工具授权模式"""
        try:
            # 检查客户端是否支持 MCP 操作
            if (
                not hasattr(self.llm_client, "enable_auto_execute")
                or not hasattr(self.llm_client, "disable_auto_execute")
            ):
                return

            # 先禁用按钮防止重复点击
            mcp_btn = self.query_one("#mcp-btn", Button)
            mcp_btn.disabled = True
            mcp_btn.label = _("切换中...")

            # 根据当前状态调用相应的方法
            if self.auto_execute_status:
                # 当前是自动执行，切换为手动确认
                await self.llm_client.disable_auto_execute()  # type: ignore[attr-defined]
            else:
                # 当前是手动确认，切换为自动执行
                await self.llm_client.enable_auto_execute()  # type: ignore[attr-defined]

            # 重新获取状态以确保同步
            if hasattr(self.llm_client, "get_auto_execute_status"):
                self.auto_execute_status = await self.llm_client.get_auto_execute_status()  # type: ignore[attr-defined]

            # 更新按钮状态
            mcp_btn.label = _("自动执行") if self.auto_execute_status else _("手动确认")
            mcp_btn.disabled = False

        except (OSError, ValueError, RuntimeError):
            # 发生错误时恢复按钮状态
            mcp_btn = self.query_one("#mcp-btn", Button)
            mcp_btn.label = _("自动执行") if self.auto_execute_status else _("手动确认")
            mcp_btn.disabled = False
