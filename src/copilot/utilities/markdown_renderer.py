# Copyright (c) Huawei Technologies Co., Ltd. 2024-2025. All rights reserved.

from rich.console import Group
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel

from copilot.utilities.i18n import main_content_panel_alpha_warning


class MarkdownRenderer:
    """Markdown 渲染器"""

    @staticmethod
    def update(live: Live, content: str, sugggestion: str = "", *, refresh: bool = True) -> None:
        """更新 Markdown 内容"""
        content_panel = Panel(
            Markdown(content, code_theme="github-dark"),
            border_style="gray50",
            subtitle=main_content_panel_alpha_warning,
            subtitle_align="right",
        )
        if not sugggestion:
            live.update(content_panel, refresh=refresh)
            return
        sugggestion_panel = Panel(Markdown(sugggestion, code_theme="github-dark"), border_style="gray50")
        live.update(
            Group(content_panel, sugggestion_panel),
            refresh=refresh,
        )
