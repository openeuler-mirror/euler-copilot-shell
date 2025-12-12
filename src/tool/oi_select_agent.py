"""智能体选择工具"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from textual.app import App, ComposeResult
from textual.containers import Container

from app.dialogs import AgentSelectionDialog
from backend.factory import BackendFactory
from config.manager import ConfigManager
from config.model import Backend
from i18n.manager import _
from log.manager import get_logger, log_exception, setup_logging

if TYPE_CHECKING:
    from logging import Logger


class AgentSelectorApp(App):
    """智能体选择应用"""

    CSS_PATH = Path(__file__).parent.parent / "app" / "css" / "styles.tcss"

    BINDINGS: ClassVar = [
        ("escape", "quit", _("退出")),
    ]

    def __init__(self, agent_list: list[tuple[str, str]], current_agent: tuple[str, str]) -> None:
        """初始化智能体选择应用"""
        super().__init__()
        self.agent_list = agent_list
        self.current_agent = current_agent
        self.selected_agent: tuple[str, str] | None = None
        self.selection_made = False

    def compose(self) -> ComposeResult:
        """构建应用界面"""
        yield Container(id="main-container")

    def on_mount(self) -> None:
        """应用挂载时显示选择对话框"""

        def on_agent_selected(selected_agent: tuple[str, str]) -> None:
            """智能体选择回调"""
            self.selected_agent = selected_agent
            self.selection_made = True
            self.exit()

        dialog = AgentSelectionDialog(self.agent_list, on_agent_selected, self.current_agent)
        self.push_screen(dialog)

    async def action_quit(self) -> None:
        """退出应用"""
        self.exit()


async def get_agent_list(config_manager: ConfigManager, logger: Logger) -> list[tuple[str, str]]:
    """获取智能体列表"""
    # 创建 LLM 客户端
    llm_client = BackendFactory.create_client(config_manager)

    # 构建智能体列表 - 默认第一项为"智能问答"（无智能体）
    agent_list = [("", _("智能问答"))]

    # 尝试获取可用智能体
    if not hasattr(llm_client, "get_available_agents"):
        logger.warning("当前客户端不支持智能体功能，使用默认选项")
        return agent_list

    try:
        available_agents = await llm_client.get_available_agents()  # type: ignore[attr-defined]
        # 添加获取到的智能体
        agent_list.extend(
            [
                (agent.app_id, agent.name)
                for agent in available_agents
                if hasattr(agent, "app_id") and hasattr(agent, "name")
            ],
        )
        logger.info("成功获取到 %d 个智能体", len(agent_list) - 1)
    except (AttributeError, OSError, ValueError, RuntimeError) as e:
        logger.warning("获取智能体列表失败，使用默认选项: %s", str(e))

    return agent_list


def get_current_agent(config_manager: ConfigManager, agent_list: list[tuple[str, str]]) -> tuple[str, str]:
    """获取当前默认智能体"""
    current_app_id = config_manager.get_default_app()
    current_agent = ("", _("智能问答"))
    for agent in agent_list:
        if agent[0] == current_app_id:
            current_agent = agent
            break
    return current_agent


async def run_agent_selector(
    agent_list: list[tuple[str, str]],
    current_agent: tuple[str, str],
) -> tuple[str, str] | None:
    """运行智能体选择器"""
    app = AgentSelectorApp(agent_list, current_agent)
    await app.run_async()
    return app.selected_agent if app.selection_made else None


def handle_agent_selection(
    config_manager: ConfigManager,
    selected_agent: tuple[str, str] | None,
) -> None:
    """处理智能体选择结果"""
    if selected_agent:
        selected_app_id, selected_name = selected_agent

        # 保存选择到配置
        config_manager.set_default_app(selected_app_id)

        sys.stdout.write(_("✓ 默认智能体已设置为: {name}\n").format(name=selected_name))
        if selected_app_id:
            sys.stdout.write(_("  App ID: {app_id}\n").format(app_id=selected_app_id))
        else:
            sys.stdout.write(_("  已设置为智能问答模式（无智能体）\n"))
    else:
        sys.stdout.write(_("已取消选择\n"))


async def select_agent() -> None:
    """智能体选择功能主入口"""
    # 初始化配置和日志系统
    config_manager = ConfigManager()
    setup_logging(config_manager)
    # 注意：这里不启用控制台输出，让日志只写入文件

    logger = get_logger(__name__)

    # 检查是否使用 eulerintelli 后端
    if config_manager.get_backend() != Backend.EULERINTELLI:
        sys.stderr.write(_("错误: 智能体功能需要使用 Witty Assistant 后端\n"))
        sys.stderr.write(_("请先运行以下命令切换后端：\n"))
        sys.stderr.write(_("  oi  # 然后按下 Ctrl+S 进入设置界面切换到 Witty Assistant 后端\n"))
        sys.exit(1)

    try:
        # 创建 LLM 客户端并获取智能体列表
        agent_list = await get_agent_list(config_manager, logger)

        # 获取当前默认智能体
        current_agent = get_current_agent(config_manager, agent_list)

        # 运行选择应用
        selected_agent = await run_agent_selector(agent_list, current_agent)

        # 处理选择结果
        handle_agent_selection(config_manager, selected_agent)

    except (OSError, ValueError, RuntimeError) as e:
        log_exception(logger, "智能体选择功能发生错误", e)
        sys.stderr.write(_("错误: {error}\n").format(error=str(e)))
        sys.exit(1)
