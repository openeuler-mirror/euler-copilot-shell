"""
Agent 管理模块。

处理 MCP 服务和智能体的注册、安装、激活和管理。

该模块提供:
- McpConfig: MCP 配置数据模型
- McpConfigLoader: MCP 配置文件加载器
- ApiClient: HTTP API 客户端
- AgentManager: 智能体管理器主类
"""

from __future__ import annotations

import asyncio
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx
import toml

from config.manager import ConfigManager
from i18n.manager import _
from log.manager import get_logger

from .models import AgentInitStatus, DeploymentState

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

logger = get_logger(__name__)

# HTTP 状态码常量
HTTP_OK = 200


class ConfigError(Exception):
    """配置错误异常"""


class ApiError(Exception):
    """API 错误异常"""


@dataclass
class McpConfig:
    """MCP 配置模型"""

    name: str
    description: str
    overview: str
    config: dict[str, Any]
    mcp_type: str


@dataclass
class McpServerInfo:
    """MCP 服务信息"""

    service_id: str
    name: str
    config_path: Path
    config: McpConfig


@dataclass
class AgentInfo:
    """智能体信息"""

    app_id: str
    name: str
    description: str
    mcp_services: list[str]


@dataclass
class AppConfig:
    """应用配置信息（从 TOML 文件读取）"""

    app_type: str
    name: str
    description: str
    mcp_path: list[str]
    published: bool = True


class McpConfigLoader:
    """MCP 配置加载器"""

    def __init__(self, config_dir: Path) -> None:
        """初始化配置加载器"""
        self.config_dir = config_dir

    def load_all_configs(self) -> list[tuple[Path, McpConfig]]:
        """加载所有 MCP 配置"""
        configs = []
        if not self.config_dir.exists():
            msg = f"配置目录不存在: {self.config_dir}"
            logger.error(msg)
            raise ConfigError(msg)

        for subdir in self.config_dir.iterdir():
            if subdir.is_dir():
                config_file = subdir / "config.json"
                if config_file.exists():
                    try:
                        config = self._load_config(config_file, subdir.name)
                        configs.append((config_file, config))
                        logger.info("加载 MCP 配置: %s", subdir.name)
                    except (json.JSONDecodeError, KeyError):
                        logger.exception("加载配置文件失败: %s", config_file)
                        continue

        if not configs:
            msg = f"未找到有效的 MCP 配置文件在: {self.config_dir}"
            logger.warning(msg)

        return configs

    def _load_config(self, config_file: Path, name: str) -> McpConfig:
        """加载单个配置文件"""
        with config_file.open(encoding="utf-8") as f:
            config_data = json.load(f)

        return McpConfig(
            name=config_data.get("name", name),
            description=config_data.get("description", name),
            overview=config_data.get("overview", name),
            config=config_data.get("config", {}),
            mcp_type=config_data.get("mcpType", "sse"),
        )


