"""设置页面"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from textual import on
from textual.containers import Container, Horizontal
from textual.css.query import NoMatches
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static

from app.dialogs import ExitDialog, UserConfigDialog
from config import Backend, ConfigManager
from i18n.manager import _
from log import get_logger
from tool.validators import APIValidator, validate_oi_connection

if TYPE_CHECKING:
    from textual.app import ComposeResult
    from textual.events import Key

    from backend import LLMClientBase


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
                *self._create_common_widgets(),
                *self._create_backend_widgets(),
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
        # 启动配置验证
        self._schedule_validation()

        # 确保操作按钮始终可见
        self._ensure_buttons_visible()

    @on(Input.Changed, "#base-url, #api-key, #model-input")
    def on_config_changed(self) -> None:
        """当 Base URL、API Key 或模型改变时验证配置"""
        if self.backend == Backend.OPENAI:
            # 获取当前模型输入值
            try:
                model_input = self.query_one("#model-input", Input)
                self.selected_model = model_input.value
            except NoMatches:
                # 如果模型输入框不存在，跳过
                pass

        # 重新验证配置
        self._schedule_validation()

    @on(Button.Pressed, "#backend-btn")
    def toggle_backend(self) -> None:
        """切换后端"""
        # 切换后端类型
        self.backend = (
            Backend.SYSAGENT if self.backend == Backend.OPENAI else Backend.OPENAI
        )

        # 更新后端按钮文本
        backend_btn = self.query_one("#backend-btn", Button)
        backend_btn.label = self.backend.get_display_name()

        # 更新配置输入框的值
        self._load_config_inputs()

        # 替换后端特定的 UI 组件
        self._replace_backend_widgets()

        # 确保按钮可见
        self._ensure_buttons_visible()

        # 切换后端后重新验证配置
        self._schedule_validation()

    @on(Button.Pressed, "#user-config-btn")
    def open_user_config(self) -> None:
        """打开用户配置对话框"""
        dialog = UserConfigDialog(self.config_manager, self.llm_client)
        self.app.push_screen(dialog)

    @on(Button.Pressed, "#save-btn")
    def save_settings(self) -> None:
        """保存设置"""
        # 取消所有后台任务
        self._cancel_background_tasks()

        # 检查验证状态
        if not self.is_validated:
            return

        # 获取旧配置
        old_backend, old_base, old_key = self._get_old_config()

        # 保存新配置
        base_url, api_key = self._save_new_config()

        # 判断是否需要刷新客户端
        need_refresh = self._should_refresh_client(old_backend, old_base, old_key, base_url, api_key)

        # 刷新客户端
        if need_refresh:
            self._refresh_app_client()

        self.app.pop_screen()

    @on(Button.Pressed, "#cancel-btn")
    def cancel_settings(self) -> None:
        """取消设置"""
        self._cancel_background_tasks()
        self.app.pop_screen()

    def on_key(self, event: Key) -> None:
        """处理键盘事件"""
        if event.key == "escape":
            self._cancel_background_tasks()
            # ESC 键退出设置页面，等效于取消
            self.app.pop_screen()
        if event.key == "ctrl+q":
            self.app.push_screen(ExitDialog())
            event.prevent_default()
            event.stop()

    def _create_common_widgets(self) -> list:
        """创建通用的 UI 组件（所有后端共享）"""
        return [
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
                    else self.config_manager.get_witty_url(),
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
                    else self.config_manager.get_witty_key(),
                    classes="settings-input",
                    id="api-key",
                    placeholder=_("API 访问密钥，可选"),
                    password=True,
                ),
                classes="settings-option"),
        ]

    def _create_backend_widgets(self) -> list:
        """创建后端特定的 UI 组件"""
        if self.backend == Backend.OPENAI:
            return [
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

        # SYSAGENT 后端
        return [
            Horizontal(
                Label(_("用户设置:"), classes="settings-label"),
                Button(
                    _("更改用户设置"),
                    id="user-config-btn",
                    classes="settings-button",
                ),
                id="user-config-section",
                classes="settings-option",
            ),
        ]

    def _cancel_background_tasks(self) -> None:
        """取消所有后台任务"""
        for task in self.background_tasks:
            if not task.done():
                task.cancel()
        self.background_tasks.clear()

    def _get_old_config(self) -> tuple[Backend, str, str]:
        """获取旧配置"""
        old_backend = self.config_manager.get_backend()

        if old_backend == Backend.OPENAI:
            old_base = self.config_manager.get_base_url()
            old_key = self.config_manager.get_api_key()
        else:
            old_base = self.config_manager.get_witty_url()
            old_key = self.config_manager.get_witty_key()

        return old_backend, old_base, old_key

    def _save_new_config(self) -> tuple[str, str]:
        """保存新配置并返回 base_url 和 api_key"""
        self.config_manager.set_backend(self.backend)

        base_url = self.query_one("#base-url", Input).value
        api_key = self.query_one("#api-key", Input).value

        if self.backend == Backend.OPENAI:
            self._save_openai_config(base_url, api_key)
        else:  # witty
            self.config_manager.set_witty_url(base_url)
            self.config_manager.set_witty_key(api_key)

        return base_url, api_key

    def _save_openai_config(self, base_url: str, api_key: str) -> None:
        """保存 OpenAI 配置"""
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

    def _should_refresh_client(
        self,
        old_backend: Backend,
        old_base: str,
        old_key: str,
        new_base: str,
        new_key: str,
    ) -> bool:
        """判断是否需要刷新客户端"""
        # 后端类型变化
        if old_backend != self.backend:
            return True

        # 同一后端，URL 或 Key 变化
        if old_base != new_base or old_key != new_key:
            return True

        # OpenAI 后端，检查模型是否变化
        if self.backend == Backend.OPENAI:
            old_model = self.config_manager.get_model()
            if old_model != self.selected_model:
                return True

        return False

    def _refresh_app_client(self) -> None:
        """刷新应用客户端"""
        refresh_method = getattr(self.app, "refresh_llm_client", None)
        if refresh_method:
            refresh_method()

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

    def _load_config_inputs(self) -> None:
        """根据当前后端载入配置输入框的值"""
        base_url = self.query_one("#base-url", Input)
        api_key = self.query_one("#api-key", Input)

        if self.backend == Backend.OPENAI:
            base_url.value = self.config_manager.get_base_url()
            api_key.value = self.config_manager.get_api_key()
        else:  # SYSAGENT
            base_url.value = self.config_manager.get_witty_url()
            api_key.value = self.config_manager.get_witty_key()

    def _replace_backend_widgets(self) -> None:
        """替换后端特定的 UI 组件"""
        container = self.query_one("#settings-container")
        spacer = self.query_one("#spacer")

        # 移除所有后端特定的组件
        for section_id in ["#model-section", "#user-config-section"]:
            sections = self.query(section_id)
            for section in sections:
                section.remove()

        # 添加新的后端特定组件
        for widget in self._create_backend_widgets():
            if spacer:
                container.mount(widget, before=spacer)
            else:
                container.mount(widget)

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
                # 验证 sysAgent 配置
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
