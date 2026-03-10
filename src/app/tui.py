"""基于 Textual 的 TUI 应用"""

from __future__ import annotations

import asyncio
import atexit
import contextlib
import shutil
import subprocess
import time
from typing import TYPE_CHECKING, Any, ClassVar, NamedTuple, cast

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Container
from textual.message import Message
from textual.widgets import Footer, Input, Markdown, Static

from __version__ import __version__
from app.dialogs import AgentSelectionDialog, BackendRequiredDialog, ExitDialog
from app.logo import WittyLogo
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
    from textual.timer import Timer
    from textual.visual import VisualType
    from textual.widget import Widget

    from backend import LLMClientBase


class ContentChunkParams(NamedTuple):
    """内容块处理参数"""

    content: str
    is_llm_output: bool
    current_content: str
    is_first_content: bool


class StreamUIFlushParams(NamedTuple):
    """流式输出 UI 刷新节流参数"""

    flush_interval: float
    flush_char_threshold: int
    scroll_interval: float


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

    # Textual Timer 不接受 0 秒 delay（会在定时器内部产生除零风险，且可能导致渲染永远不触发）。
    # 这里用一个非常小的正值来模拟“下一次事件循环/下一帧”再应用更新，从而合并高频流式更新。
    _RENDER_DEBOUNCE_DELAY_SECONDS: ClassVar[float] = 0.01

    # 自适应降频：根据“上一帧真实渲染耗时”动态调整去抖延迟。
    _RENDER_DEBOUNCE_MIN_SECONDS: ClassVar[float] = 0.01
    _RENDER_DEBOUNCE_MAX_SECONDS: ClassVar[float] = 0.5
    _RENDER_TIME_TO_DEBOUNCE_MULTIPLIER: ClassVar[float] = 2.0
    RENDER_TIME_EMA_ALPHA: ClassVar[float] = 0.2

    def __init__(self, markdown_content: str = "") -> None:
        """初始化 Markdown 输出组件"""
        super().__init__(markdown_content)
        self.current_content = markdown_content
        # 去抖渲染：在高频流式更新下合并渲染任务，避免 Markdown 解析/布局事件堆积
        self._pending_markdown: str | None = None
        self._render_timer: Timer | None = None
        # generation gating：用于屏蔽取消/退出后已排队的回调“余震”
        self._scheduled_generation: int | None = None
        # EMA 的平均渲染耗时（秒），以及下一次的去抖延迟（秒）
        self._render_time_ema_seconds: float | None = None
        self._adaptive_debounce_seconds: float = self._RENDER_DEBOUNCE_DELAY_SECONDS
        self.add_class("llm-output")
        self.can_focus = True

    def action_copy(self) -> None:
        """复制内容到剪贴板"""
        if self._copy_selected_text():
            return
        if self.current_content:
            self.app.copy_to_clipboard(self.current_content)

    def get_content(self) -> str:
        """获取当前 Markdown 原始内容"""
        return self.current_content

    def update_markdown(self, markdown_content: str) -> None:
        """更新 Markdown 内容"""
        self.current_content = markdown_content
        self._pending_markdown = markdown_content

        # 允许在未挂载到 App 的场景下（例如单元测试/构造阶段）直接应用，避免 set_timer 依赖消息循环。
        if self.app is None:
            self._apply_pending_markdown()
            return

        # 记录本次调度的 generation，用于后续回调执行时校验是否已被取消/退出
        self._scheduled_generation = self._get_app_render_generation()

        # 取消旧的未执行渲染，仅保留最新一次
        if self._render_timer is not None:
            try:
                self._render_timer.stop()
            except (AttributeError, RuntimeError):
                # Timer 偶发异常不应影响主流程
                if self.app is not None:
                    self.app.log("[TUI] Failed to stop markdown render timer")
                self._render_timer = None

        # 延迟到一个时间片后再更新（自适应），合并同一段时间内的多次更新
        delay = self._adaptive_debounce_seconds
        if delay <= 0:
            delay = self._RENDER_DEBOUNCE_MIN_SECONDS
        self._render_timer = self.set_timer(delay, self._apply_pending_markdown)

    def cancel_pending_render(self) -> None:
        """取消尚未执行的渲染（用于取消/退出时阻断后续 UI 更新）。"""
        self._pending_markdown = None
        self._scheduled_generation = None
        if self._render_timer is not None:
            try:
                self._render_timer.stop()
            except (AttributeError, RuntimeError):
                if self.app is not None:
                    self.app.log("[TUI] Failed to stop markdown render timer")
            finally:
                self._render_timer = None

    def _apply_pending_markdown(self) -> None:
        """将最新的 pending Markdown 应用到组件。"""
        try:
            if self._pending_markdown is None:
                return

            # generation gating：如果 App 已经进入新一代（取消/退出），则跳过渲染
            current_generation = self._get_app_render_generation()
            if (
                current_generation is not None
                and self._scheduled_generation is not None
                and current_generation != self._scheduled_generation
            ):
                return

            # 这里调用 update 会触发 Markdown 解析与布局，必须保证已经做过节流/去抖
            start = time.perf_counter()
            self.update(self._pending_markdown)
            duration = time.perf_counter() - start
            self._record_render_duration(duration)
        finally:
            self._pending_markdown = None
            self._render_timer = None
            self._scheduled_generation = None

    def _get_app_render_generation(self) -> int | None:
        """从 App 获取当前 render generation（若可用）。"""
        app = self.app
        if app is None:
            return None

        getter = getattr(app, "_get_render_generation", None)
        if callable(getter):
            try:
                return cast("int", getter())
            except (AttributeError, RuntimeError, ValueError, TypeError):
                return None

        # 兼容兜底：直接读取属性（不建议外部依赖）
        generation = getattr(app, "_render_generation", None)
        return cast("int | None", generation)

    def _record_render_duration(self, duration_seconds: float) -> None:
        """记录一次真实渲染耗时，并据此更新自适应去抖延迟。"""
        if duration_seconds <= 0:
            return

        if self._render_time_ema_seconds is None:
            ema = duration_seconds
        else:
            alpha = self.RENDER_TIME_EMA_ALPHA
            ema = (alpha * duration_seconds) + ((1 - alpha) * self._render_time_ema_seconds)
        self._render_time_ema_seconds = ema

        target_delay = self._RENDER_TIME_TO_DEBOUNCE_MULTIPLIER * ema
        # 夹逼范围，防止过度降低实时性或完全卡住
        self._adaptive_debounce_seconds = max(
            self._RENDER_DEBOUNCE_MIN_SECONDS,
            min(self._RENDER_DEBOUNCE_MAX_SECONDS, target_delay),
        )

        # 将渲染耗时上报给 App（用于流式 flush 的自适应降频）
        app = self.app
        reporter = getattr(app, "_report_markdown_render_duration", None) if app is not None else None
        if callable(reporter):
            try:
                reporter(duration_seconds)
            except (AttributeError, RuntimeError, ValueError, TypeError):
                # 上报失败不影响主流程
                return


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

    # 流式渲染节流参数：降低 Markdown 全量重渲染频率，避免大输出时阻塞事件循环
    STREAM_UI_FLUSH: ClassVar[StreamUIFlushParams] = StreamUIFlushParams(
        flush_interval=0.08,
        flush_char_threshold=4096,
        scroll_interval=0.12,
    )

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding(key="ctrl+q", action="request_quit", description=_("Quit")),
        Binding(key="ctrl+s", action="settings", description=_("Settings")),
        Binding(key="ctrl+r", action="reset_conversation", description=_("Reset")),
        Binding(key="ctrl+t", action="choose_agent", description=_("Agent")),
        Binding(key="ctrl+c", action="cancel", description=_("Cancel"), priority=True),
        Binding(key="ctrl+z", action="opencode", description=_("使用 OpenCode 智能体")),
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
        self.title = "Witty Assistant"
        self.sub_title = _("Intelligent CLI Assistant {version}").format(version=__version__)
        self.config_manager = ConfigManager()
        self.processing: bool = False
        # 添加保存任务的集合到类属性
        self.background_tasks: set[asyncio.Task] = set()
        # 创建日志实例
        self.logger = get_logger(__name__)
        # 创建并保持单一的 LLM 客户端实例以维持对话历史
        self._llm_client: LLMClientBase | None = None
        # 当前选择的智能体 - 根据配置的 default_app 初始化
        self.current_agent: tuple[str, str] = self._get_initial_agent()
        # MCP 状态
        self._mcp_mode: str = "normal"  # "normal", "confirm", "parameter"
        # MCP 进度展示状态
        self._current_progress_block: MCPProgressBlock | None = None
        self._current_waiting_block: MCPWaitingBlock | None = None
        self._mcp_cluster_active: bool = False
        self._mcp_step_blocks: dict[str, MCPProgressBlock] = {}
        # LOGO 显示状态
        self._has_conversation: bool = False
        # generation gating：取消/退出时 bump，用于屏蔽已经排队的 UI 更新回调（timer/call_after_refresh）
        self._render_generation: int = 0
        # 全局统计 Markdown 渲染耗时 EMA（用于动态调整 flush 频率）
        self._markdown_render_ema_seconds: float | None = None

    def compose(self) -> ComposeResult:
        """构建界面"""
        yield OIHeader()
        with FocusableContainer(id="output-container"):
            yield WittyLogo()
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
        # 重新显示 LOGO
        self._has_conversation = False
        # 确保不会重复挂载 LOGO
        with contextlib.suppress(Exception):
            logo = self.query_one("#witty-logo", WittyLogo)
            logo.remove()
        output_container.mount(WittyLogo())

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

    def action_opencode(self) -> None:
        """打开 OpenCode 编辑器，覆盖当前窗口"""
        # 只有在主界面（无其他屏幕）时才响应
        if not self._is_in_main_interface():
            return

        # 检查 opencode 命令是否存在
        opencode_path = shutil.which("opencode")
        if not opencode_path:
            # 如果找不到 opencode 命令，则无事发生
            self.logger.debug("OpenCode 未安装，命令未执行")
            return

        # 注册退出后要执行的函数
        def launch_opencode() -> None:
            """在 Python 进程退出后，在恢复的终端中启动 OpenCode"""
            with contextlib.suppress(OSError, subprocess.SubprocessError):
                # 使用 subprocess.run 在前台运行 OpenCode
                # 不使用 os.execvp，让 Python 正常退出以确保终端状态恢复
                # 使用完整路径以避免安全警告
                subprocess.run([opencode_path, "."], check=False)  # noqa: S603

        atexit.register(launch_opencode)

        # 退出 Textual 应用，这会恢复终端状态
        self.exit()

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

            # generation gating：先 bump，屏蔽已排队的回调
            self._bump_render_generation("cancel")

            # 先清理可能排队的 Markdown 渲染任务，避免 Ctrl+C 后仍持续刷新
            self._cancel_pending_output_renders()

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
            if self.current_agent and self.current_agent[0] and isinstance(self._llm_client, HermesChatClient):
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
        # generation gating：退出前 bump，避免退出过程中仍有 UI 回调试图执行
        self._bump_render_generation("exit")
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

        # 首次对话时移除 LOGO
        if not self._has_conversation:
            self._remove_logo()
            self._has_conversation = True

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
            # UI 刷新节流状态
            "last_ui_flush_time": start_time,
            "pending_chars": 0,
            "last_scroll_time": start_time,
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
            did_update_ui = await self._process_stream_content(
                content,
                stream_state,
                output_container,
                is_llm_output=is_llm_output,
                current_time=current_time,
            )

            # 合并滚动：仅在 UI 真正更新时、且按间隔节流滚动到底部
            if did_update_ui:
                self._maybe_scroll_to_end(output_container, stream_state, current_time)

            # 让出事件循环，确保键盘事件（如 Ctrl+C）有机会被处理
            await asyncio.sleep(0)

        # 流结束兜底：若尾部内容未达到节流阈值，则强制 flush，避免最后几个 chunk 丢失
        try:
            pending_chars = cast("int", stream_state.get("pending_chars", 0))
            current_line = cast(
                "OutputLine | MarkdownOutput | None",
                stream_state.get("current_line"),
            )
            if pending_chars > 0 and current_line is not None:
                self._flush_current_line(current_line, stream_state)
                now = asyncio.get_event_loop().time()
                stream_state["last_ui_flush_time"] = now
                stream_state["pending_chars"] = 0
                # 若发生可见更新，尽量把最终内容滚到可见位置
                self._maybe_scroll_to_end(output_container, stream_state, now)
        except (AttributeError, RuntimeError, ValueError, TypeError):
            # 退出/卸载过程中可能无法安全刷新，忽略兜底失败
            self.logger.debug("[TUI] Final stream flush skipped", exc_info=True)

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

    def _get_render_generation(self) -> int:
        """获取当前 render generation。"""
        return self._render_generation

    def _bump_render_generation(self, reason: str) -> None:
        """进入新一代渲染周期，用于取消/退出时阻断“余震”回调。"""
        self._render_generation += 1
        self.logger.debug("[TUI] Bump render generation to %d (%s)", self._render_generation, reason)

    def _report_markdown_render_duration(self, duration_seconds: float) -> None:
        """接收 Markdown 组件上报的渲染耗时，用于流式刷新自适应降频。"""
        if duration_seconds <= 0:
            return

        if self._markdown_render_ema_seconds is None:
            self._markdown_render_ema_seconds = duration_seconds
            return

        alpha = MarkdownOutput.RENDER_TIME_EMA_ALPHA
        self._markdown_render_ema_seconds = (alpha * duration_seconds) + (
            (1 - alpha) * self._markdown_render_ema_seconds
        )

    def _cancel_pending_output_renders(self) -> None:
        """取消输出区域内所有 Markdown 组件的待渲染任务。"""
        try:
            output_container = self.query_one("#output-container")
            for widget in output_container.query(MarkdownOutput):
                try:
                    widget.cancel_pending_render()
                except (AttributeError, RuntimeError, ValueError):
                    # 单个组件异常不影响整体取消
                    self.logger.debug("[TUI] Cancel pending render failed", exc_info=True)
        except (AttributeError, RuntimeError, ValueError):
            self.logger.debug("[TUI] Failed to cancel pending renders", exc_info=True)

    async def _process_stream_content(
        self,
        content: str,
        stream_state: dict,
        output_container: Container,
        *,
        is_llm_output: bool,
        current_time: float,
    ) -> bool:
        """处理流式内容，返回本次调用是否发生可见 UI 更新（mount/update）。"""
        stats_handled = self._try_handle_llm_stats_chunk(
            content,
            stream_state,
            output_container,
            is_llm_output=is_llm_output,
        )
        if stats_handled is not None:
            return stats_handled

        mcp_handled, content = self._try_handle_mcp_progress(content, output_container)
        if mcp_handled:
            # 自动执行模式下，MCP 进度块插入后必须重置当前输出组件状态，
            # 确保后续 LLM 文本创建新的输出组件，实现工具调用和文本的交替显示。
            # 否则后续文本会追加到 MCP 进度块之前的旧 MarkdownOutput 上，
            # 导致所有文本堆在一起而非按时间顺序与工具调用交替出现。
            current_line = cast("OutputLine | MarkdownOutput | None", stream_state.get("current_line"))
            if current_line is not None and cast("int", stream_state.get("pending_chars", 0)) > 0:
                self._flush_current_line(current_line, stream_state)
                stream_state["pending_chars"] = 0
                stream_state["last_ui_flush_time"] = current_time
            stream_state["current_line"] = None
            stream_state["is_first_content"] = True
            stream_state["current_content"] = ""
            return True

        current_line = cast("OutputLine | MarkdownOutput | None", stream_state.get("current_line"))
        current_kind = (
            "markdown"
            if isinstance(current_line, MarkdownOutput)
            else "text"
            if isinstance(current_line, OutputLine)
            else None
        )
        incoming_kind = "markdown" if is_llm_output else "text"

        # 若输出类型切换，在创建新组件前强制 flush 旧组件（把未刷新的累计内容推到 UI）
        if (
            current_line is not None
            and current_kind is not None
            and current_kind != incoming_kind
            and cast("int", stream_state.get("pending_chars", 0)) > 0
        ):
            self._flush_current_line(current_line, stream_state)
            stream_state["last_ui_flush_time"] = current_time
            stream_state["pending_chars"] = 0

        # 第一段内容或类型切换：创建适当的输出组件
        if (
            cast("bool", stream_state.get("is_first_content", True))
            or current_line is None
            or current_kind != incoming_kind
        ):
            stream_state["is_first_content"] = False
            stream_state["current_content"] = content
            stream_state["pending_chars"] = 0
            stream_state["last_ui_flush_time"] = current_time

            new_line: OutputLine | MarkdownOutput = MarkdownOutput(content) if is_llm_output else OutputLine(content)
            output_container.mount(new_line)
            stream_state["current_line"] = new_line

            # 任意非 MCP 输出都会结束当前进度块序列
            self._mcp_cluster_active = False
            self._current_progress_block = None
            return True

        # 后续内容：累计到 current_content，并按阈值节流刷新 UI
        stream_state["current_content"] = cast("str", stream_state.get("current_content", "")) + content
        stream_state["pending_chars"] = cast("int", stream_state.get("pending_chars", 0)) + len(content)

        if not self._should_flush_ui(stream_state, current_time, is_markdown=isinstance(current_line, MarkdownOutput)):
            return False

        self._flush_current_line(current_line, stream_state)
        stream_state["last_ui_flush_time"] = current_time
        stream_state["pending_chars"] = 0
        return True

    def _should_flush_ui(self, stream_state: dict, current_time: float, *, is_markdown: bool) -> bool:
        """判断是否应刷新 UI（Markdown 全量重渲染是主要开销点，需节流）。"""
        last_flush_time = cast("float", stream_state.get("last_ui_flush_time", 0.0))
        pending_chars = cast("int", stream_state.get("pending_chars", 0))
        params = self.STREAM_UI_FLUSH

        flush_interval = params.flush_interval
        flush_char_threshold = params.flush_char_threshold

        # 若 Markdown 渲染真实耗时变大，则动态降低刷新频率，避免超大表格触发雪崩
        if is_markdown and self._markdown_render_ema_seconds is not None:
            # 至少为 base，最多 0.8s，目标约为 2x 平均渲染耗时
            flush_interval = max(flush_interval, min(0.8, 2.0 * self._markdown_render_ema_seconds))
            # 同步提高字符阈值，减少刷新次数（上限 64k）
            scaled = int(flush_char_threshold * (1.0 + (self._markdown_render_ema_seconds / 0.05)))
            flush_char_threshold = min(65536, max(flush_char_threshold, scaled))

        if pending_chars >= flush_char_threshold:
            return True
        return (current_time - last_flush_time) >= flush_interval

    def _flush_current_line(self, current_line: OutputLine | MarkdownOutput, stream_state: dict) -> None:
        """将累计内容写回 UI 组件"""
        current_content = cast("str", stream_state.get("current_content", ""))
        if isinstance(current_line, MarkdownOutput):
            current_line.update_markdown(current_content)
        else:
            current_line.update(current_content)

    def _maybe_scroll_to_end(self, output_container: Container, stream_state: dict, current_time: float) -> None:
        """按间隔节流滚动到底部，避免每个 chunk 触发滚动与重排"""
        last_scroll_time = cast("float", stream_state.get("last_scroll_time", 0.0))
        if (current_time - last_scroll_time) < self.STREAM_UI_FLUSH.scroll_interval:
            return
        stream_state["last_scroll_time"] = current_time

        # 使用 call_after_refresh 合并滚动到下一次 UI 刷新周期（并做 generation gating）
        generation = self._render_generation

        def _do_scroll() -> None:
            if self._render_generation != generation:
                return
            output_container.scroll_end(animate=False)

        self.call_after_refresh(_do_scroll)

    def _try_handle_llm_stats_chunk(
        self,
        content: str,
        stream_state: dict,
        output_container: Container,
        *,
        is_llm_output: bool,
    ) -> bool | None:
        """若为 LLM 统计段落则处理并返回 True/False；否则返回 None。"""
        if not (is_llm_output and content.startswith(LLM_STATS_PREFIX)):
            return None

        stats_payload = content[len(LLM_STATS_PREFIX) :].strip()
        if not stats_payload:
            return False

        # 注意：UI 刷新有节流逻辑，可能存在 stream_state 里累积了尾部内容、但组件还没 update 的情况。
        # 若此时使用 current_line.get_content() 作为基准去追加统计段落，会导致尾部内容被覆盖丢失。
        current_line = cast("OutputLine | MarkdownOutput | None", stream_state.get("current_line"))
        stats_paragraph = f"\n\n> {stats_payload}"

        processed: OutputLine | MarkdownOutput | None
        if isinstance(current_line, MarkdownOutput):
            base_content = cast("str", stream_state.get("current_content", ""))
            updated = base_content + stats_paragraph
            current_line.update_markdown(updated)
            processed = current_line
        else:
            processed = self._append_llm_stats_block(stats_payload, current_line, output_container)

        if processed is not None:
            stream_state["current_line"] = processed
            stream_state["current_content"] = processed.get_content()
            # 统计段落已触发一次“全量更新”，清空 pending 以避免后续兜底 flush 覆盖内容
            stream_state["pending_chars"] = 0
        stream_state["is_first_content"] = False

        # 统计段属于普通输出，结束 MCP 进度块序列
        self._mcp_cluster_active = False
        self._current_progress_block = None
        return True

    def _try_handle_mcp_progress(self, content: str, output_container: Container) -> tuple[bool, str]:
        """若为 MCP 进度消息则处理并返回 (True, cleaned_content)；否则返回 (False, cleaned_content)。"""
        tag_info, cleaned_content = extract_mcp_tag(content)
        replace_tag_info: MCPTagInfo | None = None
        mcp_tag_info: MCPTagInfo | None = None
        if tag_info:
            if MCPTags.REPLACE_PREFIX in content:
                replace_tag_info = tag_info
            elif MCPTags.MCP_PREFIX in content:
                mcp_tag_info = tag_info

        step_tag = replace_tag_info or mcp_tag_info
        if step_tag is not None and is_mcp_message(content):
            self._handle_mcp_progress_message(cleaned_content, step_tag, output_container)
            return True, cleaned_content

        return False, cleaned_content

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
            new_line: OutputLine | MarkdownOutput = MarkdownOutput(content) if is_llm_output else OutputLine(content)
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

            # 滚动到底部以确保用户看到错误信息（并做 generation gating）
            generation = self._render_generation

            def _do_scroll() -> None:
                if self._render_generation != generation:
                    return
                output_container.scroll_end(animate=False)

            self.call_after_refresh(_do_scroll)

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
        # 合并到刷新周期，避免频繁滚动导致额外重排（并做 generation gating）
        generation = self._render_generation

        def _do_scroll() -> None:
            if self._render_generation != generation:
                return
            output_container.scroll_end(animate=False)

        self.call_after_refresh(_do_scroll)
        # 让出事件循环，避免阻塞键盘事件
        await asyncio.sleep(0)

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
            current_token = self.config_manager.get_witty_key()

            # 如果 personalToken 不一致，更新配置
            if personal_token != current_token:
                self.logger.info("检测到 personalToken 变更，正在同步到配置...")
                self.config_manager.set_witty_key(personal_token)
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
            # 检测智能体是否发生变更
            previous_agent_id = self.current_agent[0]
            app_id, _name = selected_agent
            agent_changed = previous_agent_id != app_id

            self.current_agent = selected_agent

            # 设置智能体到客户端
            if isinstance(llm_client, HermesChatClient):
                llm_client.set_current_agent(app_id)

                # 如果智能体发生变更且当前已有会话，强制重置 conversation
                if agent_changed and self._get_current_conversation_id():
                    llm_client.reset_conversation()
                    self.logger.info("智能体已变更，已重置会话")

                    # 在界面上显示提示信息
                    try:
                        output_container = self.query_one("#output-container")
                        output_container.mount(
                            MarkdownOutput(_("Agent changed, conversation has been reset")).add_class(
                                "mcp-progress-block",
                            ),
                        )
                        output_container.mount(OutputLine(""))  # 添加空行分隔
                        # 滚动到底部显示提示
                        output_container.scroll_end(animate=False)
                    except Exception:
                        self.logger.exception("显示智能体变更提示失败")

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
                did_update_ui = await self._process_stream_content(
                    content,
                    stream_state,
                    output_container,
                    is_llm_output=is_llm_output,
                    current_time=current_time,
                )

                if did_update_ui:
                    self._maybe_scroll_to_end(output_container, stream_state, current_time)

                await asyncio.sleep(0)

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

            if backend == Backend.SYSAGENT:
                # 验证 Hermes 配置
                llm_client = self.get_llm_client()
                if isinstance(llm_client, HermesChatClient):
                    # 检查当前 token 状态
                    current_token = self.config_manager.get_witty_key()
                    http_token = llm_client.http_manager.auth_token
                    self.logger.info(
                        "Hermes 验证前状态 - 配置 token 长度: %d, http_token 长度: %d",
                        len(current_token) if current_token else 0,
                        len(http_token) if http_token else 0,
                    )
                    result = await llm_client.ensure_user_info_loaded()
                    self.logger.info("Hermes 配置验证结果: %s", result)
                    if result:
                        await llm_client.activate_all_mcp_services()
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

        config_token = self.config_manager.get_witty_key()
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
            self._llm_client.clear_user_info_cache()
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

    def _remove_logo(self) -> None:
        """移除 LOGO 组件"""
        try:
            logo = self.query_one("#witty-logo", WittyLogo)
            logo.remove()
        except Exception:
            # LOGO 可能已经被移除或不存在
            self.logger.exception("移除 LOGO 组件时发生错误")

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
