"""基于 Textual 的 TUI 应用"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, ClassVar, NamedTuple, cast

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Container
from textual.message import Message
from textual.widgets import Footer, Input, Markdown, Static

from __version__ import __version__
from app.dialogs import AgentSelectionDialog, BackendRequiredDialog, ExitDialog
from app.mcp_widgets import MCPConfirmResult, MCPConfirmWidget, MCPParameterResult, MCPParameterWidget
from app.settings import SettingsScreen
from app.tui_header import OIHeader
from app.tui_mcp_handler import TUIMCPEventHandler
from backend import BackendFactory, HermesChatClient, OpenAIClient
from backend.hermes.exceptions import HermesAPIError
from backend.hermes.mcp_helpers import (
    LLM_STATS_PREFIX,
    MCPEmojis,
    MCPTagInfo,
    MCPTags,
    extract_mcp_tag,
    format_error_message,
    is_mcp_message,
)
from config import ConfigManager
from config.model import Backend
from i18n.manager import _
from log.manager import get_logger, log_exception
from tool.command_processor import process_command
from tool.validators import APIValidator

if TYPE_CHECKING:
    from textual.events import Key as KeyEvent
    from textual.visual import VisualType
    from textual.widget import Widget

    from backend import LLMClientBase


class ContentChunkParams(NamedTuple):
    """内容块处理参数"""

    content: str
    is_llm_output: bool
    current_content: str
    is_first_content: bool


class SelectionCopyMixin:
    """为支持文本选择复制的组件提供通用方法"""

    def _copy_selected_text(self) -> bool:
        """若当前屏幕存在文本选区则复制选中内容"""
        widget = cast("Widget", self)
        app = widget.app
        if app is None:
            return False

        screen = widget.screen
        if screen is not None:
            selected_text = screen.get_selected_text()
            if selected_text is not None:
                app.copy_to_clipboard(selected_text)
                return True

        selection = widget.text_selection
        if selection is None:
            return False

        extracted = widget.get_selection(selection)
        if not extracted:
            return False

        selected_text, _ = extracted
        if not selected_text:
            return False

        app.copy_to_clipboard(selected_text)
        return True


class FocusableContainer(Container):
    """可聚焦的容器，用于接收键盘事件处理滚动"""

    def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        """初始化可聚焦的容器"""
        super().__init__(*args, **kwargs)
        # 设置为可聚焦
        self.can_focus = True

    def on_key(self, event: KeyEvent) -> None:
        """处理键盘事件"""
        key_handled = True

        if event.key == "up":
            # 向上滚动
            self.scroll_up()
        elif event.key == "down":
            # 向下滚动
            self.scroll_down()
        elif event.key == "page_up":
            # 向上翻页
            for _ in range(10):  # 模拟翻页效果
                self.scroll_up()
        elif event.key == "page_down":
            # 向下翻页
            for _ in range(10):  # 模拟翻页效果
                self.scroll_down()
        elif event.key == "home":
            # 滚动到顶部
            self.scroll_home()
        elif event.key == "end":
            # 滚动到底部
            self.scroll_end()
        else:
            # 其他按键不处理
            key_handled = False
            return

        # 只有当我们处理了按键时，才阻止事件传递
        if key_handled:
            event.prevent_default()
            event.stop()
            # 确保视图更新
            self.refresh()


class OutputLine(SelectionCopyMixin, Static):
    """输出行组件"""

    def __init__(self, text: str = "", *, command: bool = False) -> None:
        """初始化输出行组件"""
        super().__init__(text, markup=False)
        if command:
            self.add_class("command-line")
        self.text_content = text
        self.can_focus = True

    def action_copy(self) -> None:
        """复制内容到剪贴板"""
        if self._copy_selected_text():
            return
        if self.text_content:
            self.app.copy_to_clipboard(self.text_content)

    def update(self, content: VisualType = "", *, layout: bool = True) -> None:
        """更新组件内容，确保禁用富文本标记解析"""
        # 如果是字符串，更新内部存储的文本内容
        if isinstance(content, str):
            self.text_content = content
        # 调用父类方法进行实际更新
        super().update(content, layout=layout)

    def get_content(self) -> str:
        """获取组件内容的纯文本表示"""
        return self.text_content


class MarkdownOutput(SelectionCopyMixin, Markdown):
    """Markdown 输出组件"""

    def __init__(self, markdown_content: str = "") -> None:
        """初始化 Markdown 输出组件"""
        super().__init__(markdown_content)
        self.current_content = markdown_content
        self.add_class("llm-output")
        self.can_focus = True

    def action_copy(self) -> None:
        """复制内容到剪贴板"""
        if self._copy_selected_text():
            return
        if self.current_content:
            self.app.copy_to_clipboard(self.current_content)

    def update_markdown(self, markdown_content: str) -> None:
        """更新 Markdown 内容"""
        self.current_content = markdown_content
        self.update(markdown_content)

    def get_content(self) -> str:
        """获取当前 Markdown 原始内容"""
        return self.current_content


class MCPProgressBlock(MarkdownOutput):
    """用于展示连续 MCP 步骤的进度块"""

    def __init__(self) -> None:
        """初始化进度块"""
        super().__init__("")
        self.add_class("mcp-progress-block")
        self._steps: list[tuple[str, str]] = []
        self._step_index: dict[str, int] = {}

    def upsert_step(self, step_id: str, markdown_content: str) -> None:
        """添加或更新指定步骤的展示内容"""
        if step_id in self._step_index:
            idx = self._step_index[step_id]
            self._steps[idx] = (step_id, markdown_content)
        else:
            self._step_index[step_id] = len(self._steps)
            self._steps.append((step_id, markdown_content))
        self._refresh()

    def has_step(self, step_id: str) -> bool:
        """检查是否已存在指定步骤"""
        return step_id in self._step_index

    def reset(self) -> None:
        """清空所有步骤内容"""
        self._steps.clear()
        self._step_index.clear()
        self.update_markdown("")

    def _refresh(self) -> None:
        """重新渲染当前步骤内容"""
        if not self._steps:
            self.update_markdown("")
            return
        combined = "\n\n".join(step_content for _step_id, step_content in self._steps if step_content)
        self.update_markdown(combined)


class MCPWaitingBlock(MarkdownOutput):
    """用于提示等待确认或参数输入的特殊块"""

    def __init__(self, markdown_content: str = "") -> None:
        """初始化等待块"""
        super().__init__(markdown_content)
        self.add_class("mcp-waiting-block")


class CommandInput(Input):
    """命令输入组件"""

    def __init__(self) -> None:
        """初始化命令输入组件"""
        super().__init__(placeholder=_("Enter command or question..."), id="command-input")


class IntelligentTerminal(App):
    """基于 Textual 的智能终端应用"""

    CSS_PATH = "css/styles.tcss"

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding(key="ctrl+q", action="request_quit", description=_("Quit")),
        Binding(key="ctrl+s", action="settings", description=_("Settings")),
        Binding(key="ctrl+r", action="reset_conversation", description=_("Reset")),
        Binding(key="ctrl+t", action="choose_agent", description=_("Agent")),
        Binding(key="ctrl+c", action="cancel", description=_("Cancel"), priority=True),
        Binding(key="tab", action="toggle_focus", description=_("Focus")),
    ]

    class SwitchToMCPConfirm(Message):
        """切换到 MCP 确认界面的消息"""

        def __init__(self, event) -> None:  # noqa: ANN001
            """初始化消息"""
            super().__init__()
            self.event = event

    class SwitchToMCPParameter(Message):
        """切换到 MCP 参数输入界面的消息"""

        def __init__(self, event) -> None:  # noqa: ANN001
            """初始化消息"""
            super().__init__()
            self.event = event

    def __init__(self) -> None:
        """初始化应用"""
        super().__init__()
        # 设置应用标题
        self.title = "openEuler Intelligence"
        self.sub_title = _("Intelligent CLI Assistant {version}").format(version=__version__)
        self.config_manager = ConfigManager()
        self.processing: bool = False
        # 添加保存任务的集合到类属性
        self.background_tasks: set[asyncio.Task] = set()
        # 创建并保持单一的 LLM 客户端实例以维持对话历史
        self._llm_client: LLMClientBase | None = None
        # 当前选择的智能体 - 根据配置的 default_app 初始化
        self.current_agent: tuple[str, str] = self._get_initial_agent()
        # MCP 状态
        self._mcp_mode: str = "normal"  # "normal", "confirm", "parameter"
        # 创建日志实例
        self.logger = get_logger(__name__)
        # MCP 进度展示状态
        self._current_progress_block: MCPProgressBlock | None = None
        self._current_waiting_block: MCPWaitingBlock | None = None
        self._mcp_cluster_active: bool = False
        self._mcp_step_blocks: dict[str, MCPProgressBlock] = {}

    def compose(self) -> ComposeResult:
        """构建界面"""
        yield OIHeader()
        yield FocusableContainer(id="output-container")
        with Container(id="input-container", classes="normal-mode"):
            yield CommandInput()
        yield Footer(show_command_palette=False)

    def action_settings(self) -> None:
        """打开设置页面"""
        # 只有在主界面（无其他屏幕）时才响应
        if not self._is_in_main_interface():
            return
        self.push_screen(SettingsScreen(self.config_manager, self.get_llm_client()))

    def action_request_quit(self) -> None:
        """请求退出应用"""
        # 检查是否已经在退出对话框
        if self._is_exit_dialog_open():
            return
        self.push_screen(ExitDialog())

    def action_reset_conversation(self) -> None:
        """重置对话历史记录的动作"""
        # 只有在主界面（无其他屏幕）时才响应
        if not self._is_in_main_interface():
            return
        if self._llm_client is not None and hasattr(self._llm_client, "reset_conversation"):
            self._llm_client.reset_conversation()
        # 清除屏幕上的所有内容
        output_container = self.query_one("#output-container")
        output_container.remove_children()
        # 清理 MCP 状态
        self._reset_mcp_state()

    def action_choose_agent(self) -> None:
        """选择智能体的动作"""
        # 只有在主界面（无其他屏幕）时才响应
        if not self._is_in_main_interface():
            return
        # 获取 Hermes 客户端
        llm_client = self.get_llm_client()

        # 检查客户端类型
        if not hasattr(llm_client, "get_available_agents"):
            # 显示后端要求提示对话框
            self.push_screen(BackendRequiredDialog())
            return

        # 异步获取智能体列表
        task = asyncio.create_task(self._show_agent_selection())
        self.background_tasks.add(task)
        task.add_done_callback(self._task_done_callback)

    def action_toggle_focus(self) -> None:
        """在命令输入框和文本区域之间切换焦点"""
        # 获取当前聚焦的组件
        focused = self.focused

        # 检查是否聚焦在输入组件（包括 MCP 组件）
        is_input_focused = isinstance(focused, CommandInput) or (
            focused is not None and hasattr(focused, "id") and focused.id in ["mcp-confirm", "mcp-parameter"]
        )

        if is_input_focused:
            # 如果当前聚焦在输入组件，则聚焦到输出容器
            output_container = self.query_one("#output-container", FocusableContainer)
            output_container.focus()
        else:
            # 否则聚焦到当前的输入组件
            self._focus_current_input_widget()

    def action_cancel(self) -> None:
        """取消当前正在进行的操作（命令执行或AI问答）"""
        if self.processing:
            self.logger.info("用户请求取消当前操作")

            # 取消当前所有的后台任务
            interrupted_count = 0
            for task in list(self.background_tasks):
                if not task.done():
                    task.cancel()
                    interrupted_count += 1
                    self.logger.debug("已取消后台任务")

            # 取消 LLM 客户端请求
            if self._llm_client is not None:
                # 异步调用取消方法
                cancel_task = asyncio.create_task(self._cancel_llm_request())
                self.background_tasks.add(cancel_task)
                cancel_task.add_done_callback(self._task_done_callback)

            if interrupted_count > 0:
                # 显示中断消息
                output_container = self.query_one("#output-container")
                interrupt_line = OutputLine(_("[Cancelled]"))
                output_container.mount(interrupt_line)
                # 异步滚动到底部
                scroll_task = asyncio.create_task(self._scroll_to_end())
                self.background_tasks.add(scroll_task)
                scroll_task.add_done_callback(self._task_done_callback)
            return

        # 如果没有正在进行的操作，尝试调用当前焦点组件的复制功能
        focused_widget = self.focused
        if focused_widget and hasattr(focused_widget, "action_copy"):
            try:
                # 显式转换为 Any 以绕过类型检查，因为我们已经检查了 hasattr
                cast("Any", focused_widget).action_copy()
            except Exception:
                self.logger.exception("执行复制操作失败")
        else:
            self.logger.debug("当前没有正在进行的操作可以取消，且当前组件不支持复制")

    def on_mount(self) -> None:
        """初始化完成时设置焦点和绑定"""
        # 确保初始状态是正常模式
        self._mcp_mode = "normal"

        # 清理任何可能的重复组件
        try:
            # 移除任何可能的重复ID组件
            existing_widgets = self.query("#command-input")
            if len(existing_widgets) > 1:
                # 如果有多个相同ID的组件，移除多余的
                for widget in existing_widgets[1:]:
                    widget.remove()
        except Exception:
            # 忽略清理过程中的异常
            self.logger.exception("清理重复组件失败")

        self._focus_current_input_widget()

        # 初始化默认智能体
        self._initialize_default_agent()

    def get_llm_client(self) -> LLMClientBase:
        """获取大模型客户端，使用单例模式维持对话历史"""
        if self._llm_client is None:
            self._llm_client = BackendFactory.create_client(self.config_manager)

            # 初始化时设置智能体状态
            if (self.current_agent and self.current_agent[0] and
                isinstance(self._llm_client, HermesChatClient)):
                self._llm_client.set_current_agent(self.current_agent[0])

        # 为 Hermes 客户端设置 MCP 事件处理器以支持 MCP 交互
        if isinstance(self._llm_client, HermesChatClient):
            mcp_handler = TUIMCPEventHandler(self, self._llm_client)
            self._llm_client.set_mcp_handler(mcp_handler)

            # 确保智能体状态同步
            if self.current_agent and self.current_agent[0]:
                current_client_agent = getattr(self._llm_client, "current_agent_id", "")
                if current_client_agent != self.current_agent[0]:
                    self._llm_client.set_current_agent(self.current_agent[0])

        return self._llm_client

    def refresh_llm_client(self) -> None:
        """重新创建 LLM 客户端实例，用于后端/URL/API Key/模型 变更后刷新连接"""
        # 保存当前智能体状态以便恢复
        current_agent_id = self.current_agent[0] if self.current_agent else ""

        # 保存 OpenAI 客户端的对话历史
        conversation_history = None
        if isinstance(self._llm_client, OpenAIClient):
            conversation_history = self._llm_client.conversation_history

        self._llm_client = BackendFactory.create_client(self.config_manager)

        # 恢复 OpenAI 客户端的对话历史
        if conversation_history is not None and isinstance(self._llm_client, OpenAIClient):
            self._llm_client.conversation_history = conversation_history

        # 恢复智能体状态到新的客户端
        if current_agent_id and isinstance(self._llm_client, HermesChatClient):
            self._llm_client.set_current_agent(current_agent_id)

        # 为 Hermes 客户端设置 MCP 事件处理器并加载用户信息
        if isinstance(self._llm_client, HermesChatClient):
            mcp_handler = TUIMCPEventHandler(self, self._llm_client)
            self._llm_client.set_mcp_handler(mcp_handler)

            # 创建异步任务加载用户信息并同步 personalToken
            task = asyncio.create_task(self._ensure_hermes_user_info())
            self.background_tasks.add(task)
            task.add_done_callback(self.background_tasks.discard)

    def exit(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        """退出应用前取消所有后台任务"""
        # 取消所有正在运行的后台任务
        for task in self.background_tasks:
            if not task.done():
                task.cancel()

        # 清理 LLM 客户端连接
        if self._llm_client is not None:
            # 创建清理任务并在当前事件循环中执行
            cleanup_task = asyncio.create_task(self._cleanup_llm_client())
            self.background_tasks.add(cleanup_task)
            cleanup_task.add_done_callback(self._cleanup_task_done_callback)

        # 调用父类的exit方法
        super().exit(*args, **kwargs)

    @on(Input.Submitted, "#command-input")
    def handle_input(self, event: Input.Submitted) -> None:
        """处理命令输入"""
        if not self._is_in_main_interface():
            return

        user_input = event.value.strip()
        if not user_input or self.processing:
            return

        # 清空输入框
        input_widget = self.query_one(CommandInput)
        input_widget.value = ""

        # 显示命令
        output_container = self.query_one("#output-container")
        output_container.mount(OutputLine(f"> {user_input}", command=True))

        # 滚动到输出容器的底部
        output_container.scroll_end(animate=False)

        # 异步处理命令
        self.processing = True
        # 创建任务并保存到类属性中的任务集合
        task = asyncio.create_task(self._process_command(user_input))
        self.background_tasks.add(task)
        # 添加完成回调，自动从集合中移除
        task.add_done_callback(self._task_done_callback)

    @on(SwitchToMCPConfirm)
    def handle_switch_to_mcp_confirm(self, message: SwitchToMCPConfirm) -> None:
        """处理切换到 MCP 确认界面的消息"""
        self._mcp_mode = "confirm"
        self._replace_input_with_mcp_widget(MCPConfirmWidget(message.event, widget_id="mcp-confirm"))

    @on(SwitchToMCPParameter)
    def handle_switch_to_mcp_parameter(self, message: SwitchToMCPParameter) -> None:
        """处理切换到 MCP 参数输入界面的消息"""
        self._mcp_mode = "parameter"
        self._replace_input_with_mcp_widget(MCPParameterWidget(message.event, widget_id="mcp-parameter"))

    @on(MCPConfirmResult)
    def handle_mcp_confirm_result(self, message: MCPConfirmResult) -> None:
        """处理 MCP 确认结果"""
        if not self._is_conversation_ready(message.conversation_id) or self.processing:
            return

        self.processing = True  # 设置处理标志，防止重复处理
        # 立即恢复正常输入界面
        self._remove_waiting_block()
        self._restore_normal_input()
        # 发送 MCP 响应并处理结果
        params = {"confirm": message.confirmed}
        task = asyncio.create_task(self._send_mcp_response(params=params))
        self.background_tasks.add(task)
        task.add_done_callback(self._task_done_callback)

    @on(MCPParameterResult)
    def handle_mcp_parameter_result(self, message: MCPParameterResult) -> None:
        """处理 MCP 参数结果"""
        if not self._is_conversation_ready(message.conversation_id) or self.processing:
            return

        self.processing = True  # 设置处理标志，防止重复处理
        # 立即恢复正常输入界面
        self._remove_waiting_block()
        self._restore_normal_input()
        # 发送 MCP 响应并处理结果
        params = message.params if message.params is not None else {}
        task = asyncio.create_task(self._send_mcp_response(params=params))
        self.background_tasks.add(task)
        task.add_done_callback(self._task_done_callback)

    def _is_in_main_interface(self) -> bool:
        """检查是否在主界面（没有其他屏幕弹出）"""
        # 检查是否有活动的屏幕栈，除了主屏幕外没有其他屏幕
        return len(self.screen_stack) <= 1

    def _is_exit_dialog_open(self) -> bool:
        """检查是否已经打开了退出对话框"""
        # 检查当前活动屏幕是否是退出对话框
        current_screen = self.screen
        return hasattr(current_screen, "__class__") and current_screen.__class__.__name__ == "ExitDialog"

    def _task_done_callback(self, task: asyncio.Task) -> None:
        """任务完成回调，从任务集合中移除"""
        if task in self.background_tasks:
            self.background_tasks.remove(task)
        # 捕获任务中的异常，防止未处理异常
        try:
            task.result()
        except asyncio.CancelledError:
            # 任务被取消是正常情况，不需要记录错误
            pass
        except Exception as e:
            # 记录错误日志
            self.logger.exception("Task execution error occurred")
            # 尝试在前端显示错误信息
            self._display_error_in_ui(e)
        finally:
            # 确保处理标志被重置
            self.processing = False

    async def _cancel_llm_request(self) -> None:
        """异步取消 LLM 请求"""
        try:
            if self._llm_client is not None:
                await self._llm_client.interrupt()
                self.logger.info("LLM 请求已取消")
        except Exception:
            self.logger.exception("取消 LLM 请求时出错")

    async def _process_command(self, user_input: str) -> None:
        """异步处理命令"""
        try:
            output_container = self.query_one("#output-container", Container)
            received_any_content = await self._handle_command_stream(user_input, output_container)

            # 如果没有收到任何内容且应用仍在运行，显示错误信息
            if not received_any_content and hasattr(self, "is_running") and self.is_running:
                output_container.mount(
                    OutputLine(
                        _("No response received, please check network connection or try again later"),
                        command=False,
                    ),
                )

        except asyncio.CancelledError:
            # 任务被取消，通常是因为应用退出
            self.logger.info("Command processing cancelled")
        except Exception as e:
            # 记录错误日志
            self.logger.exception("Command processing error occurred")
            # 添加异常处理，显示错误信息
            try:
                output_container = self.query_one("#output-container", Container)
                error_msg = self._format_error_message(e)
                # 检查应用是否已经开始退出
                if hasattr(self, "is_running") and self.is_running:
                    output_container.mount(OutputLine(format_error_message(error_msg), command=False))
            except (AttributeError, ValueError, RuntimeError):
                # 如果UI组件已不可用，只记录错误日志
                self.logger.exception("Failed to display error message")
        finally:
            # 重新聚焦到输入框（如果应用仍在运行）
            try:
                if hasattr(self, "is_running") and self.is_running:
                    self._focus_current_input_widget()
            except (AttributeError, ValueError, RuntimeError):
                # 应用可能正在退出，忽略聚焦错误
                self.logger.debug("[TUI] Failed to focus input widget, app may be exiting")
            # 注意：不在这里重置processing标志，由回调函数处理

    async def _handle_command_stream(self, user_input: str, output_container: Container) -> bool:
        """处理命令流式响应"""
        # 在新的命令会话开始时重置MCP状态跟踪
        if self._llm_client and isinstance(self._llm_client, HermesChatClient):
            self._llm_client.stream_processor.reset_status_tracking()

        # 新的命令意味着新的进度块序列
        self._mcp_cluster_active = False
        self._current_progress_block = None
        self._mcp_step_blocks.clear()

        stream_state = self._init_stream_state()

        try:
            received_any_content = await self._process_stream(
                user_input,
                output_container,
                stream_state,
            )
        except TimeoutError:
            received_any_content = self._handle_timeout_error(output_container, stream_state)
        except asyncio.CancelledError:
            received_any_content = self._handle_cancelled_error(output_container, stream_state)

        return received_any_content

    def _init_stream_state(self) -> dict:
        """初始化流处理状态"""
        start_time = asyncio.get_event_loop().time()
        return {
            "current_line": None,
            "current_content": "",
            "is_first_content": True,
            "received_any_content": False,
            "start_time": start_time,
            "timeout_seconds": None,  # 无总体超时限制，支持超长时间任务
            "last_content_time": start_time,
            "no_content_timeout": 1800.0,  # 30分钟无内容超时
        }

    async def _process_stream(
        self,
        user_input: str,
        output_container: Container,
        stream_state: dict,
    ) -> bool:
        """处理命令输出流"""
        async for output_tuple in process_command(user_input, self.get_llm_client()):
            content, is_llm_output = output_tuple
            stream_state["received_any_content"] = True
            current_time = asyncio.get_event_loop().time()

            # 更新最后收到内容的时间
            if content.strip():
                stream_state["last_content_time"] = current_time

            # 检查超时
            if self._check_timeouts(current_time, stream_state, output_container):
                break

            # 处理内容
            await self._process_stream_content(
                content,
                stream_state,
                output_container,
                is_llm_output=is_llm_output,
            )

            # 滚动到底部
            await self._scroll_to_end()

        return stream_state["received_any_content"]

    def _check_timeouts(
        self,
        current_time: float,
        stream_state: dict,
        output_container: Container,
    ) -> bool:
        """检查各种超时条件，返回是否应该中断处理"""
        timeout_seconds = stream_state["timeout_seconds"]
        if timeout_seconds is not None and current_time - stream_state["start_time"] > timeout_seconds:
            output_container.mount(OutputLine(_("Request timeout, processing stopped"), command=False))
            return True

        # 检查无内容超时
        received_any_content = stream_state["received_any_content"]
        time_since_last_content = current_time - stream_state["last_content_time"]
        if received_any_content and time_since_last_content > stream_state["no_content_timeout"]:
            output_container.mount(OutputLine(_("No response for a long time, processing stopped"), command=False))
            return True

        return False

    async def _process_stream_content(
        self,
        content: str,
        stream_state: dict,
        output_container: Container,
        *,
        is_llm_output: bool,
    ) -> None:
        """处理流式内容"""
        params = ContentChunkParams(
            content=content,
            is_llm_output=is_llm_output,
            current_content=stream_state["current_content"],
            is_first_content=stream_state["is_first_content"],
        )

        is_llm_stats_chunk = content.startswith(LLM_STATS_PREFIX)

        processed_line = await self._process_content_chunk(
            params,
            stream_state["current_line"],
            output_container,
        )

        # 检查是否是 MCP 消息处理（返回值为 None 表示是 MCP 消息）
        tag_info, _cleaned_content = extract_mcp_tag(content)
        is_mcp_detected = processed_line is None and tag_info is not None

        # 只有当返回值不为None时才更新current_line
        if processed_line is not None:
            stream_state["current_line"] = processed_line

        if processed_line is not None and not is_mcp_detected:
            # 任意非 MCP 输出都会结束当前进度块序列
            self._mcp_cluster_active = False
            self._current_progress_block = None

        # 更新状态 - 但是不要让 MCP 消息影响流状态
        if is_llm_stats_chunk:
            stream_state["is_first_content"] = False
            current_line_widget = stream_state.get("current_line")
            if isinstance(current_line_widget, MarkdownOutput):
                stream_state["current_content"] = current_line_widget.get_content()
            return

        if not is_mcp_detected:
            if stream_state["is_first_content"]:
                stream_state["is_first_content"] = False
                # 第一次内容直接设置为当前内容，不需要累积
                if is_llm_output:
                    stream_state["current_content"] = content
                else:
                    # 非LLM输出，重置累积内容
                    stream_state["current_content"] = ""
            elif isinstance(stream_state["current_line"], MarkdownOutput) and is_llm_output:
                # 只有在LLM输出且有有效的 MarkdownOutput 时才累积
                stream_state["current_content"] += content

    def _handle_timeout_error(self, output_container: Container, stream_state: dict) -> bool:
        """处理超时错误"""
        self.logger.warning("Command stream timed out")
        if hasattr(self, "is_running") and self.is_running:
            output_container.mount(OutputLine(_("Request timeout, please try again later"), command=False))
        return stream_state["received_any_content"]

    def _handle_cancelled_error(self, output_container: Container, stream_state: dict) -> bool:
        """处理取消错误"""
        self.logger.info("Command stream was cancelled")
        return stream_state["received_any_content"]

    async def _process_content_chunk(
        self,
        params: ContentChunkParams,
        current_line: OutputLine | MarkdownOutput | None,
        output_container: Container,
    ) -> OutputLine | MarkdownOutput | None:
        """处理单个内容块"""
        content = params.content
        is_llm_output = params.is_llm_output
        current_content = params.current_content
        is_first_content = params.is_first_content

        # 处理 LLM 输出的统计段落
        if is_llm_output and content.startswith(LLM_STATS_PREFIX):
            stats_payload = content[len(LLM_STATS_PREFIX) :].strip()
            return self._append_llm_stats_block(stats_payload, current_line, output_container)

        # 检查是否包含MCP标记（替换标记或MCP标记）
        tag_info, cleaned_content = extract_mcp_tag(content)
        replace_tag_info: MCPTagInfo | None = None
        mcp_tag_info: MCPTagInfo | None = None

        # 根据原始内容判断标记类型
        if tag_info:
            if MCPTags.REPLACE_PREFIX in content:
                replace_tag_info = tag_info
            elif MCPTags.MCP_PREFIX in content:
                mcp_tag_info = tag_info

        # 检查是否为 MCP 进度消息
        step_tag = replace_tag_info or mcp_tag_info
        is_progress_message = step_tag is not None and is_mcp_message(content)

        # 如果是进度消息，使用专门的处理方法，无论 is_llm_output 的值
        if is_progress_message and step_tag:
            self._handle_mcp_progress_message(
                cleaned_content,
                step_tag,
                output_container,
            )
            return None

        # 使用清理后的内容进行后续处理
        content = cleaned_content

        self.logger.debug("[TUI] 处理内容: %s", content.strip()[:50])

        # 处理第一段内容，创建适当的输出组件
        if is_first_content:
            new_line: OutputLine | MarkdownOutput = (
                MarkdownOutput(content) if is_llm_output else OutputLine(content)
            )
            output_container.mount(new_line)
            return new_line

        # 处理后续内容
        if is_llm_output and isinstance(current_line, MarkdownOutput):
            # 继续累积LLM富文本内容
            # 注意：current_content 已经包含了之前的所有内容，包括第一次的内容
            updated_content = current_content + content
            current_line.update_markdown(updated_content)
            return current_line

        if not is_llm_output and isinstance(current_line, OutputLine):
            # 继续累积命令输出纯文本
            current_text = current_line.get_content()
            current_line.update(current_text + content)
            return current_line

        # 输出类型发生变化，创建新的输出组件
        # 对于输出类型变化，如果是LLM输出，应该包含累积的内容；否则只包含当前内容
        if is_llm_output:
            # 如果切换到LLM输出，使用累积的内容（如果有的话）
            content_to_display = current_content + content if current_content else content
            new_line = MarkdownOutput(content_to_display)
        else:
            # 如果切换到非LLM输出，只使用当前内容
            new_line = OutputLine(content)
        output_container.mount(new_line)
        return new_line

    def _append_llm_stats_block(
        self,
        stats_payload: str,
        current_line: OutputLine | MarkdownOutput | None,
        output_container: Container,
    ) -> OutputLine | MarkdownOutput | None:
        """在 Markdown 输出末尾添加 LLM 统计段落"""
        if not stats_payload:
            return current_line

        stats_paragraph = f"\n\n> {stats_payload}"

        if isinstance(current_line, MarkdownOutput):
            updated = current_line.get_content() + stats_paragraph
            current_line.update_markdown(updated)
            return current_line

        # 没有现有 Markdown 输出时，创建新的 Markdown 块
        new_line = MarkdownOutput(f"> {stats_payload}")
        output_container.mount(new_line)
        return new_line

    def _handle_mcp_progress_message(
        self,
        content: str,
        step_tag: MCPTagInfo,
        output_container: Container,
    ) -> None:
        """处理 MCP 进度消息"""
        progress_block = self._get_or_create_progress_block(step_tag.identifier, output_container)
        waiting_state = self._detect_waiting_state(content)
        if waiting_state:
            self._show_waiting_block(content, output_container)
            return

        progress_block.upsert_step(step_tag.identifier, content)
        self.logger.debug("[TUI] 更新工具 %s 的进度: %s", step_tag.display_name, content.strip()[:50])

    def _get_or_create_progress_block(self, step_id: str, output_container: Container) -> MCPProgressBlock:
        """按步骤 ID 查找或创建 MCP 进度块"""
        existing_block = self._mcp_step_blocks.get(step_id)
        if existing_block is not None and getattr(existing_block, "is_attached", True):
            return existing_block

        if existing_block is not None:
            # 映射已失效，清理引用
            self._mcp_step_blocks.pop(step_id, None)

        block: MCPProgressBlock
        if (
            self._mcp_cluster_active
            and self._current_progress_block is not None
            and getattr(self._current_progress_block, "is_attached", True)
        ):
            block = self._current_progress_block
        else:
            block = MCPProgressBlock()
            output_container.mount(block)
            self._current_progress_block = block
            self._mcp_cluster_active = True

        self._mcp_step_blocks[step_id] = block
        return block

    def _detect_waiting_state(self, content: str) -> str | None:
        """检测当前内容是否处于等待确认/参数状态"""
        if MCPEmojis.WAITING_PARAM in content:
            return "param"
        if MCPEmojis.WAITING_START in content:
            return "confirm"
        return None

    def _show_waiting_block(self, content: str, output_container: Container) -> None:
        """展示等待状态提示块"""
        if self._current_waiting_block is None or not getattr(self._current_waiting_block, "is_attached", True):
            waiting_block = MCPWaitingBlock(content)
            self._current_waiting_block = waiting_block
            output_container.mount(waiting_block)
        else:
            self._current_waiting_block.update_markdown(content)

    def _remove_waiting_block(self) -> None:
        """移除等待状态提示块"""
        if self._current_waiting_block is None:
            return
        try:
            if getattr(self._current_waiting_block, "parent", None) is not None:
                self._current_waiting_block.remove()
        except (AttributeError, RuntimeError, ValueError):
            self.logger.debug("[TUI] 移除等待块时出现异常", exc_info=True)
        finally:
            self._current_waiting_block = None

    def _reset_mcp_state(self) -> None:
        """重置 MCP 进度展示状态"""
        self._mcp_cluster_active = False
        self._current_progress_block = None
        self._mcp_step_blocks.clear()
        self._remove_waiting_block()

    def _get_current_conversation_id(self) -> str:
        """从 LLM 客户端获取当前会话 ID"""
        llm_client = self._llm_client
        if llm_client is None:
            return ""

        try:
            manager = getattr(llm_client, "conversation_manager", None)
            if manager is None:
                return ""
            return manager.get_conversation_id()
        except (AttributeError, RuntimeError, ValueError):
            self.logger.debug("获取会话 ID 失败", exc_info=True)
            return ""

    def _is_conversation_ready(self, message_id: str) -> bool:
        """确认当前会话 ID 已就绪且与消息一致"""
        current_id = self._get_current_conversation_id()
        if not current_id:
            self.logger.warning("忽略 MCP 事件：当前会话尚未建立")
            return False

        if message_id and message_id != current_id:
            self.logger.info(
                "忽略 MCP 事件：会话 ID 不匹配 (%s != %s)",
                message_id,
                current_id,
            )
            return False

        return True

    def _format_error_message(self, error: BaseException) -> str:
        """格式化错误消息"""
        error_str = str(error).lower()
        error_type = type(error).__name__.lower()

        # 处理 HermesAPIError 特殊情况
        if hasattr(error, "status_code") and hasattr(error, "message"):
            if error.status_code == 500:  # type: ignore[attr-defined]  # noqa: PLR2004
                return _("Server error: {message}").format(message=error.message)  # type: ignore[attr-defined]
            if error.status_code >= 400:  # type: ignore[attr-defined]  # noqa: PLR2004
                return _("Request failed: {message}").format(message=error.message)  # type: ignore[attr-defined]

        # 定义错误匹配规则和对应的用户友好消息
        error_patterns = {
            _("Network connection interrupted, please check network and try again"): [
                "remoteprotocolerror",
                "server disconnected",
                "peer closed connection",
                "connection reset",
                "connection refused",
                "broken pipe",
            ],
            _("Request timeout, please try again later"): [
                "timeout",
                "timed out",
            ],
            _("Network connection error, please check network and try again"): [
                "network",
                "connection",
                "unreachable",
                "resolve",
                "dns",
                "httperror",
                "requestserror",
            ],
            _("Server response error, please try again later"): [
                "http",
                "status",
                "response",
            ],
            _("Data format error, please try again later"): [
                "json",
                "decode",
                "parse",
                "invalid",
                "malformed",
            ],
            _("Authentication failed, please check configuration"): [
                "auth",
                "unauthorized",
                "forbidden",
                "token",
            ],
        }

        # 检查错误字符串匹配
        for message, patterns in error_patterns.items():
            if any(pattern in error_str for pattern in patterns):
                return message

        # 检查错误类型匹配（用于服务端响应异常）
        if any(
            keyword in error_type
            for keyword in [
                "httperror",
                "httpstatuserror",
                "requesterror",
            ]
        ):
            return _("Server response error, please try again later")

        return _("Error processing command: {error}").format(error=str(error))

    def _display_error_in_ui(self, error: BaseException) -> None:
        """在UI界面显示错误信息"""
        try:
            # 检查应用是否仍在运行
            if not (hasattr(self, "is_running") and self.is_running):
                return

            # 获取输出容器
            output_container = self.query_one("#output-container", Container)

            # 格式化错误消息
            error_msg = self._format_error_message(error)

            # 显示错误信息
            output_container.mount(OutputLine(f"❌ {error_msg}", command=False))

            # 滚动到底部以确保用户看到错误信息
            self.call_after_refresh(lambda: output_container.scroll_end(animate=False))

        except Exception:
            # 如果UI显示失败，至少记录错误日志
            self.logger.exception("无法在UI中显示错误信息")

    def _focus_current_input_widget(self) -> None:
        """聚焦到当前的输入组件，考虑 MCP 模式状态"""
        try:
            if self._mcp_mode == "normal":
                # 正常模式，聚焦到 CommandInput
                self.query_one(CommandInput).focus()
            elif self._mcp_mode == "confirm":
                # MCP 确认模式，聚焦到 MCP 确认组件
                try:
                    mcp_widget = self.query_one("#mcp-confirm")
                    mcp_widget.focus()
                except (AttributeError, ValueError, RuntimeError):
                    # 如果MCP组件不存在，回退到正常模式
                    self._mcp_mode = "normal"
                    self.query_one(CommandInput).focus()
            elif self._mcp_mode == "parameter":
                # MCP 参数模式，聚焦到 MCP 参数组件
                try:
                    mcp_widget = self.query_one("#mcp-parameter")
                    mcp_widget.focus()
                except (AttributeError, ValueError, RuntimeError):
                    # 如果MCP组件不存在，回退到正常模式
                    self._mcp_mode = "normal"
                    self.query_one(CommandInput).focus()
            else:
                # 未知模式，重置为正常模式并聚焦到 CommandInput
                self.logger.warning("未知的 MCP 模式: %s，重置为正常模式", self._mcp_mode)
                self._mcp_mode = "normal"
                self.query_one(CommandInput).focus()
        except (AttributeError, ValueError, RuntimeError) as e:
            # 聚焦失败时记录调试信息，但不抛出异常
            self.logger.debug("[TUI] Failed to focus input widget: %s", str(e))

    async def _scroll_to_end(self) -> None:
        """滚动到容器底部的辅助方法"""
        # 获取输出容器
        output_container = self.query_one("#output-container")
        # 使用同步方法滚动，确保UI更新
        output_container.scroll_end(animate=False)
        # 等待一个小的延迟，确保UI有时间更新
        await asyncio.sleep(0.01)

    async def _ensure_hermes_user_info(self) -> None:
        """确保 Hermes 用户信息已加载并同步 personalToken 到配置"""
        if not isinstance(self._llm_client, HermesChatClient):
            return

        try:
            # 加载用户信息
            success = await self._llm_client.ensure_user_info_loaded()
            if not success:
                self.logger.warning("加载用户信息失败")
                return

            # 获取 personalToken
            personal_token = self._llm_client.get_personal_token()
            if not personal_token:
                self.logger.info("服务器未返回 personalToken，跳过同步")
                return

            # 获取当前配置中的 personalToken
            current_token = self.config_manager.get_eulerintelli_key()

            # 如果 personalToken 不一致，更新配置
            if personal_token != current_token:
                self.logger.info("检测到 personalToken 变更，正在同步到配置...")
                self.config_manager.set_eulerintelli_key(personal_token)
                self.logger.info("PersonalToken 已同步到配置文件")
            else:
                self.logger.info("PersonalToken 与配置一致，无需同步")

        except (OSError, ValueError, RuntimeError) as e:
            log_exception(self.logger, "加载用户信息或同步 personalToken 时发生错误", e)

    async def _cleanup_llm_client(self) -> None:
        """异步清理 LLM 客户端"""
        if self._llm_client is not None:
            try:
                await self._llm_client.close()
                self.logger.info("LLM 客户端已安全关闭")
            except (OSError, RuntimeError, ValueError, HermesAPIError) as e:
                log_exception(self.logger, "关闭 LLM 客户端时出错", e)

    def _cleanup_task_done_callback(self, task: asyncio.Task) -> None:
        """清理任务完成回调"""
        if task in self.background_tasks:
            self.background_tasks.remove(task)
        try:
            task.result()
        except asyncio.CancelledError:
            pass
        except (OSError, ValueError, RuntimeError):
            self.logger.exception("LLM client cleanup error")

    async def _show_agent_selection(self) -> None:
        """显示智能体选择对话框"""
        try:
            llm_client = self.get_llm_client()

            # 构建智能体列表 - 默认第一项为"智能问答"（无智能体）
            agent_list = [("", _("智能问答"))]

            # 尝试获取可用智能体
            if hasattr(llm_client, "get_available_agents"):
                try:
                    available_agents = await llm_client.get_available_agents()  # type: ignore[attr-defined]
                    # 添加获取到的智能体
                    agent_list.extend(
                        [
                            (agent.app_id, agent.name)
                            for agent in available_agents
                            if hasattr(agent, "app_id") and hasattr(agent, "name")
                        ],
                    )
                except (AttributeError, OSError, ValueError, RuntimeError) as e:
                    self.logger.warning("获取智能体列表失败，使用默认选项: %s", str(e))
                    # 继续使用默认的智能问答选项
            else:
                self.logger.info("当前客户端不支持智能体功能，显示默认选项")

            # 使用当前智能体状态，不重新读取配置
            await self._display_agent_dialog(agent_list, llm_client)

        except (OSError, ValueError, RuntimeError) as e:
            log_exception(self.logger, "显示智能体选择对话框失败", e)
            # 即使出错也显示默认选项
            agent_list = [("", _("智能问答"))]
            try:
                llm_client = self.get_llm_client()
                await self._display_agent_dialog(agent_list, llm_client)
            except (OSError, ValueError, RuntimeError, AttributeError):
                self.logger.exception("无法显示智能体选择对话框")

    async def _display_agent_dialog(
        self,
        agent_list: list[tuple[str, str]],
        llm_client: LLMClientBase,
    ) -> None:
        """显示智能体选择对话框"""

        def on_agent_selected(selected_agent: tuple[str, str]) -> None:
            """智能体选择回调"""
            self.current_agent = selected_agent
            app_id, _name = selected_agent

            # 设置智能体到客户端
            if isinstance(llm_client, HermesChatClient):
                llm_client.set_current_agent(app_id)

        dialog = AgentSelectionDialog(agent_list, on_agent_selected, self.current_agent)
        self.push_screen(dialog)

    def _replace_input_with_mcp_widget(self, widget) -> None:  # noqa: ANN001
        """替换输入容器中的组件为 MCP 交互组件"""
        try:
            input_container = self.query_one("#input-container")

            # 切换到 MCP 模式样式
            input_container.remove_class("normal-mode")
            input_container.add_class("mcp-mode")

            # 移除所有子组件
            input_container.remove_children()

            # 添加新的 MCP 组件
            input_container.mount(widget)

            # 延迟聚焦，确保组件完全挂载
            self.set_timer(0.05, lambda: widget.focus())

        except Exception:
            self.logger.exception("替换输入组件失败")
            # 如果替换失败，尝试恢复正常输入
            try:
                self._restore_normal_input()
            except Exception:
                self.logger.exception("恢复正常输入失败")

    def _restore_normal_input(self) -> None:
        """恢复正常的命令输入组件"""
        try:
            input_container = self.query_one("#input-container")

            # 重置 MCP 状态
            self._mcp_mode = "normal"

            # 切换回正常模式样式
            input_container.remove_class("mcp-mode")
            input_container.add_class("normal-mode")

            # 移除所有子组件
            input_container.remove_children()

            # 添加正常的命令输入组件
            command_input = CommandInput()
            input_container.mount(command_input)

            # 聚焦到输入框
            self._focus_current_input_widget()

        except Exception:
            self.logger.exception("恢复正常输入组件失败")
            # 如果恢复失败，至少要重置状态
            self._mcp_mode = "normal"

    async def _send_mcp_response(self, *, params: dict[str, Any]) -> None:
        """发送 MCP 响应并处理结果"""
        output_container: Container | None = None

        try:
            # 先获取输出容器，确保可以显示错误信息
            output_container = self.query_one("#output-container", Container)

            # 发送 MCP 响应并处理流式回复
            llm_client = self.get_llm_client()
            if hasattr(llm_client, "send_mcp_response"):
                success = await self._handle_mcp_response_stream(
                    params=params,
                    output_container=output_container,
                    llm_client=llm_client,
                )
                if not success:
                    # 如果没有收到任何响应内容，显示默认消息
                    output_container.mount(OutputLine(_("💡 MCP response sent")))
            else:
                self.logger.error("当前客户端不支持 MCP 响应功能")
                output_container.mount(OutputLine(_("❌ Current client does not support MCP response")))

        except Exception as e:
            self.logger.exception("发送 MCP 响应失败")
            # 显示错误信息
            if output_container is not None:
                try:
                    error_message = self._format_error_message(e)
                    output_container.mount(
                        OutputLine(_("❌ Failed to send MCP response: {error}").format(error=error_message)),
                    )
                except Exception:
                    # 如果连显示错误信息都失败了，至少记录日志
                    self.logger.exception("无法显示错误信息")
        finally:
            # 重置处理标志，不再在这里恢复输入界面
            self.processing = False

    async def _handle_mcp_response_stream(
        self,
        *,
        params: dict[str, Any],
        output_container: Container,
        llm_client: LLMClientBase,
    ) -> bool:
        """处理 MCP 响应的流式回复"""
        if not isinstance(llm_client, HermesChatClient):
            self.logger.error("当前客户端不支持 MCP 响应功能")
            output_container.mount(OutputLine(_("❌ Current client does not support MCP response")))
            return False

        # 使用统一的流状态管理，与 _handle_command_stream 保持一致
        stream_state = self._init_stream_state()

        try:
            async for content in llm_client.send_mcp_response(params=params):
                if not content.strip():
                    continue

                stream_state["received_any_content"] = True
                current_time = asyncio.get_event_loop().time()

                # 更新最后收到内容的时间
                if content.strip():
                    stream_state["last_content_time"] = current_time

                # 检查超时
                if self._check_timeouts(current_time, stream_state, output_container):
                    break

                # 判断是否为 LLM 输出内容
                tag_info, _cleaned_content = extract_mcp_tag(content)
                is_llm_output = tag_info is None

                # 处理内容
                await self._process_stream_content(
                    content,
                    stream_state,
                    output_container,
                    is_llm_output=is_llm_output,
                )

                # 滚动到底部
                await self._scroll_to_end()

            return stream_state["received_any_content"]
        except asyncio.CancelledError:
            output_container.mount(OutputLine(_("🚫 MCP response cancelled")))
            raise

    def _get_initial_agent(self) -> tuple[str, str]:
        """根据配置获取初始智能体，只在应用启动时调用"""
        default_app = self.config_manager.get_default_app()
        if default_app:
            # 如果配置了默认智能体，尝试获取对应的名称
            # 这里先返回 ID 和 ID 作为临时方案，后续在智能体列表加载后更新名称
            return (default_app, default_app)
        # 如果没有配置默认智能体，使用智能问答
        return ("", _("智能问答"))

    def _reinitialize_agent_state(self) -> None:
        """重新初始化智能体状态，用于后端切换时"""
        # 尝试异步更新智能体信息（如果新后端支持智能体功能）
        self._initialize_default_agent()

    def _initialize_default_agent(self) -> None:
        """初始化默认智能体，包含配置验证"""
        # 首先验证后端配置
        validation_task = asyncio.create_task(self._validate_and_setup_configuration())
        self.background_tasks.add(validation_task)
        validation_task.add_done_callback(self._task_done_callback)

    async def _validate_and_setup_configuration(self) -> None:
        """验证配置并设置智能体，如果配置无效则弹出设置页面"""
        try:
            # 获取当前后端配置
            backend = self.config_manager.get_backend()

            # 验证配置
            is_valid = await self._validate_backend_configuration(backend)

            if is_valid:
                # 配置验证通过，继续初始化智能体
                await self._setup_agent_after_validation()
            else:
                # 配置验证失败，显示通知并弹出设置页面
                self._show_config_validation_notification()
                await self._show_settings_for_config_fix()

        except Exception:
            self.logger.exception("配置验证过程中发生错误")
            # 即使验证出错，也弹出设置页面让用户手动配置
            self._show_config_validation_notification()
            await self._show_settings_for_config_fix()

    async def _validate_backend_configuration(self, backend: Backend) -> bool:
        """验证后端配置"""
        self.logger.info("开始验证后端配置: %s", backend)
        try:
            if backend == Backend.OPENAI:
                # 验证 OpenAI 配置
                validator = APIValidator()
                base_url = self.config_manager.get_base_url()
                api_key = self.config_manager.get_api_key()
                model = self.config_manager.get_model()
                valid, _, _ = await validator.validate_llm_config(
                    endpoint=base_url,
                    api_key=api_key,
                    model=model,
                    timeout=10,
                )
                self.logger.info("OpenAI 配置验证结果: %s", valid)
                return valid

            if backend == Backend.EULERINTELLI:
                # 验证 Hermes 配置
                llm_client = self.get_llm_client()
                if isinstance(llm_client, HermesChatClient):
                    # 检查当前 token 状态
                    current_token = self.config_manager.get_eulerintelli_key()
                    http_token = llm_client.http_manager.auth_token
                    self.logger.info(
                        "Hermes 验证前状态 - 配置 token 长度: %d, http_token 长度: %d",
                        len(current_token) if current_token else 0,
                        len(http_token) if http_token else 0,
                    )
                    result = await llm_client.ensure_user_info_loaded()
                    self.logger.info("Hermes 配置验证结果: %s", result)
                    return result
                self.logger.warning("LLM 客户端不是 HermesChatClient 类型")
                return False

        except Exception:
            self.logger.exception("验证后端配置时发生错误")
            return False

        else:
            self.logger.warning("未知的后端类型: %s", backend)
            return False

    def _show_config_validation_notification(self) -> None:
        """显示配置验证失败的通知"""
        self.notify(
            _("Backend configuration validation failed, please check and modify"),
            title=_("Configuration Error"),
            severity="error",
            timeout=1,
        )

    async def _show_settings_for_config_fix(self) -> None:
        """弹出设置页面让用户修改配置"""
        try:
            # 弹出设置页面
            settings_screen = SettingsScreen(self.config_manager, self.get_llm_client())
            self.push_screen(settings_screen)

            # 等待设置页面退出
            await self._wait_for_settings_screen_exit()

            # 设置页面退出后，同步客户端的 token 状态
            # 这是为了处理自动登录更新了配置但客户端状态不一致的情况
            await self._sync_client_token_state()

            # 重新验证配置
            backend = self.config_manager.get_backend()
            is_valid = await self._validate_backend_configuration(backend)

            if not is_valid:
                # 如果还是无效，递归调用自己再次弹出设置页面
                self._show_config_validation_notification()
                await self._show_settings_for_config_fix()
            else:
                # 配置验证通过，继续初始化智能体
                await self._setup_agent_after_validation()

        except Exception:
            self.logger.exception("显示设置页面时发生错误")

    async def _sync_client_token_state(self) -> None:
        """同步客户端的 token 状态与配置"""
        if not isinstance(self._llm_client, HermesChatClient):
            return

        config_token = self.config_manager.get_eulerintelli_key()
        client_token = self._llm_client.http_manager.auth_token

        if config_token != client_token:
            self.logger.info(
                "检测到 token 状态不一致，同步中... (配置: %d字符, 客户端: %d字符)",
                len(config_token) if config_token else 0,
                len(client_token) if client_token else 0,
            )
            # 更新客户端的 token
            self._llm_client.http_manager.auth_token = config_token
            # 重置 HTTP 客户端，使用新的 token
            if self._llm_client.http_manager.client is not None:
                self._llm_client.http_manager.client = None
            # 清除用户信息缓存，强制重新获取
            self._llm_client._user_info = None
            self.logger.info("客户端 token 状态已同步")

    async def _wait_for_settings_screen_exit(self) -> None:
        """等待设置页面退出"""
        # 使用事件来等待设置页面退出，而不是轮询
        exit_event = asyncio.Event()

        # 创建一个任务来监控屏幕栈变化
        async def monitor_screen_stack() -> None:
            current_stack_length = len(self.screen_stack)
            while current_stack_length > 1:
                await asyncio.sleep(0.05)  # 短暂等待后重新检查
                current_stack_length = len(self.screen_stack)
            exit_event.set()

        # 启动监控任务
        monitor_task = asyncio.create_task(monitor_screen_stack())

        # 等待退出事件
        try:
            await exit_event.wait()
        finally:
            # 取消监控任务
            if not monitor_task.done():
                monitor_task.cancel()

    async def _setup_agent_after_validation(self) -> None:
        """配置验证通过后设置智能体"""
        try:
            # 如果当前智能体是基于 default_app 配置的，且需要更新名称
            app_id, name = self.current_agent
            if app_id and app_id == name:  # 这表示我们在 _get_initial_agent 中使用了临时方案
                # 异步获取智能体信息并更新名称
                await self._update_agent_name_from_list()
        except Exception:
            self.logger.exception("设置智能体时发生错误")

    async def _update_agent_name_from_list(self) -> None:
        """从智能体列表中更新当前智能体的名称"""
        try:
            llm_client = self.get_llm_client()
            if hasattr(llm_client, "get_available_agents"):
                available_agents = await llm_client.get_available_agents()  # type: ignore[attr-defined]
                app_id, _name = self.current_agent

                # 查找匹配的智能体
                agent_found = False
                for agent in available_agents:
                    if hasattr(agent, "app_id") and hasattr(agent, "name") and agent.app_id == app_id:
                        # 更新智能体信息
                        self.current_agent = (agent.app_id, agent.name)
                        # 设置智能体到客户端
                        if hasattr(llm_client, "set_current_agent"):
                            llm_client.set_current_agent(app_id)  # type: ignore[attr-defined]
                        agent_found = True
                        break

                # 如果没有找到匹配的智能体，说明配置的默认智能体ID已无效
                if not agent_found and app_id:
                    self.logger.warning("配置的默认智能体 '%s' 不存在，回退到智能问答并清理配置", app_id)
                    # 回退到智能问答
                    self.current_agent = ("", _("智能问答"))
                    # 清理配置中的无效ID
                    self.config_manager.set_default_app("")
                    # 确保客户端也切换到智能问答
                    if hasattr(llm_client, "set_current_agent"):
                        llm_client.set_current_agent("")  # type: ignore[attr-defined]
        except (AttributeError, OSError, ValueError, RuntimeError) as e:
            self.logger.warning("无法更新智能体名称: %s", str(e))
