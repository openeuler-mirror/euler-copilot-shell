"""Shell completion 脚本生成测试"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import Mock

import pytest

import main
from i18n.manager import get_locale, init_i18n
from tool.completion import (
    _ROOT_COMMANDS,
    _SET_DEFAULT_SUBCOMMANDS,
    generate_completion_script,
    get_default_install_path,
)

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.unit
@pytest.mark.parametrize(
    ("shell", "expected_snippet"),
    [
        ("bash", "complete -F _witty_completion witty"),
        ("zsh", "#compdef witty"),
        ("fish", "complete -c witty"),
    ],
)
def test_completion_command_installs_script(
    shell: str,
    expected_snippet: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """验证 completion 命令会安装脚本，并输出提示信息（脚本不会立刻生效）"""
    previous_locale = get_locale()
    init_i18n("zh_CN")
    try:
        # 将 HOME/XDG 指向临时目录，避免污染真实用户环境
        home = tmp_path / "home"
        home.mkdir(parents=True, exist_ok=True)
        monkeypatch.setenv("HOME", str(home))
        monkeypatch.setenv("XDG_CONFIG_HOME", str(home / "xdg_config"))
        monkeypatch.setenv("XDG_DATA_HOME", str(home / "xdg_data"))

        config = Mock()
        handled = main._dispatch_cli(["completion", shell], config)  # noqa: SLF001
        assert handled is True

        target = get_default_install_path(shell)
        assert target.exists()
        content = target.read_text(encoding="utf-8")
        assert expected_snippet in content

        out = capsys.readouterr().out
        # 输出中应包含安装路径及“不会立即生效”的提示（中文）
        assert str(target) in out
        assert "不会在当前会话立刻生效" in out
    finally:
        init_i18n(previous_locale)


@pytest.mark.unit
def test_completion_command_detects_shell_from_env(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """验证未指定 shell 时，会从 SHELL 环境变量探测并安装。"""
    previous_locale = get_locale()
    init_i18n("en_US")
    try:
        home = tmp_path / "home"
        home.mkdir(parents=True, exist_ok=True)
        monkeypatch.setenv("HOME", str(home))
        monkeypatch.setenv("XDG_CONFIG_HOME", str(home / "xdg_config"))
        monkeypatch.setenv("XDG_DATA_HOME", str(home / "xdg_data"))
        monkeypatch.setenv("SHELL", "/bin/zsh")
        monkeypatch.delenv("FISH_VERSION", raising=False)

        config = Mock()
        handled = main._dispatch_cli(["completion"], config)  # noqa: SLF001
        assert handled is True

        target = get_default_install_path("zsh")
        assert target.exists()
        assert "#compdef witty" in target.read_text(encoding="utf-8")

        out = capsys.readouterr().out
        assert str(target) in out
        assert "Completion will not take effect" in out
    finally:
        init_i18n(previous_locale)


@pytest.mark.unit
def test_generate_completion_rejects_unknown_shell() -> None:
    """验证 generate_completion_script 对未知 shell 抛出 ValueError"""
    with pytest.raises(ValueError):  # noqa: PT011
        generate_completion_script("powershell")


@pytest.mark.unit
@pytest.mark.parametrize("shell", ["bash", "zsh", "fish"])
def test_completion_script_contains_root_commands(shell: str) -> None:
    """验证脚本包含所有根命令"""
    script = generate_completion_script(shell)
    for cmd in _ROOT_COMMANDS:
        assert cmd in script


@pytest.mark.unit
@pytest.mark.parametrize("shell", ["bash", "zsh", "fish"])
def test_completion_script_contains_set_default_subs(shell: str) -> None:
    """验证脚本包含 set-default 子命令"""
    script = generate_completion_script(shell)
    for sub in _SET_DEFAULT_SUBCOMMANDS:
        assert sub in script


@pytest.mark.unit
def test_bash_completion_script_structure() -> None:
    """验证 bash 脚本的基本结构"""
    script = generate_completion_script("bash")
    assert "# bash completion for witty" in script
    assert "_witty_completion()" in script
    assert "complete -F _witty_completion witty" in script
    assert "COMP_WORDS" in script
    assert "compgen" in script


@pytest.mark.unit
def test_zsh_completion_script_structure() -> None:
    """验证 zsh 脚本的基本结构"""
    script = generate_completion_script("zsh")
    assert script.startswith("#compdef witty")
    assert "bashcompinit" in script
    assert "autoload -U +X bashcompinit" in script


@pytest.mark.unit
def test_fish_completion_script_structure() -> None:
    """验证 fish 脚本的基本结构"""
    script = generate_completion_script("fish")
    assert script.startswith("# fish completion for witty")
    assert "complete -c witty" in script
    assert "__fish_use_subcommand" in script
    assert "__fish_seen_subcommand_from" in script


@pytest.mark.unit
def test_completion_script_contains_log_levels() -> None:
    """验证脚本包含日志级别选项"""
    script = generate_completion_script("bash")  # 任意 shell 都应包含
    from config.model import LogLevel  # noqa: PLC0415
    for level in LogLevel.__members__:
        assert level in script


@pytest.mark.unit
def test_completion_script_contains_locales() -> None:
    """验证脚本包含语言选项"""
    script = generate_completion_script("bash")  # 任意 shell 都应包含
    from i18n.manager import get_supported_locales  # noqa: PLC0415
    for locale in get_supported_locales():
        assert locale in script


@pytest.mark.unit
def test_generate_completion_script_returns_string() -> None:
    """验证函数返回字符串类型"""
    for shell in ["bash", "zsh", "fish"]:
        result = generate_completion_script(shell)
        assert isinstance(result, str)
        assert len(result) > 0


@pytest.mark.unit
def test_completion_script_handles_case_insensitive_shell() -> None:
    """验证 shell 参数大小写不敏感"""
    script1 = generate_completion_script("BASH")
    script2 = generate_completion_script("bash")
    assert script1 == script2

    script3 = generate_completion_script("ZSH")
    script4 = generate_completion_script("zsh")
    assert script3 == script4

    script5 = generate_completion_script("FISH")
    script6 = generate_completion_script("fish")
    assert script5 == script6
