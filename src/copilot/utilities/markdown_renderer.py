# Copyright (c) Huawei Technologies Co., Ltd. 2024-2024. All rights reserved.

from rich.console import Group
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel


class MarkdownRenderer:

    @staticmethod
    def update(live: Live, content: str, sugggestion: str = '', refresh: bool = True):
        content_panel = Panel(Markdown(content, code_theme='github-dark'), border_style='gray50')
        if not sugggestion:
            live.update(content_panel, refresh=refresh)
            return
        sugggestion_panel = Panel(Markdown(sugggestion, code_theme='github-dark'), border_style='gray50')
        live.update(
            Group(content_panel, sugggestion_panel),
            refresh=refresh
        )
