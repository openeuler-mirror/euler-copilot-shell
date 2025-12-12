"""
LLM 配置管理工具

允许用户通过 TUI 界面修改已部署系统的 LLM 和 Embedding 配置。
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import subprocess
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

import toml
from textual import on
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static, TabbedContent, TabPane

from app.deployment.models import EmbeddingConfig, LLMConfig
from app.tui_header import OIHeader
from i18n.manager import _
from log.manager import get_logger
from tool.validators import APIValidator

logger = get_logger(__name__)


class ValidationStatus(Enum):
    """验证状态枚举"""

    PENDING = "pending"
    VALIDATING = "validating"
    VALID = "valid"
    INVALID = "invalid"
    NOT_REQUIRED = "not_required"


@dataclass
class LLMSystemConfig:
    """
    系统 LLM 配置

    管理已部署系统的 LLM 和 Embedding 配置。
    """

    # 系统配置文件路径
    FRAMEWORK_CONFIG_PATH = Path("/etc/euler-copilot-framework/config.toml")
    RAG_ENV_PATH = Path("/etc/euler-copilot-rag/data_chain/env")

    # systemctl 服务名称
    RUNTIME_SERVICE = "oi-runtime"
    RAG_SERVICE = "oi-rag"

    llm: LLMConfig = field(default_factory=LLMConfig)
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    detected_function_call_type: str = field(default="function_call")

    @classmethod
    def check_prerequisites(cls) -> tuple[bool, list[str]]:
        """
        检查前置条件

        Returns:
            tuple[bool, list[str]]: (是否满足条件, 错误消息列表)

        """
        errors = []

        # 检查是否以管理员权限运行
        if os.geteuid() != 0:
            errors.append(_("需要管理员权限才能修改 Witty Assistant 配置文件"))
            # 如果没有管理员权限，直接返回，避免后续的文件操作引发权限错误
            return False, errors

        try:
            # 检查核心配置文件是否存在（必须存在）
            if not cls.FRAMEWORK_CONFIG_PATH.exists():
                errors.append(_("配置文件不存在: {path}").format(path=cls.FRAMEWORK_CONFIG_PATH))
                errors.append(_("请先运行 '(sudo) oi --init' 部署后端服务"))

            # 检查核心配置文件是否可写（必须可写）
            if cls.FRAMEWORK_CONFIG_PATH.exists() and not os.access(cls.FRAMEWORK_CONFIG_PATH, os.W_OK):
                errors.append(_("配置文件不可写: {path}").format(path=cls.FRAMEWORK_CONFIG_PATH))

            # 检查 RAG_ENV_PATH 文件是否可写（如果存在的话）
            if cls.RAG_ENV_PATH.exists() and not os.access(cls.RAG_ENV_PATH, os.W_OK):
                errors.append(_("配置文件不可写: {path}").format(path=cls.RAG_ENV_PATH))

        except PermissionError as e:
            errors.append(_("访问配置文件时权限不足: {error}").format(error=str(e)))
        except OSError as e:
            errors.append(_("访问配置文件时发生错误: {error}").format(error=str(e)))

        return len(errors) == 0, errors

    @classmethod
    def load_current_config(cls) -> LLMSystemConfig:
        """
        从系统配置文件加载当前配置

        Returns:
            LLMSystemConfig: 当前系统配置

        """
        config = cls()

        try:
            # 先从 env 文件加载配置（如果存在，作为基础配置）
            if cls.RAG_ENV_PATH.exists():
                config._load_from_env()

            # 从 config.toml 加载配置（最高优先级，覆盖 env 配置）
            if cls.FRAMEWORK_CONFIG_PATH.exists():
                config._load_from_toml()
            else:
                error_msg = f"核心配置文件不存在: {cls.FRAMEWORK_CONFIG_PATH}"
                raise FileNotFoundError(error_msg)

        except PermissionError as e:
            logger.exception("权限不足，无法访问配置文件")
            error_msg = _("权限不足：无法访问配置文件 {filename}，请以管理员身份运行").format(
                filename=e.filename if hasattr(e, "filename") else "",
            )
            raise PermissionError(error_msg) from e
        except (OSError, ValueError, toml.TomlDecodeError):
            logger.exception("加载系统配置失败")
            raise

        return config

    def save_config(self) -> None:
        """
        保存配置到系统文件

        Raises:
            OSError: 文件操作失败
            ValueError: 配置值无效

        """
        try:
            # 保存到 config.toml（必须存在的文件）
            if self.FRAMEWORK_CONFIG_PATH.exists():
                self._save_to_toml()
            else:
                error_msg = f"核心配置文件不存在，无法保存: {self.FRAMEWORK_CONFIG_PATH}"
                raise FileNotFoundError(error_msg)

            # 保存到 env 文件（可选，仅在文件存在时保存）
            if self.RAG_ENV_PATH.exists():
                self._save_to_env()
                logger.info("已保存到 RAG 环境配置文件")
            else:
                logger.info("RAG 环境配置文件不存在，跳过保存")

            logger.info("系统配置保存成功")

        except (OSError, ValueError, toml.TomlDecodeError):
            logger.exception("保存系统配置失败")
            raise

    def restart_services(self) -> tuple[bool, list[str]]:
        """
        重启相关 systemctl 服务

        Returns:
            tuple[bool, list[str]]: (是否成功, 错误消息列表)

        """
        errors = []

        for service in [self.RUNTIME_SERVICE, self.RAG_SERVICE]:
            try:
                # 验证服务名称以防止代码注入
                if service not in {self.RUNTIME_SERVICE, self.RAG_SERVICE}:
                    error_msg = f"无效的服务名称: {service}"
                    logger.error(error_msg)
                    errors.append(error_msg)
                    continue

                logger.info("正在重启服务: %s", service)
                # subprocess 调用是安全的，因为我们已经验证了服务名称
                subprocess.run(  # noqa: S603
                    ["/usr/bin/systemctl", "restart", service],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    check=True,
                )
                logger.info("服务 %s 重启成功", service)

            except subprocess.CalledProcessError as e:
                error_msg = f"重启服务 {service} 失败: {e.stderr.strip() if e.stderr else str(e)}"
                logger.warning(error_msg)  # 不使用 exception，因为这是预期可能的错误
                errors.append(error_msg)

            except subprocess.TimeoutExpired:
                error_msg = f"重启服务 {service} 超时"
                logger.warning(error_msg)  # 不使用 exception，因为这是预期可能的错误
                errors.append(error_msg)

            except (OSError, FileNotFoundError) as e:
                error_msg = f"重启服务 {service} 时发生异常: {e}"
                logger.exception(error_msg)
                errors.append(error_msg)

        return len(errors) == 0, errors

    async def validate_llm_connectivity(self) -> tuple[bool, str, dict]:
        """
        验证 LLM API 连接性

        Returns:
            tuple[bool, str, dict]: (是否验证成功, 消息, 验证详细信息)

        """
        if not self.llm.endpoint.strip():
            return False, "LLM API 端点不能为空", {}

        validator = APIValidator()
        is_valid, message, info = await validator.validate_llm_config(
            self.llm.endpoint,
            self.llm.api_key,
            self.llm.model,
            300,  # 使用默认超时时间 300 秒
            self.llm.max_tokens,  # 传递最大令牌数
            self.llm.temperature,  # 传递温度参数
        )

        # 保存检测到的 function call 类型
        if is_valid and info.get("supports_function_call", False):
            self.detected_function_call_type = info.get("detected_function_call_type", "function_call")

        return is_valid, message, info

    async def validate_embedding_connectivity(self) -> tuple[bool, str, dict]:
        """
        验证 Embedding API 连接性

        Returns:
            tuple[bool, str, dict]: (是否验证成功, 消息, 验证详细信息)

        """
        if not self.embedding.endpoint.strip():
            return False, "Embedding API 端点不能为空", {}

        validator = APIValidator()
        is_valid, message, info = await validator.validate_embedding_config(
            self.embedding.endpoint,
            self.embedding.api_key,
            self.embedding.model,
            300,  # 使用默认超时时间 300 秒
        )

        # 如果验证成功，保存检测到的 embedding 类型
        if is_valid and info.get("type"):
            detected_type = info.get("type")
            if detected_type in ("openai", "mindie"):
                self.embedding.type = detected_type

        return is_valid, message, info

    def _load_from_toml(self) -> None:
        """
        从 TOML 文件加载配置

        最高优先级，覆盖其他配置
        """
        try:
            with self.FRAMEWORK_CONFIG_PATH.open(encoding="utf-8") as f:
                data = toml.load(f)

            # 加载 LLM 配置
            self._load_llm_config_from_toml(data)

            # 加载 Embedding 配置
            self._load_embedding_config_from_toml(data)

        except PermissionError:
            logger.exception("权限不足，无法读取 TOML 配置文件")
            raise
        except (OSError, toml.TomlDecodeError):
            logger.exception("从 TOML 文件加载配置失败")
            raise

    def _load_llm_config_from_toml(self, data: dict) -> None:
        """从 TOML 数据中加载 LLM 配置"""
        # 先从 [llm] 部分加载基础配置
        if "llm" in data:
            llm_data = data["llm"]
            self.llm.endpoint = llm_data.get("endpoint", "")
            self.llm.api_key = llm_data.get("key", "")
            self.llm.model = llm_data.get("model", "")
            self.llm.max_tokens = llm_data.get("max_tokens", 8192)
            self.llm.temperature = llm_data.get("temperature", 0.7)

        # 如果存在 [function_call] 配置，优先使用它覆盖 [llm] 配置
        if "function_call" in data:
            fc_data = data["function_call"]
            self.llm.endpoint = fc_data.get("endpoint", self.llm.endpoint)
            self.llm.api_key = fc_data.get("api_key", self.llm.api_key)
            self.llm.model = fc_data.get("model", self.llm.model)
            self.llm.max_tokens = fc_data.get("max_tokens", self.llm.max_tokens)
            self.llm.temperature = fc_data.get("temperature", self.llm.temperature)

    def _load_embedding_config_from_toml(self, data: dict) -> None:
        """从 TOML 数据中加载 Embedding 配置"""
        if "embedding" not in data:
            return

        embed_data = data["embedding"]
        self.embedding.type = embed_data.get("type", "openai")
        self.embedding.endpoint = embed_data.get("endpoint", "")
        self.embedding.api_key = embed_data.get("api_key", "")
        self.embedding.model = embed_data.get("model", "")

    def _load_from_env(self) -> None:
        """
        从 ENV 文件加载配置

        作为基础配置，优先级较低
        """
        try:
            env_vars = {}
            with self.RAG_ENV_PATH.open(encoding="utf-8") as f:
                for file_line in f:
                    stripped_line = file_line.strip()
                    if stripped_line and not stripped_line.startswith("#") and "=" in stripped_line:
                        key, value = stripped_line.split("=", 1)
                        env_vars[key.strip()] = value.strip()

            # 加载 LLM 配置
            self.llm.model = env_vars.get("MODEL_NAME", self.llm.model)
            self.llm.endpoint = env_vars.get("OPENAI_API_BASE", self.llm.endpoint)
            self.llm.api_key = env_vars.get("OPENAI_API_KEY", self.llm.api_key)

            with contextlib.suppress(ValueError):
                self.llm.max_tokens = int(env_vars["MAX_TOKENS"])

            with contextlib.suppress(ValueError):
                self.llm.temperature = float(env_vars["TEMPERATURE"])

            # 加载 Embedding 配置
            self.embedding.type = env_vars.get("EMBEDDING_TYPE", self.embedding.type)
            self.embedding.endpoint = env_vars.get("EMBEDDING_ENDPOINT", self.embedding.endpoint)
            self.embedding.api_key = env_vars.get("EMBEDDING_API_KEY", self.embedding.api_key)
            self.embedding.model = env_vars.get("EMBEDDING_MODEL_NAME", self.embedding.model)

        except PermissionError:
            logger.exception("权限不足，无法读取 ENV 配置文件")
            raise
        except OSError:
            logger.exception("从 ENV 文件加载配置失败")
            raise

    def _save_to_toml(self) -> None:
        """保存配置到 TOML 文件"""
        try:
            # 读取现有配置
            with self.FRAMEWORK_CONFIG_PATH.open(encoding="utf-8") as f:
                data = toml.load(f)

            # 更新 LLM 配置
            if "llm" not in data:
                data["llm"] = {}
            data["llm"].update(
                {
                    "endpoint": self.llm.endpoint,
                    "key": self.llm.api_key,
                    "model": self.llm.model,
                    "max_tokens": self.llm.max_tokens,
                    "temperature": self.llm.temperature,
                },
            )

            # 更新 function_call 配置（与 llm 配置保持同步）
            if "function_call" not in data:
                data["function_call"] = {}
            data["function_call"].update(
                {
                    "backend": self.detected_function_call_type,
                    "endpoint": self.llm.endpoint,
                    "api_key": self.llm.api_key,
                    "model": self.llm.model,
                    "max_tokens": self.llm.max_tokens,
                    "temperature": self.llm.temperature,
                },
            )

            # 更新 Embedding 配置
            if "embedding" not in data:
                data["embedding"] = {}
            data["embedding"].update(
                {
                    "type": self.embedding.type,
                    "endpoint": self.embedding.endpoint,
                    "api_key": self.embedding.api_key,
                    "model": self.embedding.model,
                },
            )

            # 写回文件
            with self.FRAMEWORK_CONFIG_PATH.open("w", encoding="utf-8") as f:
                toml.dump(data, f)

        except (OSError, toml.TomlDecodeError):
            logger.exception("保存到 TOML 文件失败")
            raise

    def _save_to_env(self) -> None:
        """保存配置到 ENV 文件"""
        try:
            # 读取现有文件内容
            lines = []
            with self.RAG_ENV_PATH.open(encoding="utf-8") as f:
                lines = f.readlines()

            # 更新配置值
            updated_vars = {
                "MODEL_NAME": self.llm.model,
                "OPENAI_API_BASE": self.llm.endpoint,
                "OPENAI_API_KEY": self.llm.api_key,
                "MAX_TOKENS": str(self.llm.max_tokens),
                "TEMPERATURE": str(self.llm.temperature),
                "EMBEDDING_TYPE": self.embedding.type,
                "EMBEDDING_ENDPOINT": self.embedding.endpoint,
                "EMBEDDING_API_KEY": self.embedding.api_key,
                "EMBEDDING_MODEL_NAME": self.embedding.model,
            }

            # 处理每一行
            new_lines = []
            updated_keys = set()

            for line in lines:
                stripped = line.strip()
                if stripped and not stripped.startswith("#") and "=" in stripped:
                    key = stripped.split("=", 1)[0].strip()
                    if key in updated_vars:
                        new_lines.append(f"{key} = {updated_vars[key]}\n")
                        updated_keys.add(key)
                    else:
                        new_lines.append(line)
                else:
                    new_lines.append(line)

            # 添加没有更新的新配置项
            for key, value in updated_vars.items():
                if key not in updated_keys:
                    new_lines.append(f"{key} = {value}\n")

            # 写回文件
            with self.RAG_ENV_PATH.open("w", encoding="utf-8") as f:
                f.writelines(new_lines)

        except OSError:
            logger.exception("保存到 ENV 文件失败")
            raise


class LLMConfigScreen(ModalScreen[bool]):
    """
    LLM 配置屏幕

    允许用户修改已部署系统的 LLM 和 Embedding 配置。
    """

    CSS = """
    LLMConfigScreen {
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

    #save, #cancel {
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
        """初始化 LLM 配置屏幕"""
        super().__init__()
        self.config = LLMSystemConfig()
        self._llm_validation_task: asyncio.Task[None] | None = None
        self._embedding_validation_task: asyncio.Task[None] | None = None
        self._background_tasks: set[asyncio.Task] = set()

        # 验证状态跟踪
        self.llm_validation_status: ValidationStatus = ValidationStatus.PENDING
        self.embedding_validation_status: ValidationStatus = ValidationStatus.PENDING

    def compose(self) -> ComposeResult:
        """组合界面组件"""
        with Container(classes="config-container"):
            yield OIHeader()

            with TabbedContent():
                with TabPane("LLM 配置", id="llm_tab"):
                    yield from self._compose_llm_config()

                with TabPane("Embedding 配置", id="embedding_tab"):
                    yield from self._compose_embedding_config()

            with Horizontal(classes="button-row"):
                yield Button("保存配置", id="save", variant="primary")
                yield Button("取消", id="cancel")

    async def on_mount(self) -> None:
        """界面挂载时加载当前配置"""
        try:
            # 加载当前系统配置
            self.config = LLMSystemConfig.load_current_config()

            # 更新界面显示的值
            self._update_form_values()

            # 初始化验证状态和保存按钮状态
            self._initialize_validation_status()

        except FileNotFoundError:
            logger.exception("核心配置文件缺失")
            self.notify("错误：核心配置文件不存在，请检查系统安装", severity="error")
            # 延迟退出，让用户看到错误消息
            task = asyncio.create_task(self._delayed_exit())
            self._background_tasks.add(task)
            task.add_done_callback(self._background_tasks.discard)
        except PermissionError:
            logger.exception("配置文件访问权限不足")
            self.notify("错误：没有权限访问配置文件，请以管理员身份运行", severity="error")
            # 延迟退出，让用户看到错误消息
            task = asyncio.create_task(self._delayed_exit())
            self._background_tasks.add(task)
            task.add_done_callback(self._background_tasks.discard)
        except (OSError, ValueError, AttributeError):
            logger.exception("加载系统配置失败")
            self.notify("加载系统配置失败，请检查系统状态", severity="error")
            # 延迟退出，让用户看到错误消息
            task = asyncio.create_task(self._delayed_exit())
            self._background_tasks.add(task)
            task.add_done_callback(self._background_tasks.discard)

    @on(Button.Pressed, "#save")
    async def on_save_button_pressed(self) -> None:
        """处理保存按钮点击"""
        if await self._collect_and_save_config():
            self.dismiss(result=True)

    @on(Button.Pressed, "#cancel")
    def on_cancel_button_pressed(self) -> None:
        """处理取消按钮点击"""
        self.dismiss(result=False)

    @on(Input.Changed, "#llm_endpoint, #llm_api_key, #llm_model, #llm_max_tokens, #llm_temperature")
    async def on_llm_field_changed(self, event: Input.Changed) -> None:
        """处理 LLM 字段变化，检查是否需要自动验证"""
        # 重置 LLM 验证状态
        self.llm_validation_status = ValidationStatus.PENDING

        # 取消之前的验证任务
        if self._llm_validation_task and not self._llm_validation_task.done():
            self._llm_validation_task.cancel()

        # 更新保存按钮状态
        self._update_save_button_state()

        # 检查是否所有核心字段都已填写
        if self._should_validate_llm():
            # 延迟验证，避免用户输入时频繁验证
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

        # 更新保存按钮状态
        self._update_save_button_state()

        # 检查是否需要验证 Embedding
        if self._should_validate_embedding():
            # 延迟验证，避免用户输入时频繁验证
            self._embedding_validation_task = asyncio.create_task(self._delayed_embedding_validation())

    def _compose_llm_config(self) -> ComposeResult:
        """组合 LLM 配置组件"""
        with Vertical(classes="llm-config-container"):
            yield Static("大语言模型配置", classes="form-label")

            with Horizontal(classes="form-row"):
                yield Label("API 端点:", classes="form-label")
                yield Input(
                    value=self.config.llm.endpoint,
                    placeholder="模型 API 访问地址，如 ollama: http://localhost:11434/v1",
                    id="llm_endpoint",
                    classes="form-input",
                )

            with Horizontal(classes="form-row"):
                yield Label("API 密钥:", classes="form-label")
                yield Input(
                    value=self.config.llm.api_key,
                    placeholder="API 访问密钥，可选，请根据模型提供商指引填写",
                    password=True,
                    id="llm_api_key",
                    classes="form-input",
                )

            with Horizontal(classes="form-row"):
                yield Label("模型名称:", classes="form-label")
                yield Input(
                    value=self.config.llm.model,
                    placeholder="模型名称，可选，请根据模型提供商指引填写",
                    id="llm_model",
                    classes="form-input",
                )

            with Horizontal(classes="form-row"):
                yield Label("最大输出令牌数:", classes="form-label")
                yield Input(
                    value=str(self.config.llm.max_tokens),
                    placeholder="8192",
                    id="llm_max_tokens",
                    classes="form-input",
                )

            with Horizontal(classes="form-row"):
                yield Label("温度参数:", classes="form-label")
                yield Input(
                    value=str(self.config.llm.temperature),
                    placeholder="0.7",
                    id="llm_temperature",
                    classes="form-input",
                )

            with Horizontal(classes="form-row"):
                yield Label("验证状态:", classes="form-label")
                yield Static("未验证", id="llm_validation_status", classes="form-input")

    def _compose_embedding_config(self) -> ComposeResult:
        """组合 Embedding 配置组件"""
        with Vertical(classes="embedding-config-container"):
            yield Static("嵌入模型配置", classes="form-label")

            with Horizontal(classes="form-row"):
                yield Label("API 端点:", classes="form-label")
                yield Input(
                    value=self.config.embedding.endpoint,
                    placeholder="模型 API 访问地址，如 ollama: http://localhost:11434/v1",
                    id="embedding_endpoint",
                    classes="form-input",
                )

            with Horizontal(classes="form-row"):
                yield Label("API 密钥:", classes="form-label")
                yield Input(
                    value=self.config.embedding.api_key,
                    placeholder="API 访问密钥，可选，请根据模型提供商指引填写",
                    password=True,
                    id="embedding_api_key",
                    classes="form-input",
                )

            with Horizontal(classes="form-row"):
                yield Label("模型名称:", classes="form-label")
                yield Input(
                    value=self.config.embedding.model,
                    placeholder="模型名称，可选，请根据模型提供商指引填写",
                    id="embedding_model",
                    classes="form-input",
                )

            with Horizontal(classes="form-row"):
                yield Label("验证状态:", classes="form-label")
                yield Static("未验证", id="embedding_validation_status", classes="form-input")

    async def _delayed_exit(self) -> None:
        """延迟退出，让用户有时间查看错误消息"""
        await asyncio.sleep(3)  # 等待 3 秒让用户看到消息
        self.dismiss(result=False)

    def _update_form_values(self) -> None:
        """更新表单显示的值"""
        try:
            # 更新 LLM 配置显示
            self.query_one("#llm_endpoint", Input).value = self.config.llm.endpoint
            self.query_one("#llm_api_key", Input).value = self.config.llm.api_key
            self.query_one("#llm_model", Input).value = self.config.llm.model
            self.query_one("#llm_max_tokens", Input).value = str(self.config.llm.max_tokens)
            self.query_one("#llm_temperature", Input).value = str(self.config.llm.temperature)

            # 更新 Embedding 配置显示
            self.query_one("#embedding_endpoint", Input).value = self.config.embedding.endpoint
            self.query_one("#embedding_api_key", Input).value = self.config.embedding.api_key
            self.query_one("#embedding_model", Input).value = self.config.embedding.model

        except (ValueError, AttributeError):
            # 如果获取失败，记录警告并使用默认值
            logger.warning("更新表单值时出现警告")

    def _initialize_validation_status(self) -> None:
        """初始化验证状态"""
        # 初始化 Embedding 验证状态
        if self._is_embedding_required():
            self.embedding_validation_status = ValidationStatus.PENDING
        else:
            self.embedding_validation_status = ValidationStatus.NOT_REQUIRED
            # 如果不需要验证 Embedding，显示相应状态
            try:
                embedding_status = self.query_one("#embedding_validation_status", Static)
                embedding_status.update("[dim]不需要验证[/dim]")
            except (ValueError, AttributeError):
                pass

        # 更新保存按钮状态
        self._update_save_button_state()

    def _should_validate_llm(self) -> bool:
        """检查是否应该验证 LLM 配置"""
        try:
            return bool(self.query_one("#llm_endpoint", Input).value.strip())
        except (ValueError, AttributeError):
            return False

    def _should_validate_embedding(self) -> bool:
        """检查是否应该验证 Embedding 配置"""
        try:
            return bool(self.query_one("#embedding_endpoint", Input).value.strip())
        except (ValueError, AttributeError):
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

    async def _validate_llm_config(self) -> None:
        """验证 LLM 配置"""
        # 更新状态为验证中
        self.llm_validation_status = ValidationStatus.VALIDATING
        status_widget = self.query_one("#llm_validation_status", Static)
        status_widget.update("[yellow]验证中...[/yellow]")
        self._update_save_button_state()

        # 收集当前 LLM 配置
        self._collect_llm_config()

        try:
            # 执行验证
            is_valid, message, _info = await self.config.validate_llm_connectivity()

            # 更新验证状态
            if is_valid:
                self.llm_validation_status = ValidationStatus.VALID
                status_widget.update(f"[green]✓ {message}[/green]")
            else:
                self.llm_validation_status = ValidationStatus.INVALID
                status_widget.update(f"[red]✗ {message}[/red]")

        except (ValueError, AttributeError, OSError) as e:
            self.llm_validation_status = ValidationStatus.INVALID
            status_widget.update(f"[red]✗ 验证异常: {e}[/red]")
            self.notify(f"LLM 验证过程中出现异常: {e}", severity="error")

        # 更新保存按钮状态
        self._update_save_button_state()

    async def _validate_embedding_config(self) -> None:
        """验证 Embedding 配置"""
        # 更新状态为验证中
        self.embedding_validation_status = ValidationStatus.VALIDATING
        status_widget = self.query_one("#embedding_validation_status", Static)
        status_widget.update("[yellow]验证中...[/yellow]")
        self._update_save_button_state()

        # 收集当前 Embedding 配置
        self._collect_embedding_config()

        try:
            # 执行验证
            is_valid, message, _info = await self.config.validate_embedding_connectivity()

            # 更新验证状态
            if is_valid:
                self.embedding_validation_status = ValidationStatus.VALID
                status_widget.update(f"[green]✓ {message}[/green]")
            else:
                self.embedding_validation_status = ValidationStatus.INVALID
                status_widget.update(f"[red]✗ {message}[/red]")

        except (ValueError, AttributeError, OSError) as e:
            self.embedding_validation_status = ValidationStatus.INVALID
            status_widget.update(f"[red]✗ 验证异常: {e}[/red]")
            self.notify(f"Embedding 验证过程中出现异常: {e}", severity="error")

        # 更新保存按钮状态
        self._update_save_button_state()

    def _collect_llm_config(self) -> None:
        """收集 LLM 配置"""
        try:
            self.config.llm.endpoint = self.query_one("#llm_endpoint", Input).value.strip()
            self.config.llm.api_key = self.query_one("#llm_api_key", Input).value.strip()
            self.config.llm.model = self.query_one("#llm_model", Input).value.strip()

            # 处理 max_tokens，如果为空或无效则使用默认值 8192
            max_tokens_value = self.query_one("#llm_max_tokens", Input).value.strip()
            if max_tokens_value:
                try:
                    self.config.llm.max_tokens = int(max_tokens_value)
                except ValueError:
                    self.config.llm.max_tokens = 8192
            else:
                self.config.llm.max_tokens = 8192

            # 处理 temperature，如果为空或无效则使用默认值 0.7
            temperature_value = self.query_one("#llm_temperature", Input).value.strip()
            if temperature_value:
                try:
                    self.config.llm.temperature = float(temperature_value)
                except ValueError:
                    self.config.llm.temperature = 0.7
            else:
                self.config.llm.temperature = 0.7

        except (ValueError, AttributeError):
            # 如果转换失败，使用默认值
            pass

    def _collect_embedding_config(self) -> None:
        """收集 Embedding 配置"""
        try:
            self.config.embedding.type = "openai"  # 固定使用 openai 类型
            self.config.embedding.endpoint = self.query_one("#embedding_endpoint", Input).value.strip()
            self.config.embedding.api_key = self.query_one("#embedding_api_key", Input).value.strip()
            self.config.embedding.model = self.query_one("#embedding_model", Input).value.strip()
        except (ValueError, AttributeError):
            # 如果获取失败，记录警告并使用默认值
            logger.warning("获取 Embedding 配置失败，使用默认值")

    def _is_embedding_required(self) -> bool:
        """检查是否需要验证 Embedding 配置"""
        # 如果 RAG 环境文件存在，则需要验证 Embedding
        if self.config.RAG_ENV_PATH.exists():
            return True

        # 如果用户填写了 Embedding 配置，则需要验证
        try:
            endpoint = self.query_one("#embedding_endpoint", Input).value.strip()
            api_key = self.query_one("#embedding_api_key", Input).value.strip()
            model = self.query_one("#embedding_model", Input).value.strip()
            return bool(endpoint or api_key or model)
        except (ValueError, AttributeError):
            return False

    def _update_save_button_state(self) -> None:
        """根据验证状态更新保存按钮状态"""
        try:
            save_button = self.query_one("#save", Button)

            # 检查 LLM 验证状态
            if self.llm_validation_status in (
                ValidationStatus.PENDING,
                ValidationStatus.VALIDATING,
                ValidationStatus.INVALID,
            ):
                save_button.disabled = True
                return

            # 检查 Embedding 验证状态
            if self._is_embedding_required() and self.embedding_validation_status in (
                ValidationStatus.PENDING,
                ValidationStatus.VALIDATING,
                ValidationStatus.INVALID,
            ):
                save_button.disabled = True
                return

            # 所有必要的验证都通过，启用保存按钮
            save_button.disabled = False

        except (ValueError, AttributeError):
            # 如果出现异常，为安全起见禁用保存按钮
            pass

    async def _collect_and_save_config(self) -> bool:
        """收集用户配置并保存"""
        try:
            # 收集配置
            self._collect_llm_config()
            self._collect_embedding_config()

            # 验证配置
            if not self.config.llm.endpoint.strip():
                self.notify("LLM API 端点不能为空", severity="error")
                return False

            # 保存配置
            self.config.save_config()
            self.notify("配置保存成功", severity="information")

            # 重启服务
            success, errors = self.config.restart_services()
            if success:
                self.notify("服务重启成功", severity="information")
            else:
                error_msg = "服务重启失败:\n" + "\n".join(errors)
                self.notify(error_msg, severity="error")

        except Exception as e:
            self.notify(f"保存配置失败: {e}", severity="error")
            logger.exception("保存配置失败:")
            return False
        else:
            return True


class LLMConfigApp(App[bool]):
    """LLM 配置应用"""

    CSS_PATH = str(Path(__file__).parent.parent / "app" / "css" / "styles.tcss")
    TITLE = "Witty Assistant LLM 配置工具"

    def __init__(self) -> None:
        """初始化应用"""
        super().__init__()
        self.config_result: bool | None = None

    def on_mount(self) -> None:
        """应用启动时显示配置屏幕"""
        self.push_screen(LLMConfigScreen(), self._handle_screen_result)

    def _handle_screen_result(self, result: bool | None) -> None:  # noqa: FBT001
        """处理配置屏幕结果"""
        self.config_result = result
        self.exit()


def llm_config() -> None:
    """
    LLM 配置主函数

    --llm-config 参数的入口点。
    """
    logger.info("启动 LLM 配置工具")

    try:
        # 检查前置条件
        ok, errors = LLMSystemConfig.check_prerequisites()
        if not ok:
            sys.stderr.write("错误：无法启动 LLM 配置工具\n")
            for error in errors:
                sys.stderr.write(f"  - {error}\n")
            sys.exit(1)

        # 启动 TUI 应用
        app = LLMConfigApp()
        app.run()

        # 检查应用内部存储的结果
        if app.config_result:
            sys.stdout.write("✓ LLM 配置更新完成\n")
        else:
            sys.stdout.write("配置更新已取消\n")

    except KeyboardInterrupt:
        sys.stderr.write("\n配置已取消\n")
        sys.exit(1)
    except (OSError, ValueError, RuntimeError) as e:
        logger.exception("LLM 配置工具发生异常")
        sys.stderr.write(f"错误：{e}\n")
        sys.exit(1)


if __name__ == "__main__":
    llm_config()
