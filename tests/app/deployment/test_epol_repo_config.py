"""测试 EPOL 仓库配置解析和 update-EPOL 构造逻辑。"""

from __future__ import annotations

from textwrap import dedent
from typing import TYPE_CHECKING

from app.deployment.service import DeploymentService

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_get_epol_repo_config_with_standard_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """测试从标准 openEuler.repo 文件中读取 EPOL 仓库配置。"""
    # 创建模拟的 openEuler.repo 文件
    repo_file = tmp_path / "openEuler.repo"
    repo_content = """\
[OS]
name=OS
baseurl=https://repo.openeuler.org/openEuler-24.03-LTS-SP3/OS/$basearch/
enabled=1
gpgcheck=1
gpgkey=http://repo.openeuler.org/openEuler-24.03-LTS-SP3/OS/$basearch/RPM-GPG-KEY-openEuler

[EPOL]
name=EPOL
baseurl=https://repo.openeuler.org/openEuler-24.03-LTS-SP3/EPOL/main/$basearch/
metadata_expire=1h
enabled=1
gpgcheck=1
gpgkey=http://repo.openeuler.org/openEuler-24.03-LTS-SP3/OS/$basearch/RPM-GPG-KEY-openEuler
"""
    repo_file.write_text(repo_content, encoding="utf-8")

    # Mock Path 对象
    monkeypatch.setattr(
        "app.deployment.service.Path",
        lambda path: repo_file if "openEuler.repo" in path else tmp_path / path,
    )

    service = DeploymentService()
    result = service._get_epol_repo_config()  # noqa: SLF001

    # 验证返回结果
    assert result is not None
    epol_baseurl, gpgkey_url = result
    assert epol_baseurl == "https://repo.openeuler.org/openEuler-24.03-LTS-SP3/EPOL/main/$basearch/"
    assert gpgkey_url == "http://repo.openeuler.org/openEuler-24.03-LTS-SP3/OS/$basearch/RPM-GPG-KEY-openEuler"


