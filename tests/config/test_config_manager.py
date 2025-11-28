"""ConfigManager 文件操作测试"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from config.manager import ConfigManager
from config.model import ConfigModel

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture(autouse=True)
def _reset_config_model() -> None:
    """确保每个测试都有干净的默认配置"""
    ConfigManager.data = ConfigModel()


def _patch_paths(
    monkeypatch: pytest.MonkeyPatch,
    user_path: Path,
    global_path: Path,
) -> None:
    monkeypatch.setattr(ConfigManager, "USER_CONFIG_PATH", user_path)
    monkeypatch.setattr(ConfigManager, "USER_CONFIG_DIR", user_path.parent)
    monkeypatch.setattr(ConfigManager, "GLOBAL_CONFIG_PATH", global_path)
    monkeypatch.setattr(ConfigManager, "GLOBAL_CONFIG_DIR", global_path.parent)


@pytest.mark.unit
def test_init_copies_global_template(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """当用户配置缺失时应复制全局模板"""
    global_dir = tmp_path / "config"
    global_dir.mkdir()
    global_path = global_dir / "template.json"
    user_dir = tmp_path / "user"
    user_dir.mkdir()
    user_path = user_dir / "smart-shell.json"

    template = {
        "openai": {"base_url": "http://demo", "model": "gpt"},
        "eulerintelli": {"base_url": "http://oi", "api_key": "token"},
    }
    global_path.write_text(json.dumps(template), encoding="utf-8")

    _patch_paths(monkeypatch, user_path, global_path)

    manager = ConfigManager()

    assert user_path.exists()
    data = json.loads(user_path.read_text(encoding="utf-8"))
    assert data["openai"]["base_url"] == "http://demo"
    assert manager.get_eulerintelli_key() == "token"


@pytest.mark.unit
def test_init_creates_default_when_no_template(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """全局模板缺失时应生成默认配置"""
    global_dir = tmp_path / "config"
    global_dir.mkdir()
    global_path = global_dir / "template.json"
    user_dir = tmp_path / "user"
    user_dir.mkdir()
    user_path = user_dir / "smart-shell.json"

    _patch_paths(monkeypatch, user_path, global_path)

    manager = ConfigManager()

    assert user_path.exists()
    data = json.loads(user_path.read_text(encoding="utf-8"))
    assert data["openai"]["api_key"] == ""
    manager.set_eulerintelli_url("https://oi.local")
    assert (
        json.loads(user_path.read_text(encoding="utf-8"))["eulerintelli"]["base_url"]
        == "https://oi.local"
    )


@pytest.mark.unit
def test_validate_and_update_config_merges_missing_fields(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """validate_and_update_config 会补齐缺失字段"""
    global_dir = tmp_path / "config"
    global_dir.mkdir()
    global_path = global_dir / "template.json"
    user_dir = tmp_path / "user"
    user_dir.mkdir()
    user_path = user_dir / "smart-shell.json"
    user_path.parent.mkdir(parents=True, exist_ok=True)

    minimal_config = {"openai": {"base_url": "http://demo"}}
    user_path.write_text(json.dumps(minimal_config), encoding="utf-8")

    _patch_paths(monkeypatch, user_path, global_path)

    manager = ConfigManager()
    updated = manager.validate_and_update_config()

    assert updated is True
    data = json.loads(user_path.read_text(encoding="utf-8"))
    assert "model" in data["openai"]
    assert data["openai"]["model"] == ConfigModel().openai.model
