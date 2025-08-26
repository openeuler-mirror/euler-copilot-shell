"""日志管理器"""

from __future__ import annotations

import contextlib
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from config.manager import ConfigManager


class LogManager:
    """日志管理器"""

    def __init__(self, config_manager: ConfigManager | None = None) -> None:
        """初始化日志管理器"""
        self._log_dir = Path.home() / ".cache" / "openEuler Intelligence" / "logs"
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._current_log_file: Path | None = None
        self._config_manager = config_manager
        self._setup_logging()
        self._cleanup_old_logs()

    def enable_console_output(self) -> None:
        """启用控制台日志输出（用于非 TUI 模式）"""
        root_logger = logging.getLogger()

        # 检查是否已经有控制台处理器
        for handler in root_logger.handlers:
            if isinstance(handler, logging.StreamHandler) and handler.stream.name == "<stderr>":
                return  # 已经存在控制台处理器

        # 添加控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            ),
        )
        root_logger.addHandler(console_handler)

    def disable_console_output(self) -> None:
        """禁用控制台日志输出（用于 TUI 模式）"""
        root_logger = logging.getLogger()

        # 移除所有控制台处理器
        handlers_to_remove = [
            handler
            for handler in root_logger.handlers
            if isinstance(handler, logging.StreamHandler) and handler.stream.name == "<stderr>"
        ]

        for handler in handlers_to_remove:
            root_logger.removeHandler(handler)
            handler.close()

    def get_logger(self, name: str) -> logging.Logger:
        """获取指定名称的日志记录器"""
        return logging.getLogger(name)

    def get_latest_logs(self, max_lines: int = 1000) -> list[str]:
        """
        获取最新的日志内容

        Args:
            max_lines: 最大行数，默认1000行

        Returns:
            日志行列表

        """
        # 查找所有日志文件
        log_files = list(self._log_dir.glob("smart-shell-*.log"))
        if not log_files:
            return ["未找到日志文件"]

        # 过滤掉空文件，按修改时间排序
        non_empty_files = [f for f in log_files if f.stat().st_size > 0]

        if not non_empty_files:
            return ["未找到有效的日志文件"]

        # 获取最新的非空文件
        latest_log_file = max(non_empty_files, key=lambda f: f.stat().st_mtime)

        try:
            with latest_log_file.open(encoding="utf-8") as f:
                lines = f.readlines()
                # 返回最后max_lines行
                return lines[-max_lines:] if len(lines) > max_lines else lines
        except (OSError, UnicodeDecodeError) as e:
            return [f"读取日志文件失败: {e}"]

    def reconfigure_logging(self, config_manager: ConfigManager | None = None) -> None:
        """重新配置日志系统（用于运行时更新配置）"""
        # 更新配置管理器
        if config_manager is not None:
            self._config_manager = config_manager

        # 获取新的日志级别并更新
        log_level = self._get_log_level()
        root_logger = logging.getLogger()
        root_logger.setLevel(log_level)

        # 同时更新所有现有处理器的级别
        for handler in root_logger.handlers:
            handler.setLevel(log_level)

    def cleanup_empty_logs(self) -> None:
        """清理空的日志文件（应用退出时调用）"""
        with contextlib.suppress(OSError):
            for log_file in self._log_dir.glob("smart-shell-*.log"):
                # 检查文件大小，删除空文件
                if log_file.stat().st_size == 0:
                    # 如果是当前日志文件且应用刚启动就退出，仍然删除空文件
                    with contextlib.suppress(OSError):
                        log_file.unlink()

    def _get_log_level(self) -> int:
        """获取当前配置的日志级别"""
        log_level = logging.DEBUG  # 默认级别
        if self._config_manager is not None:
            try:
                config_log_level = self._config_manager.get_log_level()
                log_level = getattr(logging, config_log_level.value)
            except (AttributeError, ValueError, TypeError) as e:
                # 如果配置管理器不可用或配置有误，使用默认级别
                # 在这里我们还不能使用 logger，因为 logging 还没完全设置好
                sys.stderr.write(f"警告: 获取日志级别配置失败: {e}, 使用默认级别 DEBUG\n")
                log_level = logging.DEBUG
        return log_level

    def _setup_logging(self) -> None:
        """配置日志系统"""
        # 生成当前时间的日志文件名
        current_time = datetime.now(tz=timezone.utc).astimezone()
        log_filename = f"smart-shell-{current_time.strftime('%Y%m%d-%H%M%S')}.log"
        self._current_log_file = self._log_dir / log_filename

        # 获取日志级别并配置根日志记录器
        log_level = self._get_log_level()
        handlers = [logging.FileHandler(self._current_log_file, encoding="utf-8")]

        logging.basicConfig(
            level=log_level,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=handlers,
        )

    def _parse_log_file_date(self, log_file: Path) -> datetime | None:
        """解析日志文件名中的日期"""
        try:
            file_date_str = log_file.stem.split("-", 2)[2][:8]  # 提取 YYYYMMDD
            return datetime.strptime(file_date_str, "%Y%m%d").replace(tzinfo=timezone.utc).astimezone()
        except (ValueError, IndexError):
            return None

    def _cleanup_old_logs(self) -> None:
        """清理7天前的旧日志文件"""
        logger = logging.getLogger(__name__)
        try:
            cutoff_date = datetime.now(tz=timezone.utc).astimezone() - timedelta(days=7)

            for log_file in self._log_dir.glob("smart-shell-*.log"):
                try:
                    # 跳过当前正在使用的日志文件
                    if self._current_log_file and log_file.samefile(self._current_log_file):
                        continue

                    # 解析文件日期
                    file_date = self._parse_log_file_date(log_file)
                    if file_date is None:
                        logger.warning("无法解析日志文件名: %s", log_file.name)
                        continue

                    # 删除7天前的旧日志文件
                    if file_date < cutoff_date:
                        log_file.unlink()
                        logger.info("已删除旧日志文件: %s", log_file.name)

                except OSError as e:
                    # 如果无法删除文件，记录错误但继续
                    logger.warning("无法删除日志文件 %s: %s", log_file.name, e)
                    continue
        except OSError:
            logger.exception("清理旧日志文件时出错")


