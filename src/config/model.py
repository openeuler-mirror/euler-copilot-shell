"""配置模型"""

from dataclasses import dataclass, field
from enum import Enum


class Backend(str, Enum):
    """后端类型"""

    OPENAI = "openai"
    EULERINTELLI = "eulerintelli"

    def get_display_name(self) -> str:
        """获取后端的可读显示名称"""
        display_names = {
            Backend.OPENAI: "OpenAI 大模型接口",
            Backend.EULERINTELLI: "Witty Assistant",
        }
        return display_names.get(self, self.value)


class LogLevel(str, Enum):
    """日志级别"""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


@dataclass
class OpenAIConfig:
    """OpenAI 后端配置"""

    base_url: str = field(default="")
    model: str = field(default="")
    api_key: str = field(default="")

    @classmethod
    def from_dict(cls, d: dict) -> "OpenAIConfig":
        """从字典初始化配置"""
        return cls(
            base_url=d.get("base_url", cls.base_url),
            model=d.get("model", cls.model),
            api_key=d.get("api_key", cls.api_key),
        )

    def to_dict(self) -> dict:
        """转换为字典"""
        return {"base_url": self.base_url, "model": self.model, "api_key": self.api_key}


@dataclass
class HermesConfig:
    """Hermes 后端配置"""

    base_url: str = field(default="http://127.0.0.1:8002")
    api_key: str = field(default="")
    default_app: str = field(default="")

    @classmethod
    def from_dict(cls, d: dict) -> "HermesConfig":
        """从字典初始化配置"""
        return cls(
            base_url=d.get("base_url", cls.base_url),
            api_key=d.get("api_key", cls.api_key),
            default_app=d.get("default_app", cls.default_app),
        )

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "base_url": self.base_url,
            "api_key": self.api_key,
            "default_app": self.default_app,
        }


@dataclass
class ConfigModel:
    """配置模型"""

    backend: Backend = field(default=Backend.EULERINTELLI)
    openai: OpenAIConfig = field(default_factory=OpenAIConfig)
    eulerintelli: HermesConfig = field(default_factory=HermesConfig)
    log_level: LogLevel = field(default=LogLevel.DEBUG)
    locale: str = field(default="")  # 空字符串表示自动检测系统语言

    @classmethod
    def from_dict(cls, d: dict) -> "ConfigModel":
        """从字典初始化配置模型"""
        backend_value = d.get("backend", Backend.OPENAI)
        # 确保 backend 始终是 Backend 枚举类型
        if isinstance(backend_value, Backend):
            backend = backend_value
        elif isinstance(backend_value, str):
            backend = Backend(backend_value)
        else:
            backend = Backend.OPENAI

        log_level_value = d.get("log_level", LogLevel.DEBUG)
        # 确保 log_level 始终是 LogLevel 枚举类型
        if isinstance(log_level_value, LogLevel):
            log_level = log_level_value
        elif isinstance(log_level_value, str):
            try:
                log_level = LogLevel(log_level_value)
            except ValueError:
                log_level = LogLevel.DEBUG
        else:
            log_level = LogLevel.DEBUG

        return cls(
            backend=backend,
            openai=OpenAIConfig.from_dict(d.get("openai", {})),
            eulerintelli=HermesConfig.from_dict(d.get("eulerintelli", {})),
            log_level=log_level,
            locale=d.get("locale", ""),  # 空字符串表示自动检测
        )

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "backend": self.backend.value,  # 保存枚举的值
            "openai": self.openai.to_dict(),
            "eulerintelli": self.eulerintelli.to_dict(),
            "log_level": self.log_level.value,
            "locale": self.locale,
        }
