"""
i18n/manager.py 模块测试

测试国际化管理器的功能。
"""

from __future__ import annotations

import locale
from unittest.mock import patch

import pytest

from i18n.manager import (
    DEFAULT_LOCALE,
    FALLBACK_LOCALE,
    SUPPORTED_LOCALES,
    I18nManager,
    _,
    _detect_default_locale,
    _n,
    get_locale,
    get_supported_locales,
    init_i18n,
    set_locale,
)


class TestDetectDefaultLocale:
    """测试 _detect_default_locale 函数"""

    def test_detect_chinese(self) -> None:
        """测试检测中文环境"""
        with patch("locale.getdefaultlocale", return_value=("zh_CN.UTF-8", "UTF-8")):
            result = _detect_default_locale()
            assert result == "zh_CN"

    def test_detect_chinese_variant(self) -> None:
        """测试检测中文变体"""
        with patch("locale.getdefaultlocale", return_value=("zh_TW", "UTF-8")):
            result = _detect_default_locale()
            assert result == "zh_CN"

    def test_detect_english(self) -> None:
        """测试检测英文环境"""
        with patch("locale.getdefaultlocale", return_value=("en_US.UTF-8", "UTF-8")):
            result = _detect_default_locale()
            assert result == "en_US"

    def test_detect_english_variant(self) -> None:
        """测试检测英文变体"""
        with patch("locale.getdefaultlocale", return_value=("en_GB", "UTF-8")):
            result = _detect_default_locale()
            assert result == "en_US"

    def test_detect_unsupported_locale(self) -> None:
        """测试不支持的语言环境"""
        with patch("locale.getdefaultlocale", return_value=("fr_FR", "UTF-8")):
            result = _detect_default_locale()
            assert result == FALLBACK_LOCALE

    def test_detect_none_locale(self) -> None:
        """测试 None 语言环境"""
        with patch("locale.getdefaultlocale", return_value=(None, None)):
            result = _detect_default_locale()
            assert result == FALLBACK_LOCALE

    def test_detect_locale_error(self) -> None:
        """测试 locale 异常"""
        with patch("locale.getdefaultlocale", side_effect=locale.Error("Test error")):
            result = _detect_default_locale()
            assert result == FALLBACK_LOCALE

    def test_detect_value_error(self) -> None:
        """测试 ValueError 异常"""
        with patch("locale.getdefaultlocale", side_effect=ValueError("Test error")):
            result = _detect_default_locale()
            assert result == FALLBACK_LOCALE


class TestI18nManager:
    """测试 I18nManager 类"""

    def test_singleton(self) -> None:
        """测试单例模式"""
        manager1 = I18nManager()
        manager2 = I18nManager()
        assert manager1 is manager2

    def test_get_supported_locales(self) -> None:
        """测试获取支持的语言列表"""
        manager = I18nManager()
        locales = manager.get_supported_locales()
        assert "en_US" in locales
        assert "zh_CN" in locales
        assert locales["en_US"] == "English"
        assert locales["zh_CN"] == "简体中文"

    def test_set_locale_valid(self) -> None:
        """测试设置有效的语言环境"""
        manager = I18nManager()
        result = manager.set_locale("zh_CN")
        assert result is True
        assert manager.get_locale() == "zh_CN"

    def test_set_locale_invalid(self) -> None:
        """测试设置无效的语言环境"""
        manager = I18nManager()
        original_locale = manager.get_locale()
        result = manager.set_locale("invalid_locale")
        assert result is False
        assert manager.get_locale() == original_locale

    def test_detect_system_locale(self) -> None:
        """测试检测系统语言"""
        manager = I18nManager()
        locale_code = manager.detect_system_locale()
        assert locale_code in SUPPORTED_LOCALES

    def test_translate_simple(self) -> None:
        """测试简单翻译"""
        manager = I18nManager()
        # 设置为英文，未翻译的消息应该返回原文
        manager.set_locale("en_US")
        result = manager.translate("Test message")
        assert isinstance(result, str)

    def test_translate_with_kwargs(self) -> None:
        """测试带参数的翻译"""
        manager = I18nManager()
        manager.set_locale("en_US")
        result = manager.translate("Hello {name}", name="World")
        assert "World" in result

    def test_translate_plural(self) -> None:
        """测试复数翻译"""
        manager = I18nManager()
        manager.set_locale("en_US")
        result_singular = manager.translate_plural("item", "items", 1)
        result_plural = manager.translate_plural("item", "items", 5)
        assert isinstance(result_singular, str)
        assert isinstance(result_plural, str)


class TestI18nFunctions:
    """测试 i18n 模块级函数"""

    def test_init_i18n_auto(self) -> None:
        """测试自动初始化"""
        init_i18n()
        # 不应该抛出异常

    def test_init_i18n_with_locale(self) -> None:
        """测试指定语言初始化"""
        init_i18n("en_US")
        assert get_locale() == "en_US"

    def test_set_locale_function(self) -> None:
        """测试 set_locale 函数"""
        result = set_locale("zh_CN")
        assert result is True
        assert get_locale() == "zh_CN"

    def test_get_locale_function(self) -> None:
        """测试 get_locale 函数"""
        set_locale("en_US")
        assert get_locale() == "en_US"

    def test_get_supported_locales_function(self) -> None:
        """测试 get_supported_locales 函数"""
        locales = get_supported_locales()
        assert isinstance(locales, dict)
        assert "en_US" in locales
        assert "zh_CN" in locales

    def test_translate_shortcut(self) -> None:
        """测试 _ 翻译快捷函数"""
        set_locale("en_US")
        result = _("Test message")
        assert isinstance(result, str)

    def test_translate_shortcut_with_format(self) -> None:
        """测试 _ 翻译快捷函数带格式化"""
        set_locale("en_US")
        result = _("Value: {value}", value=42)
        assert "42" in result

    def test_translate_plural_shortcut(self) -> None:
        """测试 _n 复数翻译快捷函数"""
        set_locale("en_US")
        # _n 函数会自动将 n 作为格式化参数
        result = _n("item", "items", 1)
        assert isinstance(result, str)
        result = _n("item", "items", 5)
        assert isinstance(result, str)


class TestConstants:
    """测试常量"""

    def test_supported_locales(self) -> None:
        """测试支持的语言常量"""
        assert isinstance(SUPPORTED_LOCALES, dict)
        assert len(SUPPORTED_LOCALES) >= 2  # noqa: PLR2004

    def test_fallback_locale(self) -> None:
        """测试备用语言常量"""
        assert FALLBACK_LOCALE == "en_US"

    def test_default_locale(self) -> None:
        """测试默认语言常量"""
        assert DEFAULT_LOCALE in SUPPORTED_LOCALES
