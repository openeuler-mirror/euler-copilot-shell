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
        prog="witty",
        description=_("Witty Assistant - Intelligent command-line tool"),
        epilog=_("""
For more information and documentation, please visit:
  https://gitee.com/openeuler/euler-copilot-shell/tree/master/docs
        """),
        formatter_class=argparse.RawTextHelpFormatter,
        add_help=False,
    )

    # 通用选项组
    general_group = parser.add_argument_group(
        _("General Options"),
        _("Show help and version information"),
    )
    general_group.add_argument(
        "-h",
        "--help",
        action="help",
        help=_("Show this help message and exit"),
    )
    general_group.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
        help=_("Show program version number and exit"),
    )

    # 后端配置选项组
    backend_group = parser.add_argument_group(
        _("Backend Configuration Options"),
        _("For initializing and configuring Witty Assistant backend services"),
    )
    backend_group.add_argument(
        "--init",
        action="store_true",
        help=_(
            "Initialize Witty Assistant backend\n"
            " * Initialization requires administrator privileges and network connection",
        ),
    )
    backend_group.add_argument(
        "--llm-config",
        action="store_true",
        help=_(
            "Change Witty Assistant LLM settings (requires valid local backend service)\n"
            " * Configuration editing requires administrator privileges",
        ),
    )

    # 应用配置选项组
    app_group = parser.add_argument_group(
        _("Application Configuration Options"),
        _("For configuring application frontend behavior and preferences"),
    )
    app_group.add_argument(
        "--agent",
        action="store_true",
        help=_("Select default agent"),
    )

    # 认证管理选项组
    auth_group = parser.add_argument_group(
        _("Authentication Management Options"),
        _("For managing login and authentication"),
    )
    auth_group.add_argument(
        "--login",
        action="store_true",
        help=_("Login via browser to obtain API key"),
    )

    # 语言设置选项组
    i18n_group = parser.add_argument_group(
        _("Language Settings"),
        _("For configuring application display language"),
    )
    locale_choices = list(get_supported_locales().keys())
    locale_names = ", ".join(f"{k} ({v})" for k, v in get_supported_locales().items())
    i18n_group.add_argument(
        "--locale",
        choices=locale_choices,
        metavar="LOCALE",
        help=_("Set display language (available: {locales})").format(locales=locale_names),
    )

    # 日志管理选项组
    log_group = parser.add_argument_group(
        _("Log Management Options"),
        _("For viewing and configuring log output"),
    )
    log_group.add_argument(
        "--logs",
        action="store_true",
        help=_("Show latest log content (up to 1000 lines)"),
    )
    log_group.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        metavar="LEVEL",
        help=_("Set log level (available: DEBUG, INFO, WARNING, ERROR)"),
    )

    # 注册清理函数，确保在程序异常退出时也能清理空日志文件
    atexit.register(cleanup_empty_logs)

    return parser.parse_args()


def show_logs() -> None:
    """显示最新的日志内容"""
    # 初始化配置和日志系统
    config_manager = ConfigManager()
    setup_logging(config_manager)
    # 显示日志时启用控制台输出
    enable_console_output()

    try:
        log_lines = get_latest_logs(max_lines=1000)
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


def main() -> None:  # noqa: C901, PLR0911
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

    # 处理语言设置参数
    if args.locale:
        if set_locale(args.locale):
            config_manager.set_locale(args.locale)
            sys.stdout.write(_("✓ Language set to: {locale}\n").format(locale=args.locale))
        else:
            sys.stderr.write(_("✗ Unsupported language: {locale}\n").format(locale=args.locale))
            sys.exit(1)
        return

    if args.logs:
        show_logs()
        return

    if args.init:
        backend_init()
        return

    if args.agent:
        asyncio.run(select_agent())
        return

    if args.llm_config:
        llm_config()
        return

    # 处理命令行参数设置的日志级别
    if args.log_level:
        set_log_level(config_manager, args.log_level)
        return

    # 处理认证相关参数
    if args.login:
        browser_login()
        return

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
