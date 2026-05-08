"""
部署服务模块

处理 sysAgent 部署的核心逻辑。
"""

from __future__ import annotations

import asyncio
import contextlib
import copy
import platform
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
import toml

from backend.hermes import HermesChatClient, HermesModelManager
from backend.models import LLMConfig as HermesLLMConfig
from backend.models import LLMGlobalSetting, LLMProvider, LLMType
from config.manager import ConfigManager
from i18n.manager import _
from log.manager import get_logger

from .agent import AgentManager
from .models import AgentInitStatus, DeploymentConfig, DeploymentState

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Callable

logger = get_logger(__name__)


LOCAL_DEPLOYMENT_HOST = "127.0.0.1"


class DeploymentResourceManager:
    """部署资源管理器，管理 RPM 包安装的资源文件"""

    CANDIDATE_INSTALLER_BASE_PATHS: tuple[Path, ...] = (Path("/usr/lib/witty-assistant/scripts"),)

    def __init__(self) -> None:
        """初始化资源管理器，并缓存已解析的安装器资源路径。"""
        self._resolved_installer_base_path: Path | None = None

    @property
    def installer_base_path(self) -> Path:
        """返回已解析的安装器 base path（优先使用已通过检查的路径）。"""
        if self._resolved_installer_base_path is not None:
            return self._resolved_installer_base_path
        # 未解析时返回首选路径（避免到处判断 None）；调用方应先通过 check_installer_available。
        return self.CANDIDATE_INSTALLER_BASE_PATHS[0]

    @property
    def resource_path(self) -> Path:
        """返回安装器 resources 目录路径。"""
        return self.installer_base_path / "resources"

    @property
    def deploy_script(self) -> Path:
        """返回安装器 deploy 入口脚本路径。"""
        return self.installer_base_path / "deploy"

    @property
    def config_template(self) -> Path:
        """返回安装器的配置模板文件路径（config.toml）。"""
        return self.resource_path / "config.toml"

    def check_installer_available(self) -> bool:
        """检查安装器是否可用，并缓存实际可用的资源路径。"""
        for base_path in self.CANDIDATE_INSTALLER_BASE_PATHS:
            resource_path = base_path / "resources"
            deploy_script = base_path / "deploy"
            config_template = resource_path / "config.toml"

            if base_path.exists() and resource_path.exists() and deploy_script.exists() and config_template.exists():
                self._resolved_installer_base_path = base_path
                return True

        return False

    @classmethod
    def get_template_content(cls, template_path: Path) -> str:
        """获取模板文件内容"""
        try:
            return template_path.read_text(encoding="utf-8")
        except OSError as e:
            logger.exception("读取模板文件失败 %s", template_path)
            msg = _("无法读取模板文件: {path}").format(path=template_path)
            raise RuntimeError(msg) from e

    @classmethod
    def update_toml_values(cls, content: str) -> str:
        """更新 TOML 配置文件的值"""
        try:
            # 解析 TOML 内容
            toml_data = toml.loads(content)

            # 更新服务器 IP
            server_host = LOCAL_DEPLOYMENT_HOST

            # 更新 fastapi 域名
            if "fastapi" in toml_data:
                toml_data["fastapi"]["domain"] = server_host

            # 将更新后的数据转换回 TOML 格式
            return toml.dumps(toml_data)

        except toml.TomlDecodeError as e:
            logger.exception("解析 TOML 内容时出错")
            msg = _("TOML 格式错误: {error}").format(error=e)
            raise ValueError(msg) from e
        except Exception as e:
            logger.exception("更新 TOML 配置时发生错误")
            msg = _("更新 TOML 配置失败: {error}").format(error=e)
            raise RuntimeError(msg) from e


