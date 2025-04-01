"""基于 Textual 的 TUI 应用"""

import asyncio
from typing import ClassVar, Optional, Union

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.visual import VisualType
from textual.widgets import Button, Footer, Header, Input, Label, RichLog, Static

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
        self.text_content = text

    def update(self, content: VisualType = "") -> None:
        """更新组件内容，确保禁用富文本标记解析"""
        # 如果是字符串，更新内部存储的文本内容
        if isinstance(content, str):
            self.text_content = content
        # 调用父类方法进行实际更新
        super().update(content)

    def get_content(self) -> str:
        """获取组件内容的纯文本表示"""
        return self.text_content


class MarkdownOutputLine(RichLog):
    """Markdown输出行组件，使用RichLog直接显示Rich格式化的Markdown"""

    def __init__(self, markdown: str = "") -> None:
        """初始化支持真正富文本的Markdown输出组件"""
        # 确保正确初始化，并禁用垂直滚动条
        super().__init__(highlight=True, markup=True)
        # 设置重要属性
        self.show_vertical_scroll = False  # 禁用垂直滚动条
        self.show_cursor = False  # 隐藏光标
        self.auto_height = True  # 自动调整高度
        self.wrap = True  # 自动换行
        # 设置样式，确保内容正确显示并不会被截断
        self.styles.width = "100%"
        self.styles.height = "auto"  # 自动高度
        # 储存原始内容
        self.current_content = markdown
        # 清除默认内容
        self.clear()
        # 使用rich的Markdown渲染器渲染内容
        if markdown:
            from rich.markdown import Markdown as RichMarkdown

            # 强制设置代码高亮，确保代码块正确渲染
            self.write(RichMarkdown(markdown, code_theme="monokai"))
            # 强制刷新渲染
            self.refresh()

    def update_markdown(self, markdown: str) -> None:
        """更新Markdown内容"""
        from rich.markdown import Markdown as RichMarkdown

        self.current_content = markdown
        # 清除现有内容
        self.clear()
        # 重新渲染markdown，强制使用代码高亮主题
        self.write(RichMarkdown(markdown, code_theme="monokai"))
        # 强制刷新渲染
        self.refresh()

    def get_content(self) -> str:
        """获取当前Markdown原始内容"""
        return self.current_content


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
            current_line: Optional[Union[OutputLine, MarkdownOutputLine]] = None
            current_content = ""  # 用于累积内容
            output_container = self.query_one("#output-container", Container)
            is_first_content = True  # 标记是否是第一段内容

            # 通过process_command获取命令处理结果和输出类型
            async for output_tuple in process_command(user_input, self._get_llm_client()):
                content, is_llm_output = output_tuple  # 解包输出内容和类型标志

                # 处理第一段内容，创建适当的输出组件
                if is_first_content:
                    is_first_content = False

                    if is_llm_output:
                        # LLM输出，使用富文本渲染
                        current_line = MarkdownOutputLine(content)
                        current_content = content
                    else:
                        # 系统命令输出，使用纯文本
                        current_line = OutputLine(content)
                        current_content = content

                    # 将组件添加到输出容器
                    output_container.mount(current_line)
                # 处理后续内容
                elif is_llm_output and isinstance(current_line, MarkdownOutputLine):
                    # 继续累积LLM富文本内容
                    current_content += content
                    current_line.update_markdown(current_content)
                elif not is_llm_output and isinstance(current_line, OutputLine):
                    # 继续累积命令输出纯文本
                    current_text = current_line.get_content()
                    current_line.update(current_text + content)
                else:
                    # 输出类型发生变化，创建新的输出组件
                    if is_llm_output:
                        current_line = MarkdownOutputLine(content)
                        current_content = content
                    else:
                        current_line = OutputLine(content)
                        current_content = content

                    output_container.mount(current_line)

                # 滚动到底部
                await self._scroll_to_end()

        except Exception as e:
            # 添加异常处理，显示错误信息
            output_container = self.query_one("#output-container", Container)
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
