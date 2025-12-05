"""
validators.py 模块测试

测试配置验证器的功能。
"""

from __future__ import annotations

import os
from unittest.mock import Mock, patch

import pytest

from tool.validators import (
    FALSY_VALUES,
    HTTP_FORBIDDEN,
    HTTP_NOT_FOUND,
    HTTP_OK,
    HTTP_UNAUTHORIZED,
    MAX_MODEL_DISPLAY,
    SSL_SKIP_ENV_VAR,
    SSL_VERIFY_ENV_VAR,
    TOKEN_HEX_LENGTH,
    TOKEN_LONG_TERM_LENGTH,
    TOKEN_LONG_TERM_PREFIX,
    TOKEN_PREVIEW_LENGTH,
    TRUTHY_VALUES,
    APIValidator,
    _parse_env_flag,
    _resolve_verify_ssl,
    is_browser_available,
    should_verify_ssl,
)


class TestParseEnvFlag:
    """测试 _parse_env_flag 函数"""

    def test_parse_none(self) -> None:
        """测试 None 值"""
        assert _parse_env_flag(None) is None

    @pytest.mark.parametrize("value", ["1", "true", "yes", "on", "TRUE", "True", "YES", "ON"])
    def test_parse_truthy_values(self, value: str) -> None:
        """测试真值"""
        assert _parse_env_flag(value) is True

    @pytest.mark.parametrize("value", ["0", "false", "no", "off", "FALSE", "False", "NO", "OFF"])
    def test_parse_falsy_values(self, value: str) -> None:
        """测试假值"""
        assert _parse_env_flag(value) is False

    @pytest.mark.parametrize("value", ["maybe", "unknown", "2", ""])
    def test_parse_invalid_values(self, value: str) -> None:
        """测试无效值"""
        assert _parse_env_flag(value) is None

    def test_parse_with_whitespace(self) -> None:
        """测试带空白的值"""
        assert _parse_env_flag("  true  ") is True
        assert _parse_env_flag("  false  ") is False


class TestResolveVerifySSL:
    """测试 _resolve_verify_ssl 函数"""

    def test_explicit_true(self) -> None:
        """测试显式传入 True"""
        assert _resolve_verify_ssl(verify_ssl=True) is True

    def test_explicit_false(self) -> None:
        """测试显式传入 False"""
        assert _resolve_verify_ssl(verify_ssl=False) is False

    def test_skip_env_true(self) -> None:
        """测试 SKIP 环境变量为 True"""
        with patch.dict(os.environ, {SSL_SKIP_ENV_VAR: "true"}):
            assert _resolve_verify_ssl() is False

    def test_skip_env_false(self) -> None:
        """测试 SKIP 环境变量为 False"""
        with patch.dict(os.environ, {SSL_SKIP_ENV_VAR: "false"}, clear=False):
            # 清除可能存在的 VERIFY 环境变量
            env = {SSL_SKIP_ENV_VAR: "false"}
            if SSL_VERIFY_ENV_VAR in os.environ:
                env[SSL_VERIFY_ENV_VAR] = ""
            with patch.dict(os.environ, env, clear=False):
                result = _resolve_verify_ssl()
                assert result is True

    def test_verify_env_true(self) -> None:
        """测试 VERIFY 环境变量为 True"""
        # 确保 SKIP 不干扰
        env = {SSL_VERIFY_ENV_VAR: "true"}
        with patch.dict(os.environ, env, clear=True):
            assert _resolve_verify_ssl() is True

    def test_verify_env_false(self) -> None:
        """测试 VERIFY 环境变量为 False"""
        env = {SSL_VERIFY_ENV_VAR: "false"}
        with patch.dict(os.environ, env, clear=True):
            assert _resolve_verify_ssl() is False

    def test_default_true(self) -> None:
        """测试默认值为 True"""
        with patch.dict(os.environ, {}, clear=True):
            assert _resolve_verify_ssl() is True

    def test_explicit_overrides_env(self) -> None:
        """测试显式参数覆盖环境变量"""
        with patch.dict(os.environ, {SSL_SKIP_ENV_VAR: "true"}):
            assert _resolve_verify_ssl(verify_ssl=True) is True


