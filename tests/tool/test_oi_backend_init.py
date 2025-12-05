"""
oi_backend_init.py 模块测试

测试后端初始化工具的函数。
"""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from tool.oi_backend_init import backend_init


class TestBackendInit:
    """测试 backend_init 函数"""

    @patch("tool.oi_backend_init.ConfigManager")
    @patch("tool.oi_backend_init.get_logger")
    def test_backend_init_config_updated(
        self,
        mock_get_logger: Mock,
        mock_config_manager_class: Mock,
    ) -> None:
        """测试配置文件更新的情况"""
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger

        mock_config_manager = Mock()
        mock_config_manager.validate_and_update_config.return_value = True
        mock_config_manager_class.return_value = mock_config_manager

        # Mock App 类，避免实际运行 TUI
        with patch("tool.oi_backend_init.App") as mock_app_class:
            mock_app = Mock()
            mock_app.run.return_value = None
            mock_app_class.return_value = mock_app

            with patch("tool.oi_backend_init.InitializationModeScreen"):
                backend_init()

        mock_config_manager.validate_and_update_config.assert_called_once()
        # 验证日志记录
        assert any("配置文件已更新" in str(call) for call in mock_logger.info.call_args_list)

    @patch("tool.oi_backend_init.ConfigManager")
    @patch("tool.oi_backend_init.get_logger")
    def test_backend_init_config_not_updated(
        self,
        mock_get_logger: Mock,
        mock_config_manager_class: Mock,
    ) -> None:
        """测试配置文件未更新的情况"""
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger

        mock_config_manager = Mock()
        mock_config_manager.validate_and_update_config.return_value = False
        mock_config_manager_class.return_value = mock_config_manager

        with patch("tool.oi_backend_init.App") as mock_app_class:
            mock_app = Mock()
            mock_app.run.return_value = None
            mock_app_class.return_value = mock_app

            with patch("tool.oi_backend_init.InitializationModeScreen"):
                backend_init()

        mock_config_manager.validate_and_update_config.assert_called_once()
        # 验证日志记录
        assert any("配置文件检查完成" in str(call) for call in mock_logger.info.call_args_list)

    @patch("tool.oi_backend_init.ConfigManager")
    @patch("tool.oi_backend_init.get_logger")
    def test_backend_init_keyboard_interrupt(
        self,
        mock_get_logger: Mock,
        mock_config_manager_class: Mock,
    ) -> None:
        """测试用户中断（Ctrl+C）的情况"""
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger

        mock_config_manager = Mock()
        mock_config_manager.validate_and_update_config.side_effect = KeyboardInterrupt()
        mock_config_manager_class.return_value = mock_config_manager

        # 应该不会抛出异常
        backend_init()

        mock_logger.warning.assert_called()

    @patch("tool.oi_backend_init.ConfigManager")
    @patch("tool.oi_backend_init.get_logger")
    def test_backend_init_import_error(
        self,
        mock_get_logger: Mock,
        mock_config_manager_class: Mock,
    ) -> None:
        """测试导入模块失败的情况"""
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger

        mock_config_manager = Mock()
        mock_config_manager.validate_and_update_config.side_effect = ImportError("Module not found")
        mock_config_manager_class.return_value = mock_config_manager

        # 应该不会抛出异常
        backend_init()

        mock_logger.exception.assert_called()

    @patch("tool.oi_backend_init.ConfigManager")
    @patch("tool.oi_backend_init.get_logger")
    def test_backend_init_runtime_error(
        self,
        mock_get_logger: Mock,
        mock_config_manager_class: Mock,
    ) -> None:
        """测试运行时错误的情况"""
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger

        mock_config_manager = Mock()
        mock_config_manager.validate_and_update_config.side_effect = RuntimeError("Runtime error")
        mock_config_manager_class.return_value = mock_config_manager

        # 应该不会抛出异常
        backend_init()

        mock_logger.exception.assert_called()

    @patch("tool.oi_backend_init.ConfigManager")
    @patch("tool.oi_backend_init.get_logger")
    def test_backend_init_unexpected_error(
        self,
        mock_get_logger: Mock,
        mock_config_manager_class: Mock,
    ) -> None:
        """测试未预期错误的情况"""
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger

        mock_config_manager = Mock()
        mock_config_manager.validate_and_update_config.side_effect = ValueError("Unexpected")
        mock_config_manager_class.return_value = mock_config_manager

        # 未预期的错误应该被重新抛出
        with pytest.raises(ValueError, match="Unexpected"):
            backend_init()

        mock_logger.exception.assert_called()