class ApiClient:
    """API 客户端"""

    def __init__(self, server_ip: str, server_port: int) -> None:
        """初始化 API 客户端"""
        self.base_url = f"http://{server_ip}:{server_port}"
        self.timeout = 10.0

    async def register_mcp_service(self, config: McpConfig) -> str:
        """注册 MCP 服务"""
        url = f"{self.base_url}/api/mcp"
        payload = {
            "name": config.name,
            "description": config.description,
            "overview": config.overview,
            "config": config.config,
            "mcpType": config.mcp_type,
        }

        logger.info("注册 MCP 服务: %s", config.name)
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(url, json=payload)
                response.raise_for_status()

                result = response.json()
                if result.get("code") != HTTP_OK:
                    msg = f"注册 MCP 服务失败: {result.get('message', 'Unknown error')}"
                    logger.error(msg)
                    raise ApiError(msg)

                service_id = result["result"]["serviceId"]
                logger.info("MCP 服务注册成功: %s -> %s", config.name, service_id)

            except httpx.RequestError as e:
                msg = f"注册 MCP 服务网络错误: {e}"
                logger.exception(msg)
                raise ApiError(msg) from e

            else:
                return service_id

    async def install_mcp_service(self, service_id: str) -> None:
        """安装 MCP 服务"""
        url = f"{self.base_url}/api/mcp/{service_id}/install?install=true"

        logger.info("安装 MCP 服务: %s", service_id)
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(url)
                response.raise_for_status()
                logger.info("MCP 服务安装请求已发送: %s", service_id)
            except httpx.RequestError as e:
                msg = f"安装 MCP 服务网络错误: {e}"
                logger.exception(msg)
                raise ApiError(msg) from e

    async def check_mcp_service_status(self, service_id: str) -> str | None:
        """
        检查 MCP 服务状态

        返回值:
        - "ready": 安装完成且成功
        - "failed": 安装失败
        - "cancelled": 安装取消
        - "init": 初始化中
        - "installing": 安装中
        - None: 网络错误或无法获取状态
        """
        url = f"{self.base_url}/api/mcp/{service_id}"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(url)
                response.raise_for_status()

                result = response.json()
                # 检查 API 调用是否成功
                if result.get("code") != HTTP_OK:
                    logger.warning("获取 MCP 服务状态失败: %s", result.get("message", "Unknown error"))
                    return None

                # 获取服务状态
                service_result = result.get("result", {})
                status = service_result.get("status")

                if status in ("ready", "failed", "cancelled", "init", "installing"):
                    return status

                logger.warning("未知的 MCP 服务状态: %s", status)

            except httpx.RequestError as e:
                logger.debug("检查 MCP 服务状态网络错误: %s", e)

            return None

    async def wait_for_installation(
        self,
        service_id: str,
        max_wait_time: int = 300,
        check_interval: int = 2,
    ) -> bool:
        """
        等待 MCP 服务安装完成

        只要接口能打通、后端返回的状态没有明确成功或失败或取消，就会一直等下去。
        只有在明确失败或取消时才返回 False。
        """
        logger.info("等待 MCP 服务安装完成: %s", service_id)

        attempt = 0
        while True:
            status = await self.check_mcp_service_status(service_id)

            if status == "ready":
                logger.info("MCP 服务安装完成: %s", service_id)
                return True

            if status in ("failed", "cancelled"):
                logger.error("MCP 服务安装失败或被取消: %s (状态: %s)", service_id, status)
                return False

            if status in ("init", "installing"):
                logger.debug(
                    "MCP 服务 %s %s中... (第 %d 次检查)",
                    service_id,
                    "初始化" if status == "init" else "安装",
                    attempt + 1,
                )
            elif status is None:
                logger.debug("MCP 服务 %s 状态检查失败，继续等待... (第 %d 次检查)", service_id, attempt + 1)
            else:
                logger.debug("MCP 服务 %s 状态未知: %s，继续等待... (第 %d 次检查)", service_id, status, attempt + 1)

            # 只有在超过最大等待时间时才超时返回，但仅在没有明确失败的情况下
            attempt += 1
            if attempt * check_interval >= max_wait_time:
                # 这里不返回 False，而是继续等待，因为要求只要接口能打通就一直等
                logger.warning("MCP 服务安装等待超时: %s (已等待 %d 秒，但将继续尝试)", service_id, max_wait_time)

            await asyncio.sleep(check_interval)

    async def activate_mcp_service(self, service_id: str) -> None:
        """激活 MCP 服务"""
        url = f"{self.base_url}/api/mcp/{service_id}"
        payload = {"active": True}

        logger.info("激活 MCP 服务: %s", service_id)
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(url, json=payload)
                response.raise_for_status()

                result = response.json()
                if result.get("code") != HTTP_OK:
                    msg = f"激活 MCP 服务失败: {result.get('message', 'Unknown error')}"
                    logger.error(msg)
                    raise ApiError(msg)

                logger.info("MCP 服务激活成功: %s", service_id)

            except httpx.RequestError as e:
                msg = f"激活 MCP 服务网络错误: {e}"
                logger.exception(msg)
                raise ApiError(msg) from e

    async def create_agent(
        self,
        name: str,
        description: str,
        mcp_service_ids: list[str],
    ) -> str:
        """创建智能体"""
        url = f"{self.base_url}/api/app"
        payload = {
            "appType": "agent",
            "name": name,
            "description": description,
            "mcpService": mcp_service_ids,
            "permission": {
                "visibility": "public",
            },
        }

        logger.info("创建智能体: %s (包含 %d 个 MCP 服务)", name, len(mcp_service_ids))
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(url, json=payload)
                response.raise_for_status()

                result = response.json()
                if result.get("code") != HTTP_OK:
                    msg = f"创建智能体失败: {result.get('message', 'Unknown error')}"
                    logger.error(msg)
                    raise ApiError(msg)

                app_id = result["result"]["appId"]
                logger.info("智能体创建成功: %s -> %s", name, app_id)

            except httpx.RequestError as e:
                msg = f"创建智能体网络错误: {e}"
                logger.exception(msg)
                raise ApiError(msg) from e

            else:
                return app_id

    async def publish_agent(self, app_id: str) -> None:
        """发布智能体"""
        url = f"{self.base_url}/api/app/{app_id}"

        logger.info("发布智能体: %s", app_id)
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(url)
                response.raise_for_status()

                result = response.json()
                if result.get("code") != HTTP_OK:
                    msg = f"发布智能体失败: {result.get('message', 'Unknown error')}"
                    logger.error(msg)
                    raise ApiError(msg)

                logger.info("智能体发布成功: %s", app_id)

            except httpx.RequestError as e:
                msg = f"发布智能体网络错误: {e}"
                logger.exception(msg)
                raise ApiError(msg) from e