class TestShouldVerifySSL:
    """测试 should_verify_ssl 函数"""

    def test_delegates_to_resolve(self) -> None:
        """测试委托给 _resolve_verify_ssl"""
        assert should_verify_ssl(verify_ssl=True) is True
        assert should_verify_ssl(verify_ssl=False) is False


class TestIsBrowserAvailable:
    """测试 is_browser_available 函数"""

    def test_browser_available(self) -> None:
        """测试浏览器可用"""
        mock_browser = Mock()
        with patch("webbrowser.get", return_value=mock_browser):
            assert is_browser_available() is True

    def test_browser_returns_none(self) -> None:
        """测试浏览器返回 None"""
        with patch("webbrowser.get", return_value=None):
            assert is_browser_available() is False

    def test_browser_error(self) -> None:
        """测试浏览器错误"""
        import webbrowser  # noqa: PLC0415

        with patch("webbrowser.get", side_effect=webbrowser.Error("No browser")):
            assert is_browser_available() is False

    def test_browser_os_error(self) -> None:
        """测试 OSError"""
        with patch("webbrowser.get", side_effect=OSError("OS error")):
            assert is_browser_available() is False

    def test_browser_runtime_error(self) -> None:
        """测试 RuntimeError"""
        with patch("webbrowser.get", side_effect=RuntimeError("Runtime error")):
            assert is_browser_available() is False


class TestAPIValidator:
    """测试 APIValidator 类"""

    def test_init_default_ssl(self) -> None:
        """测试默认 SSL 设置"""
        with patch.dict(os.environ, {}, clear=True):
            validator = APIValidator()
            assert validator.verify_ssl is True

    def test_init_explicit_ssl_true(self) -> None:
        """测试显式 SSL True"""
        validator = APIValidator(verify_ssl=True)
        assert validator.verify_ssl is True

    def test_init_explicit_ssl_false(self) -> None:
        """测试显式 SSL False"""
        validator = APIValidator(verify_ssl=False)
        assert validator.verify_ssl is False

    def test_init_with_env_skip(self) -> None:
        """测试从环境变量读取 SSL 设置"""
        with patch.dict(os.environ, {SSL_SKIP_ENV_VAR: "true"}):
            validator = APIValidator()
            assert validator.verify_ssl is False


class TestConstants:
    """测试常量定义"""

    def test_http_status_codes(self) -> None:
        """测试 HTTP 状态码常量"""
        assert HTTP_OK == 200  # noqa: PLR2004
        assert HTTP_UNAUTHORIZED == 401  # noqa: PLR2004
        assert HTTP_FORBIDDEN == 403  # noqa: PLR2004
        assert HTTP_NOT_FOUND == 404  # noqa: PLR2004

    def test_max_model_display(self) -> None:
        """测试最大模型显示数"""
        assert MAX_MODEL_DISPLAY == 5  # noqa: PLR2004

    def test_truthy_values(self) -> None:
        """测试真值集合"""
        assert "1" in TRUTHY_VALUES
        assert "true" in TRUTHY_VALUES
        assert "yes" in TRUTHY_VALUES
        assert "on" in TRUTHY_VALUES

    def test_falsy_values(self) -> None:
        """测试假值集合"""
        assert "0" in FALSY_VALUES
        assert "false" in FALSY_VALUES
        assert "no" in FALSY_VALUES
        assert "off" in FALSY_VALUES

    def test_ssl_env_vars(self) -> None:
        """测试 SSL 环境变量名"""
        assert SSL_VERIFY_ENV_VAR == "OI_SSL_VERIFY"
        assert SSL_SKIP_ENV_VAR == "OI_SKIP_SSL_VERIFY"

    def test_token_constants(self) -> None:
        """测试令牌常量"""
        assert TOKEN_HEX_LENGTH == 32  # noqa: PLR2004
        assert TOKEN_LONG_TERM_PREFIX == "sk-"  # noqa: S105
        assert TOKEN_LONG_TERM_LENGTH == 35  # noqa: PLR2004
        assert TOKEN_PREVIEW_LENGTH == 5  # noqa: PLR2004
