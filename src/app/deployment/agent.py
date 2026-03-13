"""
Agent 管理模块。

处理 MCP 服务和智能体的注册、安装、激活和管理。

该模块提供:
- McpConfig: MCP 配置数据模型
- McpConfigLoader: MCP 配置文件加载器
- AgentManager: 智能体管理器主类
"""

from __future__ import annotations

import asyncio
import copy
import getpass
import json
import subprocess
import tomllib
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, NoReturn

import yaml

from config.manager import ConfigManager
from i18n.manager import _
from log.manager import get_logger

from .models import AgentInitStatus, DeploymentState

if TYPE_CHECKING:
    from collections.abc import Callable

logger = get_logger(__name__)

MAX_FIRST_QUESTIONS = 3


class ConfigError(Exception):
    """配置错误异常"""


@dataclass
class McpConfig:
    """MCP 配置模型"""

    name: str
    description: str
    overview: str
    mcp_servers: dict[str, Any]
    mcp_type: str
    author: str = "openEuler"


@dataclass
class AppConfig:
    """应用配置信息（从 TOML 文件读取）"""

    app_type: str
    name: str
    description: str
    mcp_path: list[str]
    published: bool = True
    version: str = "1.0.0"
    author: str = "openEuler"
    history_len: int = 3
    icon: str = ""
    hashes: dict[str, str] = field(default_factory=dict)
    links: list[dict[str, str]] = field(default_factory=list)
    first_questions: list[str] = field(default_factory=list)
    permission: dict[str, Any] = field(
        default_factory=lambda: {"type": "public", "users": []},
    )


@dataclass
class AppMetadata:
    """智能体元数据（用于写入 YAML 文件）"""

    type: str = "app"
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    author: str = "openEuler"
    app_type: str = "agent"
    published: bool = True
    history_len: int = 3
    mcp_service: list[str] = field(default_factory=list)
    hashes: dict[str, str] = field(default_factory=dict)
    links: list[dict[str, str]] = field(default_factory=list)
    first_questions: list[str] = field(default_factory=list)
    permission: dict[str, Any] = field(
        default_factory=lambda: {"type": "public", "users": []},
    )


class McpConfigLoader:
    """MCP 配置加载器"""

    def __init__(self, config_dir: Path) -> None:
        """初始化配置加载器"""
        self.config_dir = config_dir

    def load_all_configs(self) -> list[tuple[str, McpConfig]]:
        """
        加载所有 MCP 配置

        Returns:
            list[tuple[str, McpConfig]]: (目录名, 配置对象) 的列表

        """
        configs = []
        if not self.config_dir.exists():
            msg = f"配置目录不存在: {self.config_dir}"
            logger.error(msg)
            raise ConfigError(msg)

        logger.info("开始扫描 MCP 配置目录: %s", self.config_dir)
        for subdir in self.config_dir.iterdir():
            if subdir.is_dir():
                logger.debug("检查子目录: %s", subdir.name)
                config_file = subdir / "config.json"
                if config_file.exists():
                    logger.debug("找到配置文件: %s", config_file)
                    try:
                        config = self._load_config(config_file, subdir.name)
                        configs.append((subdir.name, config))
                        logger.debug("成功加载 MCP 配置: %s (名称: %s)", subdir.name, config.name)
                    except Exception:
                        logger.exception("加载 MCP 配置失败: %s", config_file)
                        continue
                else:
                    logger.debug("子目录 %s 中没有 config.json", subdir.name)

        if not configs:
            msg = f"未找到有效的 MCP 配置文件在: {self.config_dir}"
            logger.warning(msg)
        else:
            logger.info("共加载了 %d 个 MCP 配置", len(configs))

        return configs

    def _load_config(self, config_file: Path, name: str) -> McpConfig:
        """加载单个配置文件"""
        with config_file.open(encoding="utf-8") as f:
            config_data = json.load(f)

        raw_servers = config_data.get("mcpServers")
        mcp_servers: dict[str, Any] = {}

        if isinstance(raw_servers, dict) and raw_servers:
            mcp_servers = {
                str(server_name): server_config
                if isinstance(server_config, dict)
                else {}
                for server_name, server_config in raw_servers.items()
            }
        else:
            legacy_config = config_data.get("config", {})
            if isinstance(legacy_config, dict) and legacy_config:
                mcp_servers = {name: legacy_config}

        return McpConfig(
            name=config_data.get("name", name),
            description=config_data.get("description", name),
            overview=config_data.get("overview", name),
            mcp_servers=mcp_servers,
            mcp_type=config_data.get("mcpType", "sse"),
            author=config_data.get("author", "openEuler"),
        )