class AgentManager:
    """智能体管理器"""

    def __init__(self, server_ip: str = "127.0.0.1", server_port: int = 8002) -> None:
        """初始化智能体管理器"""
        self.api_client = ApiClient(server_ip, server_port)
        self.config_manager = ConfigManager()

        resource_paths = [
            Path("/usr/lib/euler-copilot-framework/mcp_center"),  # 生产环境
            Path("scripts/deploy/5-resource"),  # 旧的开发环境（兼容）
            Path(__file__).parent.parent.parent / "scripts/deploy/5-resource",  # 旧的开发环境（绝对路径兼容）
        ]

        self.resource_dir = next((p for p in resource_paths if p.exists()), None)
        if not self.resource_dir:
            logger.error("[DeploymentHelper] 未找到有效的资源路径")
            return
        logger.info("[DeploymentHelper] 使用资源路径: %s", self.resource_dir)

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
        self._report_progress(state, _("[bold blue]开始初始化智能体...[/bold blue]"), progress_callback)

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
        # 1. 安装 systemd 服务文件
        if not await self._install_service_files(state, progress_callback):
            return AgentInitStatus.FAILED

        # 2. 运行脚本拉起 MCP Server 进程
        if not await self._start_mcp_servers(state, progress_callback):
            return AgentInitStatus.FAILED

        # 3. 验证 MCP Server 服务状态
        if not await self._verify_mcp_services(state, progress_callback):
            return AgentInitStatus.FAILED

        # 4. 加载 MCP 配置并注册服务
        mcp_service_mapping = await self._register_all_mcp_services(state, progress_callback)
        if not mcp_service_mapping:
            return AgentInitStatus.FAILED

        # 5. 读取应用配置并创建智能体
        default_app_id = await self._create_agents_from_config(
            mcp_service_mapping,
            state,
            progress_callback,
        )

        if default_app_id:
            self._report_progress(
                state,
                _("[bold green]智能体初始化完成! 默认 App ID: {app_id}[/bold green]").format(app_id=default_app_id),
                progress_callback,
            )
            logger.info("智能体初始化成功完成，默认 App ID: %s", default_app_id)
            return AgentInitStatus.SUCCESS

        # 如果没有创建任何智能体，显示警告并返回成功状态
        self._report_progress(state, _("[yellow]未能创建任何智能体[/yellow]"), progress_callback)
        return AgentInitStatus.SUCCESS

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

        # 获取所有 .service 文件
        service_files = list(self.service_dir.glob("*.service"))
        if not service_files:
            self._report_progress(
                state,
                _("[yellow]未找到服务配置文件，跳过{operation}[/yellow]").format(operation=operation_name),
                callback,
            )
            return None

        return service_files

    async def _process_service_files(
        self,
        service_files: list[Path],
        state: DeploymentState,
        callback: Callable[[DeploymentState], None] | None,
        processor_func: Callable[
            [Path, DeploymentState, Callable[[DeploymentState], None] | None],
            Awaitable[tuple[bool, str]],
        ],
    ) -> tuple[bool, list[str], list[str]]:
        """
        处理服务文件的通用框架

        Args:
            service_files: 要处理的服务文件列表
            state: 部署状态
            callback: 进度回调函数
            processor_func: 处理单个文件的函数，返回 (成功标志, 文件名)

        Returns:
            tuple[bool, list[str], list[str]]: (总体是否成功, 成功的文件列表, 失败的文件列表)

        """
        success_files = []
        failed_files = []

        for service_file in service_files:
            try:
                success, file_identifier = await processor_func(service_file, state, callback)
                if success:
                    success_files.append(file_identifier)
                else:
                    failed_files.append(file_identifier)
            except Exception:
                file_identifier = service_file.stem
                self._report_progress(
                    state,
                    _("    [red]处理 {file} 时发生异常[/red]").format(file=file_identifier),
                    callback,
                )
                logger.exception("处理服务文件时发生异常: %s", service_file)
                failed_files.append(file_identifier)

        return len(failed_files) == 0, success_files, failed_files

    async def _install_service_files(
        self,
        state: DeploymentState,
        callback: Callable[[DeploymentState], None] | None,
    ) -> bool:
        """安装 systemd 服务文件"""
        self._report_progress(state, _("[cyan]安装 systemd 服务文件...[/cyan]"), callback)

        # 获取服务文件列表
        service_files = self._get_service_files(state, callback, _("服务文件安装"))
        if service_files is None:
            return True

        # 处理所有服务文件
        _overall_success, installed_files, _failed_files = await self._process_service_files(
            service_files,
            state,
            callback,
            self._install_single_service_file,
        )

        # 如果有成功安装的文件，重新加载 systemd 配置
        if installed_files:
            if not await self._reload_systemd_daemon(state, callback):
                return False

            self._report_progress(
                state,
                _("[green]成功安装 {count} 个服务文件[/green]").format(count=len(installed_files)),
                callback,
            )

        return True

    async def _install_single_service_file(
        self,
        service_file: Path,
        state: DeploymentState,
        callback: Callable[[DeploymentState], None] | None,
    ) -> tuple[bool, str]:
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
            # 复制服务文件到 systemd 目录
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
            return False, service_name
        else:
            if process.returncode == 0:
                self._report_progress(
                    state,
                    _("    [green]{name} 复制成功[/green]").format(name=service_name),
                    callback,
                )
                logger.info("服务文件复制成功: %s -> %s", service_file, target_path)
                return True, service_name

            error_output = stderr.decode("utf-8") if stderr else ""
            self._report_progress(
                state,
                _("    [red]{name} 复制失败: {error}[/red]").format(name=service_name, error=error_output),
                callback,
            )
            logger.error("服务文件复制失败: %s, 错误: %s", service_file, error_output)
            return False, service_name

    async def _reload_systemd_daemon(
        self,
        state: DeploymentState,
        callback: Callable[[DeploymentState], None] | None,
    ) -> bool:
        """重新加载 systemd 配置"""
        self._report_progress(state, _("[cyan]重新加载 systemd 配置...[/cyan]"), callback)

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
                _("[red]systemd 配置重新加载失败: {error}[/red]").format(error=error_output),
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
        self._report_progress(state, _("[cyan]启动 MCP Server 进程...[/cyan]"), callback)

        if not self.run_script_path or not self.run_script_path.exists():
            self._report_progress(
                state,
                _("[red]MCP 启动脚本不存在: {path}[/red]").format(path=self.run_script_path),
                callback,
            )
            logger.error("MCP 启动脚本不存在: %s", self.run_script_path)
            return False

        # 1. 先检查并清理可能存在的旧进程
        if not await self._cleanup_old_mcp_processes(state, callback):
            # 清理失败不会阻止继续执行，只是记录警告
            self._report_progress(
                state,
                _("[yellow]清理旧进程时遇到问题，但继续执行启动脚本[/yellow]"),
                callback,
            )

        # 2. 执行启动脚本
        try:
            # 执行 run.sh 脚本
            cmd = f"bash {self.run_script_path}"
            self._report_progress(state, _("  [blue]执行命令: {cmd}[/blue]").format(cmd=cmd), callback)
            logger.info("执行 MCP 启动脚本: %s", cmd)

            process = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )

            stdout, _stderr = await process.communicate()
            output = stdout.decode("utf-8") if stdout else ""

            if process.returncode == 0:
                self._report_progress(
                    state,
                    _("[green]MCP Server 启动脚本执行成功[/green]"),
                    callback,
                )
                logger.info("MCP Server 启动脚本执行成功")
                return True

        except Exception:
            error_msg = _("执行 MCP Server 启动脚本失败")
            self._report_progress(state, f"[red]{error_msg}[/red]", callback)
            logger.exception(error_msg)
            return False
        else:
            self._report_progress(
                state,
                _("[red]MCP Server 启动脚本执行失败 (返回码: {code})[/red]").format(code=process.returncode),
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
        # 静默获取服务文件列表
        if not self.service_dir or not self.service_dir.exists():
            return True

        service_files = list(self.service_dir.glob("*.service"))
        if not service_files:
            return True

        # 静默清理服务
        for service_file in service_files:
            service_name = service_file.stem  # 去掉 .service 后缀
            await self._stop_service(service_name)

        return True

    async def _stop_service(self, service_name: str) -> None:
        """静默停止服务"""
        try:
            # 检查服务状态
            status_cmd = f"systemctl is-active {service_name}"
            status_process = await asyncio.create_subprocess_shell(
                status_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await status_process.communicate()
            status = stdout.decode("utf-8").strip() if stdout else ""

            # 如果服务正在运行，静默停止它
            if status == "active":
                stop_cmd = f"sudo systemctl stop {service_name}"
                await asyncio.create_subprocess_shell(
                    stop_cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
        except (OSError, subprocess.SubprocessError):
            # 静默忽略任何错误
            logger.debug("静默停止服务时发生异常: %s", service_name)

    async def _verify_mcp_services(
        self,
        state: DeploymentState,
        callback: Callable[[DeploymentState], None] | None,
    ) -> bool:
        """验证 MCP Server 服务状态"""
        self._report_progress(state, _("[cyan]验证 MCP Server 服务状态...[/cyan]"), callback)

        # 获取服务文件列表
        service_files = self._get_service_files(state, callback, _("服务验证"))
        if service_files is None:
            return True

        # 处理所有服务文件
        _overall_success, _active_services, failed_services = await self._process_service_files(
            service_files,
            state,
            callback,
            self._verify_single_service,
        )

        if failed_services:
            self._report_progress(
                state,
                _("[red]关键服务状态异常: {services}，停止初始化[/red]").format(services=", ".join(failed_services)),
                callback,
            )
            logger.error("关键服务状态异常，停止初始化: %s", failed_services)
            return False

        self._report_progress(state, _("[green]MCP Server 服务验证完成[/green]"), callback)
        return True

    async def _verify_single_service(
        self,
        service_file: Path,
        state: DeploymentState,
        callback: Callable[[DeploymentState], None] | None,
        retry_count: int = 0,
    ) -> tuple[bool, str]:
        """验证单个服务状态"""
        await asyncio.sleep(0.1)

        service_name = service_file.stem  # 去掉 .service 后缀

        # 限制递归次数，最多重试6次（30秒）
        max_retries = 6
        if retry_count > max_retries:
            self._report_progress(
                state,
                _("    [red]{name} 启动超时 (30秒)[/red]").format(name=service_name),
                callback,
            )
            logger.error("服务启动超时: %s", service_name)
            return False, service_name

        if retry_count == 0:
            self._report_progress(
                state,
                _("  [magenta]检查服务状态: {name}[/magenta]").format(name=service_name),
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
            # 使用 systemctl status 获取详细状态信息
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
            return False, service_name
        else:
            # systemctl status 返回码: 0=active, 1=dead, 2=unknown, 3=not-found, 4=permission-denied
            if process.returncode == 0 and "active (running)" in output.lower():
                # 服务正常运行
                self._report_progress(
                    state,
                    _("    [green]{service_name} 状态正常 (active running)[/green]").format(service_name=service_name),
                    callback,
                )
                logger.info("服务状态正常: %s", service_name)
                return True, service_name

            # 分析输出内容，检查是否有失败信息
            if "failed" in output.lower() or "code=exited" in output.lower():
                self._report_progress(
                    state,
                    _("    [red]{service_name} 服务启动失败[/red]").format(service_name=service_name),
                    callback,
                )
                logger.error("服务启动失败: %s, 详细信息: %s", service_name, output.strip())
                return False, service_name

            # 检查是否真的在启动中（activating 状态）
            if "activating" in output.lower() and "start" in output.lower():
                if retry_count == 0:
                    self._report_progress(
                        state,
                        _("    [yellow]{service_name} 正在启动中，等待启动完成...[/yellow]").format(
                            service_name=service_name,
                        ),
                        callback,
                    )
                    logger.info("服务正在启动中，等待启动完成: %s", service_name)

                # 等待3秒后递归调用自己
                await asyncio.sleep(3)
                return await self._verify_single_service(service_file, state, callback, retry_count + 1)

            # 其他状态都认为是异常
            self._report_progress(
                state,
                _("    [red]{service_name} 状态异常 (返回码: {returncode})[/red]").format(
                    service_name=service_name,
                    returncode=process.returncode,
                ),
                callback,
            )
            logger.warning("服务状态异常: %s, 返回码: %d, 输出: %s", service_name, process.returncode, output.strip())
            return False, service_name

    async def _register_all_mcp_services(
        self,
        state: DeploymentState,
        callback: Callable[[DeploymentState], None] | None,
    ) -> dict[str, str]:
        """
        注册所有 MCP 服务

        Returns:
            dict[str, str]: MCP 路径名 -> 服务 ID 的映射

        """
        self._report_progress(state, _("[cyan]注册 MCP 服务...[/cyan]"), callback)

        # 加载 MCP 配置
        configs = await self._load_mcp_configs(state, callback)
        if not configs:
            return {}

        mcp_service_mapping = {}

        for config_path, config in configs:
            service_id = await self._process_mcp_service(config, state, callback)
            if service_id:
                # 使用配置目录名作为 MCP 路径名
                mcp_path_name = config_path.parent.name
                mcp_service_mapping[mcp_path_name] = service_id
                self._report_progress(
                    state,
                    _("  [green]{name} 注册成功: {mcp_path} -> {service_id}[/green]").format(
                        name=config.name,
                        mcp_path=mcp_path_name,
                        service_id=service_id,
                    ),
                    callback,
                )
            else:
                self._report_progress(
                    state,
                    _("  [red]MCP 服务 {name} 注册失败[/red]").format(name=config.name),
                    callback,
                )

        self._report_progress(
            state,
            _("[green]MCP 服务注册完成，成功 {count} 个[/green]").format(count=len(mcp_service_mapping)),
            callback,
        )
        return mcp_service_mapping

    async def _create_agents_from_config(
        self,
        mcp_service_mapping: dict[str, str],
        state: DeploymentState,
        callback: Callable[[DeploymentState], None] | None,
    ) -> str | None:
        """从配置文件创建智能体"""
        self._report_progress(state, _("[cyan]读取应用配置并创建智能体...[/cyan]"), callback)

        # 读取应用配置
        app_configs = await self._load_app_configs(state, callback)
        if not app_configs:
            return None

        created_agents = []
        default_app_id = None

        for i, app_config in enumerate(app_configs):
            app_id = await self._create_single_agent(
                app_config,
                mcp_service_mapping,
                state,
                callback,
            )

            if app_id:
                created_agents.append(app_id)

                # 第一个智能体设置为默认智能体
                if i == 0:
                    default_app_id = app_id
                    self._report_progress(
                        state,
                        _("  [dim]设置默认智能体: {name}[/dim]").format(name=app_config.name),
                        callback,
                    )
                    self.config_manager.set_default_app(app_id)

        if created_agents:
            self._report_progress(
                state,
                _("[green]成功创建 {count} 个智能体[/green]").format(count=len(created_agents)),
                callback,
            )
            return default_app_id

        self._report_progress(state, _("[red]未能创建任何智能体[/red]"), callback)
        return None

    async def _create_single_agent(
        self,
        app_config: AppConfig,
        mcp_service_mapping: dict[str, str],
        state: DeploymentState,
        callback: Callable[[DeploymentState], None] | None,
    ) -> str | None:
        """创建单个智能体"""
        self._report_progress(
            state,
            _("[magenta]创建智能体: {name}[/magenta]").format(name=app_config.name),
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
                _("  [yellow]缺少 MCP 服务: {services}，跳过[/yellow]").format(services=", ".join(missing_services)),
                callback,
            )
            logger.warning("智能体 %s 缺少 MCP 服务: %s", app_config.name, missing_services)
            return None

        if not mcp_service_ids:
            self._report_progress(
                state,
                _("  [yellow]智能体 {name} 没有可用的 MCP 服务，跳过[/yellow]").format(name=app_config.name),
                callback,
            )
            return None

        try:
            # 创建智能体
            app_id = await self.api_client.create_agent(
                app_config.name,
                app_config.description,
                mcp_service_ids,
            )

            # 发布智能体
            if app_config.published:
                await self.api_client.publish_agent(app_id)

        except Exception:
            self._report_progress(
                state,
                _("  [red]创建智能体 {name} 失败[/red]").format(name=app_config.name),
                callback,
            )
            logger.exception("创建智能体失败: %s", app_config.name)
            return None
        else:
            self._report_progress(
                state,
                _("  [green]智能体 {name} 创建成功: {app_id}[/green]").format(
                    name=app_config.name,
                    app_id=app_id,
                ),
                callback,
            )
            return app_id

    def _resolve_mcp_services(
        self,
        mcp_paths: list[str],
        mcp_service_mapping: dict[str, str],
    ) -> tuple[list[str], list[str]]:
        """解析 MCP 路径为服务 ID"""
        mcp_service_ids = []
        missing_services = []

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
        self._report_progress(state, _("[cyan]加载应用配置文件...[/cyan]"), callback)

        if not self.app_config_path or not self.app_config_path.exists():
            self._report_progress(
                state,
                _("[red]应用配置文件不存在: {path}[/red]").format(path=self.app_config_path),
                callback,
            )
            logger.error("应用配置文件不存在: %s", self.app_config_path)
            return []

        try:
            with self.app_config_path.open(encoding="utf-8") as f:
                config_data = toml.load(f)

            applications = config_data.get("applications", [])
            if not applications:
                self._report_progress(
                    state,
                    _("[yellow]配置文件中没有找到应用定义[/yellow]"),
                    callback,
                )
                logger.warning("配置文件中没有找到应用定义")
                return []

            app_configs = []
            for app_data in applications:
                try:
                    app_config = AppConfig(
                        app_type=app_data.get("appType", "agent"),
                        name=app_data["name"],
                        description=app_data["description"],
                        mcp_path=app_data["mcpPath"],
                        published=app_data.get("published", True),
                    )
                    app_configs.append(app_config)
                except KeyError as e:
                    self._report_progress(
                        state,
                        _("  [red]应用配置缺少必需字段: {field}[/red]").format(field=e),
                        callback,
                    )
                    logger.exception("应用配置缺少必需字段")
                    continue

        except Exception:
            error_msg = _("加载应用配置文件失败: {path}").format(path=self.app_config_path)
            self._report_progress(state, f"[red]{error_msg}[/red]", callback)
            logger.exception(error_msg)
            return []
        else:
            self._report_progress(
                state,
                _("[green]成功加载 {count} 个应用配置[/green]").format(count=len(app_configs)),
                callback,
            )
            return app_configs

    async def _load_mcp_configs(
        self,
        state: DeploymentState,
        callback: Callable[[DeploymentState], None] | None,
    ) -> list[tuple[Path, McpConfig]]:
        """加载 MCP 配置"""
        self._report_progress(state, _("[cyan]加载 MCP 配置文件...[/cyan]"), callback)

        config_loader = McpConfigLoader(self.mcp_config_dir)
        configs = config_loader.load_all_configs()

        if not configs:
            self._report_progress(state, _("[yellow]未找到 MCP 配置文件[/yellow]"), callback)
            return []

        self._report_progress(
            state,
            _("[green]成功加载 {count} 个 MCP 配置[/green]").format(count=len(configs)),
            callback,
        )
        return configs

    async def _process_mcp_service(
        self,
        config: McpConfig,
        state: DeploymentState,
        callback: Callable[[DeploymentState], None] | None,
    ) -> str | None:
        """处理单个 MCP 服务"""
        # 如果是 SSE 类型，先验证 URL 可用且为 SSE
        if config.mcp_type == "sse":
            valid = await self._validate_sse_endpoint(config, state, callback)
            if not valid:
                self._report_progress(
                    state,
                    _("  [red]MCP 服务 {name} SSE Endpoint 验证失败[/red]").format(name=config.name),
                    callback,
                )
                return None
        try:
            # 注册服务
            service_id = await self._register_mcp_service(config, state, callback)

            # 安装并等待完成
            if not await self._install_and_wait_mcp_service(service_id, config.name, state, callback):
                return None

            # 激活服务
            await self._activate_mcp_service(service_id, config.name, state, callback)

        except (ApiError, httpx.RequestError, Exception) as e:
            self._report_progress(
                state,
                _("  [red]{name} 处理失败: {error}[/red]").format(name=config.name, error=e),
                callback,
            )
            logger.exception("MCP 服务 %s 处理失败", config.name)
            return None

        return service_id

    async def _register_mcp_service(
        self,
        config: McpConfig,
        state: DeploymentState,
        callback: Callable[[DeploymentState], None] | None,
    ) -> str:
        """注册 MCP 服务"""
        self._report_progress(state, _("  [blue]注册 {name}...[/blue]").format(name=config.name), callback)
        return await self.api_client.register_mcp_service(config)

    async def _install_and_wait_mcp_service(
        self,
        service_id: str,
        config_name: str,
        state: DeploymentState,
        callback: Callable[[DeploymentState], None] | None,
    ) -> bool:
        """安装并等待 MCP 服务完成"""
        self._report_progress(
            state,
            _("  [cyan]安装 {name} (ID: {service_id})...[/cyan]").format(name=config_name, service_id=service_id),
            callback,
        )
        await self.api_client.install_mcp_service(service_id)

        self._report_progress(state, _("  [dim]等待 {name} 安装完成...[/dim]").format(name=config_name), callback)
        if not await self.api_client.wait_for_installation(service_id):
            self._report_progress(state, _("  [red]{name} 安装超时[/red]").format(name=config_name), callback)
            return False

        return True

    async def _activate_mcp_service(
        self,
        service_id: str,
        config_name: str,
        state: DeploymentState,
        callback: Callable[[DeploymentState], None] | None,
    ) -> None:
        """激活 MCP 服务"""
        self._report_progress(state, _("  [yellow]激活 {name}...[/yellow]").format(name=config_name), callback)
        await self.api_client.activate_mcp_service(service_id)
        self._report_progress(state, _("  [green]{name} 处理完成[/green]").format(name=config_name), callback)

    async def _validate_sse_endpoint(
        self,
        config: McpConfig,
        state: DeploymentState,
        callback: Callable[[DeploymentState], None] | None,
    ) -> bool:
        """验证 SSE Endpoint 是否可用"""
        url = config.config.get("url") or ""
        self._report_progress(
            state,
            _("[magenta]验证 SSE Endpoint: {name} -> {url}[/magenta]").format(name=config.name, url=url),
            callback,
        )

        # 重试配置
        max_attempts = 5  # 10秒 / 2秒 = 5次
        retry_interval = 2  # 2秒重试间隔

        for attempt in range(1, max_attempts + 1):
            # 方式1：先尝试原来的简单 GET 请求方式
            if await self._try_simple_sse_check(url, config.name, attempt, max_attempts):
                self._report_progress(
                    state,
                    _("  [green]{name} SSE Endpoint 验证通过[/green]").format(name=config.name),
                    callback,
                )
                logger.info("SSE Endpoint 简单验证成功: %s (尝试 %d 次)", url, attempt)
                return True

            # 方式2：如果简单方式失败，尝试 MCP 协议 initialize 方法
            if await self._try_mcp_initialize_check(url, config.name, attempt, max_attempts):
                self._report_progress(
                    state,
                    _("  [green]{name} SSE Endpoint 验证通过[/green]").format(name=config.name),
                    callback,
                )
                logger.info("SSE Endpoint MCP 协议验证成功: %s (尝试 %d 次)", url, attempt)
                return True

            # 如果还有重试机会，等待后继续
            if attempt < max_attempts:
                await asyncio.sleep(retry_interval)

        # 所有尝试都失败了
        self._report_progress(
            state,
            _("  [red]{name} SSE Endpoint 验证失败: 30秒内无法连接[/red]").format(name=config.name),
            callback,
        )
        logger.error(
            "SSE Endpoint 验证最终失败: %s (尝试了 %d 次，耗时 %d 秒)",
            url,
            max_attempts,
            max_attempts * retry_interval,
        )
        return False

    async def _try_simple_sse_check(
        self,
        url: str,
        config_name: str,
        attempt: int,
        max_attempts: int,
    ) -> bool:
        """尝试简单的 SSE 检查（原来的方式）"""
        try:
            # 使用流式请求，只读取响应头，避免 SSE 连接一直保持开放
            async with (
                httpx.AsyncClient(timeout=self.api_client.timeout) as client,
                client.stream("GET", url, headers={"Accept": "text/event-stream"}) as response,
            ):
                if response.status_code == HTTP_OK:
                    logger.debug("SSE Endpoint 简单检查成功: %s (尝试 %d 次)", url, attempt)
                    return True

                logger.debug(
                    "SSE Endpoint 简单检查响应码非 200: %s, 状态码: %d, 尝试: %d/%d",
                    url,
                    response.status_code,
                    attempt,
                    max_attempts,
                )

        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            logger.debug("SSE Endpoint 简单检查连接失败: %s, 错误: %s, 尝试: %d/%d", url, e, attempt, max_attempts)

        return False

    async def _try_mcp_initialize_check(
        self,
        url: str,
        config_name: str,
        attempt: int,
        max_attempts: int,
    ) -> bool:
        """尝试 MCP 协议的 initialize 检查"""
        # MCP 协议初始化请求负载
        mcp_payload = {
            "jsonrpc": "2.0",
            "id": "health-check",
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "Witty Assistant",
                    "version": "1.0",
                },
            },
        }

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json,text/event-stream",
            "MCP-Protocol-Version": "2024-11-05",
        }

        try:
            async with httpx.AsyncClient(timeout=self.api_client.timeout) as client:
                response = await client.post(url, json=mcp_payload, headers=headers)

                if response.status_code == HTTP_OK:
                    # 尝试解析 SSE 响应，确保是有效的 MCP JSON-RPC 响应
                    try:
                        response_text = response.text

                        # 检查是否是 SSE 格式的响应
                        if "event: message" in response_text and "data: " in response_text:
                            logger.debug("SSE Endpoint MCP 协议检查成功: %s (尝试 %d 次)", url, attempt)
                            return True

                        # 限制日志输出长度，避免过长的响应内容
                        max_log_length = 100
                        truncated_response = (
                            response_text[:max_log_length] + "..."
                            if len(response_text) > max_log_length
                            else response_text
                        )
                        logger.debug(
                            "SSE Endpoint MCP 响应格式异常: %s, 响应: %s, 尝试: %d/%d",
                            url,
                            truncated_response,
                            attempt,
                            max_attempts,
                        )
                    except json.JSONDecodeError:
                        logger.debug(
                            "SSE Endpoint MCP 响应非 JSON 格式: %s, 尝试: %d/%d",
                            url,
                            attempt,
                            max_attempts,
                        )
                else:
                    logger.debug(
                        "SSE Endpoint MCP 响应码非 200: %s, 状态码: %d, 尝试: %d/%d",
                        url,
                        response.status_code,
                        attempt,
                        max_attempts,
                    )

        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            logger.debug("SSE Endpoint MCP 连接失败: %s, 错误: %s, 尝试: %d/%d", url, e, attempt, max_attempts)

        return False
