"""基于 Textual 的 TUI 应用"""

import asyncio
from typing import ClassVar, Optional

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Header, Input, Label, Static

from app.settings import SettingsScreen
from backend.openai import OpenAIClient
from config import ConfigManager
from tool.command_processor import process_command


class OutputLine(Static):
    """输出行组件"""

    DEFAULT_CSS_CLASS = "output-line"

    def __init__(self, text: str = "", *, command: bool = False) -> None:
        """初始化输出行组件"""
        # 禁用富文本标记解析，防止LLM输出中的特殊字符导致渲染错误
        super().__init__(text, markup=False)
        if command:
            self.add_class("command-line")

    def update(self, content="") -> None:
        """更新组件内容，确保禁用富文本标记解析"""
        # 重写update方法，确保更新内容时也禁用富文本标记解析
        super().update(content)


class CommandInput(Input):
    """命令输入组件"""

    def __init__(self) -> None:
        """初始化命令输入组件"""
        super().__init__(placeholder="输入命令或问题...", id="command-input")


class ExitDialog(ModalScreen):
    """退出确认对话框"""

    def compose(self) -> ComposeResult:
        """构建退出确认对话框"""
        yield Container(
            Container(
                Label("确认退出吗？", id="dialog-text"),
                Horizontal(
                    Button("取消", classes="dialog-button", id="cancel"),
                    Button("确认", classes="dialog-button", id="confirm"),
                    id="dialog-buttons",
                ),
                id="exit-dialog",
            ),
            id="exit-dialog-screen",
        )

    @on(Button.Pressed, "#cancel")
    def cancel_exit(self) -> None:
        """取消退出"""
        self.app.pop_screen()

    @on(Button.Pressed, "#confirm")
    def confirm_exit(self) -> None:
        """确认退出"""
        self.app.exit()


class EulerCopilot(App):
    """基于 Textual 的智能终端应用"""

    CSS_PATH = "css/smart_shell.tcss"
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding(key="ctrl+s", action="settings", description="设置"),
        Binding(key="esc", action="request_quit", description="退出"),
    ]

    def __init__(self) -> None:
        """初始化应用"""
        super().__init__()
        self.config_manager = ConfigManager()
        self.processing: bool = False
        # 添加保存任务的集合到类属性
        self.background_tasks: set[asyncio.Task] = set()

    def compose(self) -> ComposeResult:
        """构建界面"""
        yield Header(show_clock=True)
        yield Container(id="output-container")
        with Container(id="input-container"):
            yield CommandInput()
        yield Footer()

    def action_settings(self) -> None:
        """打开设置页面"""
        self.push_screen(SettingsScreen(self.config_manager, self._get_llm_client()))

    def action_request_quit(self) -> None:
        """请求退出应用"""
        self.push_screen(ExitDialog())

    def on_mount(self) -> None:
        """初始化完成时设置焦点"""
        self.query_one(CommandInput).focus()

    def exit(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        """退出应用前取消所有后台任务"""
        # 取消所有正在运行的后台任务
        for task in self.background_tasks:
            if not task.done():
                task.cancel()
        # 调用父类的exit方法
        super().exit(*args, **kwargs)

    @on(Input.Submitted, "#command-input")
    def handle_input(self, event: Input.Submitted) -> None:
        """处理命令输入"""
        user_input = event.value.strip()
        if not user_input or self.processing:
            return

        # 清空输入框
        input_widget = self.query_one(CommandInput)
        input_widget.value = ""

        # 显示命令
        output_container = self.query_one("#output-container")
        output_container.mount(OutputLine(f"> {user_input}", command=True))

        # 异步处理命令
        self.processing = True
        # 创建任务并保存到类属性中的任务集合
        task = asyncio.create_task(self._process_command(user_input))
        self.background_tasks.add(task)
        # 添加完成回调，自动从集合中移除
        task.add_done_callback(self._task_done_callback)

    def _task_done_callback(self, task: asyncio.Task) -> None:
        """任务完成回调，从任务集合中移除"""
        if task in self.background_tasks:
            self.background_tasks.remove(task)
        # 捕获任务中的异常，防止未处理异常
        try:
            task.result()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self.log.error("Command processing error: %s", e)  # noqa: TRY400
        finally:
            # 确保处理标志被重置
            self.processing = False

    async def _process_command(self, user_input: str) -> None:
        """异步处理命令"""
        try:
            first_chunk = True
            current_line: Optional[OutputLine] = None
            output_container = self.query_one("#output-container")

            async for output in process_command(user_input, self._get_llm_client()):
                if first_chunk:
                    current_line = OutputLine(output)
                    output_container.mount(current_line)
                    first_chunk = False
                elif "\n" in output:
                    # 处理流式输出中的换行
                    parts = output.split("\n")
                    if current_line:
                        # 获取当前文本
                        current_text = str(current_line.renderable)
                        current_line.update(current_text + parts[0])
                        for part in parts[1:]:
                            current_line = OutputLine(part)
                            output_container.mount(current_line)
                elif current_line:
                    # 获取当前文本
                    current_text = str(current_line.renderable)
                    current_line.update(current_text + output)

                # 滚动到底部
                await self._scroll_to_end()
        except Exception as e:
            # 添加异常处理，显示错误信息
            output_container = self.query_one("#output-container")
            output_container.mount(OutputLine(f"处理命令时出错: {e!s}", command=False))
        finally:
            # 重新聚焦到输入框
            self.query_one(CommandInput).focus()
            # 注意：不在这里重置processing标志，由回调函数处理

    async def _scroll_to_end(self) -> None:
        """滚动到容器底部的辅助方法"""
        # 获取输出容器
        output_container = self.query_one("#output-container")
        # 使用同步方法滚动，确保UI更新
        output_container.scroll_end(animate=False)
        # 等待一个小的延迟，确保UI有时间更新
        await asyncio.sleep(0.01)

    def _get_llm_client(self) -> OpenAIClient:
        """获取大模型客户端"""
        return OpenAIClient(
            base_url=self.config_manager.get_base_url(),
            model=self.config_manager.get_model(),
            api_key=self.config_manager.get_api_key(),
        )
