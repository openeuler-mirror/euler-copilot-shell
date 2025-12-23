"""Textual TUI 中 Markdown 去抖渲染的回归测试。"""

import pytest
from textual.app import App, ComposeResult

from app.tui import MarkdownOutput


class _MarkdownOutputTestApp(App[None]):
    def compose(self) -> ComposeResult:
        yield MarkdownOutput("")


@pytest.mark.asyncio
async def test_markdown_output_debounce_timer_safe_and_flushes() -> None:
    """
    回归：Markdown 去抖渲染不应使用 0 秒 Timer。

    该问题会导致：
    - UI 不刷新（pending 永远不被应用）
    - 退出/关闭时 Textual timer stop 流程出现 ZeroDivisionError
    """
    app = _MarkdownOutputTestApp()

    async with app.run_test() as pilot:
        widget = pilot.app.query_one(MarkdownOutput)

        # 模拟高频流式更新（只应最终应用最后一次）
        widget.update_markdown("a")
        widget.update_markdown("ab")
        widget.update_markdown("abc")

        # 等待去抖计时器触发
        await pilot.pause(0.1)

        assert widget.get_content() == "abc"
        # pending / timer 应在应用后清理，避免退出时还残留定时器
        assert widget._pending_markdown is None  # noqa: SLF001
        assert widget._render_timer is None  # noqa: SLF001

        # 能够正常退出（回归点：不应在退出时抛 timer 相关异常）
        await pilot.exit(None)