class DeploymentService:
    """
    部署服务

    负责执行 sysAgent 的部署流程。
    基于已安装的 witty-assistant-installer RPM 包资源。
    """

    def __init__(self) -> None:
        """初始化部署服务"""
        self.state = DeploymentState()
        self._process: asyncio.subprocess.Process | None = None
        self.resource_manager = DeploymentResourceManager()

    # 公共方法

    async def check_and_install_dependencies(
        self,
        progress_callback: Callable[[DeploymentState], None] | None = None,
    ) -> tuple[bool, list[str]]:
        """
        检查并自动安装部署依赖

        Returns:
            tuple[bool, list[str]]: (是否成功, 错误信息列表)

        """
        errors = []
        temp_state = DeploymentState()

        # 更新状态
        if progress_callback:
            temp_state.current_step_name = _("检查部署依赖")
            temp_state.add_log(_("正在检查部署环境依赖..."))
            progress_callback(temp_state)

        # 检查操作系统
        if not self.detect_openeuler():
            errors.append(_("仅支持 openEuler 操作系统"))
            return False, errors

        # 检查 Python 版本兼容性
        python_version = sys.version_info
        current_version = f"{python_version.major}.{python_version.minor}"
        if python_version < (3, 10) and progress_callback:
            warning_msg = _("⚠ 检测到 Python {version}，建议升级至 3.10 或更高版本以获得最佳兼容性").format(
                version=current_version,
            )
            temp_state.add_log(warning_msg)
            progress_callback(temp_state)

        # 检查并安装 witty-assistant-installer
        if not self.resource_manager.check_installer_available():
            if progress_callback:
                temp_state.add_log(_("缺少 witty-assistant-installer 包，正在尝试安装..."))
                progress_callback(temp_state)

            success, install_errors = await self._install_intelligence_installer(progress_callback)
            if not success:
                errors.extend(install_errors)
                return False, errors

        # 检查 sudo 权限
        if not await self.check_sudo_privileges():
            errors.append(_("需要管理员权限，请确保可以使用 sudo"))
            return False, errors

        if progress_callback:
            temp_state.add_log(_("✓ 部署环境依赖检查完成"))
            progress_callback(temp_state)

        return True, []

    def detect_openeuler(self) -> bool:
        """检测是否为 openEuler 系统"""
        try:
            # 检查 /etc/os-release
            os_release_path = Path("/etc/os-release")
            if os_release_path.exists():
                content = os_release_path.read_text(encoding="utf-8").lower()
                if "openeuler" in content or "huawei cloud euleros" in content:
                    return True

            # 检查 /etc/openEuler-release
            openeuler_release_path = Path("/etc/openEuler-release")
            hce_release_path = Path("/etc/hce-release")
            if openeuler_release_path.exists() or hce_release_path.exists():
                return True

        except OSError as e:
            logger.warning("检测操作系统时发生错误: %s", e)
            return False
        else:
            # 检查 platform 信息
            system_info = platform.platform().lower()
            return "openeuler" in system_info

    async def check_sudo_privileges(self) -> bool:
        """检查 sudo 权限"""
        try:
            process = await asyncio.create_subprocess_exec(
                "sudo",
                "-n",
                "true",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            return_code = await process.wait()
        except OSError:
            return False
        else:
            return return_code == 0

    async def deploy(
        self,
        config: DeploymentConfig,
        progress_callback: Callable[[DeploymentState], None] | None = None,
    ) -> bool:
        """
        执行部署

        Args:
            config: 部署配置
            progress_callback: 进度回调函数

        Returns:
            bool: 部署是否成功

        """
        # 在部署开始时更新当前用户的配置，确保使用正确的后端 URL
        self._update_backend_url_config(config)

        try:
            logger.info("开始部署 sysAgent")

            # 重置状态
            self.state.reset()
            self.state.is_running = True

            # 执行部署步骤
            success = await self._execute_deployment_steps(config, progress_callback)

            if not success:
                return False

        except Exception:
            logger.exception("部署过程中发生错误")
            self.state.is_running = False
            self.state.is_failed = True
            self.state.error_message = _("部署过程中发生异常")
            self.state.add_log(_("✗ 部署失败"))

            if progress_callback:
                progress_callback(self.state)

            return False

        # 部署完成，创建全局配置模板供其他用户使用
        self.state.is_running = False
        self.state.is_completed = True
        self.state.add_log(_("✓ sysAgent 部署完成！"))

        # 创建全局配置模板，包含部署时的配置信息
        await self._create_global_config_template(config)

        if progress_callback:
            progress_callback(self.state)

        logger.info("部署完成")
        return True

    def cancel_deployment(self) -> None:
        """取消部署"""
        if self._process:
            try:
                self._process.terminate()
                logger.info("部署进程已终止")
            except OSError as e:
                logger.warning("终止部署进程时发生错误: %s", e)

    # 私有方法

    async def _install_intelligence_installer(
        self,
        progress_callback: Callable[[DeploymentState], None] | None = None,
    ) -> tuple[bool, list[str]]:
        """
        安装 witty-assistant-installer 包

        Returns:
            tuple[bool, list[str]]: (是否成功安装, 错误信息列表)

        """
        errors = []

        try:
            temp_state = DeploymentState()
            if progress_callback:
                temp_state.add_log(_("正在安装 witty-assistant-installer..."))
                progress_callback(temp_state)

            # 执行安装命令
            cmd = ["sudo", "dnf", "install", "-y", "witty-assistant-installer"]
            success, output_lines = await self._execute_install_command(cmd, progress_callback, temp_state)

            if success:
                # 验证安装是否成功
                if self.resource_manager.check_installer_available():
                    if progress_callback:
                        temp_state.add_log(_("✓ witty-assistant-installer 安装成功"))
                        progress_callback(temp_state)
                    return True, []

                errors.append(_("witty-assistant-installer 安装后资源文件仍然缺失"))
                return False, errors

            errors.append(_("安装 witty-assistant-installer 失败"))
            # 添加安装输出到错误信息
            if output_lines:
                errors.append(_("安装输出:"))
                errors.extend(output_lines[-5:])  # 只显示最后5行

        except Exception as e:
            errors.append(_("安装过程中发生异常: {error}").format(error=e))
            logger.exception("安装 witty-assistant-installer 时发生异常")

        return False, errors

    async def _execute_deployment_steps(
        self,
        config: DeploymentConfig,
        progress_callback: Callable[[DeploymentState], None] | None,
    ) -> bool:
        """执行所有部署步骤"""
        # 检查并停止旧的 oi-runtime、oi-rag 和 sysagent 服务
        if not await self._check_and_stop_old_service(progress_callback):
            return False

        steps = [
            self._check_environment,
            self._setup_epol_repo,
            self._run_env_check_script,
            self._run_install_dependency_script,
            self._install_opencode_step,
            self._generate_config_files,
            self._run_init_config_script,
            self._register_llm_models_step,
            self._run_agent_init,
        ]

        self.state.total_steps = len(steps)

        for step in steps:
            if not await step(config, progress_callback):
                return False

        return True

    async def _execute_install_command(
        self,
        cmd: list[str],
        progress_callback: Callable[[DeploymentState], None] | None,
        temp_state: DeploymentState,
    ) -> tuple[bool, list[str]]:
        """执行安装命令"""
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )

        # 读取安装输出
        output_lines = []
        if process.stdout:
            async for line in self._read_process_output_lines(process):
                output_lines.append(line)
                if progress_callback:
                    temp_state.add_log(f"安装: {line}")
                    progress_callback(temp_state)

        # 等待进程结束
        return_code = await process.wait()
        return return_code == 0, output_lines

    async def _check_environment(
        self,
        config: DeploymentConfig,
        progress_callback: Callable[[DeploymentState], None] | None,
    ) -> bool:
        """检查系统环境和资源"""
        self.state.current_step = 1
        self.state.current_step_name = _("检查系统环境")
        self.state.add_log(_("正在检查系统环境..."))

        if progress_callback:
            progress_callback(self.state)

        # 检查操作系统
        if not self.detect_openeuler():
            self.state.add_log(_("✗ 错误: 仅支持 openEuler 操作系统"))
            return False
        self.state.add_log(_("✓ 检测到 openEuler 操作系统"))

        # 检查安装器资源
        if not self.resource_manager.check_installer_available():
            self.state.add_log(_("✗ 错误: witty-assistant-installer 包未安装或资源缺失"))
            self.state.add_log(_("请先安装: sudo dnf install -y witty-assistant-installer"))
            return False
        self.state.add_log(_("✓ witty-assistant-installer 资源可用"))

        # 检查权限
        if not await self.check_sudo_privileges():
            self.state.add_log(_("✗ 错误: 需要管理员权限"))
            return False
        self.state.add_log(_("✓ 具有管理员权限"))

        return True

    def _get_epol_repo_config(self) -> tuple[str, str | None] | None:
        """
        从 openEuler.repo 文件读取 EPOL 仓库配置

        Returns:
            tuple[str, str | None] | None: (epol_baseurl, gpgkey_url) 或 None（未找到配置）
            如果 EPOL 没有配置 gpgkey，则返回的 gpgkey_url 为 None

        """
        repo_file_path = Path("/etc/yum.repos.d/openEuler.repo")

        try:
            if not repo_file_path.exists():
                logger.warning("未找到 openEuler.repo")
                return None

            content = repo_file_path.read_text(encoding="utf-8")
        except OSError as e:
            logger.warning("读取 openEuler.repo 失败: %s", e)
            return None
        else:
            epol_config = self._parse_epol_section(content)

            if not epol_config:
                return None

            # 直接返回 EPOL 的配置，不做推断
            return epol_config

    def _parse_epol_section(self, content: str) -> tuple[str, str | None] | None:
        """解析 repo 文件内容，提取 EPOL section 的配置（gpgkey 为可选项）"""
        current_section = None
        epol_baseurl = None
        epol_gpgkey = None

        for raw_line in content.splitlines():
            line = raw_line.strip()

            if line.startswith("[") and line.endswith("]"):
                current_section = line[1:-1]
                continue

            if current_section == "EPOL":
                if line.startswith("baseurl="):
                    epol_baseurl = line.split("=", 1)[1].strip()
                elif line.startswith("gpgkey="):
                    epol_gpgkey = line.split("=", 1)[1].strip()

        if not epol_baseurl:
            logger.warning("未能从 openEuler.repo 找到 EPOL 仓库配置")
            return None

        logger.debug("EPOL 配置已读取%s", "" if epol_gpgkey else " (无 gpgkey)")
        return epol_baseurl, epol_gpgkey

    async def _setup_epol_repo(
        self,
        config: DeploymentConfig,
        progress_callback: Callable[[DeploymentState], None] | None,
    ) -> bool:
        """配置 update-EPOL 软件源"""
        self.state.current_step = 2
        self.state.current_step_name = _("配置 EPOL 软件源")
        self.state.add_log(_("正在配置 update-EPOL 软件源..."))

        if progress_callback:
            progress_callback(self.state)

        try:
            # 检查是否已存在包含 /EPOL/update/ 的仓库
            check_process = await asyncio.create_subprocess_exec(
                "dnf",
                "repolist",
                "-v",
                "--enabled",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _stderr = await check_process.communicate()
            repolist_output = stdout.decode("utf-8", errors="ignore")

            # 检查输出中是否包含 /EPOL/update/ 路径
            if "/EPOL/update/" in repolist_output:
                self.state.add_log(_("✓ update-EPOL 软件源已存在，跳过配置"))
                logger.info("检测到已存在包含 /EPOL/update/ 的软件源，跳过配置")
                return True

            # 获取 EPOL 仓库配置
            epol_config = self._get_epol_repo_config()
            if not epol_config:
                self.state.add_log(_("✗ 无法读取 EPOL 仓库配置，跳过 update-EPOL 配置"))
                logger.warning("无法读取 EPOL 仓库配置，跳过 update-EPOL 配置")
                return True  # 不阻止部署继续

            epol_baseurl, epol_gpgkey = epol_config

            # 基于 EPOL 仓库的 baseurl 构造 update-EPOL 的 URL
            # 将 /EPOL/main/ 替换为 /EPOL/update/main/
            # 例如：https://repo.openeuler.org/openEuler-24.03-LTS-SP3/EPOL/main/$basearch/
            # 转换为：https://repo.openeuler.org/openEuler-24.03-LTS-SP3/EPOL/update/main/$basearch/
            if "/EPOL/main/" in epol_baseurl:
                update_epol_baseurl = epol_baseurl.replace("/EPOL/main/", "/EPOL/update/main/")
            else:
                # 如果不是标准格式，尝试在 EPOL 后插入 update
                update_epol_baseurl = epol_baseurl.replace("/EPOL/", "/EPOL/update/")

            # 如果 EPOL 有 gpgkey，直接使用；否则关闭 gpg 校验
            if epol_gpgkey:
                gpgcheck = "1"
                gpgkey_line = f"gpgkey={epol_gpgkey}"
                self.state.add_log(_("  使用 EPOL 的 GPG 密钥"))
            else:
                gpgcheck = "0"
                gpgkey_line = ""
                self.state.add_log(_("  ⚠ EPOL 未配置 GPG 密钥，已关闭 GPG 校验"))
                logger.warning("EPOL 未配置 gpgkey，update-EPOL 将关闭 gpgcheck")

            # 生成 repo 文件内容
            repo_lines = [
                "[update-EPOL]",
                "name=update-EPOL",
                f"baseurl={update_epol_baseurl}",
                "metadata_expire=1h",
                "enabled=1",
                f"gpgcheck={gpgcheck}",
            ]
            if gpgkey_line:
                repo_lines.append(gpgkey_line)

            repo_content = "\n".join(repo_lines) + "\n"

            # 写入 repo 文件
            repo_file_path = "/etc/yum.repos.d/openEuler-EPOL-update.repo"
            write_cmd = ["tee", repo_file_path]
            process = await asyncio.create_subprocess_exec(
                *write_cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _stdout, stderr = await process.communicate(repo_content.encode("utf-8"))

            if process.returncode != 0:
                error_msg = stderr.decode("utf-8", errors="ignore").strip()
                self.state.add_log(_("✗ 写入 EPOL repo 文件失败: {error}").format(error=error_msg))
                return False

            self.state.add_log(_("✓ update-EPOL 软件源配置完成"))
            logger.info("update-EPOL 软件源配置完成")

        except Exception as e:
            self.state.add_log(_("✗ 配置 EPOL 软件源失败: {error}").format(error=e))
            logger.exception("配置 EPOL 软件源失败")
            return False

        return True

    async def _run_env_check_script(
        self,
        config: DeploymentConfig,
        progress_callback: Callable[[DeploymentState], None] | None,
    ) -> bool:
        """运行环境检查脚本"""
        self.state.current_step = 3
        self.state.current_step_name = _("检查系统环境")
        self.state.add_log(_("正在执行系统环境检查..."))

        if progress_callback:
            progress_callback(self.state)

        try:
            script_path = self.resource_manager.installer_base_path / "1-check-env" / "check_env.sh"
            return await self._run_script(script_path, _("环境检查脚本"), progress_callback)
        except Exception as e:
            self.state.add_log(_("✗ 环境检查失败: {error}").format(error=e))
            logger.exception("环境检查脚本执行失败")
            return False

    async def _run_install_dependency_script(
        self,
        config: DeploymentConfig,
        progress_callback: Callable[[DeploymentState], None] | None,
    ) -> bool:
        """运行依赖安装脚本"""
        self.state.current_step = 4
        self.state.current_step_name = _("安装依赖组件")
        self.state.add_log(_("正在安装后端依赖组件..."))

        if progress_callback:
            progress_callback(self.state)

        try:
            script_path = (
                self.resource_manager.installer_base_path / "2-install-dependency" / "install_openEulerIntelligence.sh"
            )
            return await self._run_script(script_path, _("依赖安装脚本"), progress_callback)
        except Exception as e:
            self.state.add_log(_("✗ 依赖安装失败: {error}").format(error=e))
            logger.exception("依赖安装脚本执行失败")
            return False

    async def _run_init_config_script(
        self,
        config: DeploymentConfig,
        progress_callback: Callable[[DeploymentState], None] | None,
    ) -> bool:
        """运行配置初始化脚本"""
        self.state.current_step = 7
        self.state.current_step_name = _("初始化配置和服务")
        self.state.add_log(_("正在初始化配置和启动服务..."))

        if progress_callback:
            progress_callback(self.state)

        try:
            script_path = self.resource_manager.installer_base_path / "3-install-server" / "init_config.sh"
            return await self._run_script(script_path, _("配置初始化脚本"), progress_callback)
        except Exception as e:
            self.state.add_log(_("✗ 配置初始化失败: {error}").format(error=e))
            logger.exception("配置初始化脚本执行失败")
            return False

    async def _run_script(
        self,
        script_path: Path,
        script_name: str,
        progress_callback: Callable[[DeploymentState], None] | None,
    ) -> bool:
        """运行部署脚本"""
        if not script_path.exists():
            self.state.add_log(_("✗ 脚本文件不存在: {path}").format(path=script_path))
            return False

        try:
            # 切换到脚本所在目录
            script_dir = script_path.parent
            script_file = script_path.name

            cmd = ["sudo", "bash", script_file]

            self._process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=script_dir,
            )

            # 创建心跳任务，定期更新界面
            heartbeat_task = asyncio.create_task(self._heartbeat_progress(progress_callback))

            try:
                # 读取输出
                async for line in self._read_process_output_lines(self._process):
                    self.state.add_log(line)
                    if progress_callback:
                        progress_callback(self.state)

                # 等待进程结束
                return_code = await self._process.wait()
            finally:
                # 取消心跳任务
                heartbeat_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await heartbeat_task

            self._process = None

            if return_code == 0:
                self.state.add_log(_("✓ {name}执行成功").format(name=script_name))
                return True

        except Exception as e:
            self.state.add_log(_("✗ 运行{name}时发生错误: {error}").format(name=script_name, error=e))
            logger.exception("运行脚本失败: %s", script_path)
            return False

        else:
            self.state.add_log(_("✗ {name}执行失败，返回码: {code}").format(name=script_name, code=return_code))
            return False

    async def _heartbeat_progress(self, progress_callback: Callable[[DeploymentState], None] | None) -> None:
        """心跳进度更新，确保界面不会卡死"""
        if not progress_callback:
            return

        with contextlib.suppress(asyncio.CancelledError):
            while True:
                await asyncio.sleep(1.0)  # 每秒更新一次
                if progress_callback:
                    progress_callback(self.state)

    async def _generate_config_files(
        self,
        config: DeploymentConfig,
        progress_callback: Callable[[DeploymentState], None] | None,
    ) -> bool:
        """生成配置文件"""
        self.state.current_step = 6
        self.state.current_step_name = _("更新配置文件")
        self.state.add_log(_("正在更新配置文件..."))

        if progress_callback:
            progress_callback(self.state)

        try:
            # 更新 config.toml 文件
            await self._update_config_toml(config)
            self.state.add_log(_("✓ 更新 config.toml 配置文件"))

        except Exception as e:
            self.state.add_log(_("✗ 更新配置文件失败: {error}").format(error=e))
            logger.exception("更新配置文件失败")
            return False

        return True

    async def _update_config_toml(self, config: DeploymentConfig) -> None:
        """更新 config.toml 配置文件"""
        template_content = self.resource_manager.get_template_content(
            self.resource_manager.config_template,
        )

        updated_content = self.resource_manager.update_toml_values(
            template_content,
        )

        # 备份原文件并写入新内容
        backup_cmd = [
            "sudo",
            "cp",
            str(self.resource_manager.config_template),
            f"{self.resource_manager.config_template}.backup",
        ]
        backup_process = await asyncio.create_subprocess_exec(
            *backup_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _backup_stdout, backup_stderr = await backup_process.communicate()

        if backup_process.returncode != 0:
            error_msg = backup_stderr.decode("utf-8", errors="ignore").strip()
            msg = _("备份 config.toml 文件失败: {error}").format(error=error_msg)
            raise RuntimeError(msg)

        # 写入更新后的内容
        write_cmd = ["sudo", "tee", str(self.resource_manager.config_template)]
        process = await asyncio.create_subprocess_exec(
            *write_cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _write_stdout, write_stderr = await process.communicate(updated_content.encode())

        if process.returncode != 0:
            error_msg = write_stderr.decode("utf-8", errors="ignore").strip()
            msg = _("写入 config.toml 文件失败: {error}").format(error=error_msg)
            raise RuntimeError(msg)

    async def _read_process_output_lines(self, process: asyncio.subprocess.Process) -> AsyncGenerator[str, None]:
        """读取进程输出行"""
        if not process.stdout:
            return

        while not process.stdout.at_eof():
            try:
                line = await process.stdout.readline()
                if not line:
                    break

                decoded_line = line.decode("utf-8", errors="ignore").strip()
                if decoded_line:
                    yield decoded_line

                # 每次读取后让出控制权
                await asyncio.sleep(0)

            except OSError as e:
                logger.warning("读取进程输出时发生错误: %s", e)
                break

    async def _check_framework_service_health(
        self,
        server_host: str,
        server_port: int,
        progress_callback: Callable[[DeploymentState], None] | None,
    ) -> bool:
        """检查 sysagent 服务健康状态"""
        # 1. 检查 systemctl sysagent 服务状态
        if not await self._check_systemctl_service_status(progress_callback):
            return False

        # 2. 检查 HTTP API 接口连通性
        return await self._check_framework_api_health(server_host, server_port, progress_callback)

    async def _check_systemctl_service_status(
        self,
        progress_callback: Callable[[DeploymentState], None] | None,
    ) -> bool:
        """检查 systemctl sysagent 服务状态，每2秒检查一次，5次后超时"""
        max_attempts = 5
        check_interval = 2.0  # 2秒

        for attempt in range(1, max_attempts + 1):
            self.state.add_log(
                _("检查 sysagent 服务状态 ({current}/{total})...").format(
                    current=attempt,
                    total=max_attempts,
                ),
            )

            if progress_callback:
                progress_callback(self.state)

            try:
                # 使用 systemctl is-active 检查服务状态
                process = await asyncio.create_subprocess_exec(
                    "systemctl",
                    "is-active",
                    "sysagent",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )

                stdout, _stderr = await process.communicate()
                status = stdout.decode("utf-8").strip()

                if process.returncode == 0 and status == "active":
                    self.state.add_log(_("✓ Framework 服务状态正常"))
                    return True

                self.state.add_log(_("Framework 服务状态: {status}").format(status=status))

                if attempt < max_attempts:
                    self.state.add_log(_("等待 {seconds} 秒后重试...").format(seconds=check_interval))
                    await asyncio.sleep(check_interval)

            except (OSError, TimeoutError) as e:
                self.state.add_log(_("检查服务状态时发生错误: {error}").format(error=e))
                if attempt < max_attempts:
                    await asyncio.sleep(check_interval)

        self.state.add_log(_("✗ Framework 服务状态检查超时失败"))
        return False

    async def _check_framework_api_health(
        self,
        server_host: str,
        server_port: int,
        progress_callback: Callable[[DeploymentState], None] | None,
    ) -> bool:
        """
        检查 sysagent API 健康状态

        通过尝试登录 Hermes 后端验证服务是否就绪。
        每5秒检查一次，2分钟后超时。

        Args:
            server_host: 服务器地址
            server_port: 服务器端口
            progress_callback: 进度回调函数

        Returns:
            bool: 服务是否就绪

        """
        max_attempts = 24
        check_interval = 5.0  # 5秒
        base_url = f"http://{server_host}:{server_port}"

        self.state.add_log(_("等待后端服务就绪"))

        # 创建配置管理器用于保存登录后的 token
        config_manager = ConfigManager()

        for attempt in range(1, max_attempts + 1):
            logger.debug("第 %d 次检查后端服务状态...", attempt)
            if progress_callback:
                progress_callback(self.state)

            try:
                hermes_client = HermesChatClient(base_url, config_manager=config_manager)

                try:
                    user_info_loaded = await hermes_client.ensure_user_info_loaded()

                    if user_info_loaded:
                        self.state.add_log(_("✓ 后端服务已就绪"))
                        return True

                finally:
                    await hermes_client.close()

            except httpx.ConnectError:
                pass
            except httpx.TimeoutException:
                self.state.add_log(_("连接 {url} 超时").format(url=base_url))
            except (httpx.RequestError, OSError) as e:
                self.state.add_log(_("API 连通性检查时发生错误: {error}").format(error=e))

            if attempt < max_attempts:
                await asyncio.sleep(check_interval)

        self.state.add_log(_("✗ 后端 API 服务检查超时失败"))
        return False

    async def _register_llm_models_step(
        self,
        config: DeploymentConfig,
        progress_callback: Callable[[DeploymentState], None] | None,
    ) -> bool:
        """
        第 8 步：注册 LLM 模型

        在后端服务拉起后，先进行健康检查，然后注册 LLM 和 Embedding 模型。
        这一步包含用户登录、获取 token 等操作。

        Args:
            config: 部署配置
            progress_callback: 进度回调函数

        Returns:
            bool: 是否成功

        """
        self.state.current_step = 8
        self.state.current_step_name = _("注册大模型配置")
        self.state.add_log(_("正在检查 sysAgent 服务状态..."))

        if progress_callback:
            progress_callback(self.state)

        # 使用固定的本地服务地址和默认端口
        server_host = LOCAL_DEPLOYMENT_HOST
        server_port = 8002

        # 检查 sysAgent 服务状态
        if not await self._check_framework_service_health(server_host, server_port, progress_callback):
            self.state.add_log(_("✗ 后端服务检查失败"))
            return False

        self.state.add_log(_("✓ 后端服务检查通过"))

        # 注册用户配置的 LLM 和 Embedding 模型到后端
        await self._register_llm_models(config, progress_callback)

        return True

    async def _run_agent_init(
        self,
        config: DeploymentConfig,
        progress_callback: Callable[[DeploymentState], None] | None,
    ) -> bool:
        """运行 Agent 初始化脚本"""
        self.state.current_step = 9
        self.state.current_step_name = _("初始化 Agent 服务")
        self.state.add_log(_("正在初始化 Agent 和 MCP 服务..."))

        if progress_callback:
            progress_callback(self.state)

        # 初始化 Agent 和 MCP 服务
        agent_manager = AgentManager()
        init_status = await agent_manager.initialize_agents(self.state, progress_callback)

        if init_status == AgentInitStatus.SUCCESS:
            self.state.add_log(_("✓ Agent 初始化完成"))
            return True

        if init_status == AgentInitStatus.SKIPPED:
            self.state.add_log(_("⚠ Agent 初始化已跳过（RPM 包不可用），但部署将继续进行"))
            return True  # 跳过不算失败，继续部署

        # FAILED
        self.state.add_log("✗ Agent 初始化失败")
        return False

    async def _install_opencode_step(
        self,
        config: DeploymentConfig,
        progress_callback: Callable[[DeploymentState], None] | None,
    ) -> bool:
        """检查并安装 opencode-ai"""
        self.state.current_step = 5
        self.state.current_step_name = _("安装 opencode-ai")
        self.state.add_log(_("正在检查 opencode-ai 安装状态..."))

        if progress_callback:
            progress_callback(self.state)

        try:
            # 检查 opencode 是否已安装
            if await self._check_opencode_installed():
                self.state.add_log(_("✓ opencode-ai 已安装，跳过安装步骤"))
                return True

            self.state.add_log(_("opencode-ai 未安装，开始安装流程..."))

            # 安装 nodejs
            if not await self._install_nodejs(progress_callback):
                self.state.add_log(_("⚠ nodejs 安装失败，跳过 opencode-ai 安装"))
                return True  # 不阻止部署继续

            # 配置 npm 镜像源（如果需要）
            await self._configure_npm_mirror(progress_callback)

            # 安装 opencode-ai
            if await self._install_opencode(progress_callback):
                self.state.add_log(_("✓ opencode-ai 安装完成"))
                return True
            self.state.add_log(_("⚠ opencode-ai 安装失败，但部署将继续进行"))

        except Exception as e:
            self.state.add_log(_("⚠ 安装 opencode-ai 时发生异常: {error}").format(error=e))
            logger.exception("安装 opencode-ai 时发生异常")
        return True  # 不阻断部署流程

    async def _check_opencode_installed(self) -> bool:
        """检查 opencode-ai 是否已安装"""
        try:
            process = await asyncio.create_subprocess_exec(
                "which",
                "opencode",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await process.wait()
        except Exception:
            logger.exception("检查 opencode-ai 安装状态失败")
            return False
        else:
            return process.returncode == 0

    async def _install_nodejs(
        self,
        progress_callback: Callable[[DeploymentState], None] | None,
    ) -> bool:
        """安装 nodejs"""
        self.state.add_log(_("正在检查 npm 安装状态..."))
        if progress_callback:
            progress_callback(self.state)

        # 检查 npm 是否已安装
        try:
            process = await asyncio.create_subprocess_exec(
                "which",
                "npm",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await process.wait()
            if process.returncode == 0:
                self.state.add_log(_("✓ npm 已安装"))
                return True
        except Exception:
            logger.exception("检查 npm 安装状态失败")

        # 安装 nodejs 和 npm
        self.state.add_log(_("正在通过 dnf 安装 nodejs 和 npm..."))
        if progress_callback:
            progress_callback(self.state)

        try:
            cmd = ["dnf", "install", "-y", "nodejs", "npm"]
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )

            # 读取安装输出
            if process.stdout:
                async for line in self._read_process_output_lines(process):
                    self.state.add_log(f"nodejs: {line}")
                    if progress_callback:
                        progress_callback(self.state)

            return_code = await process.wait()

            if return_code == 0:
                self.state.add_log(_("✓ nodejs 安装成功"))
                return True
            self.state.add_log(_("✗ nodejs 安装失败，返回码: {code}").format(code=return_code))

        except Exception as e:
            self.state.add_log(_("✗ 安装 nodejs 时发生错误: {error}").format(error=e))
            logger.exception("安装 nodejs 失败")
        return False

    async def _check_npm_availability(self) -> bool:
        """检查 npm 是否可用"""
        try:
            process = await asyncio.create_subprocess_exec(
                "npm",
                "ping",
                "--registry",
                "https://registry.npmjs.org",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(process.wait(), timeout=10.0)
        except Exception:
            logger.exception("检查 npm 可用性失败")
            return False
        else:
            return process.returncode == 0

    async def _configure_npm_mirror(
        self,
        progress_callback: Callable[[DeploymentState], None] | None,
    ) -> None:
        """配置 npm 镜像源（如果 npm 官方源不可用）"""
        self.state.add_log(_("正在检查 npm 可用性..."))
        if progress_callback:
            progress_callback(self.state)

        # 检查 npm 官方源是否可用
        if await self._check_npm_availability():
            self.state.add_log(_("✓ npm 官方源可用"))
            return

        self.state.add_log(_("npm 官方源不可用，配置国内镜像源..."))

        # 尝试配置国内镜像源（按优先级）
        mirrors = [
            ("华为云镜像", "https://repo.huaweicloud.com/repository/npm/"),
            ("腾讯云镜像", "http://mirrors.cloud.tencent.com/npm/"),
            ("淘宝镜像", "https://registry.npmmirror.com"),
        ]

        for mirror_name, mirror_url in mirrors:
            try:
                self.state.add_log(_("尝试配置 {name}: {url}").format(name=mirror_name, url=mirror_url))
                if progress_callback:
                    progress_callback(self.state)

                process = await asyncio.create_subprocess_exec(
                    "npm",
                    "config",
                    "set",
                    "registry",
                    mirror_url,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await process.wait()

                if process.returncode == 0:
                    self.state.add_log(_("✓ 已配置 npm 镜像源: {name}").format(name=mirror_name))
                    return

            except OSError as e:
                self.state.add_log(_("配置 {name} 失败: {error}").format(name=mirror_name, error=e))
                continue

        self.state.add_log(_("⚠ 无法配置 npm 镜像源，将使用默认源"))

    async def _install_opencode(
        self,
        progress_callback: Callable[[DeploymentState], None] | None,
    ) -> bool:
        """安装 opencode-ai"""
        self.state.add_log(_("正在全局安装 opencode-ai..."))
        if progress_callback:
            progress_callback(self.state)

        try:
            cmd = ["npm", "install", "-g", "opencode-ai"]
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )

            # 读取安装输出
            if process.stdout:
                async for line in self._read_process_output_lines(process):
                    # 过滤掉 npm 的进度条和警告信息
                    if line and not line.startswith(("npm WARN", "npm notice")):
                        self.state.add_log(f"npm: {line}")
                        if progress_callback:
                            progress_callback(self.state)

            return_code = await process.wait()

            if return_code == 0:
                # 验证安装是否成功
                if await self._check_opencode_installed():
                    return True
                self.state.add_log(_("✗ opencode-ai 安装后验证失败"))
                return False
            self.state.add_log(_("✗ opencode-ai 安装失败，返回码: {code}").format(code=return_code))

        except Exception as e:
            self.state.add_log(_("✗ 安装 opencode-ai 时发生错误: {error}").format(error=e))
            logger.exception("安装 opencode-ai 失败")
        return False

    async def _create_global_config_template(self, config: DeploymentConfig) -> None:
        """
        创建全局配置模板

        基于当前 root 用户的实际配置创建全局配置模板，供其他用户使用
        这样可以确保模板包含部署过程中生成的所有配置信息（如 Agent AppID 等）
        同时将部署时经过验证的大模型配置设置为默认的 OpenAI 配置

        注意：模板中不包含 token，其他用户需要自己登录获取 token

        Args:
            config: 部署配置

        """
        try:
            # 获取当前 root 用户的实际配置（包含 Agent 初始化后的完整配置）
            current_config_manager = ConfigManager()

            # 将部署时用户输入的经过验证的大模型信息设置为默认的 OpenAI 配置
            # 这样其他用户可以直接使用这些已验证的配置
            current_config_manager.set_base_url(config.llm.endpoint)
            current_config_manager.set_model(config.llm.model)
            current_config_manager.set_api_key(config.llm.api_key)

            # 写入默认的 Chat 模型 llm_id（后端服务使用），让其他用户开箱即用。
            # 优先使用部署时注册/验证的模型 ID；若为空则回退到默认值。
            llm_id = (config.llm.model or "").strip() or "default-llm"
            current_config_manager.set_llm_chat_model(llm_id)

            # 创建专用的模板配置管理器
            template_manager = ConfigManager.create_deployment_manager()

            # 将当前 root 用户的完整配置复制到模板中。
            # 注意：仅清除模板中的 Hermes token（witty.api_key），不要影响 root/current 用户本地配置。
            template_manager.data = copy.deepcopy(current_config_manager.data)
            template_manager.data.witty.api_key = ""

            # 创建全局配置模板文件
            success = template_manager.create_global_template()

            if success:
                self.state.add_log(_("✓ 全局配置模板创建成功，其他用户可正常使用"))
                logger.info("全局配置模板创建成功，包含部署时的完整配置信息")
            else:
                self.state.add_log(_("⚠ 全局配置模板创建失败，可能影响其他用户使用"))
                logger.warning("全局配置模板创建失败")

        except Exception:
            logger.exception("创建全局配置模板时发生异常")
            self.state.add_log(_("⚠ 配置模板创建异常，可能影响其他用户使用"))

    def _update_backend_url_config(self, config: DeploymentConfig) -> None:
        """
        更新当前用户的配置

        在部署开始时根据部署模式
        更新 sysAgent 的 URL 配置

        Args:
            config: 部署配置

        """
        try:
            config_manager = ConfigManager()

            # 根据部署配置更新 sysAgent URL
            server_host = LOCAL_DEPLOYMENT_HOST
            witty_url = f"http://{server_host}:8002"

            config_manager.set_witty_url(witty_url)
            logger.info("已更新当前用户 sysAgent URL: %s", witty_url)

        except Exception:
            logger.exception("更新当前用户配置时发生异常")

    async def _check_and_stop_old_service(
        self,
        progress_callback: Callable[[DeploymentState], None] | None,
    ) -> bool:
        """
        检查并停止旧的 oi-runtime、oi-rag 和 sysagent 服务

        Args:
            progress_callback: 进度回调函数

        Returns:
            bool: 处理是否成功

        """
        if progress_callback:
            progress_callback(self.state)

        services_to_check = ["oi-runtime", "oi-rag", "sysagent"]

        for service_name in services_to_check:
            try:
                # 检查服务状态
                process = await asyncio.create_subprocess_exec(
                    "systemctl",
                    "is-active",
                    service_name,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )

                stdout, _stderr = await process.communicate()
                status = stdout.decode("utf-8").strip()

                if process.returncode == 0 and status == "active":
                    logger.info("发现正在运行的 %s 服务，正在停止...", service_name)

                    if progress_callback:
                        progress_callback(self.state)

                    # 停止服务
                    stop_process = await asyncio.create_subprocess_exec(
                        "sudo",
                        "systemctl",
                        "stop",
                        service_name,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )

                    _, stop_stderr = await stop_process.communicate()

                    if stop_process.returncode == 0:
                        logger.info("旧的 %s 服务已停止", service_name)
                    else:
                        error_msg = stop_stderr.decode("utf-8", errors="ignore").strip()
                        logger.warning("⚠ 停止 %s 服务时出现警告: %s", service_name, error_msg)
                        # 继续部署，不因停止服务失败而中断

                    # 等待服务完全停止
                    await asyncio.sleep(1.0)

                elif status in ("inactive", "failed"):
                    logger.info("✓ 没有发现运行中的 %s 服务", service_name)
                else:
                    logger.warning("%s 服务状态: %s", service_name.capitalize(), status)

            except (OSError, TimeoutError) as e:
                # 如果系统中没有该服务，systemctl 命令可能会失败
                # 这种情况下我们记录信息但不阻止部署继续进行
                logger.warning("检查 %s 服务状态时发生错误: %s", service_name, e)
                continue

            except Exception:
                logger.exception("处理 %s 服务时发生异常", service_name)
                return False

        # 等待所有服务完全停止
        await asyncio.sleep(1.0)

        return True

    async def _register_llm_models(
        self,
        config: DeploymentConfig,
        progress_callback: Callable[[DeploymentState], None] | None,
    ) -> None:
        """
        注册用户配置的 LLM 和 Embedding 模型到后端

        部署完成后，将用户在部署 UI 中填写的模型信息注册到 Hermes 后端：
        1. 使用 ConfigManager 获取已保存的配置，创建 HermesChatClient
        2. 注册 LLM 模型（类型为 chat + function）
        3. 注册 Embedding 模型（类型为 embedding）
        4. 更新全局设置，指定 function call 和 embedding 使用的模型

        部署服务一定是 sudoer 运行的，所以登录后的用户一定是 admin。

        Args:
            config: 部署配置
            progress_callback: 进度回调函数

        """
        self.state.add_log(_("正在注册大模型配置..."))
        if progress_callback:
            progress_callback(self.state)

        # 使用 ConfigManager 获取已保存的配置，验证前面写入的配置是否正确
        config_manager = ConfigManager()
        base_url = config_manager.get_witty_url()

        if not base_url:
            self.state.add_log(_("⚠ 未找到 Hermes 后端 URL 配置，跳过模型注册"))
            logger.warning("未找到 Hermes 后端 URL 配置，跳过模型注册")
            return

        # 使用 ConfigManager 创建 HermesChatClient，验证配置正确性
        hermes_client = HermesChatClient(base_url, config_manager=config_manager)

        try:
            # 连接并验证管理员权限
            is_admin = await self._connect_hermes_as_admin(hermes_client, progress_callback)
            if not is_admin:
                return

            # 执行模型注册
            await self._do_register_models(hermes_client.model_manager, config)

        except Exception as e:  # noqa: BLE001
            # 模型注册失败不影响部署成功，只记录警告
            self.state.add_log(_("⚠ 注册模型时发生错误: {error}").format(error=e))
            logger.warning("注册模型时发生错误: %s", e)

        finally:
            await hermes_client.close()

        if progress_callback:
            progress_callback(self.state)

    async def _connect_hermes_as_admin(
        self,
        hermes_client: HermesChatClient,
        progress_callback: Callable[[DeploymentState], None] | None,
    ) -> bool:
        """
        连接 Hermes 后端并验证管理员权限

        Args:
            hermes_client: Hermes 客户端
            progress_callback: 进度回调函数

        Returns:
            bool: 是否成功连接且为管理员

        """
        self.state.add_log(_("正在连接 Hermes 后端服务..."))
        if progress_callback:
            progress_callback(self.state)

        # 加载用户信息（会自动触发登录流程获取 token）
        user_info_loaded = await hermes_client.ensure_user_info_loaded()
        if not user_info_loaded:
            self.state.add_log(_("⚠ 无法连接 Hermes 后端服务，跳过模型注册"))
            logger.warning("无法加载用户信息，跳过模型注册")
            return False

        # 验证当前用户是否为管理员
        if not hermes_client.is_admin():
            self.state.add_log(_("⚠ 当前用户非管理员，跳过模型注册"))
            logger.warning("当前用户非管理员，跳过模型注册")
            return False

        self.state.add_log(_("✓ 已连接 Hermes 后端服务（管理员权限）"))
        logger.info("已成功连接 Hermes 后端（管理员权限）")
        return True

    async def _do_register_models(
        self,
        model_manager: HermesModelManager,
        config: DeploymentConfig,
    ) -> None:
        """
        执行模型注册操作

        Args:
            model_manager: Hermes 模型管理器
            config: 部署配置

        """
        llm_model_id: str | None = None
        embedding_model_id: str | None = None

        # 1. 注册 LLM 模型（chat + function）
        if config.llm.endpoint:
            llm_model_id = await self._register_llm_model(model_manager, config)

        # 2. 注册 Embedding 模型
        if config.embedding.endpoint:
            embedding_model_id = await self._register_embedding_model(model_manager, config)

        # 3. 更新全局设置
        if llm_model_id or embedding_model_id:
            global_setting = LLMGlobalSetting(
                function_llm=llm_model_id,
                embedding_llm=embedding_model_id,
            )
            await model_manager.update_global_setting(global_setting)
            self.state.add_log(_("✓ 已更新全局模型设置"))
            logger.info("已更新全局模型设置 - function: %s, embedding: %s", llm_model_id, embedding_model_id)

    async def _register_llm_model(
        self,
        model_manager: HermesModelManager,
        config: DeploymentConfig,
    ) -> str:
        """注册 LLM 模型"""
        llm_model_id = config.llm.model or "default-llm"
        llm_config = HermesLLMConfig(
            provider=LLMProvider.OPENAI,
            ctx_length=config.llm.ctx_length,
            id=llm_model_id,
            base_url=config.llm.endpoint,
            api_key=config.llm.api_key,
            model_name=config.llm.model,
            max_tokens=config.llm.max_tokens,
            llm_description=_("部署时配置的 Chat 模型（支持 Function Call）"),
            llm_type=[LLMType.CHAT, LLMType.FUNCTION],
            extra_data={"temperature": config.llm.temperature},
        )

        await model_manager.create_or_update_model(llm_config)
        self.state.add_log(_("✓ 已注册 LLM 模型: {model}").format(model=llm_model_id))
        logger.info("已注册 LLM 模型: %s", llm_model_id)
        return llm_model_id

    async def _register_embedding_model(
        self,
        model_manager: HermesModelManager,
        config: DeploymentConfig,
    ) -> str:
        """注册 Embedding 模型"""
        embedding_model_id = config.embedding.model or "default-embedding"
        embedding_provider = LLMProvider.TEI if config.embedding.type == "mindie" else LLMProvider.OPENAI

        embedding_config = HermesLLMConfig(
            provider=embedding_provider,
            ctx_length=config.embedding.ctx_length,
            id=embedding_model_id,
            base_url=config.embedding.endpoint,
            api_key=config.embedding.api_key,
            model_name=config.embedding.model,
            llm_description=_("部署时配置的 Embedding 模型"),
            llm_type=[LLMType.EMBEDDING],
        )

        await model_manager.create_or_update_model(embedding_config)
        self.state.add_log(_("✓ 已注册 Embedding 模型: {model}").format(model=embedding_model_id))
        logger.info("已注册 Embedding 模型: %s", embedding_model_id)
        return embedding_model_id
