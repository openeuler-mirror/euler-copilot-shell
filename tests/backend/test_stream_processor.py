"""Tests for Hermes stream processor metadata handling."""

from backend.hermes.mcp_helpers import LLM_STATS_PREFIX
from backend.hermes.stream import HermesStreamEvent, HermesStreamProcessor

STEP_NAME = "cat_file_view_tool"
STEP_ID = "step-123"


def _build_event(event_type: str, metadata: dict | None = None) -> HermesStreamEvent:
    flow = {
        "stepName": STEP_NAME,
        "stepId": STEP_ID,
        "stepStatus": "success",
        "executorStatus": "running",
    }
    data = {
        "event": event_type,
        "flow": flow,
        "content": {},
        "metadata": metadata or {},
    }
    return HermesStreamEvent(event_type, data)


def test_format_mcp_status_appends_metadata_once_step_completes() -> None:
    """Final MCP lines should embed token/time statistics right after the completion text."""
    processor = HermesStreamProcessor()
    event = _build_event(
        "step.output",
        metadata={"inputTokens": 12, "outputTokens": 34, "timeCost": 5.678},
    )

    message = processor.format_mcp_status(event)

    assert message is not None
    assert "↑12" in message
    assert "↓34" in message
    assert "5.678s" in message


def test_format_llm_stats_marker_for_final_executor_stop() -> None:
    """FINAL executor.stop events should emit a dedicated stats marker for the TUI."""
    processor = HermesStreamProcessor()
    event = HermesStreamEvent(
        "executor.stop",
        {
            "event": "executor.stop",
            "flow": {"stepName": "FINAL", "stepId": "final-step", "stepStatus": "success"},
            "content": {},
            "metadata": {"inputTokens": 354, "outputTokens": 78, "timeCost": 23.477},
        },
    )

    marker = processor.format_llm_stats_marker(event)

    assert marker is not None
    assert marker.startswith(LLM_STATS_PREFIX)
    assert "↑354" in marker
    assert "↓78" in marker
    assert "23.477s" in marker
