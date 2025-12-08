"""应用入口点"""

import argparse
import asyncio
import atexit
import sys

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
from tool import backend_init, browser_login, llm_config, select_agent


def parse_args() -> argparse.Namespace:
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        prog="oi",
        description=_("openEuler Intelligence - Intelligent command-line tool"),
        epilog=_("""
For more information and documentation, please visit:
  https://gitee.com/openeuler/euler-copilot-shell/tree/master/docs
        """),
        formatter_class=argparse.RawTextHelpFormatter,
    )

    # 主命令的版本参数
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
        help=_("Show program version number and exit"),
    )

    # 创建子命令解析器
    subparsers = parser.add_subparsers(
        dest="command",
        title=_("Available Commands"),
        description=_("Use 'oi <command> --help' for more information on a specific command"),
        metavar="<command>",
    )

    # init 子命令
    subparsers.add_parser(
        "init",
        help=_("Initialize openEuler Intelligence backend"),
        description=_(
            "Initialize openEuler Intelligence backend\n"
            " * Initialization requires administrator privileges and network connection",
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )

    # logs 子命令
    logs_parser = subparsers.add_parser(
        "logs",
        help=_("View and manage application logs"),
        description=_("View and manage application logs"),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    logs_parser.add_argument(
        "-n",
        "--lines",
        type=int,
        default=1000,
        metavar="N",
        help=_("Number of log lines to display (default: 1000)"),
    )

    # login 子命令
    subparsers.add_parser(
        "login",
        help=_("Login via browser to obtain API key"),
        description=_("Login via browser to obtain API key"),
        formatter_class=argparse.RawTextHelpFormatter,
    )

    # set-default 子命令
    set_default_parser = subparsers.add_parser(
        "set-default",
        help=_("Configure default settings"),
        description=_("Configure default settings for openEuler Intelligence"),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    set_default_parser.add_argument(
        "--llm-config",
        action="store_true",
        help=_(
            "Change openEuler Intelligence LLM settings (requires valid local backend service)\n"
            " * Configuration editing requires administrator privileges",
        ),
    )
    set_default_parser.add_argument(
        "--agent",
        action="store_true",
        help=_("Select default agent"),
    )
    locale_choices = list(get_supported_locales().keys())
    locale_names = ", ".join(f"{k} ({v})" for k, v in get_supported_locales().items())
    set_default_parser.add_argument(
        "--locale",
        choices=locale_choices,
        metavar="LOCALE",
        help=_("Set display language (available: {locales})").format(locales=locale_names),
    )
    set_default_parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        metavar="LEVEL",
        help=_("Set log level (available: DEBUG, INFO, WARNING, ERROR)"),
    )

    # 注册清理函数，确保在程序异常退出时也能清理空日志文件
    atexit.register(cleanup_empty_logs)

    return parser.parse_args()


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


def handle_set_default(args: argparse.Namespace, config_manager: ConfigManager) -> bool:
    """
    处理 set-default 子命令。

    Args:
        args: 解析后的命令行参数
        config_manager: 配置管理器实例

    Returns:
        bool: 是否执行了任何操作

    """
    handled = False

    # 处理语言设置参数
    if args.locale:
        if set_locale(args.locale):
            config_manager.set_locale(args.locale)
            sys.stdout.write(_("✓ Language set to: {locale}\n").format(locale=args.locale))
        else:
            sys.stderr.write(_("✗ Unsupported language: {locale}\n").format(locale=args.locale))
            sys.exit(1)
        handled = True

    # 处理日志级别设置
    if args.log_level:
        set_log_level(config_manager, args.log_level)
        handled = True

    # 处理 LLM 配置
    if args.llm_config:
        llm_config()
        handled = True

    # 处理 agent 选择
    if args.agent:
        asyncio.run(select_agent())
        handled = True

    # 如果没有指定任何参数，显示帮助信息
    if not handled:
        sys.stderr.write(
            _("No option specified. Use 'oi set-default --help' for available options.\n"),
        )
        sys.exit(1)

    return handled


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

    # 解析命令行参数（需要在初始化 i18n 后进行，以支持翻译）
    args = parse_args()

    # 根据子命令分发处理
    if args.command == "init":
        backend_init()
        return

    if args.command == "logs":
        show_logs(max_lines=args.lines)
        return

    if args.command == "login":
        browser_login()
        return

    if args.command == "set-default":
        handle_set_default(args, config_manager)
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
        logger.exception(_("Fatal error in Intelligent Shell application"))
        raise


if __name__ == "__main__":
    sys.exit(main() or 0)
