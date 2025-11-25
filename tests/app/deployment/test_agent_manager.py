"""AgentManager 辅助方法测试"""

import pytest

from app.deployment.agent import AgentManager


@pytest.mark.unit
class TestAgentManagerHelpers:
    """聚焦于纯粹的辅助方法，避免执行系统命令"""

    def test_normalize_mcp_config_applies_defaults(self) -> None:
        """非列表/字典字段会被纠正，同时保留其余值"""
        manager = AgentManager()

        timeout_override = 10

        normalized = manager._normalize_mcp_config(  # noqa: SLF001
            {
                "autoApprove": "alice",  # 非列表 -> 应重置
                "headers": ["invalid"],  # 非 dict -> 应重置
                "timeout": timeout_override,
                "disabled": True,
                "auto_install": False,
            },
        )

        assert normalized["autoApprove"] == []
        assert normalized["headers"] == {}
        assert normalized["timeout"] == timeout_override
        assert normalized["disabled"] is True
        assert normalized["autoInstall"] is False  # 保留旧字段的显式值
        assert normalized["env"] == {}
        assert "auto_install" not in normalized

    def test_normalize_mcp_config_when_missing(self) -> None:
        """空配置将被填充为默认值"""
        manager = AgentManager()
        normalized = manager._normalize_mcp_config({})  # noqa: SLF001
        assert normalized == {
            "env": {},
            "autoApprove": [],
            "disabled": False,
            "autoInstall": True,
            "timeout": 60,
            "description": "",
            "headers": {},
            "url": "",
        }

    def test_resolve_mcp_services(self) -> None:
        """确认缺失的服务会被单独列出"""
        manager = AgentManager()
        mapping = {"tool-a": "svc-1", "tool-b": "svc-2"}

        resolved, missing = manager._resolve_mcp_services(  # noqa: SLF001
            ["tool-a", "tool-c"],
            mapping,
        )

        assert resolved == ["svc-1"]
        assert missing == ["tool-c"]
