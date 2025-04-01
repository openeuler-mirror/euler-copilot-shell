"""设置页面"""

import asyncio

from textual import on
from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.screen import Screen
from textual.widgets import Button, Input, Label, Static

from backend.openai import OpenAIClient
from config import Backend, ConfigManager


class SettingsScreen(Screen):
    """设置页面"""

    CSS_PATH = "css/styles.tcss"

    def __init__(self, config_manager: ConfigManager, llm_client: OpenAIClient) -> None:
        """初始化设置页面"""
        super().__init__()
        self.config_manager = config_manager
        self.llm_client = llm_client
        self.backend = self.config_manager.get_backend()
        self.models: list[str] = []
        self.selected_model = self.config_manager.get_model()
        # 添加保存任务的集合
        self.background_tasks: set[asyncio.Task] = set()

    def compose(self) -> ComposeResult:
        """构建设置页面"""
        yield Container(
            Container(
                Label("设置", id="settings-title"),
                # 后端选择
                Horizontal(
                    Label("后端:", classes="settings-label"),
                    Button(f"{self.backend}", id="backend-btn", classes="settings-value settings-button"),
                    classes="settings-option",
                ),
                # Base URL 输入
                Horizontal(
                    Label("Base URL:", classes="settings-label"),
                    Input(
                        value=self.config_manager.get_base_url()
                        if self.backend == Backend.OPENAI
                        else self.config_manager.get_eulercopilot_url(),
                        id="base-url",
                    ),
                    classes="settings-option",
                ),
                # API Key 输入
                Horizontal(
                    Label("API Key:", classes="settings-label"),
                    Input(
                        value=self.config_manager.get_api_key()
                        if self.backend == Backend.OPENAI
                        else self.config_manager.get_eulercopilot_key(),
                        id="api-key",
                    ),
                    classes="settings-option",
                ),
                # 模型选择（仅 OpenAI 后端显示）
                *(
                    [
                        Horizontal(
                            Label("模型:", classes="settings-label"),
                            Button(f"{self.selected_model}", id="model-btn", classes="settings-value settings-button"),
                            id="model-section",
                            classes="settings-option",
                        ),
                    ]
                    if self.backend == Backend.OPENAI
                    else []
                ),
                # 添加一个空白区域，确保操作按钮始终可见
                Static("", id="spacer"),
                # 操作按钮
                Horizontal(
                    Button("保存", id="save-btn", classes="settings-button"),
                    Button("取消", id="cancel-btn", classes="settings-button"),
                    id="action-buttons",
                    classes="settings-option",
                ),
                id="settings-container",
            ),
            id="settings-screen",
        )

    def on_mount(self) -> None:
        """组件挂载时加载可用模型"""
        if self.backend == Backend.OPENAI:
            task = asyncio.create_task(self.load_models())
            # 保存任务引用
            self.background_tasks.add(task)
            task.add_done_callback(self.background_tasks.discard)

        # 确保操作按钮始终可见
        self._ensure_buttons_visible()

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

    async def load_models(self) -> None:
        """异步加载可用模型列表"""
        try:
            self.models = await self.llm_client.get_available_models()
            if self.models and self.selected_model not in self.models:
                self.selected_model = self.models[0]

            # 更新模型按钮文本
            model_btn = self.query_one("#model-btn", Button)
            model_btn.label = self.selected_model
        except Exception:
            model_btn = self.query_one("#model-btn", Button)
            model_btn.label = "暂无可用模型"

    @on(Button.Pressed, "#backend-btn")
    def toggle_backend(self) -> None:
        """切换后端"""
        current = self.backend
        new = Backend.EULERCOPILOT if current == Backend.OPENAI else Backend.OPENAI
        self.backend = new

        # 更新按钮文本
        backend_btn = self.query_one("#backend-btn", Button)
        backend_btn.label = new

        # 更新 URL 和 API Key
        base_url = self.query_one("#base-url", Input)
        api_key = self.query_one("#api-key", Input)

        if new == Backend.OPENAI:
            base_url.value = self.config_manager.get_base_url()
            api_key.value = self.config_manager.get_api_key()

            # 添加模型选择部分
            if not self.query("#model-section"):
                container = self.query_one("#settings-container")
                spacer = self.query_one("#spacer")
                model_section = Horizontal(
                    Label("模型:", classes="settings-label"),
                    Button(self.selected_model, id="model-btn", classes="settings-value settings-button"),
                    id="model-section",
                    classes="settings-option",
                )

                # 在spacer前面添加model_section
                if spacer:
                    container.mount(model_section, before=spacer)
                else:
                    container.mount(model_section)

                # 重新加载模型
                task = asyncio.create_task(self.load_models())
                # 保存任务引用
                self.background_tasks.add(task)
                task.add_done_callback(self.background_tasks.discard)
        else:
            base_url.value = self.config_manager.get_eulercopilot_url()
            api_key.value = self.config_manager.get_eulercopilot_key()

            # 移除模型选择部分
            model_section = self.query("#model-section")
            if model_section:
                model_section[0].remove()

        # 确保按钮可见
        self._ensure_buttons_visible()

    @on(Button.Pressed, "#model-btn")
    def toggle_model(self) -> None:
        """循环切换模型"""
        if not self.models:
            return

        try:
            # 如果当前选择的模型在列表中，则找到它的索引
            if self.selected_model in self.models:
                idx = self.models.index(self.selected_model)
                idx = (idx + 1) % len(self.models)
            else:
                # 如果不在列表中，则从第一个模型开始
                idx = 0
            self.selected_model = self.models[idx]

            # 更新按钮文本
            model_btn = self.query_one("#model-btn", Button)
            model_btn.label = self.selected_model
        except Exception:
            # 处理任何可能的异常
            self.selected_model = self.models[0] if self.models else "默认模型"
            model_btn = self.query_one("#model-btn", Button)
            model_btn.label = self.selected_model

    @on(Button.Pressed, "#save-btn")
    def save_settings(self) -> None:
        """保存设置"""
        self.config_manager.set_backend(self.backend)

        base_url = self.query_one("#base-url", Input).value
        api_key = self.query_one("#api-key", Input).value

        if self.backend == Backend.OPENAI:
            self.config_manager.set_base_url(base_url)
            self.config_manager.set_api_key(api_key)
            self.config_manager.set_model(self.selected_model)
        else:  # eulercopilot
            self.config_manager.set_eulercopilot_url(base_url)
            self.config_manager.set_eulercopilot_key(api_key)

        self.app.pop_screen()

    @on(Button.Pressed, "#cancel-btn")
    def cancel_settings(self) -> None:
        """取消设置"""
        self.app.pop_screen()
