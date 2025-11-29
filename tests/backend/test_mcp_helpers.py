"""Tests for MCP helper utilities based on live Hermes responses."""

from backend.hermes.mcp_helpers import MCPTags, create_mcp_tag, extract_mcp_tag

STEP_ONE_ID = "bb86d4ba-57d3-41cf-a060-919a9cc582f0"
STEP_TWO_ID = "4c37b4a6-cb09-408b-91bd-005d9b3b187d"
STEP_NAME = "cat_file_view_tool"


def test_create_mcp_tag_matches_stream_format() -> None:
    """Ensure create_mcp_tag emits the same format logged by Hermes SSE events."""
    tag = create_mcp_tag(STEP_NAME, step_id=STEP_ONE_ID)

    expected = f"{MCPTags.MCP_PREFIX}{STEP_ONE_ID}|{STEP_NAME}{MCPTags.TAG_SUFFIX}"
    assert tag == expected


def test_create_replace_tag_matches_stream_format() -> None:
    """REPLACE 标签应与后续同一步骤进度更新时的格式保持一致."""
    tag = create_mcp_tag(STEP_NAME, step_id=STEP_ONE_ID, is_replace=True)

    expected = f"{MCPTags.REPLACE_PREFIX}{STEP_ONE_ID}|{STEP_NAME}{MCPTags.TAG_SUFFIX}"
    assert tag == expected


def test_extract_mcp_tag_with_step_id_and_multiline_content() -> None:
    """Tags carrying a step_id should keep identifier and preserve the body."""
    body = "\n📥 工具 `cat_file_view_tool` 正在执行...\n"
    tagged = f"{create_mcp_tag(STEP_NAME, step_id=STEP_ONE_ID)}{body}"

    tag_info, cleaned = extract_mcp_tag(tagged)

    assert tag_info is not None
    assert tag_info.identifier == STEP_ONE_ID
    assert tag_info.tool_name == STEP_NAME
    assert cleaned == body.strip()


def test_extract_replace_tag_for_second_step() -> None:
    """REPLACE 标签应支持不同 stepId，且能返回对应主体。"""
    message = "\n✅ 工具 `cat_file_view_tool` 执行完成\n"
    tagged = f"{create_mcp_tag(STEP_NAME, step_id=STEP_TWO_ID, is_replace=True)}{message}"

    tag_info, cleaned = extract_mcp_tag(tagged)

    assert tag_info is not None
    assert tag_info.identifier == STEP_TWO_ID
    assert tag_info.tool_name == STEP_NAME
    assert cleaned == message.strip()


def test_extract_mcp_tag_without_step_id() -> None:
    """Legacy tags without step ids should still parse as before."""
    legacy_tag = f"{MCPTags.MCP_PREFIX}{STEP_NAME}{MCPTags.TAG_SUFFIX}结果"

    tag_info, cleaned = extract_mcp_tag(legacy_tag)

    assert tag_info is not None
    assert tag_info.identifier == STEP_NAME
    assert tag_info.tool_name == STEP_NAME
    assert cleaned == "结果"
