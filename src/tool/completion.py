"""Shell completion script generation utilities."""

from __future__ import annotations

import textwrap
from typing import Final

from config.model import LogLevel
from i18n.manager import get_supported_locales

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
