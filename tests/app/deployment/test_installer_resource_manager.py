"""测试安装器资源路径解析逻辑。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.deployment.service import DeploymentResourceManager

if TYPE_CHECKING:
    from pathlib import Path

    from _pytest.monkeypatch import MonkeyPatch


def _make_installer_tree(base_path: Path) -> None:
    """构造一个满足安装器检查条件的最小目录结构。"""
    (base_path / "resources").mkdir(parents=True, exist_ok=True)
    (base_path / "resources" / "config.toml").write_text("# template\n", encoding="utf-8")
    (base_path / "deploy").write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")


def test_check_installer_available_picks_valid_candidate(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    """当存在多个候选路径时，应选择第一个满足完整资源条件的路径。"""
    invalid_base = tmp_path / "usr" / "lib" / "witty-assistant" / "scripts"
    valid_base = tmp_path / "usr" / "lib64" / "witty-assistant" / "scripts"

    # invalid candidate: base exists but missing required files
    invalid_base.mkdir(parents=True, exist_ok=True)

    # valid candidate tree
    _make_installer_tree(valid_base)

    monkeypatch.setattr(
        DeploymentResourceManager,
        "CANDIDATE_INSTALLER_BASE_PATHS",
        (invalid_base, valid_base),
    )

    mgr = DeploymentResourceManager()
    assert mgr.check_installer_available() is True
    assert mgr.installer_base_path == valid_base
    assert mgr.resource_path == valid_base / "resources"
    assert mgr.deploy_script == valid_base / "deploy"
    assert mgr.config_template == valid_base / "resources" / "config.toml"


def test_check_installer_available_false_when_missing_all(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    """当所有候选路径都缺失必要文件时，应返回 False。"""
    base = tmp_path / "usr" / "lib" / "witty-assistant" / "scripts"
    base.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(DeploymentResourceManager, "CANDIDATE_INSTALLER_BASE_PATHS", (base,))

    mgr = DeploymentResourceManager()
    assert mgr.check_installer_available() is False
