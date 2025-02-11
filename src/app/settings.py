"""设置页面"""

import asyncio
from typing import Callable

import urwid

from backend.openai import OpenAIClient
from config import Backend, ConfigManager


class SettingsPage(urwid.WidgetWrap):
    """设置页面

    允许用户查看并编辑应用设置
    """

    def __init__(self,
            config_manager: ConfigManager,
            llm_client: OpenAIClient,
            on_close: Callable[[], None],
        ) -> None:
        """初始化设置页面"""
        self.config_manager = config_manager
        self.llm_client = llm_client
        self.on_close = on_close

        self.backend = self.config_manager.get_backend()
        # 使用按钮来选择后端
        self.backend_btn = urwid.Button("后端: " + self.backend, on_press=self.select_backend)
        # 构建界面
        self._build_ui()
        super().__init__(self.box)

    def select_backend(self, _button: urwid.Button) -> None:
        """点击后端按钮切换后端（openai 与 eulercopilot），并刷新设置页面"""
        current = self.config_manager.get_backend()
        new = Backend.EULERCOPILOT if current == Backend.OPENAI else Backend.OPENAI
        self.config_manager.set_backend(new)
        self.backend = new
        # 更新后端按钮
        self.backend_btn.set_label("后端: " + self.backend)
        # 重建页面
        self._build_ui()

    async def load_models(self) -> None:
        """异步加载可用模型列表，并初始化默认选择"""
        models = await self.llm_client.get_available_models()
        if models:
            self.models = models
            if self.selected_model not in models:
                self.selected_model = models[0]
            self.model_btn.set_label("模型: " + self.selected_model)
            urwid.connect_signal(self.model_btn, "click", self.select_model)
        else:
            self.model_btn.set_label("")

    def select_model(self, _button: urwid.Button) -> None:
        """点击模型按钮循环切换模型"""
        if self.models:
            idx = self.models.index(self.selected_model)
            idx = (idx + 1) % len(self.models)
            self.selected_model = self.models[idx]
            self.model_btn.set_label("模型: " + self.selected_model)

    def save_settings(self, button: urwid.Button) -> None:
        """保存用户更新的设置"""
        self.config_manager.set_backend(self.backend)
        if self.backend == "openai":
            self.config_manager.set_base_url(self.base_url_edit.get_edit_text())
            self.config_manager.set_api_key(self.api_key_edit.get_edit_text())
            self.config_manager.set_model(self.selected_model)
        else:  # eulercopilot
            self.config_manager.set_eulercopilot_url(self.base_url_edit.get_edit_text())
            self.config_manager.set_eulercopilot_key(self.api_key_edit.get_edit_text())
        self.close(button)

    def close(self, _button: urwid.Button) -> None:
        """关闭设置页面"""
        self.on_close()

    def _build_ui(self) -> None:
        """构建或重建页面控件"""
        body_widgets = [self.backend_btn]
        if self.backend == "openai":
            self.base_url_edit = urwid.Edit("Base URL: ", self.config_manager.get_base_url())
            self.model_btn = urwid.Button("模型: " + self.config_manager.get_model(), on_press=self.select_model)
            self.api_key_edit = urwid.Edit("API Key: ", self.config_manager.get_api_key())
            body_widgets = [
                self.backend_btn,
                self.base_url_edit,
                urwid.Text("模型:"),
                self.model_btn,
                self.api_key_edit,
            ]
            # 异步加载所有模型
            self.models = []
            self.selected_model = self.config_manager.get_model()
            self.load_models_task = asyncio.ensure_future(self.load_models())
        else:  # eulercopilot
            self.base_url_edit = urwid.Edit("Base URL: ", self.config_manager.get_eulercopilot_url())
            self.api_key_edit = urwid.Edit("API Key: ", self.config_manager.get_eulercopilot_key())
            body_widgets = [
                self.backend_btn,
                self.base_url_edit,
                self.api_key_edit,
            ]
        self.save_btn = urwid.Button("保存", self.save_settings)
        self.cancel_btn = urwid.Button("取消", self.close)
        body_widgets.append(urwid.Columns([self.save_btn, self.cancel_btn], dividechars=2))
        pile = urwid.Pile(body_widgets)
        fill = urwid.Filler(pile)
        self.box = urwid.LineBox(fill, title="设置")
        self._w = self.box