def test_get_epol_repo_config_with_huawei_cloud_mirror(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """测试从华为云镜像的 repo 文件中读取 EPOL 配置。"""
    repo_file = tmp_path / "openEuler.repo"
    repo_content = """\
[EPOL]
name=EPOL
baseurl=https://repo.huaweicloud.com/openeuler/openEuler-24.03-LTS-SP3/EPOL/main/$basearch/
enabled=1
gpgcheck=1
gpgkey=https://repo.huaweicloud.com/openeuler/openEuler-24.03-LTS-SP3/OS/$basearch/RPM-GPG-KEY-openEuler
"""
    repo_file.write_text(repo_content, encoding="utf-8")

    monkeypatch.setattr(
        "app.deployment.service.Path",
        lambda path: repo_file if "openEuler.repo" in path else tmp_path / path,
    )

    service = DeploymentService()
    result = service._get_epol_repo_config()  # noqa: SLF001

    assert result is not None
    epol_baseurl, gpgkey_url = result
    assert epol_baseurl == "https://repo.huaweicloud.com/openeuler/openEuler-24.03-LTS-SP3/EPOL/main/$basearch/"
    assert (
        gpgkey_url
        == "https://repo.huaweicloud.com/openeuler/openEuler-24.03-LTS-SP3/OS/$basearch/RPM-GPG-KEY-openEuler"
    )


def test_get_epol_repo_config_with_non_standard_distro(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """测试非标准发行版（不包含 openEuler 字符串）的 EPOL 配置。"""
    repo_file = tmp_path / "openEuler.repo"
    repo_content = """\
[EPOL]
name=EPOL
baseurl=https://enterprise.example.com/distro/24.03/EPOL/main/$basearch/
enabled=1
gpgcheck=1
gpgkey=https://enterprise.example.com/distro/24.03/OS/$basearch/RPM-GPG-KEY-enterprise
"""
    repo_file.write_text(repo_content, encoding="utf-8")

    monkeypatch.setattr(
        "app.deployment.service.Path",
        lambda path: repo_file if "openEuler.repo" in path else tmp_path / path,
    )

    service = DeploymentService()
    result = service._get_epol_repo_config()  # noqa: SLF001

    assert result is not None
    epol_baseurl, gpgkey_url = result
    assert epol_baseurl == "https://enterprise.example.com/distro/24.03/EPOL/main/$basearch/"
    assert gpgkey_url == "https://enterprise.example.com/distro/24.03/OS/$basearch/RPM-GPG-KEY-enterprise"


def test_get_epol_repo_config_fallback_when_no_gpgkey(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """测试当 EPOL 配置缺少 gpgkey 时，返回 None 作为 gpgkey（不推断）。"""
    repo_file = tmp_path / "openEuler.repo"
    repo_content = """\
[EPOL]
name=EPOL
baseurl=https://repo.openeuler.org/openEuler-24.03-LTS-SP3/EPOL/main/$basearch/
enabled=1
"""
    repo_file.write_text(repo_content, encoding="utf-8")

    monkeypatch.setattr(
        "app.deployment.service.Path",
        lambda path: repo_file if "openEuler.repo" in path else tmp_path / path,
    )

    service = DeploymentService()
    result = service._get_epol_repo_config()  # noqa: SLF001

    assert result is not None
    epol_baseurl, gpgkey_url = result
    assert epol_baseurl == "https://repo.openeuler.org/openEuler-24.03-LTS-SP3/EPOL/main/$basearch/"
    # EPOL 没有 gpgkey 时，直接返回 None（不推断）
    assert gpgkey_url is None


def test_get_epol_repo_config_returns_none_when_no_epol(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """测试当 repo 文件中没有 EPOL 配置时，返回 None。"""
    repo_file = tmp_path / "openEuler.repo"
    repo_content = """\
[OS]
name=OS
baseurl=https://repo.openeuler.org/openEuler-24.03-LTS-SP3/OS/$basearch/
enabled=1
"""
    repo_file.write_text(repo_content, encoding="utf-8")

    monkeypatch.setattr(
        "app.deployment.service.Path",
        lambda path: repo_file if "openEuler.repo" in path else tmp_path / path,
    )

    service = DeploymentService()
    result = service._get_epol_repo_config()  # noqa: SLF001

    assert result is None


def test_get_epol_repo_config_returns_none_when_file_not_exists(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试当 repo 文件不存在时，返回 None。"""
    non_existent_path = tmp_path / "non_existent" / "openEuler.repo"

    monkeypatch.setattr(
        "app.deployment.service.Path",
        lambda path: non_existent_path if "openEuler.repo" in path else tmp_path / path,
    )

    service = DeploymentService()
    result = service._get_epol_repo_config()  # noqa: SLF001

    assert result is None


def test_construct_update_epol_from_standard_epol() -> None:
    """测试基于标准 EPOL baseurl 构造 update-EPOL URL。"""
    epol_baseurl = "https://repo.openeuler.org/openEuler-24.03-LTS-SP3/EPOL/main/$basearch/"

    # 构造 update-EPOL URL（模拟 _setup_epol_repo 中的逻辑）
    if "/EPOL/main/" in epol_baseurl:
        update_epol_baseurl = epol_baseurl.replace("/EPOL/main/", "/EPOL/update/main/")
    else:
        update_epol_baseurl = epol_baseurl.replace("/EPOL/", "/EPOL/update/")

    # 验证转换结果
    assert update_epol_baseurl == "https://repo.openeuler.org/openEuler-24.03-LTS-SP3/EPOL/update/main/$basearch/"


def test_construct_update_epol_from_non_standard_format() -> None:
    """测试基于非标准格式的 EPOL baseurl 构造 update-EPOL URL。"""
    # 某些发行版可能不使用 /EPOL/main/ 格式
    epol_baseurl = "https://enterprise.example.com/distro/24.03/EPOL/$basearch/"

    if "/EPOL/main/" in epol_baseurl:
        update_epol_baseurl = epol_baseurl.replace("/EPOL/main/", "/EPOL/update/main/")
    else:
        update_epol_baseurl = epol_baseurl.replace("/EPOL/", "/EPOL/update/")

    # 验证转换结果
    assert update_epol_baseurl == "https://enterprise.example.com/distro/24.03/EPOL/update/$basearch/"


def test_update_epol_repo_configuration_format() -> None:
    """测试 update-EPOL 仓库配置的完整格式。"""
    epol_baseurl = "https://repo.openeuler.org/openEuler-24.03-LTS-SP3/EPOL/main/$basearch/"
    gpgkey_url = "http://repo.openeuler.org/openEuler-24.03-LTS-SP3/OS/$basearch/RPM-GPG-KEY-openEuler"

    # 构造 update-EPOL URL
    update_epol_baseurl = epol_baseurl.replace("/EPOL/main/", "/EPOL/update/main/")

    # 生成 repo 配置（模拟 _setup_epol_repo 中的逻辑）
    repo_content = dedent(f"""\
        [update-EPOL]
        name=update-EPOL
        baseurl={update_epol_baseurl}
        metadata_expire=1h
        enabled=1
        gpgcheck=1
        gpgkey={gpgkey_url}
    """)

    # 验证配置内容
    assert "[update-EPOL]" in repo_content
    assert "name=update-EPOL" in repo_content
    assert "baseurl=https://repo.openeuler.org/openEuler-24.03-LTS-SP3/EPOL/update/main/$basearch/" in repo_content
    assert "gpgkey=http://repo.openeuler.org/openEuler-24.03-LTS-SP3/OS/$basearch/RPM-GPG-KEY-openEuler" in repo_content
    assert "enabled=1" in repo_content
    assert "gpgcheck=1" in repo_content
