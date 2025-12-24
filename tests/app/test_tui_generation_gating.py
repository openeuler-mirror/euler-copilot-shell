"""
generation gating 的回归测试。

目标：确保 Ctrl+C / 取消 / 退出后，已经排队的 Markdown 渲染回调不会继续消耗 CPU 或触发重渲染。
"""

import pytest
from textual.app import App, ComposeResult

from app.tui import MarkdownOutput


class _GenerationTestApp(App[None]):
    def __init__(self) -> None:
        super().__init__()
        self._render_generation = 0
        self.last_reported_duration: float | None = None

    def _get_render_generation(self) -> int:
        return self._render_generation

    def bump(self) -> None:
        self._render_generation += 1

    def _report_markdown_render_duration(self, duration_seconds: float) -> None:
        self.last_reported_duration = duration_seconds

    def compose(self) -> ComposeResult:
        yield MarkdownOutput("")


@pytest.mark.asyncio
async def test_markdown_timer_callback_is_ignored_after_generation_bump() -> None:
    """Bump generation 后，先前排队的 Markdown timer 回调应被忽略并完成清理。"""
    app = _GenerationTestApp()

    async with app.run_test() as pilot:
        widget = pilot.app.query_one(MarkdownOutput)
        test_app = pilot.app  # type: ignore[assignment]
        assert isinstance(test_app, _GenerationTestApp)

        # 安排一次去抖渲染，但在 timer 触发前 bump generation
        widget.update_markdown("hello")
        test_app.bump()

        # 等待超过最小去抖时间，确保回调若执行也应被 gate 掉
        await pilot.pause(0.1)

        # 回调应该清理 pending/timer，并且不应上报渲染耗时（意味着没有执行 update 解析）
        assert widget._pending_markdown is None  # noqa: SLF001
        assert widget._render_timer is None  # noqa: SLF001
        assert test_app.last_reported_duration is None

        await pilot.exit(None)
