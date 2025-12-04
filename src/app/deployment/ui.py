"""
部署配置 TUI 界面

提供用户友好的部署配置界面。
"""

from __future__ import annotations

import asyncio
import contextlib
from enum import Enum
from typing import TYPE_CHECKING

from rich.errors import MarkupError
from textual import on
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Input,
    Label,
    RichLog,
    Static,
    TabbedContent,
    TabPane,
)

from app.tui_header import OIHeader
from i18n.manager import _

from .models import DeploymentConfig, DeploymentState, EmbeddingConfig, LLMConfig
from .service import DeploymentService

if TYPE_CHECKING:
    from textual.app import ComposeResult

FULL_PROGRESS = 100


class ValidationStatus(Enum):
    """验证状态枚举"""

    PENDING = "pending"
    VALIDATING = "validating"
    VALID = "valid"
    INVALID = "invalid"
    NOT_REQUIRED = "not_required"


class DeploymentConfigScreen(ModalScreen[bool]):
    """
    部署配置屏幕

    允许用户配置部署参数的模态对话框。
    """

    CSS = """
    DeploymentConfigScreen {
        align: center middle;
    }

    .config-container {
        width: 95%;
        max-width: 130;
        height: 95%;
        background: $surface;
        border: solid $primary;
        padding: 0 1;
    }

    .form-row {
        height: 3;
        margin: 0;
    }

    .form-label {
        width: 18;
        text-align: left;
        text-style: bold;
        content-align: left middle;
    }

    .form-input {
        width: 1fr;
        margin-left: 1;
    }

    .button-row {
        height: 3;
        margin: 1 0 0 0;
        align: center middle;
    }

    #llm_validation_status, #embedding_validation_status {
        text-style: italic;
    }

    #deploy, #cancel {
        margin: 0 1;
        width: auto;
        min-height: 3;
        height: 3;
    }

    TabbedContent {
        height: 1fr;
    }

    TabPane {
        height: auto;
        scrollbar-size: 1 1;
        overflow: auto;
    }

    .llm-config-container, .embedding-config-container {
        height: 1fr;
        scrollbar-size: 1 1;
        overflow-y: auto;
        overflow-x: hidden;
    }
    """

    def __init__(self) -> None:
        """初始化部署配置屏幕"""
        super().__init__()
        self.config = DeploymentConfig()

        self._llm_validation_task: asyncio.Task[None] | None = None
        self._embedding_validation_task: asyncio.Task[None] | None = None

        # 验证状态跟踪
        self.llm_validation_status: ValidationStatus = ValidationStatus.PENDING
        self.embedding_validation_status: ValidationStatus = ValidationStatus.PENDING

    def compose(self) -> ComposeResult:
        """组合界面组件"""
        with Container(classes="config-container"):
            yield OIHeader()

            with TabbedContent():
                with TabPane(_("LLM 配置"), id="llm"):
                    yield from self._compose_llm_config()

                with TabPane(_("Embedding 配置"), id="embedding"):
                    yield from self._compose_embedding_config()

            with Horizontal(classes="button-row"):
                yield Button(_("开始部署"), id="deploy", variant="success")
                yield Button(_("取消"), id="cancel", variant="error")

    async def on_mount(self) -> None:
        """界面挂载时初始化状态"""
        # 初始化验证状态
        self._initialize_validation_status()

    def _initialize_validation_status(self) -> None:
        """初始化验证状态"""
        if self._is_embedding_required():
            self.embedding_validation_status = ValidationStatus.PENDING
        else:
            self.embedding_validation_status = ValidationStatus.NOT_REQUIRED
            try:
                embedding_status = self.query_one("#embedding_validation_status", Static)
                embedding_status.update(_("[dim]不需要验证[/dim]"))
            except (ValueError, AttributeError):
                pass

        # 更新部署按钮状态
        self._update_deploy_button_state()

    def _compose_llm_config(self) -> ComposeResult:
        """组合 LLM 配置组件"""
        with Vertical(classes="llm-config-container"):
            yield Static(_("大语言模型配置"), classes="form-label")

            with Horizontal(classes="form-row"):
                yield Label(_("API 端点:"), classes="form-label")
                yield Input(
                    placeholder=_("例如：http://localhost:11434/v1"),
                    id="llm_endpoint",
                    classes="form-input",
                )

            with Horizontal(classes="form-row"):
                yield Label(_("API 密钥:"), classes="form-label")
                yield Input(
                    placeholder="sk-123456",
                    password=True,
                    id="llm_api_key",
                    classes="form-input",
                )

            with Horizontal(classes="form-row"):
                yield Label(_("模型名称:"), classes="form-label")
                yield Input(
                    placeholder=_("例如：deepseek-llm-7b-chat"),
                    id="llm_model",
                    classes="form-input",
                )

            with Horizontal(classes="form-row"):
                yield Label(_("验证状态:"), classes="form-label")
                yield Static(_("未验证"), id="llm_validation_status", classes="form-input")

            with Horizontal(classes="form-row"):
                yield Label(_("最大输出令牌数:"), classes="form-label")
                yield Input(
                    value="8192",
                    id="llm_max_tokens",
                    classes="form-input",
                )

            with Horizontal(classes="form-row"):
                yield Label(_("上下文长度:"), classes="form-label")
                yield Input(
                    value="128000",
                    id="llm_ctx_length",
                    classes="form-input",
                )

            with Horizontal(classes="form-row"):
                yield Label(_("Temperature:"), classes="form-label")
                yield Input(
                    value="0.7",
                    id="llm_temperature",
                    classes="form-input",
                )

            with Horizontal(classes="form-row"):
                yield Label(_("请求超时 (秒):"), classes="form-label")
                yield Input(
                    value="300",
                    id="llm_timeout",
                    classes="form-input",
                )

    def _compose_embedding_config(self) -> ComposeResult:
        """组合 Embedding 配置组件"""
        with Vertical(classes="embedding-config-container"):
            yield Static(_("嵌入模型配置"), classes="form-label")

            yield Static(
                _("[dim]Embedding 配置为可选项；若需启用 RAG 功能，请填写以下信息。[/dim]"),
                classes="form-input",
            )

            with Horizontal(classes="form-row"):
                yield Label(_("API 端点:"), classes="form-label")
                yield Input(
                    placeholder=_("例如：http://localhost:11434/v1"),
                    id="embedding_endpoint",
                    classes="form-input",
                )

            with Horizontal(classes="form-row"):
                yield Label(_("API 密钥:"), classes="form-label")
                yield Input(
                    placeholder="sk-123456",
                    password=True,
                    id="embedding_api_key",
                    classes="form-input",
                )

            with Horizontal(classes="form-row"):
                yield Label(_("模型名称:"), classes="form-label")
                yield Input(
                    placeholder=_("例如：bge-m3"),
                    id="embedding_model",
                    classes="form-input",
                )

            with Horizontal(classes="form-row"):
                yield Label(_("验证状态:"), classes="form-label")
                yield Static(_("未验证"), id="embedding_validation_status", classes="form-input")

            with Horizontal(classes="form-row"):
                yield Label(_("上下文长度:"), classes="form-label")
                yield Input(
                    value="8192",
                    id="embedding_ctx_length",
                    classes="form-input",
                )

    @on(Button.Pressed, "#deploy")
    async def on_deploy_button_pressed(self) -> None:
        """处理部署按钮点击"""
        if self._collect_config():
            # 基础配置验证
            is_valid, errors = self.config.validate()
            if not is_valid:
                await self.app.push_screen(
                    ErrorMessageScreen(_("配置验证失败"), errors),
                )
                return

            # 所有验证通过，开始部署
            await self.app.push_screen(DeploymentProgressScreen(self.config))

    @on(Button.Pressed, "#cancel")
    def on_cancel_button_pressed(self) -> None:
        """处理取消按钮点击"""
        # 退出整个程序
        self.app.exit()

    @on(Input.Changed, "#llm_endpoint, #llm_api_key, #llm_model")
    async def on_llm_field_changed(self, event: Input.Changed) -> None:
        """处理 LLM 字段变化，检查是否需要自动验证"""
        # 重置 LLM 验证状态
        self.llm_validation_status = ValidationStatus.PENDING

        # 取消之前的验证任务
        if self._llm_validation_task and not self._llm_validation_task.done():
            self._llm_validation_task.cancel()

        # 更新部署按钮状态
        self._update_deploy_button_state()

        # 检查是否需要验证
        if self._should_validate_llm():
            # 延迟 1 秒后进行验证，避免用户快速输入时频繁触发
            self._llm_validation_task = asyncio.create_task(self._delayed_llm_validation())

    @on(Input.Changed, "#embedding_endpoint, #embedding_api_key, #embedding_model")
    async def on_embedding_field_changed(self, event: Input.Changed) -> None:
        """处理 Embedding 字段变化，检查是否需要自动验证"""
        # 重置 Embedding 验证状态
        if self._is_embedding_required():
            self.embedding_validation_status = ValidationStatus.PENDING
        else:
            self.embedding_validation_status = ValidationStatus.NOT_REQUIRED

        # 取消之前的验证任务
        if self._embedding_validation_task and not self._embedding_validation_task.done():
            self._embedding_validation_task.cancel()

        # 更新部署按钮状态
        self._update_deploy_button_state()

        # 检查是否需要验证
        if self._should_validate_embedding():
            # 延迟 1 秒后进行验证，避免用户快速输入时频繁触发
            self._embedding_validation_task = asyncio.create_task(self._delayed_embedding_validation())

    def _should_validate_llm(self) -> bool:
        """检查是否应该验证 LLM 配置"""
        try:
            return bool(self.query_one("#llm_endpoint", Input).value.strip())
        except (AttributeError, ValueError):
            return False

    def _should_validate_embedding(self) -> bool:
        """检查是否应该验证 Embedding 配置"""
        try:
            return bool(self.query_one("#embedding_endpoint", Input).value.strip())
        except (AttributeError, ValueError):
            return False

    async def _delayed_llm_validation(self) -> None:
        """延迟 LLM 验证"""
        try:
            await asyncio.sleep(1)  # 等待 1 秒
            await self._validate_llm_config()
        except asyncio.CancelledError:
            pass

    async def _delayed_embedding_validation(self) -> None:
        """延迟 Embedding 验证"""
        try:
            await asyncio.sleep(1)  # 等待 1 秒
            await self._validate_embedding_config()
        except asyncio.CancelledError:
            pass

    def _is_embedding_required(self) -> bool:
        """检查是否需要验证 Embedding 配置"""
        try:
            endpoint = self.query_one("#embedding_endpoint", Input).value.strip()
            api_key = self.query_one("#embedding_api_key", Input).value.strip()
            model = self.query_one("#embedding_model", Input).value.strip()
            return bool(endpoint or api_key or model)

        except (AttributeError, ValueError):
            return False

    def _update_deploy_button_state(self) -> None:
        """根据验证状态更新部署按钮状态"""
        try:
            deploy_button = self.query_one("#deploy", Button)

            # 检查 LLM 验证状态
            if self.llm_validation_status in (
                ValidationStatus.PENDING,
                ValidationStatus.VALIDATING,
                ValidationStatus.INVALID,
            ):
                deploy_button.disabled = True
                return

            # 检查 Embedding 验证状态
            if self._is_embedding_required() and self.embedding_validation_status in (
                ValidationStatus.PENDING,
                ValidationStatus.VALIDATING,
                ValidationStatus.INVALID,
            ):
                deploy_button.disabled = True
                return

            # 所有必要的验证都通过，启用部署按钮
            deploy_button.disabled = False

        except (ValueError, AttributeError):
            # 如果出现异常，为安全起见禁用部署按钮
            pass

    async def _validate_llm_config(self) -> None:
        """验证 LLM 配置"""
        # 更新状态为验证中
        self.llm_validation_status = ValidationStatus.VALIDATING
        status_widget = self.query_one("#llm_validation_status", Static)
        status_widget.update("[yellow]验证中...[/yellow]")
        self._update_deploy_button_state()

        # 收集当前 LLM 配置
        self._collect_llm_config()

        try:
            # 执行验证
            is_valid, message, info = await self.config.validate_llm_connectivity()

            # 更新验证状态
            if is_valid:
                # 检查是否支持工具调用
                supports_function_call = info.get("supports_function_call", False)
                if supports_function_call:
                    self.llm_validation_status = ValidationStatus.VALID
                    status_widget.update(_("[green]✓ {message}[/green]").format(message=message))
                else:
                    self.llm_validation_status = ValidationStatus.INVALID
                    status_widget.update(_("[red]✗ 不支持工具调用[/red]"))
                    self.notify(
                        _("LLM 验证失败：模型不支持工具调用功能，无法用于部署。请选择支持工具调用的模型。"),
                        severity="error",
                    )
            else:
                self.llm_validation_status = ValidationStatus.INVALID
                status_widget.update(_("[red]✗ {message}[/red]").format(message=message))

        except (OSError, ValueError, TypeError) as e:
            self.llm_validation_status = ValidationStatus.INVALID
            status_widget.update(_("[red]✗ 验证异常: {error}[/red]").format(error=e))

        # 更新部署按钮状态
        self._update_deploy_button_state()

    async def _validate_embedding_config(self) -> None:
        """验证 Embedding 配置"""
        # 更新状态为验证中
        self.embedding_validation_status = ValidationStatus.VALIDATING
        status_widget = self.query_one("#embedding_validation_status", Static)
        status_widget.update("[yellow]验证中...[/yellow]")
        self._update_deploy_button_state()

        # 收集当前 Embedding 配置
        self._collect_embedding_config()

        try:
            # 执行验证
            is_valid, message, info = await self.config.validate_embedding_connectivity()

            # 更新验证状态
            if is_valid:
                self.embedding_validation_status = ValidationStatus.VALID
                dimension = info.get("dimension", "未知")
                status_widget.update(_("[green]✓ {message} (维度: {dimension})[/green]").format(
                    message=message,
                    dimension=dimension,
                ))
            else:
                self.embedding_validation_status = ValidationStatus.INVALID
                status_widget.update(_("[red]✗ {message}[/red]").format(message=message))

        except (OSError, ValueError, TypeError) as e:
            self.embedding_validation_status = ValidationStatus.INVALID
            status_widget.update(_("[red]✗ 验证异常: {error}[/red]").format(error=e))

        # 更新部署按钮状态
        self._update_deploy_button_state()

    def _collect_llm_config(self) -> None:
        """收集 LLM 配置"""
        try:
            self.config.llm.endpoint = self.query_one("#llm_endpoint", Input).value.strip()
            self.config.llm.api_key = self.query_one("#llm_api_key", Input).value.strip()
            self.config.llm.model = self.query_one("#llm_model", Input).value.strip()
            self.config.llm.max_tokens = int(self.query_one("#llm_max_tokens", Input).value or "8192")
            self.config.llm.ctx_length = int(self.query_one("#llm_ctx_length", Input).value or "128000")
            self.config.llm.temperature = float(self.query_one("#llm_temperature", Input).value or "0.7")
            self.config.llm.request_timeout = int(self.query_one("#llm_timeout", Input).value or "300")
        except (ValueError, AttributeError):
            # 如果转换失败，使用默认值
            pass

    def _collect_embedding_config(self) -> None:
        """收集 Embedding 配置"""
        try:
            # 固定使用 openai 类型
            self.config.embedding.type = "openai"
            self.config.embedding.endpoint = self.query_one("#embedding_endpoint", Input).value.strip()
            self.config.embedding.api_key = self.query_one("#embedding_api_key", Input).value.strip()
            self.config.embedding.model = self.query_one("#embedding_model", Input).value.strip()
            self.config.embedding.ctx_length = int(
                self.query_one("#embedding_ctx_length", Input).value or "8192",
            )
        except (ValueError, AttributeError):
            # 如果获取失败，使用默认值
            pass

    def _collect_config(self) -> bool:
        """收集用户配置"""
        try:
            # LLM 配置
            self.config.llm = LLMConfig(
                endpoint=self.query_one("#llm_endpoint", Input).value.strip(),
                api_key=self.query_one("#llm_api_key", Input).value.strip(),
                model=self.query_one("#llm_model", Input).value.strip(),
                max_tokens=int(self.query_one("#llm_max_tokens", Input).value or "8192"),
                ctx_length=int(self.query_one("#llm_ctx_length", Input).value or "128000"),
                temperature=float(self.query_one("#llm_temperature", Input).value or "0.7"),
                request_timeout=int(self.query_one("#llm_timeout", Input).value or "300"),
            )

            # Embedding 配置
            self.config.embedding = EmbeddingConfig(
                type="openai",  # 固定使用 openai 类型
                endpoint=self.query_one("#embedding_endpoint", Input).value.strip(),
                api_key=self.query_one("#embedding_api_key", Input).value.strip(),
                model=self.query_one("#embedding_model", Input).value.strip(),
                ctx_length=int(self.query_one("#embedding_ctx_length", Input).value or "8192"),
            )

        except (ValueError, AttributeError) as e:
            # 处理输入转换错误
            self.notify(f"配置输入错误: {e}", severity="error")
            return False
        else:
            return True


