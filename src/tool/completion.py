"""Shell completion script generation utilities."""

from __future__ import annotations

import os
import textwrap
from pathlib import Path
from typing import TYPE_CHECKING, Final

from config.model import LogLevel
from i18n.manager import _, get_supported_locales

if TYPE_CHECKING:
    from collections.abc import Mapping

_SUPPORTED_SHELLS: Final[tuple[str, ...]] = ("bash", "zsh", "fish")

_ROOT_COMMANDS: Final[tuple[str, ...]] = (
    "help",
    "version",
    "init",
    "logs",
    "llm",
    "set-default",
    "completion",
)

_SET_DEFAULT_SUBCOMMANDS: Final[tuple[str, ...]] = ("agent", "log-level", "locale")


def detect_default_shell(environ: Mapping[str, str] | None = None) -> str | None:
    """
    探测当前环境的默认 shell。

    规则尽量简单且可预测：
    - fish：若存在 FISH_VERSION 环境变量
    - 其他：读取 SHELL 并取 basename

    Args:
        environ: 环境变量映射，默认使用 os.environ。

    Returns:
        "bash" | "zsh" | "fish" 或 None（无法探测）。

    """
    env = os.environ if environ is None else environ
    if "FISH_VERSION" in env:
        return "fish"

    shell_path = env.get("SHELL", "").strip()
    if not shell_path:
        return None

    base = Path(shell_path).name.lower()
    if base in _SUPPORTED_SHELLS:
        return base

    # 兼容类似 /usr/local/bin/zsh 或者其它变种名称
    suffix_map: dict[str, str] = {"bash": "bash", "zsh": "zsh", "fish": "fish"}
    for suffix, normalized in suffix_map.items():
        if base.endswith(suffix):
            return normalized
    return None


def get_default_install_path(shell: str, environ: Mapping[str, str] | None = None) -> Path:
    """
    返回 completion 脚本的默认用户级安装路径（XDG 优先）。

    Args:
        shell: 目标 shell（bash/zsh/fish）。
        environ: 环境变量映射，默认使用 os.environ。

    Returns:
        建议写入的目标文件路径。

    Raises:
        ValueError: shell 不受支持。

    """
    normalized = shell.strip().lower()
    if normalized not in _SUPPORTED_SHELLS:
        msg = f"Unsupported shell: {shell}"
        raise ValueError(msg)

    env = os.environ if environ is None else environ
    home_value = env.get("HOME")
    home = Path(home_value) if home_value else Path.home()

    xdg_config_home = Path(env.get("XDG_CONFIG_HOME") or (home / ".config"))
    xdg_data_home = Path(env.get("XDG_DATA_HOME") or (home / ".local" / "share"))

    if normalized == "fish":
        return xdg_config_home / "fish" / "completions" / "witty.fish"
    if normalized == "bash":
        return xdg_data_home / "bash-completion" / "completions" / "witty"
    # zsh
    return xdg_data_home / "zsh" / "site-functions" / "_witty"


def install_completion_script(
    shell: str,
    *,
    environ: Mapping[str, str] | None = None,
    dest_path: Path | None = None,
) -> Path:
    """
    生成并安装 completion 脚本到默认位置（或指定位置）。

    该操作是幂等的：会直接覆盖目标文件，便于用户重复执行更新脚本。

    Args:
        shell: 目标 shell（bash/zsh/fish）。
        environ: 环境变量映射，默认使用 os.environ。
        dest_path: 指定写入路径；若为空则使用 get_default_install_path。

    Returns:
        实际写入的目标路径。

    """
    normalized = shell.strip().lower()
    target = dest_path or get_default_install_path(normalized, environ=environ)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(generate_completion_script(normalized), encoding="utf-8")
    return target


def get_install_hint(shell: str, target: Path) -> str:
    """
    返回安装后提示信息（不会立即生效）。

    Args:
        shell: 目标 shell（bash/zsh/fish）。
        target: 已写入的脚本路径。

    Returns:
        面向用户的多行提示文本。

    """
    normalized = shell.strip().lower()
    if normalized == "bash":
        return (
            _(
                "自动补全不会在当前会话立刻生效。\n"
                "你可以：\n"
                "  1) 重新打开终端，或\n"
                '  2) 临时执行：source "{path}"\n',
            ).format(path=target)
        )
    if normalized == "zsh":
        parent = target.parent
        return (
            _(
                "自动补全不会在当前会话立刻生效。\n"
                "你可以将目录加入 fpath 并重新初始化 compinit，例如：\n"
                '  fpath=("{dir}" $fpath)\n'
                "  autoload -U compinit && compinit\n"
                "（建议把 fpath 配置写入 ~/.zshrc）\n",
            ).format(dir=parent)
        )
    # fish
    return _(
        "自动补全不会在当前会话立刻生效。\n"
        "你可以重新打开 fish，或执行：exec fish\n",
    )


