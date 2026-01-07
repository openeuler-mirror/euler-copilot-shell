"""应用入口点"""

from __future__ import annotations

import argparse
import asyncio
import atexit
import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from __version__ import __version__
from config.manager import ConfigManager
from config.model import LogLevel
from i18n.manager import _, get_locale, get_supported_locales, init_i18n, set_locale
from log.manager import (
    cleanup_empty_logs,
    disable_console_output,
    enable_console_output,
    get_latest_logs,
    get_logger,
    setup_logging,
)
from tool import backend_init, llm_config, select_agent
from tool.completion import _SUPPORTED_SHELLS, detect_default_shell, get_install_hint, install_completion_script

if TYPE_CHECKING:
    from collections.abc import Callable


DOCS_URL: Final[str] = "https://atomgit.com/openeuler/euler-copilot-shell/tree/master/docs"

_HELP_ALIASES: Final[set[str]] = {"-h", "--help", "help"}
_VERSION_ALIASES: Final[set[str]] = {"-V", "--version", "version"}


@dataclass(frozen=True, slots=True)
class _CommandInfo:
    name: str
    summary: str


def _build_init_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(
        prog="witty init",
        description=_(
            "Initialize sysAgent\n * Initialization requires administrator privileges and network connection",
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )


def _build_logs_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="witty logs",
        description=_("View and manage application logs"),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "-n",
        "--lines",
        type=int,
        default=1000,
        metavar="N",
        help=_("Number of log lines to display (default: 1000)"),
    )
    return parser