class AgentManager:
    """智能体管理器"""

    # sysagent 配置文件路径
    SYSAGENT_CONFIG_PATH = Path("/etc/sysagent/config.toml")
    # 默认数据目录（当配置文件不存在或读取失败时使用）
    DEFAULT_DATA_DIR = Path("/var/lib/sysagent")

    def __init__(self) -> None:
        """初始化智能体管理器"""
        self.config_manager = ConfigManager()
        self.current_user = getpass.getuser()

        # 从 sysagent 配置读取数据目录
        data_dir = self._get_data_dir_from_sysagent_config()
        self.semantics_dir = data_dir / "semantics"
        self.mcp_template_dir = self.semantics_dir / "mcp" / "template"
        self.app_dir = self.semantics_dir / "app"

        # 资源路径
        self.resource_dir = Path("/usr/lib/sysagent/mcp_center")
        self.mcp_config_dir = self.resource_dir / "mcp_config"
        self.run_script_path = self.resource_dir / "run.sh"
        self.service_dir = self.resource_dir / "service"
        self.app_config_path = self.mcp_config_dir / "mcp_to_app_config.toml"

    async def initialize_agents(
        self,
        state: DeploymentState,
        progress_callback: Callable[[DeploymentState], None] | None = None,
    ) -> AgentInitStatus:
        """
        初始化智能体

        Args:
            state: 主部署流程的状态对象
            progress_callback: 进度回调函数

        Returns:
            AgentInitStatus: 初始化状态 (SUCCESS/SKIPPED/FAILED)

        """
        self._report_progress(
            state,
            _("[bold blue]开始初始化智能体...[/bold blue]"),
            progress_callback,
        )

        try:
            # 执行所有初始化步骤
            return await self._execute_initialization_steps(state, progress_callback)

        except Exception:
            error_msg = _("智能体初始化失败")
            self._report_progress(state, f"[red]{error_msg}[/red]", progress_callback)
            logger.exception(error_msg)
            return AgentInitStatus.FAILED

    async def _execute_initialization_steps(
        self,
        state: DeploymentState,
        progress_callback: Callable[[DeploymentState], None] | None,
    ) -> AgentInitStatus:
        """执行所有初始化步骤"""
        # 1. 如果本地存在 mcp_center 资源，则执行本地 MCP 服务管理。
        # 否则进入兼容模式：MCP 由外部服务托管，仅写入智能体配置。
        if self._has_local_mcp_runtime_resources():
            if not await self._install_service_files(state, progress_callback):
                return AgentInitStatus.FAILED

            if not await self._start_mcp_servers(state, progress_callback):
                return AgentInitStatus.FAILED

            if not await self._verify_mcp_services(state, progress_callback):
                return AgentInitStatus.FAILED
        else:
            logger.info(
                "未检测到本地 mcp_center 运行资源，跳过本地 MCP 服务安装与校验，使用外部托管模式",
            )

        # 2. 停止 sysagent 服务，准备写入配置
        if not await self._stop_sysagent_service(state, progress_callback):
            self._report_progress(
                state,
                _("[yellow]停止 sysagent 服务失败，但继续执行[/yellow]"),
                progress_callback,
            )

        # 3. 准备 MCP 服务映射，并在可能时写入本地 MCP 配置。
        mcp_service_mapping = await self._prepare_mcp_service_mapping(
            state,
            progress_callback,
        )
        if not mcp_service_mapping:
            return AgentInitStatus.FAILED

        # 4. 读取应用配置并写入智能体元数据
        default_app_id = await self._write_app_metadata_to_filesystem(
            mcp_service_mapping,
            state,
            progress_callback,
        )

        # 5. 重新启动 sysagent 服务
        if not await self._start_sysagent_service(state, progress_callback):
            self._report_progress(
                state,
                _("[yellow]启动 sysagent 服务失败，请手动检查[/yellow]"),
                progress_callback,
            )

        if default_app_id:
            configured = self._update_default_app_config(default_app_id)

            message = (
                _(
                    "[bold green]智能体初始化完成! 默认 App ID: {app_id}[/bold green]",
                ).format(app_id=default_app_id)
                if configured
                else _(
                    "[bold yellow]智能体初始化完成，但默认 App 未写入配置[/bold yellow]",
                )
            )

            self._report_progress(state, message, progress_callback)
            logger.info(
                "智能体初始化成功完成，默认 App ID: %s，写入配置: %s",
                default_app_id,
                configured,
            )
            return AgentInitStatus.SUCCESS

        # 如果没有创建任何智能体，显示警告并返回成功状态
        self._report_progress(
            state,
            _("[yellow]未能创建任何智能体[/yellow]"),
            progress_callback,
        )
        return AgentInitStatus.SUCCESS

    def _has_local_mcp_runtime_resources(self) -> bool:
        """判断是否存在可由本地部署流程接管的 mcp_center 运行资源。"""
        return bool(
            self.resource_dir.exists()
            and self.run_script_path.exists()
            and self.service_dir.exists()
        )

    async def _prepare_mcp_service_mapping(
        self,
        state: DeploymentState,
        callback: Callable[[DeploymentState], None] | None,
    ) -> dict[str, str]:
        """准备 mcpPath -> mcp_service_id 映射。"""
        local_mapping = await self._write_mcp_configs_to_filesystem(state, callback)

        app_configs = await self._load_app_configs(state, callback)
        fallback_mapping = self._build_fallback_mcp_service_mapping(app_configs)

        if local_mapping:
            for mcp_path, service_id in fallback_mapping.items():
                local_mapping.setdefault(mcp_path, service_id)

            return local_mapping

        if fallback_mapping:
            logger.info(
                "未找到本地 MCP 配置，已使用 mcp_to_app_config.toml 中的 mcpPath 直接生成 Agent 配置",
            )
            return fallback_mapping

        return {}

    @staticmethod
    def _build_fallback_mcp_service_mapping(app_configs: list[AppConfig]) -> dict[str, str]:
        """基于 mcp_to_app_config.toml 中的 mcpPath 构建回退映射。"""
        fallback_mapping: dict[str, str] = {}
        for app_config in app_configs:
            for mcp_path in app_config.mcp_path:
                fallback_mapping.setdefault(mcp_path, mcp_path)

        return fallback_mapping

    def _report_progress(
        self,
        state: DeploymentState,
        message: str,
        callback: Callable[[DeploymentState], None] | None = None,
    ) -> None:
        """报告进度"""
        state.add_log(message)
        if callback:
            callback(state)

    @staticmethod
    def _raise_config_error(message: str) -> NoReturn:
        """抛出配置错误。"""
        raise ConfigError(message)

    async def _write_mcp_configs_to_filesystem(
        self,
        state: DeploymentState,
        callback: Callable[[DeploymentState], None] | None,
    ) -> dict[str, str]:
        """
        将 MCP 配置写入文件系统

        Returns:
            dict[str, str]: mcp center 目录名 -> MCP ID 的映射

        """
        self._report_progress(
            state,
            _("[cyan]写入 MCP 配置到文件系统...[/cyan]"),
            callback,
        )

        # 确保目标目录存在
        self.mcp_template_dir.mkdir(parents=True, exist_ok=True)

        # 加载 MCP 配置
        configs = await self._load_mcp_configs(state, callback)
        if not configs:
            return {}

        mcp_service_mapping: dict[str, str] = {}
        seen_server_ids: set[str] = set()
        total_written = 0

        logger.info("开始写入 %d 个 MCP 配置", len(configs))
        for dir_name, config in configs:
            logger.debug("正在处理配置目录: %s, 配置名称: %s", dir_name, config.name)
            try:
                # 预扫描并校验：mcpServers 内部键名必须全局唯一。
                # 否则会导致落盘目录冲突、服务覆盖，属于致命配置错误。
                raw_servers = config.mcp_servers or {}
                if raw_servers and all(isinstance(cfg, dict) for cfg in raw_servers.values()):
                    server_entries = raw_servers
                else:
                    server_entries = {dir_name: raw_servers if isinstance(raw_servers, dict) else {}}

                if not server_entries:
                    msg = f"MCP 配置 {dir_name} 缺少 mcpServers"
                    self._raise_config_error(msg)

                server_id = next(iter(server_entries.keys()))
                if server_id in seen_server_ids:
                    msg = _(
                        "检测到重复的 mcpServers 内部键名: {server_id}。"
                        "多个 MCP 配置不能共用同一个键名，否则会发生覆盖。"
                        "请修改 /usr/lib/sysagent/mcp_center/mcp_config 下对应配置，使其键名唯一。"
                    ).format(server_id=server_id)
                    self._report_progress(state, f"[red]{msg}[/red]", callback)
                    self._raise_config_error(msg)

                seen_server_ids.add(server_id)

                mcp_id = await self._write_single_mcp_config(
                    dir_name,
                    config,
                    state,
                    callback,
                )
                if mcp_id:
                    mcp_service_mapping[dir_name] = mcp_id
                    total_written += 1
                    logger.debug("配置 %s 写入成功，MCP ID: %s", dir_name, mcp_id)
                else:
                    logger.warning("配置 %s 写入失败，未返回 MCP ID", dir_name)

            except ConfigError:
                # 配置错误属于致命问题，直接上抛让上层失败并提示用户修正配置。
                raise
            except Exception:
                self._report_progress(
                    state,
                    _("  [red]处理 {name} 失败[/red]").format(name=config.name),
                    callback,
                )
                logger.exception("处理 MCP 配置失败: %s (目录: %s)", config.name, dir_name)
                continue

        self._report_progress(
            state,
            _("[green]MCP 配置写入完成，成功 {count} 个[/green]").format(
                count=total_written,
            ),
            callback,
        )
        return mcp_service_mapping

    async def _write_single_mcp_config(
        self,
        dir_name: str,
        config: McpConfig,
        state: DeploymentState,
        callback: Callable[[DeploymentState], None] | None,
    ) -> str | None:
        """
        写入单个 MCP 配置到文件系统

        Args:
            dir_name: mcp center 中的目录名
            config: 从该目录加载的 MCP 配置
            state: 部署状态对象
            callback: 进度回调函数

        Returns:
            str | None: 成功写入的 MCP ID，失败返回 None

        """
        self._report_progress(
            state,
            _("  [blue]写入 {name}...[/blue]").format(name=config.name),
            callback,
        )

        logger.debug("处理 MCP 配置: dir_name=%s, config.name=%s", dir_name, config.name)
        raw_servers = config.mcp_servers or {}
        logger.debug("原始服务器配置: %s", raw_servers)

        if raw_servers and all(isinstance(cfg, dict) for cfg in raw_servers.values()):
            server_entries = raw_servers
        else:
            server_entries = {dir_name: raw_servers if isinstance(raw_servers, dict) else {}}

        logger.debug("解析后的服务器条目: %s", list(server_entries.keys()))

        # 每个 mcp center 子目录只包含一个 MCP 配置
        if len(server_entries) != 1:
            logger.warning(
                "MCP 配置 %s 包含 %d 个服务，预期为 1 个",
                config.name,
                len(server_entries),
            )

        mcp_id = next(iter(server_entries.keys()))
        server_config = server_entries[mcp_id]
        logger.info("提取的 MCP ID: %s", mcp_id)

        try:
            target_dir = self.mcp_template_dir / mcp_id
            logger.info("目标目录: %s", target_dir)
            target_dir.mkdir(parents=True, exist_ok=True)

            normalized_config = self._normalize_mcp_config(server_config)

            config_data = {
                "mcpServers": {mcp_id: normalized_config},
                "name": config.name,
                "overview": config.overview,
                "description": config.description,
                "mcpType": config.mcp_type,
                "author": self.current_user,
            }

            config_file = target_dir / "config.json"
            logger.info("写入配置文件: %s", config_file)
            with config_file.open("w", encoding="utf-8") as f:
                json.dump(config_data, f, ensure_ascii=False, indent=4)

            logger.info("配置文件写入成功: %s", config_file)

        except Exception:
            self._report_progress(
                state,
                _("  [red]{name} 写入失败[/red]").format(name=config.name),
                callback,
            )
            logger.exception("写入 MCP 配置失败: %s", config.name)
            return None
        else:
            self._report_progress(
                state,
                _("  [green]{name} 写入成功 (MCP ID: {mcp_id}) -> {path}[/green]").format(
                    name=config.name,
                    mcp_id=mcp_id,
                    path=target_dir,
                ),
                callback,
            )
            logger.info(
                "MCP 配置写入成功: %s (ID: %s) -> %s",
                config.name,
                mcp_id,
                target_dir,
            )
            return mcp_id

    def _normalize_mcp_config(self, raw_config: dict[str, Any]) -> dict[str, Any]:
        defaults: dict[str, Any] = {
            "env": {},
            "autoApprove": [],
            "autoInstall": True,
            "timeout": 60,
            "url": "",
            "disabled": False,
            "description": "",
            "headers": {},
        }

        merged = copy.deepcopy(defaults)
        if raw_config:
            merged.update(raw_config)

        # 兼容旧字段命名
        if "auto_install" in merged:
            merged["autoInstall"] = bool(merged.pop("auto_install"))

        if not isinstance(merged.get("autoApprove"), list):
            merged["autoApprove"] = []

        if not isinstance(merged.get("env"), dict):
            merged["env"] = {}

        if not isinstance(merged.get("headers"), dict):
            merged["headers"] = {}

        merged["autoInstall"] = bool(merged.get("autoInstall", True))

        try:
            merged["timeout"] = int(merged.get("timeout", defaults["timeout"]))
        except (TypeError, ValueError):
            merged["timeout"] = defaults["timeout"]

        merged.setdefault("url", "")

        return merged

    @staticmethod
    def _normalize_links(raw_links: Any) -> list[dict[str, str]]:
        if not isinstance(raw_links, list):
            return []

        normalized: list[dict[str, str]] = []
        for link in raw_links:
            if not isinstance(link, dict):
                continue

            title = str(link.get("title", "")).strip()
            url = str(link.get("url", "")).strip()
            if title and url:
                normalized.append({"title": title, "url": url})

        return normalized

    @staticmethod
    def _normalize_first_questions(raw_questions: Any) -> list[str]:
        if raw_questions is None:
            return []

        questions = raw_questions
        if not isinstance(questions, list):
            questions = [questions]

        normalized: list[str] = []
        for question in questions:
            if not isinstance(question, str):
                continue
            cleaned = question.strip()
            if cleaned:
                normalized.append(cleaned)
            if len(normalized) >= MAX_FIRST_QUESTIONS:
                break

        return normalized

    @staticmethod
    def _normalize_permission_data(raw_permission: Any) -> dict[str, Any]:
        default_permission = {"type": "public", "users": []}
        if not isinstance(raw_permission, dict):
            return copy.deepcopy(default_permission)

        permission_type = raw_permission.get("type") or raw_permission.get("visibility")
        if not isinstance(permission_type, str) or not permission_type:
            permission_type = default_permission["type"]

        users = raw_permission.get("users")
        if users is None:
            users = raw_permission.get("authorizedUsers")
        if not isinstance(users, list):
            users = []

        return {"type": permission_type, "users": users}

    @staticmethod
    def _normalize_hashes(raw_hashes: Any) -> dict[str, str]:
        if not isinstance(raw_hashes, dict):
            return {}

        normalized: dict[str, str] = {}
        for key, value in raw_hashes.items():
            if isinstance(value, str):
                normalized[str(key)] = value

        return normalized

    @staticmethod
    def _normalize_mcp_paths(raw_paths: Any) -> list[str]:
        if not isinstance(raw_paths, list):
            return []

        return [path for path in raw_paths if isinstance(path, str) and path]

    @staticmethod
    def _as_bool(value: Any, *, default: bool = True) -> bool:
        if isinstance(value, bool):
            return value

        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"true", "1", "yes"}:
                return True
            if normalized in {"false", "0", "no"}:
                return False

        if isinstance(value, (int, float)):
            return bool(value)

        return default

    @staticmethod
    def _safe_int(value: Any, default: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _first_existing_value(data: dict[str, Any], *keys: str) -> Any:
        for key in keys:
            if key in data:
                return data[key]
        return None

    def _get_data_dir_from_sysagent_config(self) -> Path:
        """
        从 sysagent 配置文件读取数据目录

        Returns:
            Path: 数据目录路径

        """
        try:
            if self.SYSAGENT_CONFIG_PATH.exists():
                with self.SYSAGENT_CONFIG_PATH.open("rb") as f:
                    config = tomllib.load(f)
                data_dir = config.get("deploy", {}).get("data_dir")
                if data_dir:
                    logger.debug("从 sysagent 配置读取数据目录: %s", data_dir)
                    return Path(data_dir)
            logger.warning(
                "sysagent 配置文件不存在或未配置 data_dir，使用默认路径: %s",
                self.DEFAULT_DATA_DIR,
            )
        except Exception:
            logger.exception(
                "读取 sysagent 配置失败，使用默认路径: %s",
                self.DEFAULT_DATA_DIR,
            )
        return self.DEFAULT_DATA_DIR

    async def _write_app_metadata_to_filesystem(
        self,
        mcp_service_mapping: dict[str, str],
        state: DeploymentState,
        callback: Callable[[DeploymentState], None] | None,
    ) -> str | None:
        """
        从配置文件读取应用信息并写入智能体元数据到文件系统

        Args:
            mcp_service_mapping: mcp center 目录名 -> MCP ID 的映射
            state: 部署状态对象
            callback: 进度回调函数

        Returns:
            str | None: 默认智能体的 UUID，失败返回 None

        """
        self._report_progress(
            state,
            _("[cyan]写入智能体元数据到文件系统...[/cyan]"),
            callback,
        )

        # 确保目标目录存在
        self.app_dir.mkdir(parents=True, exist_ok=True)

        # 读取应用配置
        app_configs = await self._load_app_configs(state, callback)
        if not app_configs:
            return None

        created_agents = []
        default_app_id = None

        for i, app_config in enumerate(app_configs):
            try:
                app_id = await self._write_single_app_metadata(
                    app_config,
                    mcp_service_mapping,
                    state,
                    callback,
                )
                if app_id:
                    created_agents.append((app_config.name, app_id))
                    if i == 0:
                        default_app_id = app_id

            except Exception:
                self._report_progress(
                    state,
                    _("  [red]创建 {name} 元数据失败[/red]").format(
                        name=app_config.name,
                    ),
                    callback,
                )
                logger.exception("创建智能体元数据失败: %s", app_config.name)
                continue

        if created_agents:
            self._report_progress(
                state,
                _("[green]成功创建 {count} 个智能体[/green]").format(
                    count=len(created_agents),
                ),
                callback,
            )
            for name, app_id in created_agents:
                logger.info("创建智能体成功: %s (ID: %s)", name, app_id)

        return default_app_id

    async def _write_single_app_metadata(
        self,
        app_config: AppConfig,
        mcp_service_mapping: dict[str, str],
        state: DeploymentState,
        callback: Callable[[DeploymentState], None] | None,
    ) -> str | None:
        """
        写入单个智能体元数据到文件系统

        Args:
            app_config: 应用配置
            mcp_service_mapping: mcp center 目录名 -> MCP ID 的映射
            state: 部署状态对象
            callback: 进度回调函数

        Returns:
            str | None: 创建的智能体 UUID，失败返回 None

        """
        self._report_progress(
            state,
            _("[magenta]创建智能体元数据: {name}[/magenta]").format(
                name=app_config.name,
            ),
            callback,
        )

        # 将 MCP 路径转换为服务 ID
        mcp_service_ids, missing_services = self._resolve_mcp_services(
            app_config.mcp_path,
            mcp_service_mapping,
        )

        if missing_services:
            self._report_progress(
                state,
                _("  [yellow]警告: 以下 MCP 服务未找到: {services}[/yellow]").format(
                    services=", ".join(missing_services),
                ),
                callback,
            )
            logger.warning(
                "智能体 %s 的部分 MCP 服务未找到: %s",
                app_config.name,
                missing_services,
            )

        if not mcp_service_ids:
            self._report_progress(
                state,
                _("  [red]{name} 没有可用的 MCP 服务[/red]").format(
                    name=app_config.name,
                ),
                callback,
            )
            return None

        try:
            app_id = str(uuid.uuid4())
            target_dir = self.app_dir / app_id
            target_dir.mkdir(parents=True, exist_ok=True)

            metadata = AppMetadata(
                id=app_id,
                name=app_config.name,
                description=app_config.description,
                author=self.current_user,
                app_type=app_config.app_type,
                published=app_config.published,
                history_len=app_config.history_len,
                mcp_service=mcp_service_ids,
                hashes=app_config.hashes,
                links=app_config.links,
                first_questions=app_config.first_questions,
                permission=app_config.permission,
            )

            metadata_file = target_dir / "metadata.yaml"
            metadata_dict = {
                "type": metadata.type,
                "id": metadata.id,
                "name": metadata.name,
                "description": metadata.description,
                "author": metadata.author,
                "app_type": metadata.app_type,
                "published": metadata.published,
                "history_len": metadata.history_len,
                "mcp_service": metadata.mcp_service,
                "hashes": metadata.hashes,
                "links": metadata.links,
                "first_questions": metadata.first_questions,
                "permission": metadata.permission,
            }

            with metadata_file.open("w", encoding="utf-8") as f:
                yaml.dump(
                    metadata_dict,
                    f,
                    allow_unicode=True,
                    default_flow_style=False,
                    sort_keys=False,
                )

        except Exception:
            self._report_progress(
                state,
                _("  [red]{name} 元数据创建失败[/red]").format(name=app_config.name),
                callback,
            )
            logger.exception("创建智能体元数据失败: %s", app_config.name)
            return None
        else:
            self._report_progress(
                state,
                _("  [green]{name} 元数据创建成功 (ID: {app_id})[/green]").format(
                    name=app_config.name,
                    app_id=app_id,
                ),
                callback,
            )
            logger.info("智能体元数据创建成功: %s (ID: %s)", app_config.name, app_id)
            return app_id

    def _update_default_app_config(self, default_app_id: str) -> bool:
        """将默认智能体 ID 写入配置文件"""
        try:
            self.config_manager.set_default_app(default_app_id)
        except Exception:
            logger.exception("更新默认智能体配置失败: %s", default_app_id)
            return False

        logger.info("默认智能体配置已更新: %s", default_app_id)
        return True

    def _resolve_mcp_services(
        self,
        mcp_paths: list[str],
        mcp_service_mapping: dict[str, str],
    ) -> tuple[list[str], list[str]]:
        """
        解析 MCP 路径为服务 ID

        Args:
            mcp_paths: TOML 配置中的 mcpPath 列表
            mcp_service_mapping: mcp center 目录名 -> MCP ID 的映射

        Returns:
            tuple[list[str], list[str]]: (MCP ID 列表, 未找到的路径列表)

        """
        mcp_service_ids: list[str] = []
        missing_services: list[str] = []

        for mcp_path in mcp_paths:
            if mcp_path in mcp_service_mapping:
                mcp_service_ids.append(mcp_service_mapping[mcp_path])
            else:
                missing_services.append(mcp_path)

        return mcp_service_ids, missing_services

    async def _load_app_configs(
        self,
        state: DeploymentState,
        callback: Callable[[DeploymentState], None] | None,
    ) -> list[AppConfig]:
        """加载应用配置"""
        self._report_progress(
            state,
            _("[cyan]加载应用配置文件...[/cyan]"),
            callback,
        )

        if not self.app_config_path or not self.app_config_path.exists():
            self._report_progress(
                state,
                _("[red]应用配置文件不存在: {path}[/red]").format(
                    path=self.app_config_path,
                ),
                callback,
            )
            logger.error("应用配置文件不存在: %s", self.app_config_path)
            return []

        try:
            with self.app_config_path.open("rb") as f:
                toml_data = tomllib.load(f)

            app_configs = []
            apps_data = toml_data.get("applications", [])

            for app_data in apps_data:
                first_questions_raw = self._first_existing_value(
                    app_data,
                    "first_questions",
                    "firstQuestions",
                    "recommendedQuestions",
                )

                app_config = AppConfig(
                    app_type=app_data.get("appType", "agent"),
                    name=app_data.get("name", ""),
                    description=app_data.get("description", ""),
                    mcp_path=self._normalize_mcp_paths(app_data.get("mcpPath", [])),
                    published=self._as_bool(app_data.get("published", True)),
                    version=app_data.get("version", "1.0.0"),
                    author=app_data.get("author", "openEuler"),
                    history_len=self._safe_int(
                        app_data.get("historyLen", app_data.get("dialogRounds", 3)),
                        3,
                    ),
                    icon=app_data.get("icon", ""),
                    hashes=self._normalize_hashes(app_data.get("hashes")),
                    links=self._normalize_links(app_data.get("links", [])),
                    first_questions=self._normalize_first_questions(first_questions_raw),
                    permission=self._normalize_permission_data(app_data.get("permission")),
                )
                app_configs.append(app_config)

        except Exception:
            self._report_progress(
                state,
                _("[red]加载应用配置失败[/red]"),
                callback,
            )
            logger.exception("加载应用配置失败: %s", self.app_config_path)
            return []
        else:
            self._report_progress(
                state,
                _("[green]成功加载 {count} 个应用配置[/green]").format(
                    count=len(app_configs),
                ),
                callback,
            )
            return app_configs

    async def _load_mcp_configs(
        self,
        state: DeploymentState,
        callback: Callable[[DeploymentState], None] | None,
    ) -> list[tuple[str, McpConfig]]:
        """加载 MCP 配置"""
        self._report_progress(
            state,
            _("[cyan]加载 MCP 配置文件...[/cyan]"),
            callback,
        )

        try:
            config_loader = McpConfigLoader(self.mcp_config_dir)
            configs = config_loader.load_all_configs()
        except ConfigError:
            logger.info("未找到本地 MCP 配置目录，进入外部托管兼容模式: %s", self.mcp_config_dir)
            return []

        if not configs:
            logger.info("本地 MCP 配置目录中未找到可用配置: %s", self.mcp_config_dir)

        self._report_progress(
            state,
            _("[green]成功加载 {count} 个 MCP 配置[/green]").format(count=len(configs)),
            callback,
        )
        return configs

    # ========== 以下是 systemd 服务相关方法 ==========

    async def _stop_sysagent_service(
        self,
        state: DeploymentState,
        callback: Callable[[DeploymentState], None] | None,
    ) -> bool:
        """停止 sysagent 服务"""
        self._report_progress(
            state,
            _("[cyan]停止 sysagent 服务...[/cyan]"),
            callback,
        )

        try:
            # 先检查服务是否存在
            check_cmd = "systemctl list-unit-files sysagent.service"
            check_process = await asyncio.create_subprocess_shell(
                check_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _stderr = await check_process.communicate()
            output = stdout.decode("utf-8") if stdout else ""

            if "sysagent.service" not in output:
                self._report_progress(
                    state,
                    _("[yellow]sysagent 服务不存在，跳过停止操作[/yellow]"),
                    callback,
                )
                logger.info("sysagent 服务不存在，跳过停止操作")
                return True

            # 检查服务是否正在运行
            status_cmd = "systemctl is-active sysagent"
            status_process = await asyncio.create_subprocess_shell(
                status_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _stderr = await status_process.communicate()
            status = stdout.decode("utf-8").strip() if stdout else ""

            if status != "active":
                self._report_progress(
                    state,
                    _("[green]sysagent 服务未运行，无需停止[/green]"),
                    callback,
                )
                logger.info("sysagent 服务未运行")
                return True

            # 停止服务
            stop_cmd = "sudo systemctl stop sysagent"
            stop_process = await asyncio.create_subprocess_shell(
                stop_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            _stdout, stderr = await stop_process.communicate()

        except Exception:
            self._report_progress(
                state,
                _("[red]停止 sysagent 服务时发生异常[/red]"),
                callback,
            )
            logger.exception("停止 sysagent 服务时发生异常")
            return False
        else:
            if stop_process.returncode == 0:
                self._report_progress(
                    state,
                    _("[green]sysagent 服务已停止[/green]"),
                    callback,
                )
                logger.info("sysagent 服务已停止")
                return True

            error_output = stderr.decode("utf-8") if stderr else ""
            self._report_progress(
                state,
                _("[red]停止 sysagent 服务失败: {error}[/red]").format(
                    error=error_output,
                ),
                callback,
            )
            logger.error("停止 sysagent 服务失败: %s", error_output)
            return False

    async def _start_sysagent_service(
        self,
        state: DeploymentState,
        callback: Callable[[DeploymentState], None] | None,
    ) -> bool:
        """启动 sysagent 服务"""
        self._report_progress(
            state,
            _("[cyan]启动 sysagent 服务...[/cyan]"),
            callback,
        )

        try:
            # 先检查服务是否存在
            check_cmd = "systemctl list-unit-files sysagent.service"
            check_process = await asyncio.create_subprocess_shell(
                check_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _stderr = await check_process.communicate()
            output = stdout.decode("utf-8") if stdout else ""

            if "sysagent.service" not in output:
                self._report_progress(
                    state,
                    _("[yellow]sysagent 服务不存在，跳过启动操作[/yellow]"),
                    callback,
                )
                logger.info("sysagent 服务不存在，跳过启动操作")
                return True

            # 启动服务
            start_cmd = "sudo systemctl start sysagent"
            start_process = await asyncio.create_subprocess_shell(
                start_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            _stdout, stderr = await start_process.communicate()

        except Exception:
            self._report_progress(
                state,
                _("[red]启动 sysagent 服务时发生异常[/red]"),
                callback,
            )
            logger.exception("启动 sysagent 服务时发生异常")
            return False
        else:
            if start_process.returncode == 0:
                self._report_progress(
                    state,
                    _("[green]sysagent 服务已启动[/green]"),
                    callback,
                )
                logger.info("sysagent 服务已启动")
                # 等待服务启动完成
                await asyncio.sleep(2)
                return True

            error_output = stderr.decode("utf-8") if stderr else ""
            self._report_progress(
                state,
                _("[red]启动 sysagent 服务失败: {error}[/red]").format(
                    error=error_output,
                ),
                callback,
            )
            logger.error("启动 sysagent 服务失败: %s", error_output)
            return False

    def _get_service_files(
        self,
        state: DeploymentState,
        callback: Callable[[DeploymentState], None] | None,
        operation_name: str,
    ) -> list[Path] | None:
        """
        获取服务文件列表的通用方法

        Returns:
            list[Path]: 服务文件列表，如果应该跳过操作则返回 None

        """
        if not self.service_dir or not self.service_dir.exists():
            self._report_progress(
                state,
                _("[yellow]服务配置目录不存在: {dir}，跳过{operation}[/yellow]").format(
                    dir=self.service_dir,
                    operation=operation_name,
                ),
                callback,
            )
            logger.warning("服务配置目录不存在: %s", self.service_dir)
            return None

        service_files = list(self.service_dir.glob("*.service"))
        if not service_files:
            self._report_progress(
                state,
                _("[yellow]未找到服务配置文件，跳过{operation}[/yellow]").format(
                    operation=operation_name,
                ),
                callback,
            )
            return None

        return service_files

    async def _install_service_files(
        self,
        state: DeploymentState,
        callback: Callable[[DeploymentState], None] | None,
    ) -> bool:
        """安装 systemd 服务文件"""
        self._report_progress(
            state,
            _("[cyan]安装 systemd 服务文件...[/cyan]"),
            callback,
        )

        # 获取服务文件列表
        service_files = self._get_service_files(state, callback, _("服务文件安装"))
        if service_files is None:
            return True

        installed_count = 0
        for service_file in service_files:
            try:
                if await self._install_single_service_file(service_file, state, callback):
                    installed_count += 1
            except Exception:
                self._report_progress(
                    state,
                    _("    [red]安装 {file} 时发生异常[/red]").format(
                        file=service_file.name,
                    ),
                    callback,
                )
                logger.exception("安装服务文件时发生异常: %s", service_file)

        if installed_count > 0:
            if not await self._reload_systemd_daemon(state, callback):
                return False

            self._report_progress(
                state,
                _("[green]成功安装 {count} 个服务文件[/green]").format(
                    count=installed_count,
                ),
                callback,
            )

        return True

    async def _install_single_service_file(
        self,
        service_file: Path,
        state: DeploymentState,
        callback: Callable[[DeploymentState], None] | None,
    ) -> bool:
        """安装单个服务文件"""
        service_name = service_file.name
        systemd_dir = Path("/etc/systemd/system")
        target_path = systemd_dir / service_name

        self._report_progress(
            state,
            _("  [blue]复制服务文件: {name}[/blue]").format(name=service_name),
            callback,
        )

        try:
            cmd = f"sudo cp {service_file} {target_path}"
            process = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            _stdout, stderr = await process.communicate()

        except Exception:
            self._report_progress(
                state,
                _("    [red]复制 {name} 时发生异常[/red]").format(name=service_name),
                callback,
            )
            logger.exception("复制服务文件时发生异常: %s", service_file)
            return False
        else:
            if process.returncode == 0:
                self._report_progress(
                    state,
                    _("    [green]{name} 复制成功[/green]").format(name=service_name),
                    callback,
                )
                logger.info("服务文件复制成功: %s -> %s", service_file, target_path)
                return True

            error_output = stderr.decode("utf-8") if stderr else ""
            self._report_progress(
                state,
                _("    [red]{name} 复制失败: {error}[/red]").format(
                    name=service_name,
                    error=error_output,
                ),
                callback,
            )
            logger.error("服务文件复制失败: %s, 错误: %s", service_file, error_output)
            return False

    async def _reload_systemd_daemon(
        self,
        state: DeploymentState,
        callback: Callable[[DeploymentState], None] | None,
    ) -> bool:
        """重新加载 systemd 配置"""
        self._report_progress(
            state,
            _("[cyan]重新加载 systemd 配置...[/cyan]"),
            callback,
        )

        try:
            cmd = "sudo systemctl daemon-reload"
            process = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            _stdout, stderr = await process.communicate()

        except Exception:
            self._report_progress(
                state,
                _("[red]重新加载 systemd 配置时发生异常[/red]"),
                callback,
            )
            logger.exception("重新加载 systemd 配置时发生异常")
            return False
        else:
            if process.returncode == 0:
                self._report_progress(
                    state,
                    _("[green]systemd 配置重新加载成功[/green]"),
                    callback,
                )
                logger.info("systemd 配置重新加载成功")
                return True

            error_output = stderr.decode("utf-8") if stderr else ""
            self._report_progress(
                state,
                _("[red]systemd 配置重新加载失败: {error}[/red]").format(
                    error=error_output,
                ),
                callback,
            )
            logger.error("systemd 配置重新加载失败: %s", error_output)
            return False

    async def _start_mcp_servers(
        self,
        state: DeploymentState,
        callback: Callable[[DeploymentState], None] | None,
    ) -> bool:
        """运行脚本拉起 MCP Server 进程"""
        self._report_progress(
            state,
            _("[cyan]启动 MCP Server 进程...[/cyan]"),
            callback,
        )

        if not self.run_script_path or not self.run_script_path.exists():
            self._report_progress(
                state,
                _("[red]MCP 启动脚本不存在: {path}[/red]").format(
                    path=self.run_script_path,
                ),
                callback,
            )
            logger.error("MCP 启动脚本不存在: %s", self.run_script_path)
            return False

        if not await self._cleanup_old_mcp_processes(state, callback):
            self._report_progress(
                state,
                _("[yellow]清理旧进程时遇到问题，但继续执行启动脚本[/yellow]"),
                callback,
            )

        try:
            cmd = f"bash {self.run_script_path}"
            self._report_progress(
                state,
                _("  [blue]执行命令: {cmd}[/blue]").format(cmd=cmd),
                callback,
            )
            logger.info("执行 MCP 启动脚本: %s", cmd)

            process = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )

            stdout, _stderr = await process.communicate()
            output = stdout.decode("utf-8") if stdout else ""

        except Exception:
            error_msg = _("执行 MCP Server 启动脚本失败")
            self._report_progress(state, f"[red]{error_msg}[/red]", callback)
            logger.exception(error_msg)
            return False
        else:
            if process.returncode == 0:
                self._report_progress(
                    state,
                    _("[green]MCP Server 启动脚本执行成功[/green]"),
                    callback,
                )
                logger.info("MCP Server 启动脚本执行成功")
                return True

            self._report_progress(
                state,
                _("[red]MCP Server 启动脚本执行失败 (返回码: {code})[/red]").format(
                    code=process.returncode,
                ),
                callback,
            )
            logger.error("MCP Server 启动脚本执行失败: %s, 输出: %s", cmd, output)
            return False

    async def _cleanup_old_mcp_processes(
        self,
        state: DeploymentState,
        callback: Callable[[DeploymentState], None] | None,
    ) -> bool:
        """检查并清理可能存在的旧 MCP 进程"""
        if not self.service_dir or not self.service_dir.exists():
            return True

        service_files = list(self.service_dir.glob("*.service"))
        if not service_files:
            return True

        for service_file in service_files:
            service_name = service_file.stem
            await self._stop_service(service_name)

        return True

    async def _stop_service(self, service_name: str) -> None:
        """静默停止服务"""
        try:
            status_cmd = f"systemctl is-active {service_name}"
            status_process = await asyncio.create_subprocess_shell(
                status_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await status_process.communicate()
            status = stdout.decode("utf-8").strip() if stdout else ""

            if status == "active":
                stop_cmd = f"sudo systemctl stop {service_name}"
                await asyncio.create_subprocess_shell(
                    stop_cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                logger.debug("已停止旧服务: %s", service_name)

        except (OSError, subprocess.SubprocessError):
            logger.debug("静默停止服务时发生异常: %s", service_name)

    async def _verify_mcp_services(
        self,
        state: DeploymentState,
        callback: Callable[[DeploymentState], None] | None,
    ) -> bool:
        """验证 MCP Server 服务状态"""
        self._report_progress(
            state,
            _("[cyan]验证 MCP Server 服务状态...[/cyan]"),
            callback,
        )

        # 获取服务文件列表
        service_files = self._get_service_files(state, callback, _("服务验证"))
        if service_files is None:
            return True

        failed_services = []
        for service_file in service_files:
            try:
                if not await self._verify_single_service(
                    service_file,
                    state,
                    callback,
                ):
                    failed_services.append(service_file.stem)
            except Exception:
                self._report_progress(
                    state,
                    _("    [red]验证 {file} 时发生异常[/red]").format(
                        file=service_file.stem,
                    ),
                    callback,
                )
                logger.exception("验证服务时发生异常: %s", service_file)
                failed_services.append(service_file.stem)

        if failed_services:
            self._report_progress(
                state,
                _("[red]关键服务状态异常: {services}，停止初始化[/red]").format(
                    services=", ".join(failed_services),
                ),
                callback,
            )
            logger.error("关键服务状态异常，停止初始化: %s", failed_services)
            return False

        self._report_progress(
            state,
            _("[green]MCP Server 服务验证完成[/green]"),
            callback,
        )
        return True

    async def _verify_single_service(
        self,
        service_file: Path,
        state: DeploymentState,
        callback: Callable[[DeploymentState], None] | None,
        retry_count: int = 0,
    ) -> bool:
        """验证单个服务状态"""
        await asyncio.sleep(0.1)

        service_name = service_file.stem
        max_retries = 6
        if retry_count > max_retries:
            self._report_progress(
                state,
                _("    [red]{name} 启动超时 (30秒)[/red]").format(name=service_name),
                callback,
            )
            logger.error("服务启动超时: %s", service_name)
            return False

        if retry_count == 0:
            self._report_progress(
                state,
                _("  [magenta]检查服务状态: {name}[/magenta]").format(
                    name=service_name,
                ),
                callback,
            )
        else:
            self._report_progress(
                state,
                _("    [dim]{name} 重新检查状态... (第 {count} 次)[/dim]").format(
                    name=service_name,
                    count=retry_count,
                ),
                callback,
            )

        try:
            cmd = f"systemctl status {service_name}"
            process = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, _stderr = await process.communicate()
            output = stdout.decode("utf-8") if stdout else ""

        except Exception:
            self._report_progress(
                state,
                _("    [red]检查 {name} 状态失败[/red]").format(name=service_name),
                callback,
            )
            logger.exception("检查服务状态失败: %s", service_name)
            return False
        else:
            # systemctl status 返回码: 0=active, 1=dead, 2=unknown, 3=not-found, 4=permission-denied
            if process.returncode == 0 and "active (running)" in output.lower():
                self._report_progress(
                    state,
                    _("    [green]{name} 运行正常[/green]").format(name=service_name),
                    callback,
                )
                logger.info("服务运行正常: %s", service_name)
                return True

            if "failed" in output.lower() or "code=exited" in output.lower():
                self._report_progress(
                    state,
                    _("    [red]{name} 启动失败[/red]").format(name=service_name),
                    callback,
                )
                logger.error("服务启动失败: %s\n%s", service_name, output)
                return False

            if "activating" in output.lower():
                await asyncio.sleep(5)
                return await self._verify_single_service(
                    service_file,
                    state,
                    callback,
                    retry_count + 1,
                )

            self._report_progress(
                state,
                _("    [red]{name} 状态异常[/red]").format(name=service_name),
                callback,
            )
            logger.error("服务状态异常: %s\n%s", service_name, output)
            return False
