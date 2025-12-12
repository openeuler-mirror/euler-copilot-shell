"""
oi_select_agent.py 模块测试

测试智能体选择工具的函数。
"""

from __future__ import annotations

import io
import sys
from unittest.mock import AsyncMock, Mock, patch

import pytest

from i18n.manager import _
from tool.oi_select_agent import (
    get_agent_list,
    get_current_agent,
    handle_agent_selection,
)


class MockAgent:
    """模拟智能体对象"""

    def __init__(self, app_id: str, name: str) -> None:
        """初始化模拟智能体"""
        self.app_id = app_id
        self.name = name


class TestGetAgentList:
    """测试 get_agent_list 函数"""

    @pytest.mark.asyncio
    async def test_get_agent_list_with_agents(self) -> None:
        """测试获取智能体列表成功"""
        mock_config = Mock()
        mock_logger = Mock()

        mock_agents = [
            MockAgent("agent-1", "智能体1"),
            MockAgent("agent-2", "智能体2"),
        ]

        mock_client = AsyncMock()
        mock_client.get_available_agents = AsyncMock(return_value=mock_agents)

        with patch("tool.oi_select_agent.BackendFactory") as mock_factory:
            mock_factory.create_client.return_value = mock_client
            result = await get_agent_list(mock_config, mock_logger)

        # 应该包含默认的"智能问答"和两个智能体
        assert len(result) == 3  # noqa: PLR2004
        assert result[0][0] == ""  # 默认选项的 app_id 为空
        assert result[1] == ("agent-1", "智能体1")
        assert result[2] == ("agent-2", "智能体2")

    @pytest.mark.asyncio
    async def test_get_agent_list_no_agents(self) -> None:
        """测试没有智能体时返回默认列表"""
        mock_config = Mock()
        mock_logger = Mock()

        mock_client = AsyncMock()
        mock_client.get_available_agents = AsyncMock(return_value=[])

        with patch("tool.oi_select_agent.BackendFactory") as mock_factory:
            mock_factory.create_client.return_value = mock_client
            result = await get_agent_list(mock_config, mock_logger)

        # 应该只包含默认的"智能问答"
        assert len(result) == 1
        assert result[0][0] == ""

    @pytest.mark.asyncio
    async def test_get_agent_list_client_no_support(self) -> None:
        """测试客户端不支持智能体功能"""
        mock_config = Mock()
        mock_logger = Mock()

        # 模拟一个没有 get_available_agents 方法的客户端
        mock_client = Mock(spec=[])

        with patch("tool.oi_select_agent.BackendFactory") as mock_factory:
            mock_factory.create_client.return_value = mock_client
            result = await get_agent_list(mock_config, mock_logger)

        # 应该只返回默认列表
        assert len(result) == 1
        assert result[0][0] == ""
        mock_logger.warning.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_agent_list_exception(self) -> None:
        """测试获取智能体列表异常"""
        mock_config = Mock()
        mock_logger = Mock()

        mock_client = AsyncMock()
        mock_client.get_available_agents = AsyncMock(side_effect=RuntimeError("Connection failed"))

        with patch("tool.oi_select_agent.BackendFactory") as mock_factory:
            mock_factory.create_client.return_value = mock_client
            result = await get_agent_list(mock_config, mock_logger)

        # 应该返回默认列表
        assert len(result) == 1
        mock_logger.warning.assert_called()


class TestGetCurrentAgent:
    """测试 get_current_agent 函数"""

    def test_get_current_agent_found(self) -> None:
        """测试找到当前智能体"""
        mock_config = Mock()
        mock_config.get_default_app.return_value = "agent-2"

        agent_list = [
            ("", "智能问答"),
            ("agent-1", "智能体1"),
            ("agent-2", "智能体2"),
        ]

        result = get_current_agent(mock_config, agent_list)
        assert result == ("agent-2", "智能体2")

    def test_get_current_agent_not_found(self) -> None:
        """测试未找到当前智能体，返回默认"""
        mock_config = Mock()
        mock_config.get_default_app.return_value = "non-existent"

        agent_list = [
            ("", "智能问答"),
            ("agent-1", "智能体1"),
        ]

        result = get_current_agent(mock_config, agent_list)
        # 应该返回默认的智能问答
        assert result[0] == ""

    def test_get_current_agent_empty_app_id(self) -> None:
        """测试当前 app_id 为空"""
        mock_config = Mock()
        mock_config.get_default_app.return_value = ""

        agent_list = [
            ("", "智能问答"),
            ("agent-1", "智能体1"),
        ]

        result = get_current_agent(mock_config, agent_list)
        assert result == ("", "智能问答")

    def test_get_current_agent_none_app_id(self) -> None:
        """测试当前 app_id 为 None"""
        mock_config = Mock()
        mock_config.get_default_app.return_value = None

        agent_list = [
            ("", "智能问答"),
            ("agent-1", "智能体1"),
        ]

        result = get_current_agent(mock_config, agent_list)
        # None 不等于 ""，所以应该返回默认
        assert result[0] == ""


class TestHandleAgentSelection:
    """测试 handle_agent_selection 函数"""

    def test_handle_selection_with_agent(self) -> None:
        """测试选择了智能体"""
        mock_config = Mock()
        selected = ("agent-1", "智能体1")

        captured_output = io.StringIO()
        sys.stdout = captured_output

        try:
            handle_agent_selection(mock_config, selected)
        finally:
            sys.stdout = sys.__stdout__

        mock_config.set_default_app.assert_called_once_with("agent-1")
        output = captured_output.getvalue()
        assert "智能体1" in output
        assert "agent-1" in output

    def test_handle_selection_default_qa(self) -> None:
        """测试选择了智能问答（无智能体）"""
        mock_config = Mock()
        selected = ("", "智能问答")

        captured_output = io.StringIO()
        sys.stdout = captured_output

        try:
            handle_agent_selection(mock_config, selected)
        finally:
            sys.stdout = sys.__stdout__

        mock_config.set_default_app.assert_called_once_with("")
        output = captured_output.getvalue()
        assert "智能问答" in output

    def test_handle_selection_cancelled(self) -> None:
        """测试取消选择"""
        mock_config = Mock()

        captured_output = io.StringIO()
        sys.stdout = captured_output

        try:
            handle_agent_selection(mock_config, None)
        finally:
            sys.stdout = sys.__stdout__

        mock_config.set_default_app.assert_not_called()
        output = captured_output.getvalue()
        # 源码输出包含换行符，翻译条目也以带换行的 msgid 为准
        assert _("已取消选择\n") == output


class TestAgentSelectorApp:
    """测试 AgentSelectorApp 类"""

    def test_app_initialization(self) -> None:
        """测试应用初始化"""
        from tool.oi_select_agent import AgentSelectorApp

        agent_list = [("", "智能问答"), ("agent-1", "智能体1")]
        current_agent = ("", "智能问答")

        app = AgentSelectorApp(agent_list, current_agent)

        assert app.agent_list == agent_list
        assert app.current_agent == current_agent
        assert app.selected_agent is None
        assert app.selection_made is False
