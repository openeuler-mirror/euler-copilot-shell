"""国际化管理模块"""

from __future__ import annotations

import gettext
import locale
from pathlib import Path
from typing import ClassVar

# 支持的语言列表
SUPPORTED_LOCALES = {
    "en_US": "English",
    "zh_CN": "简体中文",
}

# 备用语言（当系统语言无法检测时使用）
FALLBACK_LOCALE = "en_US"


def _detect_default_locale() -> str:
    """
    检测默认语言环境（在模块加载时调用）

    Returns:
        检测到的语言代码，如果不支持则返回备用语言（英语）

    """
    try:
        # 获取系统语言设置
        system_locale, _ = locale.getdefaultlocale()
        if system_locale:
            # 标准化语言代码 (如 zh_CN.UTF-8 -> zh_CN)
            locale_code = system_locale.split(".")[0]
            if locale_code.startswith("zh"):
                locale_code = "zh_CN"
            if locale_code.startswith("en"):
                locale_code = "en_US"
            if locale_code in SUPPORTED_LOCALES:
                return locale_code
    except (ValueError, TypeError, locale.Error):
        # 捕获可能的 locale 相关异常
        pass

    # 无法检测或不支持时，返回备用语言
    return FALLBACK_LOCALE


# 默认语言 - 根据系统语言自动检测
DEFAULT_LOCALE = _detect_default_locale()


class I18nManager:
    """国际化管理器"""

    _instance: ClassVar["I18nManager | None"] = None
    _current_locale: str = DEFAULT_LOCALE
    _translations: ClassVar[dict[str, gettext.GNUTranslations | gettext.NullTranslations]] = {}

    def __new__(cls) -> "I18nManager":
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """初始化国际化管理器"""
        if not hasattr(self, "_initialized"):
            self._locale_dir = Path(__file__).parent / "locales"
            self._domain = "messages"
            self._load_all_translations()
            self._initialized = True

    def _load_all_translations(self) -> None:
        """预加载所有支持的翻译"""
        for locale_code in SUPPORTED_LOCALES:
            try:
                translation = gettext.translation(
                    self._domain,
                    localedir=str(self._locale_dir),
                    languages=[locale_code],
                    fallback=False,
                )
                self._translations[locale_code] = translation
            except FileNotFoundError:
                # 如果翻译文件不存在，使用空翻译(返回原始文本)
                self._translations[locale_code] = gettext.NullTranslations()

    def set_locale(self, locale_code: str) -> bool:
        """
        设置当前语言环境

        Args:
            locale_code: 语言代码，如 'zh_CN', 'en_US'

        Returns:
            是否设置成功

        """
        if locale_code not in SUPPORTED_LOCALES:
            return False

        self._current_locale = locale_code

        # 安装全局翻译函数
        if locale_code in self._translations:
            self._translations[locale_code].install()

        return True

    def get_locale(self) -> str:
        """获取当前语言环境"""
        return self._current_locale

    def get_supported_locales(self) -> dict[str, str]:
        """获取支持的语言列表"""
        return SUPPORTED_LOCALES.copy()

    def detect_system_locale(self) -> str:
        """
        检测系统语言环境

        Returns:
            检测到的语言代码，如果不支持则返回默认语言

        """
        return _detect_default_locale()

    def translate(self, message: str, **kwargs: str | float) -> str:
        """
        翻译消息

        Args:
            message: 要翻译的消息
            **kwargs: 格式化参数

        Returns:
            翻译后的消息

        """
        translation = self._translations.get(
            self._current_locale,
            gettext.NullTranslations(),
        )
        translated = translation.gettext(message)

        # 支持格式化参数
        if kwargs:
            translated = translated.format(**kwargs)

        return translated

    def translate_plural(
        self,
        singular: str,
        plural: str,
        n: int,
        **kwargs: str | float,
    ) -> str:
        """
        翻译复数形式

        Args:
            singular: 单数形式
            plural: 复数形式
            n: 数量
            **kwargs: 格式化参数

        Returns:
            翻译后的消息

        """
        translation = self._translations.get(
            self._current_locale,
            gettext.NullTranslations(),
        )
        translated = translation.ngettext(singular, plural, n)

        if kwargs:
            translated = translated.format(n=n, **kwargs)

        return translated


# 全局实例
_i18n_manager = I18nManager()


def init_i18n(locale_code: str | None = None) -> None:
    """
    初始化国际化系统

    Args:
        locale_code: 语言代码，如果为 None 则自动检测系统语言

    """
    if locale_code is None:
        locale_code = _i18n_manager.detect_system_locale()

    _i18n_manager.set_locale(locale_code)


def set_locale(locale_code: str) -> bool:
    """设置当前语言环境"""
    return _i18n_manager.set_locale(locale_code)


def get_locale() -> str:
    """获取当前语言环境"""
    return _i18n_manager.get_locale()


def get_supported_locales() -> dict[str, str]:
    """获取支持的语言列表"""
    return _i18n_manager.get_supported_locales()


# 便捷的翻译函数
def _(message: str, **kwargs: str | float) -> str:
    """翻译消息的快捷函数"""
    return _i18n_manager.translate(message, **kwargs)


def _n(singular: str, plural: str, n: int, **kwargs: str | float) -> str:
    """翻译复数形式的快捷函数"""
    return _i18n_manager.translate_plural(singular, plural, n, **kwargs)