def _build_llm_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(
        prog="witty llm",
        description=_(
            "Manage Witty Assistant LLM settings\n * Configuration editing requires administrator privileges",
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )


def _build_completion_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="witty completion",
        description=_(
            "Install shell completion script for Witty Assistant\n * Supported shells: bash, zsh, fish",
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "shell",
        choices=list(_SUPPORTED_SHELLS),
        nargs="?",
        metavar="SHELL",
        help=_(
            "Target shell (bash/zsh/fish). If omitted, Witty will try to detect your current shell.",
        ),
    )
    return parser


def _normalize_log_level(value: str) -> str:
    upper = value.strip().upper()
    if upper not in {"DEBUG", "INFO", "WARNING", "ERROR"}:
        raise argparse.ArgumentTypeError(_("Invalid log level: {level}").format(level=value))
    return upper


def _build_set_default_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="witty set-default",
        description=_("Configure default settings for Witty Assistant"),
        formatter_class=argparse.RawTextHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="set_default_command", metavar="<subcommand>")

    agent_parser = subparsers.add_parser(
        "agent",
        help=_("Select default agent"),
        description=_("Select default agent"),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    agent_parser.set_defaults(_handler="agent")

    log_level_parser = subparsers.add_parser(
        "log-level",
        help=_("Set log level"),
        description=_("Set log level"),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    log_level_parser.add_argument(
        "level",
        type=_normalize_log_level,
        metavar="LEVEL",
        help=_("Log level (DEBUG/INFO/WARNING/ERROR)"),
    )
    log_level_parser.set_defaults(_handler="log-level")

    locale_parser = subparsers.add_parser(
        "locale",
        help=_("Set display language"),
        description=_("Set display language"),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    locale_choices = list(get_supported_locales().keys())
    locale_names = ", ".join(f"{k} ({v})" for k, v in get_supported_locales().items())
    locale_parser.add_argument(
        "locale",
        choices=locale_choices,
        metavar="LOCALE",
        help=_("Available locales: {locales}").format(locales=locale_names),
    )
    locale_parser.set_defaults(_handler="locale")

    return parser


def _print_root_help() -> None:
    """打印根帮助信息（带命令分组）。"""
    out = sys.stdout

    out.write(_("Witty Assistant - Intelligent command-line tool") + "\n\n")

    out.write(_("Usage:\n"))
    out.write("  witty [<command>] [<args>]\n")
    out.write("  witty help [<command>]\n")
    out.write("  witty version\n\n")

    out.write(_("Global options:\n"))
    out.write("  -h, --help     " + _("Show help and exit") + "\n")
    out.write("  -V, --version  " + _("Show program version number and exit") + "\n\n")

    groups: list[tuple[str, list[_CommandInfo]]] = [
        (
            _("版本与帮助"),
            [
                _CommandInfo("help", "witty help / witty help <command>"),
                _CommandInfo("version", "witty version"),
                _CommandInfo("completion", _("Generate shell completion scripts")),
            ],
        ),
        (
            _("初始化与调试"),
            [
                _CommandInfo("init", _("Initialize sysAgent")),
                _CommandInfo("logs", _("View and manage application logs")),
            ],
        ),
        (
            _("管理命令"),
            [
                _CommandInfo("llm", _("Manage LLM settings")),
            ],
        ),
        (
            _("设置调整"),
            [
                _CommandInfo("set-default", _("Configure default settings")),
            ],
        ),
    ]

    out.write(_("Commands:\n"))
    for group_title, commands in groups:
        out.write(f"  {group_title}:\n")
        for c in commands:
            out.write(f"    {c.name:<12} {c.summary}\n")
        out.write("\n")

    out.write(_("Run 'witty help <command>' or 'witty <command> -h' for more details.\n"))
    out.write(_("For more information and documentation, please visit:\n"))
    out.write(f"  {DOCS_URL}\n")


def _print_set_default_help() -> None:
    out = sys.stdout
    out.write(_("Configure default settings for Witty Assistant") + "\n\n")
    out.write(_("Usage:\n"))
    out.write("  witty set-default <subcommand> [<args>]\n\n")
    out.write(_("Subcommands:\n"))
    out.write(f"  {'agent':<12} " + _("Select default agent") + "\n")
    out.write(f"  {'log-level':<12} " + _("Set log level") + "\n")
    out.write(f"  {'locale':<12} " + _("Set display language") + "\n\n")
    out.write(_("Examples:\n"))
    out.write("  witty set-default agent\n")
    out.write("  witty set-default log-level INFO\n")
    out.write("  witty set-default locale zh_CN\n")


def _help_set_default(rest: list[str]) -> None:
    if not rest:
        _print_set_default_help()
        return
    # 让 argparse 输出子命令帮助（等价于: witty set-default <subcmd> -h）
    parser = _build_set_default_parser()
    try:
        parser.parse_args([rest[0], "-h"])
    except SystemExit:
        return


def _dispatch_help(path: list[str]) -> bool:
    """
    分发帮助命令。

    witty help <command> [<subcommand>].
    """
    if not path:
        _print_root_help()
        return True

    cmd = path[0]
    rest = path[1:]

    parser_factories: dict[str, Callable[[], argparse.ArgumentParser]] = {
        "init": _build_init_parser,
        "logs": _build_logs_parser,
        "llm": _build_llm_parser,
        "completion": _build_completion_parser,
    }

    if cmd == "set-default":
        _help_set_default(rest)
        return True

    if cmd == "help":
        _print_root_help()
        return True

    if cmd == "version":
        sys.stdout.write(f"witty {__version__}\n")
        return True

    factory = parser_factories.get(cmd)
    if factory is None:
        sys.stderr.write(_("Unknown command: {cmd}\n").format(cmd=cmd))
        _print_root_help()
        raise SystemExit(2)

    factory().print_help()
    return True


def _cmd_help(rest: list[str], _config_manager: ConfigManager) -> None:
    if rest:
        _dispatch_help(rest)
        return
    _print_root_help()


def _cmd_version(_rest: list[str], _config_manager: ConfigManager) -> None:
    sys.stdout.write(f"witty {__version__}\n")


def _cmd_init(rest: list[str], _config_manager: ConfigManager) -> None:
    _build_init_parser().parse_args(rest)
    backend_init()


def _cmd_logs(rest: list[str], _config_manager: ConfigManager) -> None:
    args = _build_logs_parser().parse_args(rest)
    show_logs(max_lines=args.lines)


def _cmd_llm(rest: list[str], _config_manager: ConfigManager) -> None:
    _build_llm_parser().parse_args(rest)
    llm_config()


def _cmd_completion(rest: list[str], _config_manager: ConfigManager) -> None:
    args = _build_completion_parser().parse_args(rest)
    shell: str | None = args.shell
    if shell is None:
        shell = detect_default_shell()

    if shell is None:
        sys.stderr.write(
            _(
                "Unable to detect current shell. Please specify one of: bash, zsh, fish\n",
            ),
        )
        raise SystemExit(2)

    target_path = install_completion_script(shell)
    sys.stdout.write(
        _("✓ Completion installed to: {path}\n").format(path=target_path),
    )
    sys.stdout.write(get_install_hint(shell, target_path))


def _cmd_set_default(rest: list[str], config_manager: ConfigManager) -> None:
    if not rest or rest[0] in {"-h", "--help"}:
        _print_set_default_help()
        return

    parser = _build_set_default_parser()
    args = parser.parse_args(rest)
    sub = getattr(args, "_handler", "")
    if not sub:
        sys.stderr.write(_("未指定子命令。使用 'witty help set-default' 查看可用选项。\n"))
        raise SystemExit(1)

    def _set_default_agent() -> None:
        asyncio.run(select_agent())

    def _set_default_log_level() -> None:
        set_log_level(config_manager, args.level)

    def _set_default_locale() -> None:
        if set_locale(args.locale):
            config_manager.set_locale(args.locale)
            sys.stdout.write(_("✓ Language set to: {locale}\n").format(locale=args.locale))
            return
        sys.stderr.write(_("✗ Unsupported language: {locale}\n").format(locale=args.locale))
        raise SystemExit(1)

    sub_handlers = {
        "agent": _set_default_agent,
        "log-level": _set_default_log_level,
        "locale": _set_default_locale,
    }
    sub_handler = sub_handlers.get(sub)
    if sub_handler is None:
        sys.stderr.write(_("Unknown subcommand: {cmd}\n").format(cmd=sub))
        raise SystemExit(2)
    sub_handler()


def _dispatch_cli(argv: list[str], config_manager: ConfigManager) -> bool:
    """分发 CLI 子命令。"""
    if not argv:
        return False

    # 注册清理函数，确保在程序异常退出时也能清理空日志文件
    atexit.register(cleanup_empty_logs)

    cmd = argv[0]
    rest = argv[1:]

    # 将 alias 统一归一化为子命令，减少分支。
    if cmd in _HELP_ALIASES:
        cmd = "help"
    elif cmd in _VERSION_ALIASES:
        cmd = "version"

    handlers = {
        "help": _cmd_help,
        "version": _cmd_version,
        "init": _cmd_init,
        "logs": _cmd_logs,
        "llm": _cmd_llm,
        "set-default": _cmd_set_default,
        "completion": _cmd_completion,
    }

    handler = handlers.get(cmd)
    if handler is None:
        sys.stderr.write(_("Unknown command: {cmd}\n").format(cmd=cmd))
        _print_root_help()
        raise SystemExit(2)

    handler(rest, config_manager)
    return True


def show_logs(max_lines: int = 1000) -> None:
    """
    显示最新的日志内容。

    Args:
        max_lines: 最大显示行数，默认 1000 行

    """
    # 初始化配置和日志系统
    config_manager = ConfigManager()
    setup_logging(config_manager)
    # 显示日志时启用控制台输出
    enable_console_output()

    try:
        log_lines = get_latest_logs(max_lines=max_lines)
        for line in log_lines:
            # 直接输出到标准输出，保持原有的日志格式
            sys.stdout.write(line.rstrip() + "\n")
    except (OSError, RuntimeError) as e:
        sys.stderr.write(_("Failed to retrieve logs: {error}\n").format(error=e))
        sys.exit(1)


def set_log_level(config_manager: ConfigManager, level: str) -> None:
    """设置日志级别"""
    if level not in LogLevel.__members__:
        sys.stderr.write(_("Invalid log level: {level}\n").format(level=level))
        sys.exit(1)
    config_manager.set_log_level(LogLevel(level))

    # 初始化日志系统并验证设置
    setup_logging(config_manager)
    enable_console_output()  # 启用控制台输出以显示验证信息

    logger = get_logger(__name__)
    logger.info(_("Log level has been set to: %s"), level)
    logger.debug(_("This is a DEBUG level test message"))
    logger.info(_("This is an INFO level test message"))
    logger.warning(_("This is a WARNING level test message"))
    logger.error(_("This is an ERROR level test message"))

    sys.stdout.write(_("✓ Log level successfully set to: {level}\n").format(level=level))
    sys.stdout.write(_("✓ Logging system initialized\n"))


def main() -> None:
    """主函数"""
    # 首先初始化配置管理器
    config_manager = ConfigManager()

    # 初始化国际化系统
    # 如果配置中没有设置语言（空字符串），则自动检测系统语言
    configured_locale = config_manager.get_locale()
    if configured_locale:
        # 使用用户配置的语言
        init_i18n(configured_locale)
    else:
        # 自动检测系统语言
        init_i18n(None)
        # 保存检测到的语言到配置中
        detected_locale = get_locale()
        config_manager.set_locale(detected_locale)

    # 优先处理 CLI；未指定子命令时进入 TUI
    if _dispatch_cli(sys.argv[1:], config_manager):
        return

    # 没有指定子命令时，启动 TUI
    setup_logging(config_manager)
    # 在 TUI 模式下禁用控制台日志输出，避免干扰界面
    disable_console_output()

    logger = get_logger(__name__)

    try:
        # 延迟导入 IntelligentTerminal，确保在 i18n 初始化之后
        from app.tui import IntelligentTerminal  # noqa: PLC0415

        app = IntelligentTerminal()
        app.run()
    except Exception:
        logger.exception(_("Fatal error in Witty Assistant application"))
        raise


if __name__ == "__main__":
    sys.exit(main() or 0)