class DeploymentProgressScreen(ModalScreen[bool]):
    """
    部署进度屏幕

    显示部署进度和日志的模态对话框。
    """

    CSS = """
    DeploymentProgressScreen {
        align: center middle;
    }

    .progress-container {
        width: 95%;
        max-width: 130;
        height: 95%;
        background: $surface;
        border: solid $primary;
        padding: 1;
    }

    .progress-section {
        margin: 1 0;
        height: auto;
        min-height: 6;
    }

    #step_label {
        min-height: 1;
        height: auto;
        color: $primary;
    }

    .log-section {
        margin: 1 0;
        height: 1fr;
        border: solid $secondary;
    }

    .button-section {
        height: 3;
        margin: 1 0;
        align: center middle;
    }
    """

    def __init__(self, config: DeploymentConfig) -> None:
        """
        初始化部署进度屏幕

        Args:
            config: 部署配置

        """
        super().__init__()
        self.config = config
        self.service = DeploymentService()
        self.deployment_task: asyncio.Task[None] | None = None
        self.deployment_success = False
        self.deployment_cancelled = False
        self.deployment_errors: list[str] = []
        self.deployment_progress_value = 0
        self.latest_log: str = ""

    def compose(self) -> ComposeResult:
        """组合界面组件"""
        with Container(classes="progress-container"):
            yield OIHeader()

            with Vertical(classes="progress-section"):
                yield Static(_("部署进度:"), id="progress_label")
                yield Static(_("准备开始部署..."), id="step_label")

            with Container(classes="log-section"):
                yield RichLog(id="deployment_log", highlight=True, markup=True)

            with Horizontal(classes="button-section"):
                yield Button(_("完成"), id="finish", variant="success", disabled=True)
                yield Button(_("重试"), id="retry", variant="warning", disabled=True)
                yield Button(_("重新配置"), id="reconfigure", variant="primary", disabled=True)
                yield Button(_("取消部署"), id="cancel", variant="error")

    async def on_mount(self) -> None:
        """界面挂载时开始部署"""
        await self._start_deployment()

    @on(Button.Pressed, "#finish")
    def on_finish_button_pressed(self) -> None:
        """处理完成按钮点击"""
        self.app.exit()

    @on(Button.Pressed, "#retry")
    async def on_retry_button_pressed(self) -> None:
        """处理重试按钮点击"""
        # 重置界面状态
        self._reset_ui_for_retry()
        # 重新开始部署
        await self._start_deployment()

    @on(Button.Pressed, "#reconfigure")
    async def on_reconfigure_button_pressed(self) -> None:
        """处理重新配置按钮点击"""
        # 关闭当前屏幕，返回配置屏幕
        self.dismiss(result=False)

    @on(Button.Pressed, "#cancel")
    async def on_cancel_button_pressed(self) -> None:
        """处理取消按钮点击"""
        if self.deployment_task and not self.deployment_task.done():
            # 取消部署任务
            self.service.cancel_deployment()
            self.deployment_task.cancel()
            self.deployment_cancelled = True

            # 更新界面
            self.query_one("#step_label", Static).update(_("部署已取消"))
            self.query_one("#deployment_log", RichLog).write(_("部署已被用户取消"))

            # 等待任务真正结束
            with contextlib.suppress(asyncio.CancelledError):
                await self.deployment_task

            # 更新按钮状态
            self._update_buttons_after_failure()
        else:
            # 如果部署已完成或未开始，直接退出
            self.app.exit()

    def _reset_ui_for_retry(self) -> None:
        """重置界面用于重试"""
        # 取消之前的任务
        if self.deployment_task and not self.deployment_task.done():
            self.deployment_task.cancel()
        self.deployment_task = None

        # 清空日志
        log_widget = self.query_one("#deployment_log", RichLog)
        log_widget.clear()

        # 重置状态
        self.deployment_success = False
        self.deployment_cancelled = False
        self.deployment_errors.clear()
        self.deployment_progress_value = 0  # 重置进度记录
        self.latest_log = ""

        # 重置进度
        self.query_one("#step_label", Static).update("")

        # 重置按钮状态
        self.query_one("#finish", Button).disabled = True
        self.query_one("#retry", Button).disabled = True
        self.query_one("#reconfigure", Button).disabled = True
        self.query_one("#cancel", Button).disabled = False

    def _update_buttons_after_failure(self) -> None:
        """部署失败后更新按钮状态"""
        self.query_one("#finish", Button).disabled = True
        self.query_one("#retry", Button).disabled = False
        self.query_one("#reconfigure", Button).disabled = False
        self.query_one("#cancel", Button).disabled = False

    def _update_buttons_after_success(self) -> None:
        """部署成功后更新按钮状态"""
        self.query_one("#finish", Button).disabled = False
        self.query_one("#retry", Button).disabled = True
        self.query_one("#reconfigure", Button).disabled = True
        self.query_one("#cancel", Button).disabled = True

    async def _start_deployment(self) -> None:
        """开始部署流程"""
        try:
            # 创建异步任务但不等待，让它在后台运行
            self.deployment_task = asyncio.create_task(self._execute_deployment())

            # 启动一个定时器来检查任务状态
            self.set_interval(0.1, self._check_deployment_status)

        except (OSError, RuntimeError) as e:
            self.query_one("#step_label", Static).update(_("部署启动失败"))
            self.query_one("#deployment_log", RichLog).write(_("部署启动失败: {error}").format(error=e))
            self._update_buttons_after_failure()

    def _check_deployment_status(self) -> None:
        """检查部署任务状态"""
        if self.deployment_task is None:
            return

        if self.deployment_task.done():
            # 任务完成，停止定时器
            try:
                # 获取任务结果，如果有异常会在这里抛出
                self.deployment_task.result()
            except asyncio.CancelledError:
                if not self.deployment_cancelled:
                    self.deployment_cancelled = True
                    self.query_one("#step_label", Static).update(_("部署已取消"))
                    self.query_one("#deployment_log", RichLog).write(_("部署被取消"))
                    self._update_buttons_after_failure()
            except (OSError, RuntimeError, ValueError) as e:
                self.query_one("#step_label", Static).update(_("部署异常"))
                self.query_one("#deployment_log", RichLog).write(_("部署异常: {error}").format(error=e))
                self._update_buttons_after_failure()

    async def _execute_deployment(self) -> None:
        """执行部署过程"""
        try:
            # 步骤1：检查并安装依赖
            self.query_one("#step_label", Static).update(_("正在检查部署环境..."))
            success, errors = await self.service.check_and_install_dependencies(self._on_progress_update)

            if not success:
                self.query_one("#step_label", Static).update(_("环境检查失败"))
                for error in errors:
                    self.query_one("#deployment_log", RichLog).write(f"[red]✗ {error}[/red]")
                    self.deployment_errors.append(error)
                self._update_buttons_after_failure()
                return

            # 步骤2：执行部署
            self.query_one("#step_label", Static).update(_("正在执行部署..."))
            success = await self.service.deploy(self.config, self._on_progress_update)

            # 更新界面状态
            if success:
                self.deployment_success = True

                self.query_one("#step_label", Static).update(_("部署完成！"))
                self.query_one("#deployment_log", RichLog).write(
                    _("[bold green]部署成功完成！[/bold green]"),
                )
                self._update_buttons_after_success()
                self.notify(_("部署成功完成！"), severity="information")
            else:
                self.query_one("#step_label", Static).update(_("部署失败"))
                self.query_one("#deployment_log", RichLog).write(
                    _("[bold red]部署失败，请查看上面的错误信息[/bold red]"),
                )
                self.deployment_errors.append(_("部署执行失败"))
                self._update_buttons_after_failure()
                self.notify(_("部署失败，可以重试或重新配置参数"), severity="error")

        except OSError as e:
            error_msg = _("部署过程中发生异常: {error}").format(error=e)
            self.query_one("#step_label", Static).update(_("部署异常"))
            self.query_one("#deployment_log", RichLog).write(f"[bold red]{error_msg}[/bold red]")
            self.deployment_errors.append(error_msg)
            self._update_buttons_after_failure()

    def _on_progress_update(self, state: DeploymentState) -> None:
        """处理进度更新"""
        # 更新进度条
        completed_steps = max(0, state.current_step - 1)  # 前面的步骤已完成
        progress = (completed_steps / state.total_steps * FULL_PROGRESS) if state.total_steps > 0 else 0

        # 记录最后的真实进度值，但避免倒退（除非是重置操作）
        # 只有在进度实际前进或者是初始状态时才更新
        if progress >= self.deployment_progress_value or self.deployment_progress_value == 0:
            self.deployment_progress_value = progress

        # 更新步骤标签
        step_text = _("步骤 {current}/{total}: {name}").format(
            current=state.current_step,
            total=state.total_steps,
            name=state.current_step_name,
        )
        self.query_one("#step_label", Static).update(step_text)

        # 添加最新的日志条目
        log_widget = self.query_one("#deployment_log", RichLog)
        if state.output_log and self.latest_log != state.output_log[-1]:
            # 只显示最新的日志条目
            self.latest_log = state.output_log[-1]
            try:
                if self.latest_log.startswith("✓"):
                    log_widget.write(f"[green]{self.latest_log}[/green]")
                elif self.latest_log.startswith("✗"):
                    log_widget.write(f"[red]{self.latest_log}[/red]")
                else:
                    log_widget.write(self.latest_log)
            except MarkupError:
                # 忽略日志消息格式错误
                pass


class ErrorMessageScreen(ModalScreen[None]):
    """
    错误消息屏幕

    显示错误消息的模态对话框。
    """

    CSS = """
    ErrorMessageScreen {
        align: center middle;
    }

    .error-container {
        width: 60%;
        max-width: 80;
        height: auto;
        background: $surface;
        border: solid $error;
        padding: 1;
    }

    .error-title {
        color: $error;
        text-style: bold;
        margin: 1 0;
    }

    .error-list {
        margin: 1 0;
        max-height: 20;
    }
    """

    def __init__(self, title: str, messages: list[str]) -> None:
        """
        初始化错误消息屏幕

        Args:
            title: 错误标题
            messages: 错误消息列表

        """
        super().__init__()
        self.title = title
        self.messages = messages

    def compose(self) -> ComposeResult:
        """组合界面组件"""
        with Container(classes="error-container"):
            yield Static(self.title or _("错误"), classes="error-title")

            with Vertical(classes="error-list"):
                for message in self.messages:
                    yield Static(f"• {message}")

            yield Button(_("确定"), id="ok", variant="primary")

    @on(Button.Pressed, "#ok")
    def on_ok_button_pressed(self) -> None:
        """处理确定按钮点击"""
        self.dismiss()
