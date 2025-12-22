"""Witty Assistant LOGO 组件"""

from __future__ import annotations

import os

from rich.style import Style
from rich.text import Text
from textual.color import Gradient
from textual.widgets import Static

MINIMAL_WINDOW_THRESHOLD = 72
NARROW_WINDOW_THRESHOLD = 117

# 长 LOGO（单行显示，需要宽度 >= 117）
# fmt: off
LONG_LOGO = (
    "██╗    ██╗██╗████████╗████████╗██╗   ██╗     █████╗ ███████╗███████╗██╗███████╗████████╗ █████╗ ███╗   ██╗████████╗\n"  # noqa: E501
    "██║    ██║██║╚══██╔══╝╚══██╔══╝╚██╗ ██╔╝    ██╔══██╗██╔════╝██╔════╝██║██╔════╝╚══██╔══╝██╔══██╗████╗  ██║╚══██╔══╝\n"  # noqa: E501
    "██║ █╗ ██║██║   ██║      ██║    ╚████╔╝     ███████║███████╗███████╗██║███████╗   ██║   ███████║██╔██╗ ██║   ██║\n"
    "██║███╗██║██║   ██║      ██║     ╚██╔╝      ██╔══██║╚════██║╚════██║██║╚════██║   ██║   ██╔══██║██║╚██╗██║   ██║\n"
    "╚███╔███╔╝██║   ██║      ██║      ██║       ██║  ██║███████║███████║██║███████║   ██║   ██║  ██║██║ ╚████║   ██║\n"
    " ╚══╝╚══╝ ╚═╝   ╚═╝      ╚═╝      ╚═╝       ╚═╝  ╚═╝╚══════╝╚══════╝╚═╝╚══════╝   ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═══╝   ╚═╝"
)

# 短 LOGO（两行显示，适用于窄窗口）
SHORT_LOGO = (
    "██╗    ██╗██╗████████╗████████╗██╗   ██╗\n"
    "██║    ██║██║╚══██╔══╝╚══██╔══╝╚██╗ ██╔╝\n"
    "██║ █╗ ██║██║   ██║      ██║    ╚████╔╝\n"
    "██║███╗██║██║   ██║      ██║     ╚██╔╝\n"
    "╚███╔███╔╝██║   ██║      ██║      ██║\n"
    " ╚══╝╚══╝ ╚═╝   ╚═╝      ╚═╝      ╚═╝\n"
    "\n"
    " █████╗ ███████╗███████╗██╗███████╗████████╗ █████╗ ███╗   ██╗████████╗\n"
    "██╔══██╗██╔════╝██╔════╝██║██╔════╝╚══██╔══╝██╔══██╗████╗  ██║╚══██╔══╝\n"
    "███████║███████╗███████╗██║███████╗   ██║   ███████║██╔██╗ ██║   ██║\n"
    "██╔══██║╚════██║╚════██║██║╚════██║   ██║   ██╔══██║██║╚██╗██║   ██║\n"
    "██║  ██║███████║███████║██║███████║   ██║   ██║  ██║██║ ╚████║   ██║\n"
    "╚═╝  ╚═╝╚══════╝╚══════╝╚═╝╚══════╝   ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═══╝   ╚═╝"
)

# Minimal LOGO（极窄窗口，只显示 WITTY 部分）
MINIMAL_LOGO = (
    "██╗    ██╗██╗████████╗████████╗██╗   ██╗\n"
    "██║    ██║██║╚══██╔══╝╚══██╔══╝╚██╗ ██╔╝\n"
    "██║ █╗ ██║██║   ██║      ██║    ╚████╔╝\n"
    "██║███╗██║██║   ██║      ██║     ╚██╔╝\n"
    "╚███╔███╔╝██║   ██║      ██║      ██║\n"
    " ╚══╝╚══╝ ╚═╝   ╚═╝      ╚═╝      ╚═╝"
)
# fmt: on


class WittyLogo(Static):
    """Witty Assistant LOGO 组件"""

    def __init__(self) -> None:
        """初始化 LOGO 组件"""
        super().__init__(id="witty-logo")
        self._current_logo = LONG_LOGO
        self._supports_gradient = self._check_truecolor_support()

    def on_mount(self) -> None:
        """挂载时更新 LOGO"""
        self._update_logo()

    def on_resize(self) -> None:
        """窗口大小改变时更新 LOGO"""
        self._update_logo()

    def _update_logo(self) -> None:
        """根据容器宽度更新 LOGO 显示"""
        container_width = self.size.width if self.size else NARROW_WINDOW_THRESHOLD

        if container_width >= NARROW_WINDOW_THRESHOLD:
            logo_text = LONG_LOGO
        elif container_width >= MINIMAL_WINDOW_THRESHOLD:
            logo_text = SHORT_LOGO
        else:
            logo_text = MINIMAL_LOGO

        if logo_text != self._current_logo:
            self._current_logo = logo_text

        # 应用渐变色到文本
        if self._supports_gradient:
            # 使用 Textual Gradient API 创建横向渐变
            gradient = Gradient.from_colors("#AF5FFF", "#00AFFF", "#AFFFFF")
            gradient_text = Text()

            # 分割行并计算整个 LOGO 的最大宽度
            lines = logo_text.split("\n")
            max_width = max(len(line) for line in lines) if lines else 1

            # 按行处理，基于整个 LOGO 的横向坐标应用渐变
            for line_idx, line in enumerate(lines):
                if line_idx > 0:
                    gradient_text.append("\n")

                if not line.strip():
                    gradient_text.append(line)
                    continue

                # 为当前行的每个字符基于全局横向位置应用渐变
                for char_idx, char in enumerate(line):
                    if char.strip():
                        # 计算字符在整个 LOGO 横向的位置比例
                        progress = char_idx / max(max_width - 1, 1)
                        rich_color = gradient.get_rich_color(progress)
                        gradient_text.append(char, style=Style(color=rich_color))
                    else:
                        gradient_text.append(char)

            self.update(gradient_text)
        else:
            # 不支持真彩色时使用纯色
            self.styles.color = "#5F87FF"
            self.update(logo_text)

    def _check_truecolor_support(self) -> bool:
        """检测终端是否支持真彩色"""
        term = os.environ.get("TERM", "")
        colorterm = os.environ.get("COLORTERM", "")

        # 检查常见的真彩色终端标识
        return "truecolor" in colorterm.lower() or "24bit" in colorterm.lower() or "truecolor" in term.lower()
