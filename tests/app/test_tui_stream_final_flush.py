"""
TUI 流式渲染的回归测试。

覆盖点：

1) 流式节流下，尾部短 chunk 不应因为未触发 flush 而在 UI 中永久缺失。
2) LLM token 统计段（[LLM_STATS]）应正确追加到 Markdown 输出末尾，且不会覆盖/丢失尚未 flush 的内容。
3) MCP Step 进度块应正确渲染，并包含 token/time 等信息。
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pytest
from textual.containers import Container

from app import tui
from app.tui import IntelligentTerminal, MarkdownOutput, MCPProgressBlock
from backend.hermes.mcp_helpers import LLM_STATS_PREFIX, create_mcp_tag

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


class _StreamTestTerminal(IntelligentTerminal):
    """避免网络与默认智能体初始化的最小 App。"""

    # 注意：Textual 解析 CSS_PATH 时会以“子类所在模块路径”为基准。
    # 该测试类定义在 tests/ 目录下，若继承 IntelligentTerminal 的相对 CSS_PATH，
    # 将会尝试读取 tests/app/css/styles.tcss（并不存在），导致 StylesheetError。
    # 这里直接禁用 CSS 加载即可。
    CSS_PATH = None

    def on_mount(self) -> None:
        # 测试中不执行默认智能体初始化（可能触发网络/后台任务）
        self._mcp_mode = "normal"

    def get_llm_client(self) -> object:  # type: ignore[override]
        # process_command 会被 monkeypatch，llm_client 实际不会被用到
        return object()


async def _fake_process_command(
    _user_input: str,
    _llm_client: object,
) -> AsyncIterator[tuple[str, bool]]:
    """模拟一次包含 MCP、LLM 流式输出和统计段的命令流。"""
    # MCP 进度：RAG检索
    step_id = "99e77c0f-1e3f-4e44-9cc2-9ec0dcf7b74d"  # 来自日志
    yield (
        f"{create_mcp_tag('RAG检索', step_id=step_id)}\n📥 工具 `RAG检索` 正在执行...\n",
        False,
    )
    yield (
        (
            f"{create_mcp_tag('RAG检索', step_id=step_id, is_replace=True)}\n"
            "✅ 工具 `RAG检索` 执行完成  [ ↑0 ↓0 0.802s ]\n"
        ),
        False,
    )

    # LLM 输出尾部 chunk：来自日志中“缺失”的几段
    yield ("无论你是历史爱好者", True)
    yield ("、自然探险者", True)
    yield ("，还是科技迷", True)
    yield ("，都能在这里找到", True)
    yield ("属于自己的精彩。", True)

    # LLM token 统计段：格式与 UI 展示逻辑一致（> blockquote）
    yield (f"{LLM_STATS_PREFIX}↑360 ↓368 2.948s", True)


def _iter_deltas_from_absolute_times(
    absolute_events: list[tuple[float, str, bool]],
) -> list[tuple[float, str, bool]]:
    """
    将日志里的绝对 timeCost（秒）转换为相邻事件的 delta（秒）。

    Hermes 日志中的 timeCost 是从请求开始算起的累计耗时，本测试用其相邻差值来模拟
    SSE 到达节奏（用缩放因子压缩整体耗时，避免测试变慢）。
    """
    deltas: list[tuple[float, str, bool]] = []
    prev = 0.0
    for t, text, is_llm in absolute_events:
        delta = max(0.0, t - prev)
        deltas.append((delta, text, is_llm))
        prev = t
    return deltas


async def _fake_process_command_realistic_timestamps(
    _user_input: str,
    _llm_client: object,
) -> AsyncIterator[tuple[str, bool]]:
    """
    更贴近真实日志节奏的模拟流（含时间戳）。

    参考：`witty-assistant-20251225-111953.log` 中 11:20:07~11:20:08 的一段 `text.add`。
    """
    # 缩放因子：把真实 timeCost 压缩到测试可接受范围，同时仍能触发 time-based flush。
    # 选择 0.4：0.35s 级别的间隔会变为 ~0.14s（> STREAM_UI_FLUSH.flush_interval=0.08）。
    scale = 0.4

    # MCP 进度：RAG检索（与真实日志一致）
    step_id = "99e77c0f-1e3f-4e44-9cc2-9ec0dcf7b74d"
    yield (
        f"{create_mcp_tag('RAG检索', step_id=step_id)}\n📥 工具 `RAG检索` 正在执行...\n",
        False,
    )
    # 日志中 step.output 大约发生在 0.802s
    await asyncio.sleep(0.802 * scale)
    yield (
        (
            f"{create_mcp_tag('RAG检索', step_id=step_id, is_replace=True)}\n"
            "✅ 工具 `RAG检索` 执行完成  [ ↑0 ↓0 0.802s ]\n"
        ),
        False,
    )

    # LLM 输出：摘取日志里的一段较长 `text.add`（用 timeCost 近似 SSE 到达节奏）
    absolute = [
        (0.348, "杭州", True),
        (0.349, "，", True),
        (0.349, "简称", True),
        (0.349, "“", True),
        (0.349, "杭”，是中华人民", True),
        (0.603, "共和国浙江省的省", True),
        (0.603, "会，位于中国", True),
        (0.603, "东南沿海、长江", True),
        (0.603, "三角洲南翼", True),
        (0.603, "，是一座历史悠久的", True),
        (0.604, "著名风景旅游城市", True),
        (0.613, "。\n\n**历史文化：", True),
        (0.613, "**\n杭州拥有超过", True),
        (0.613, "2200", True),
        (0.781, "年的建城史", True),
        (0.781, "，曾是吴", True),
        (0.782, "越国和南宋", True),
        (0.782, "的都城。", True),
        (0.866, "作为“丝绸之", True),
        (0.866, "府”、“鱼", True),
        (0.866, "米之乡”，杭州", True),
        (0.867, "的文化底蕴深厚。", True),
        (0.912, "西湖文化景观是", True),
        (0.912, "世界文化遗产，其中", True),
        (1.067, "“西湖十景", True),
        (1.067, "”闻名遐迩", True),
        (1.067, "。此外，杭州", True),
        (1.068, "还是中国茶文化的", True),
        (1.115, "发源地之一", True),
        (1.116, "，龙井茶", True),
        (1.116, "享誉全球。\n\n**", True),
        (1.252, "旅游资源：**\n杭州", True),
    ]

    for delta, text, is_llm in _iter_deltas_from_absolute_times(absolute):
        if delta:
            await asyncio.sleep(delta * scale)
        yield (text, is_llm)

    # 追加：复现“流尾短 chunk 可能不显示”的真实问题片段
    tail_frags = [
        "无论你是历史爱好者",
        "、自然探险者",
        "，还是科技迷",
        "，都能在这里找到",
        "属于自己的精彩。",
    ]
    for frag in tail_frags:
        # 尾部刻意使用很短的间隔，模拟容易被节流吞掉的场景
        await asyncio.sleep(0.01 * scale)
        yield (frag, True)

    # stats 段：模拟末尾追加
    await asyncio.sleep(0.02 * scale)
    yield (f"{LLM_STATS_PREFIX}↑360 ↓368 2.948s", True)


@pytest.mark.asyncio
async def test_stream_final_flush_keeps_tail_chunks_and_renders_stats_and_mcp(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """回归：流结束兜底 flush + stats 追加 + MCP step 进度展示。"""
    monkeypatch.setattr(tui, "process_command", _fake_process_command)

    app = _StreamTestTerminal()

    async with app.run_test() as pilot:
        output_container = pilot.app.query_one("#output-container", Container)

        # 直接走真实的流式路径
        await app._handle_command_stream("介绍一下杭州", output_container)  # noqa: SLF001

        # 等待去抖渲染与 call_after_refresh 回调
        await pilot.pause(0.2)

        # 1) MCP Step：应存在进度块，且展示完成态（包含 token/time）
        progress_block = pilot.app.query_one(MCPProgressBlock)
        progress_text = progress_block.get_content()
        assert "RAG检索" in progress_text
        assert "↑0" in progress_text
        assert "↓0" in progress_text
        assert "0.802s" in progress_text

        # 2) LLM Markdown：尾部 chunk 不应丢失
        markdown_blocks = [w for w in output_container.query(MarkdownOutput) if not isinstance(w, MCPProgressBlock)]
        assert markdown_blocks, "应至少渲染一个 LLM Markdown 输出块"
        llm_block = markdown_blocks[-1]
        llm_text = llm_block.get_content()
        for frag in [
            "、自然探险者",
            "，还是科技迷",
            "，都能在这里找到",
            "属于自己的精彩。",
        ]:
            assert frag in llm_text

        # 3) token 统计：应追加为 blockquote，且不会覆盖尾部内容
        assert "↑360" in llm_text
        assert "↓368" in llm_text
        assert "2.948s" in llm_text
        assert ">" in llm_text

        await pilot.exit(None)


@pytest.mark.asyncio
async def test_stream_realistic_timestamps_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    """更长、更贴近真实 SSE 时间戳的回归覆盖。"""
    monkeypatch.setattr(tui, "process_command", _fake_process_command_realistic_timestamps)

    app = _StreamTestTerminal()

    async with app.run_test() as pilot:
        output_container = pilot.app.query_one("#output-container", Container)

        await app._handle_command_stream("介绍一下杭州", output_container)  # noqa: SLF001

        # 给去抖渲染、scroll 合并与 call_after_refresh 足够时间
        await pilot.pause(0.6)

        # MCP 进度块应存在且包含完成态
        progress_block = pilot.app.query_one(MCPProgressBlock)
        progress_text = progress_block.get_content()
        assert "RAG检索" in progress_text
        assert "0.802s" in progress_text

        markdown_blocks = [w for w in output_container.query(MarkdownOutput) if not isinstance(w, MCPProgressBlock)]
        assert markdown_blocks
        llm_text = markdown_blocks[-1].get_content()

        # 断言：日志中的中间片段应出现（确保长流累计正确）
        for frag in [
            "杭州",
            "简称",
            "2200",
            "西湖文化景观",
        ]:
            assert frag in llm_text

        # 断言：流尾短 chunk 不应缺失
        for frag in [
            "、自然探险者",
            "，还是科技迷",
            "，都能在这里找到",
            "属于自己的精彩。",
        ]:
            assert frag in llm_text

        # 断言：stats 段应追加为 blockquote
        assert "↑360" in llm_text
        assert "↓368" in llm_text
        assert "2.948s" in llm_text
        assert ">" in llm_text

        await pilot.exit(None)