class _LogManagerSingleton:
    """日志管理器单例"""

    def __init__(self) -> None:
        self._instance: LogManager | None = None
        self._last_config_log_level: str | None = None

    def get_instance(self, config_manager: ConfigManager | None = None) -> LogManager:
        """获取日志管理器实例"""
        if self._instance is None:
            # 首次创建实例
            self._instance = LogManager(config_manager)
            if config_manager is not None:
                self._last_config_log_level = config_manager.get_log_level().value
        elif config_manager is not None:
            # 实例已存在，检查配置是否改变
            current_log_level = config_manager.get_log_level().value
            if self._last_config_log_level != current_log_level:
                # 配置改变，重新配置日志系统
                self._instance.reconfigure_logging(config_manager)
                self._last_config_log_level = current_log_level

        return self._instance


# 全局单例实例
_singleton = _LogManagerSingleton()


def setup_logging(config_manager: ConfigManager | None = None) -> None:
    """初始化日志系统"""
    _singleton.get_instance(config_manager)


def get_logger(name: str) -> logging.Logger:
    """获取日志记录器"""
    return _singleton.get_instance().get_logger(name)


def get_latest_logs(max_lines: int = 1000) -> list[str]:
    """
    获取最新的日志内容

    Args:
        max_lines: 最大行数，默认1000行

    Returns:
        日志行列表

    """
    return _singleton.get_instance().get_latest_logs(max_lines)


def cleanup_empty_logs() -> None:
    """清理空的日志文件"""
    _singleton.get_instance().cleanup_empty_logs()


def enable_console_output() -> None:
    """启用控制台日志输出（用于非 TUI 模式）"""
    _singleton.get_instance().enable_console_output()


def disable_console_output() -> None:
    """禁用控制台日志输出（用于 TUI 模式）"""
    _singleton.get_instance().disable_console_output()


def log_api_request(
    logger: logging.Logger,
    method: str,
    url: str,
    status_code: int,
    duration: float | None = None,
    **kwargs: Any,
) -> None:
    """记录API请求日志"""
    extra_info = " ".join(f"{k}={v}" for k, v in kwargs.items()) if kwargs else ""
    duration_str = f" ({duration:.3f}s)" if duration is not None else ""

    logger.info(
        "API请求 - %s %s - HTTP %d%s %s",
        method,
        url,
        status_code,
        duration_str,
        extra_info,
    )


def log_exception(logger: logging.Logger, message: str, exc: Exception) -> None:
    """记录异常日志"""
    logger.exception("%s: %s", message, exc)
