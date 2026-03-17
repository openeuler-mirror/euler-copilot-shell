"""
环境检查

在进入部署配置之前先检查系统环境是否满足要求。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual import on
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Static,
)

from app.deployment.service import DeploymentService
from app.deployment.ui import DeploymentConfigScreen
from i18n.manager import _

if TYPE_CHECKING:
    from textual.app import ComposeResult


class EnvironmentCheckScreen(ModalScreen[bool]):
    """
    环境检查屏幕

    在进入部署配置之前先检查系统环境是否满足要求。
    """

    CSS = """
    EnvironmentCheckScreen {
        align: center middle;
    }

    .check-container {
        width: 70%;
        max-width: 80;
        height: 60%;
        background: $surface;
        border: solid $primary;
        padding: 1;
    }

    .check-title {
        text-style: bold;
        color: $primary;
        margin: 0 0 2 0;
        text-align: center;
    }

    .check-item {
        margin: 1 0;
        height: 3;
    }

    .check-status {
        width: 4;
        text-align: center;
    }

    .check-description {
        width: 1fr;
        margin-left: 2;
    }

    .button-row {
        height: 3;
        margin: 2 0 0 0;
        align: center middle;
        dock: bottom;
    }

    .continue-button, .back-button, .exit-button {
        margin: 0 1;
    }
    """

    def __init__(self) -> None:
        """初始化环境检查屏幕"""
        super().__init__()
        self.service = DeploymentService()
        self.check_results: dict[str, bool] = {}
        self.error_messages: list[str] = []

    def compose(self) -> ComposeResult:
        """组合界面组件"""
        with Container(classes="check-container"):
            yield Static(_("环境检查"), classes="check-title")

            with Horizontal(classes="check-item"):
                yield Static("", id="os_status", classes="check-status")
                yield Static(_("检查操作系统类型..."), id="os_desc", classes="check-description")

            with Horizontal(classes="check-item"):
                yield Static("", id="sudo_status", classes="check-status")
                yield Static(_("检查管理员权限..."), id="sudo_desc", classes="check-description")

            with Horizontal(classes="button-row"):
                yield Button(_("继续配置"), id="continue", variant="success", classes="continue-button", disabled=True)
                yield Button(_("返回"), id="back", variant="primary", classes="back-button")
                yield Button(_("退出"), id="exit", variant="error", classes="exit-button")

    async def on_mount(self) -> None:
        """界面挂载时开始环境检查"""
        await self._perform_environment_check()

    async def _perform_environment_check(self) -> None:
        """执行环境检查"""
        try:
            # 检查操作系统
            await self._check_operating_system()

            # 检查 sudo 权限
            await self._check_sudo_privileges()

            # 更新界面状态
            self._update_ui_state()

        except (OSError, RuntimeError) as e:
            self.notify(_("环境检查过程中发生异常: {error}").format(error=e), severity="error")

    async def _check_operating_system(self) -> None:
        """检查操作系统类型"""
        try:
            is_openeuler = self.service.detect_openeuler()
            self.check_results["os"] = is_openeuler

            os_status = self.query_one("#os_status", Static)
            os_desc = self.query_one("#os_desc", Static)

            if is_openeuler:
                os_status.update("[green]✓[/green]")
                os_desc.update(_("操作系统: openEuler (支持)"))
            else:
                os_status.update("[red]✗[/red]")
                os_desc.update(_("操作系统: 非 openEuler (不支持)"))
                self.error_messages.append(_("仅支持 openEuler 操作系统"))

        except (OSError, RuntimeError) as e:
            self.check_results["os"] = False
            self.query_one("#os_status", Static).update("[red]✗[/red]")
            self.query_one("#os_desc", Static).update(_("操作系统检查失败: {error}").format(error=e))
            self.error_messages.append(_("操作系统检查异常: {error}").format(error=e))

    async def _check_sudo_privileges(self) -> None:
        """检查管理员权限"""
        try:
            has_sudo = await self.service.check_sudo_privileges()
            self.check_results["sudo"] = has_sudo

            sudo_status = self.query_one("#sudo_status", Static)
            sudo_desc = self.query_one("#sudo_desc", Static)

            if has_sudo:
                sudo_status.update("[green]✓[/green]")
                sudo_desc.update(_("管理员权限: 可用"))
            else:
                sudo_status.update("[red]✗[/red]")
                sudo_desc.update(_("管理员权限: 不可用 (需要 sudo)"))
                self.error_messages.append(_("需要管理员权限，请确保可以使用 sudo"))

        except (OSError, RuntimeError) as e:
            self.check_results["sudo"] = False
            self.query_one("#sudo_status", Static).update("[red]✗[/red]")
            self.query_one("#sudo_desc", Static).update(_("权限检查失败: {error}").format(error=e))
            self.error_messages.append(_("权限检查异常: {error}").format(error=e))

    def _update_ui_state(self) -> None:
        """更新界面状态"""
        all_checks_passed = all(self.check_results.values())
        continue_button = self.query_one("#continue", Button)
        if all_checks_passed:
            continue_button.disabled = False

    @on(Button.Pressed, "#continue")
    async def on_continue_button_pressed(self) -> None:
        """处理继续按钮点击"""
        self.app.push_screen(DeploymentConfigScreen())

    @on(Button.Pressed, "#back")
    async def on_back_button_pressed(self) -> None:
        """处理返回按钮点击"""
        self.dismiss(result=False)

    @on(Button.Pressed, "#exit")
    def on_exit_button_pressed(self) -> None:
        """处理退出按钮点击"""
        self.app.exit()
