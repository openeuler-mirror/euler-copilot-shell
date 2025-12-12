"""智能体相关对话框组件"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

    from textual.app import ComposeResult
    from textual.events import Key as KeyEvent

from textual.containers import Container
from textual.screen import ModalScreen
from textual.widgets import Label, Static

from i18n.manager import _


class BackendRequiredDialog(ModalScreen):
    """后端要求提示对话框"""

    def compose(self) -> ComposeResult:
        """构建后端要求提示对话框"""
        yield Container(
            Container(
                Label(_("智能体功能提示"), id="backend-dialog-title"),
                Label(_("请选择 Witty Assistant 后端来使用智能体功能"), id="backend-dialog-text"),
                Label(_("按任意键关闭"), id="backend-dialog-help"),
                id="backend-dialog",
            ),
            id="backend-dialog-screen",
        )

    def on_key(self, event: KeyEvent) -> None:
        """处理键盘事件 - 任意键关闭对话框"""
        self.app.pop_screen()


class AgentSelectionDialog(ModalScreen):
    """智能体选择对话框"""

    def __init__(
        self,
        agents: list[tuple[str, str]],
        callback: Callable[[tuple[str, str]], None],
        current_agent: tuple[str, str] | None = None,
    ) -> None:
        """
        初始化智能体选择对话框

        Args:
            agents: 智能体列表，格式为 [(app_id, name), ...]
                    第一项为("", "智能问答")表示无智能体
            callback: 选择完成后的回调函数
            current_agent: 当前已选中的智能体

        """
        super().__init__()
        self.current_agent = current_agent or ("", _("智能问答"))
        self.callback = callback

        # 重新排序智能体列表：智能问答永远第一，当前智能体（如果不是智能问答）排第二
        self.agents = self._reorder_agents(agents)

        # 滚动显示相关变量
        self.min_visible_items = 3  # 最少显示的智能体数量
        self.default_visible_items = 5  # 默认可见项目数量，会根据实际高度动态调整
        self.view_start = 0  # 当前显示区域的起始索引

        # 设置初始光标位置为当前已选中的智能体
        self.selected_index = 0
        for i, agent in enumerate(self.agents):
            if agent[0] == self.current_agent[0]:  # 按 app_id 匹配
                self.selected_index = i
                break

    def _calculate_visible_items(self) -> int:
        """
        根据对话框的实际显示高度动态计算可见项目数量

        Returns:
            可显示的智能体项目数量

        """
        try:
            # 尝试获取对话框容器的高度
            dialog_container = self.query_one("#agent-dialog", Container)
            container_height = dialog_container.size.height

            # 计算可用于显示智能体列表的高度
            # 减去标题、帮助文本等固定元素的高度
            title_height = 5  # 标题行
            help_height = 5  # 帮助文本行
            padding_height = 4  # 上下 padding

            available_height = container_height - title_height - help_height - padding_height

            # 每个智能体项目占用1行，确保至少显示最小数量
            return max(self.min_visible_items, min(available_height, len(self.agents)))

        except (AttributeError, ValueError, RuntimeError):
            # 如果无法获取高度信息，使用默认值
            return self.default_visible_items

    def compose(self) -> ComposeResult:
        """构建智能体选择对话框"""
        # 使用 Static 组件显示文本，启用 Rich markup
        agent_content = Static("", markup=True, id="agent-content")

        yield Container(
            Container(
                Label(_("OS 智能助手"), id="agent-dialog-title"),
                agent_content,
                Label(_("使用上下键选择，回车确认，ESC取消 | ✓ 表示当前选中"), id="agent-dialog-help"),
                id="agent-dialog",
            ),
            id="agent-dialog-screen",
        )

    def on_key(self, event: KeyEvent) -> None:
        """处理键盘事件"""
        if event.key == "escape":
            self.app.pop_screen()
            event.stop()
        elif event.key == "enter":
            # 确保有智能体可选择
            if self.agents and 0 <= self.selected_index < len(self.agents):
                selected_agent = self.agents[self.selected_index]
            else:
                selected_agent = ("", _("智能问答"))
            self.callback(selected_agent)
            self.app.pop_screen()
            event.stop()
        elif event.key == "up" and self.selected_index > 0:
            self.selected_index -= 1
            self._adjust_view_to_selection()
            self._update_display()
        elif event.key == "down" and self.selected_index < len(self.agents) - 1:
            self.selected_index += 1
            self._adjust_view_to_selection()
            self._update_display()

    def on_mount(self) -> None:
        """挂载时设置初始显示"""
        self._adjust_view_to_selection()
        self._update_display()

    def on_resize(self) -> None:
        """窗口大小变化时重新计算显示"""
        # 重新调整视图位置和更新显示
        self._adjust_view_to_selection()
        self._update_display()

    def _update_display(self) -> None:
        """更新显示内容"""
        # 动态计算当前可显示的项目数量
        current_visible_items = self._calculate_visible_items()

        # 计算可见区域的智能体
        visible_agents = self.agents[self.view_start : self.view_start + current_visible_items]

        # 生成文本内容
        agent_text_lines = []

        # 显示可见的智能体
        for i, (app_id, name) in enumerate(visible_agents):
            actual_index = self.view_start + i
            is_cursor = actual_index == self.selected_index
            is_current = app_id == self.current_agent[0]

            if is_cursor and is_current:
                # 光标在当前已选中的智能体上：绿底白字 + 勾选符号
                agent_text_lines.append(f"[white on green]► ✓ {name}[/white on green]")
            elif is_cursor:
                # 光标在其他智能体上：蓝底白字
                agent_text_lines.append(f"[white on blue]►   {name}[/white on blue]")
            elif is_current:
                # 当前已选中但光标不在这里：显示勾选符号
                agent_text_lines.append(f"[bright_green]  ✓ {name}[/bright_green]")
            else:
                # 普通状态：亮白字
                agent_text_lines.append(f"[bright_white]    {name}[/bright_white]")

        # 如果没有智能体，添加默认选项
        if not agent_text_lines:
            agent_text_lines.append(f"[white on green]► ✓ {_('智能问答')}[/white on green]")

        # 更新 Static 组件的内容
        try:
            agent_content = self.query_one("#agent-content", Static)
            agent_content.update("\n".join(agent_text_lines))
        except (AttributeError, ValueError, RuntimeError):
            # 如果查找失败，忽略错误
            pass

    def _reorder_agents(self, agents: list[tuple[str, str]]) -> list[tuple[str, str]]:
        """
        重新排序智能体列表

        规则：
        1. 智能问答永远排第一
        2. 如果当前智能体不是智能问答，排第二
        3. 其他智能体保持原有顺序
        """
        if not agents:
            return [("", _("智能问答"))]

        # 查找智能问答和当前智能体
        default_qa = ("", _("智能问答"))
        current_agent = self.current_agent

        reordered = []
        remaining = []

        # 第一步：处理所有智能体，分类收集
        current_found = False

        for agent in agents:
            if agent[0] == "":  # 智能问答
                # 智能问答不加入 remaining，会单独处理
                pass
            elif agent[0] == current_agent[0] and current_agent[0] != "":  # 当前智能体且不是智能问答
                current_found = True
                # 当前智能体不加入 remaining，会单独处理
            else:
                remaining.append(agent)

        # 第一项：智能问答
        reordered.append(default_qa)

        # 第二项：如果当前智能体不是智能问答且存在，加入第二位
        if current_found and current_agent[0] != "":
            reordered.append(current_agent)

        # 其余项：保持原有顺序
        reordered.extend(remaining)

        return reordered

    def _adjust_view_to_selection(self) -> None:
        """调整视图位置，确保选中项在可见区域内"""
        # 动态计算当前可显示的项目数量
        current_visible_items = self._calculate_visible_items()

        if len(self.agents) <= current_visible_items:
            # 如果总数不超过可显示数量，显示全部
            self.view_start = 0
            return

        # 确保选中项在可见区域内
        if self.selected_index < self.view_start:
            # 选中项在可见区域上方，向上滚动
            self.view_start = self.selected_index
        elif self.selected_index >= self.view_start + current_visible_items:
            # 选中项在可见区域下方，向下滚动
            self.view_start = self.selected_index - current_visible_items + 1

        # 确保 view_start 不超出范围
        max_start = max(0, len(self.agents) - current_visible_items)
        self.view_start = max(0, min(self.view_start, max_start))
