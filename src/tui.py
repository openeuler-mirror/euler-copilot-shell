"""TUI 应用"""

import asyncio
from typing import Optional, Union

import urwid
from urwid import AsyncioEventLoop

from big_model import BigModelClient
from command_processor import process_command


class TUIApplication:
    """基于 Urwid 的 TUI 应用"""

    def __init__(self) -> None:
        """初始化 TUI 应用"""
        self.output_walker = urwid.SimpleListWalker([])
        self.output_listbox = urwid.ListBox(self.output_walker)
        self.input_edit = urwid.Edit("> ")
        self.footer = urwid.Padding(self.input_edit)
        # frame 的 body 使用输出的 ListBox
        self.frame = urwid.Frame(header=None, body=self.output_listbox, footer=self.footer)
        # 初始化大模型客户端，请根据实际接口地址和密钥进行配置
        self.big_model_client = BigModelClient(
            base_url="http://127.0.0.1:1234/v1",
            model="deepseek-r1-distill-qwen-32b-mlx",
            api_key="lm-studio",
        )
        self.loop: Optional[urwid.MainLoop] = None
        # 退出确认对话框
        self.exit_dialog: Optional[urwid.Overlay] = None
        self.exit_dialog_selection: int = 0  # 0: 取消, 1: 确认

    def run(self) -> None:
        """运行 TUI 应用"""
        self.frame.focus_position = "footer"  # 设置输入框为焦点
        self.loop = urwid.MainLoop(
            self.frame,
            unhandled_input=self.handle_input,
            event_loop=AsyncioEventLoop(),
            handle_mouse=False,  # 禁用 Urwid 的鼠标事件捕获
        )
        self.loop.run()

    def append_output(self, text: str, *, streaming: bool = False) -> None:
        """追加输出文本"""
        if streaming and self.output_walker:
            last_widget = self.output_walker[-1]
            if isinstance(last_widget, urwid.Text):
                if isinstance(last_widget.text, (bytes, bytearray)):
                    last_text: str = last_widget.text.decode()
                elif isinstance(last_widget.text, memoryview):
                    last_text: str = last_widget.text.tobytes().decode()
                else:
                    last_text: str = str(last_widget.text)
                last_widget.set_text(last_text + text)
            else:
                self.output_walker.append(urwid.Text(text))
        else:
            # 正常情况：每次新添加一行（支持换行）
            lines = text.splitlines() or [text]
            for line in lines:
                self.output_walker.append(urwid.Text(line))
        # 自动滚动到最后一行
        self.output_listbox.set_focus(len(self.output_walker) - 1)
        # 自动刷新屏幕
        if isinstance(self.loop, urwid.MainLoop):
            self.loop.draw_screen()

    def get_exit_dialog_text(self) -> str:
        """返回退出对话框的文本，标记当前选项"""
        options = ["取消", "确认"]
        parts = []
        for i, option in enumerate(options):
            if i == self.exit_dialog_selection:
                parts.append(f"[{option}]")
            else:
                parts.append(option)
        return "确认退出吗？ " + "  ".join(parts)

    def show_exit_dialog(self) -> None:
        """显示退出确认对话框"""
        if not isinstance(self.loop, urwid.MainLoop):
            return
        dialog_text = urwid.Text(self.get_exit_dialog_text(), align="center")
        filler = urwid.Filler(dialog_text, valign="middle")
        overlay = urwid.Overlay(
            filler,
            self.frame,
            align="center",
            width=("relative", 50),
            valign="middle",
            height=5,
        )
        self.exit_dialog = overlay
        self.loop.widget = overlay
        self.loop.draw_screen()

    def handle_exit_dialog_input(self, key: Union[str, tuple]) -> None:
        """处理退出对话框中的键盘输入"""
        if not isinstance(self.loop, urwid.MainLoop):
            return
        if key in ("left", "right"):
            if key == "left":
                self.exit_dialog_selection = max(self.exit_dialog_selection - 1, 0)
            else:
                self.exit_dialog_selection = min(self.exit_dialog_selection + 1, 1)
            # 更新文本
            if self.exit_dialog and isinstance(self.exit_dialog.top_w, urwid.Filler):
                text_widget = self.exit_dialog.top_w.original_widget
                if isinstance(text_widget, urwid.Text):
                    text_widget.set_text(self.get_exit_dialog_text())
            self.loop.draw_screen()
        elif key == "enter":
            if self.exit_dialog_selection == 1:
                raise urwid.ExitMainLoop
            self.loop.widget = self.frame
            self.exit_dialog = None
            self.loop.draw_screen()
        elif key in ("esc",):
            self.loop.widget = self.frame
            self.exit_dialog = None
            self.loop.draw_screen()

    def handle_input(self, key: Union[str, tuple[str, int, int, int]]) -> None:
        """处理输入事件"""
        # 退出对话框优先处理
        if self.exit_dialog is not None:
            self.handle_exit_dialog_input(key)
            return
        # 处理输入
        if key == "tab":
            self._toggle_focus()
        elif key == "enter":
            self._process_enter_key()
        elif key in ("up", "down", "page up", "page down"):
            _, focus_idx = self.output_listbox.get_focus()
            if focus_idx is None:
                return
            if key in ("down", "page down") and focus_idx >= len(self.output_walker) - 1:  # 已经在底端，忽略下移操作
                return
            if key in ("up", "page up") and focus_idx <= 0:  # 已经在顶端，忽略上移操作
                return
            self.output_listbox.keypress((0, 1), key)
        elif key in ("ctrl c", "ctrl C", "esc"):
            self.exit_dialog_selection = 0  # 重置为默认选项【取消】
            self.show_exit_dialog()

    def _toggle_focus(self) -> None:
        """切换焦点"""
        if self.frame.focus_position == "footer":
            self.frame.focus_position = "body"
        else:
            self.frame.focus_position = "footer"
        if isinstance(self.loop, urwid.MainLoop):
            self.loop.draw_screen()

    def _process_enter_key(self) -> None:
        """处理回车键"""
        user_input = self.input_edit.get_edit_text()
        self.input_edit.set_edit_text("")  # 清空输入框
        self.append_output(f"> {user_input}")
        async_tasks = set()
        future = asyncio.ensure_future(self._process_command(user_input))
        async_tasks.add(future)
        future.add_done_callback(lambda _: async_tasks.discard(future))

    async def _process_command(self, user_input: str) -> None:
        """处理命令"""
        first_chunk = True
        async for output in process_command(user_input, self.big_model_client):
            if first_chunk:
                self.append_output(output, streaming=False)
                first_chunk = False
            else:
                self.append_output(output, streaming=True)
