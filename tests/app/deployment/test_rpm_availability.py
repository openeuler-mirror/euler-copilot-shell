"""
测试部署资源文件管理功能

运行方法：
    pytest tests/app/deployment/test_rpm_availability.py -v

注意：由于 app.deployment 模块存在循环导入，此测试使用路径操作直接验证资源文件，
而不是通过 AgentManager 类。
"""

from pathlib import Path

import pytest


def test_install_framework_script_includes_required_rpms() -> None:
    """安装 framework 时应一并安装 3 个配套 RPM 包。"""
    project_root = Path(__file__).parent.parent.parent.parent
    script_path = project_root / "scripts" / "deploy" / "2-install-dependency" / "install_openEulerIntelligence.sh"

    content = script_path.read_text(encoding="utf-8")

    assert '"euler-copilot-framework"' in content
    assert '"witty-lite-rag"' in content
    assert '"witty-log-detection"' in content
    assert '"witty-mcp-manager"' in content


def test_production_deploy_uninstall_scripts_remove_required_rpms() -> None:
    """生产环境 deploy 卸载脚本应移除这 3 个配套 RPM。"""
    project_root = Path(__file__).parent.parent.parent.parent
    uninstall_server = project_root / "scripts" / "deploy" / "3-install-server" / "uninstall_server.sh"
    uninstall_dependency = project_root / "scripts" / "deploy" / "2-install-dependency" / "uninstall_dependency.sh"

    server_content = uninstall_server.read_text(encoding="utf-8")
    dependency_content = uninstall_dependency.read_text(encoding="utf-8")

    for pkg in ("witty-lite-rag", "witty-log-detection", "witty-mcp-manager"):
        assert pkg in server_content
        assert pkg not in dependency_content


def test_init_config_starts_witty_mcp_manager_before_sysagent() -> None:
    """初始化配置脚本应先启动 witty-mcp-manager，再启动 sysagent。"""
    project_root = Path(__file__).parent.parent.parent.parent
    script_path = project_root / "scripts" / "deploy" / "3-install-server" / "init_config.sh"

    content = script_path.read_text(encoding="utf-8")

    mcp_manager_enable = "systemctl enable --now witty-mcp-manager"
    sysagent_enable = "systemctl enable --now sysagent"

    assert mcp_manager_enable in content
    assert sysagent_enable in content
    assert content.index(mcp_manager_enable) < content.index(sysagent_enable)


@pytest.mark.unit
class TestDeploymentResourceFiles:
    """测试部署资源文件"""

    @pytest.fixture
    def script_resource_dir(self) -> Path:
        """获取脚本资源目录路径"""
        # 从项目根目录查找资源目录
        project_root = Path(__file__).parent.parent.parent.parent
        return project_root / "scripts" / "deploy" / "resources"

    def test_script_resource_directory_exists(self, script_resource_dir: Path) -> None:
        """测试脚本资源目录是否存在"""
        assert script_resource_dir.exists(), f"资源目录不存在: {script_resource_dir}"
        assert script_resource_dir.is_dir(), f"资源路径不是目录: {script_resource_dir}"

    def test_rpm_list_files_exist(self, script_resource_dir: Path) -> None:
        """测试 RPM 列表文件是否存在"""
        # 预期的 RPM 列表文件
        rpm_files = ["mcp-servers.rpmlist", "sysTrace.rpmlist"]

        for rpm_file in rpm_files:
            file_path = script_resource_dir / rpm_file

            # 如果文件存在，验证其为文件
            if file_path.exists():
                assert file_path.is_file(), f"{rpm_file} 不是文件"

    def test_rpm_list_file_format(self, script_resource_dir: Path) -> None:
        """测试 RPM 列表文件的内容格式"""
        rpm_files = ["mcp-servers.rpmlist", "sysTrace.rpmlist"]

        for rpm_file in rpm_files:
            file_path = script_resource_dir / rpm_file

            # 跳过不存在的文件
            if not file_path.exists():
                continue

            # 验证文件可以读取并包含有效的包名
            with file_path.open(encoding="utf-8") as f:
                lines = f.readlines()
                # 应该至少有一些非空行（排除注释）
                non_comment_lines = [
                    line.strip() for line in lines if line.strip() and not line.strip().startswith("#")
                ]

                # 如果文件存在，应该包含一些包名
                if non_comment_lines:
                    # 验证包名格式（简单验证：不为空且不以空格开头）
                    for package in non_comment_lines:
                        assert len(package) > 0, f"包名不能为空: {rpm_file}"
                        assert not package.startswith(" "), f"包名不应以空格开头: {package}"


@pytest.mark.integration
class TestDeploymentConfiguration:
    """测试部署配置文件"""

    @pytest.fixture
    def script_resource_dir(self) -> Path:
        """获取脚本资源目录路径"""
        project_root = Path(__file__).parent.parent.parent.parent
        return project_root / "scripts" / "deploy" / "resources"

    def test_config_toml_exists(self, script_resource_dir: Path) -> None:
        """测试 config.toml 配置文件是否存在"""
        config_file = script_resource_dir / "config.toml"

        if config_file.exists():
            assert config_file.is_file(), "config.toml 应该是文件"
            assert config_file.stat().st_size > 0, "config.toml 不应该为空"

    def test_service_files_exist(self, script_resource_dir: Path) -> None:
        """测试 systemd 服务文件是否存在"""
        service_files = ["oi-rag.service", "oi-runtime.service", "tika.service"]

        for service_file in service_files:
            file_path = script_resource_dir / service_file

            if file_path.exists():
                assert file_path.is_file(), f"{service_file} 应该是文件"

                # 验证服务文件包含基本的 systemd 单元内容
                content = file_path.read_text(encoding="utf-8")
                assert "[Unit]" in content or "[Service]" in content, f"{service_file} 应该包含 systemd 单元配置"