def generate_completion_script(shell: str) -> str:
    """
    生成 shell completion 脚本并返回其文本内容。

    该函数故意不依赖第三方库（如 argcomplete），避免引入额外依赖并保持 RPM 打包简单。
    completion 内容为"静态补全"，覆盖本项目公开的子命令与常用参数。

    Args:
        shell: 目标 shell，支持 bash/zsh/fish。

    Returns:
        对应 shell 的脚本字符串。

    Raises:
        ValueError: 不支持的 shell。

    """
    shell = shell.strip().lower()
    if shell not in _SUPPORTED_SHELLS:
        msg = f"Unsupported shell: {shell}"
        raise ValueError(msg)

    commands = " ".join(_ROOT_COMMANDS)
    set_default_subs = " ".join(_SET_DEFAULT_SUBCOMMANDS)
    log_levels = " ".join(LogLevel.__members__.keys())
    locales = " ".join(get_supported_locales().keys())

    if shell in {"bash", "zsh"}:
        bash_body = _render_bash_completion(
            commands=commands,
            set_default_subs=set_default_subs,
            log_levels=log_levels,
            locales=locales,
        )
        if shell == "bash":
            return bash_body
        # zsh: 复用 bash completion（bashcompinit 会让 `complete` 在 zsh 下可用）
        return f"#compdef witty\nautoload -U +X bashcompinit && bashcompinit\n{bash_body}"

    return _render_fish_completion(
        commands=_ROOT_COMMANDS,
        set_default_subs=_SET_DEFAULT_SUBCOMMANDS,
        log_levels=tuple(LogLevel.__members__.keys()),
        locales=tuple(get_supported_locales().keys()),
    )


def _render_bash_completion(*, commands: str, set_default_subs: str, log_levels: str, locales: str) -> str:
    # bash completion 脚本不需要国际化，保持稳定可测试。
    template = """
        # bash completion for witty

        _witty_completion() {
            local cur prev
            cur="${COMP_WORDS[COMP_CWORD]}"
            prev="${COMP_WORDS[COMP_CWORD-1]}"

            # completing the first argument: command or global flags
            if [[ ${COMP_CWORD} -eq 1 ]]; then
                if [[ "$cur" == -* ]]; then
                    COMPREPLY=( $(compgen -W "-h --help -V --version" -- "$cur") )
                    return 0
                fi
                COMPREPLY=( $(compgen -W "__COMMANDS__" -- "$cur") )
                return 0
            fi

            local cmd="${COMP_WORDS[1]}"

            case "$cmd" in
                help)
                    if [[ ${COMP_CWORD} -eq 2 ]]; then
                        COMPREPLY=( $(compgen -W "__COMMANDS__" -- "$cur") )
                        return 0
                    fi
                    if [[ ${COMP_CWORD} -eq 3 && "${COMP_WORDS[2]}" == "set-default" ]]; then
                        COMPREPLY=( $(compgen -W "__SET_DEFAULT_SUBS__" -- "$cur") )
                        return 0
                    fi
                    ;;

                logs)
                    if [[ "$cur" == -* ]]; then
                        COMPREPLY=( $(compgen -W "-n --lines -h --help" -- "$cur") )
                        return 0
                    fi
                    ;;

                set-default)
                    if [[ ${COMP_CWORD} -eq 2 ]]; then
                        COMPREPLY=( $(compgen -W "__SET_DEFAULT_SUBS__ -h --help" -- "$cur") )
                        return 0
                    fi

                    local sub="${COMP_WORDS[2]}"
                    case "$sub" in
                        log-level)
                            if [[ ${COMP_CWORD} -eq 3 ]]; then
                                COMPREPLY=( $(compgen -W "__LOG_LEVELS__" -- "$cur") )
                                return 0
                            fi
                            ;;
                        locale)
                            if [[ ${COMP_CWORD} -eq 3 ]]; then
                                COMPREPLY=( $(compgen -W "__LOCALES__" -- "$cur") )
                                return 0
                            fi
                            ;;
                    esac
                    ;;

                completion)
                    if [[ ${COMP_CWORD} -eq 2 ]]; then
                        COMPREPLY=( $(compgen -W "bash zsh fish" -- "$cur") )
                        return 0
                    fi
                    ;;
            esac

            return 0
        }

        complete -F _witty_completion witty
        """
    script = textwrap.dedent(template)
    script = script.replace("__COMMANDS__", commands)
    script = script.replace("__SET_DEFAULT_SUBS__", set_default_subs)
    script = script.replace("__LOG_LEVELS__", log_levels)
    return script.replace("__LOCALES__", locales)


def _render_fish_completion(
    *,
    commands: tuple[str, ...],
    set_default_subs: tuple[str, ...],
    log_levels: tuple[str, ...],
    locales: tuple[str, ...],
) -> str:
    # fish completion 同样保持稳定（不依赖运行时调用 witty 本身）
    cmd_list = " ".join(commands)
    set_default_list = " ".join(set_default_subs)
    levels_list = " ".join(log_levels)
    locales_list = " ".join(locales)
    lines = [
        "# fish completion for witty",
        f"complete -c witty -f -n '__fish_use_subcommand' -a '{cmd_list}'",
        "complete -c witty -f -n '__fish_seen_subcommand_from help' "
        "-a 'help version init logs llm set-default completion'",
        "complete -c witty -f -n '__fish_seen_subcommand_from completion' -a 'bash zsh fish'",
        f"complete -c witty -f -n '__fish_seen_subcommand_from set-default' -a '{set_default_list}'",
        "complete -c witty -f -n "
        "'__fish_seen_subcommand_from set-default; and __fish_seen_subcommand_from log-level' "
        f"-a '{levels_list}'",
        "complete -c witty -f -n "
        "'__fish_seen_subcommand_from set-default; and __fish_seen_subcommand_from locale' "
        f"-a '{locales_list}'",
    ]
    return "\n".join(lines) + "\n"
