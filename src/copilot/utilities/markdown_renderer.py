# Copyright (c) Huawei Technologies Co., Ltd. 2024-2024. All rights reserved.

from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel


class MarkdownRenderer:

    @staticmethod
    def update(live: Live, markup: str):
        live.update(
            Panel(
                Markdown(markup, code_theme='github-dark'),
                border_style='gray50'
            ),
            refresh=True
        )
