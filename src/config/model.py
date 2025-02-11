"""配置模型"""

from dataclasses import dataclass, field
from enum import Enum


class Backend(str, Enum):
    """后端类型"""

    OPENAI = "openai"
    EULERCOPILOT = "eulercopilot"


@dataclass
class OpenAIConfig:
    """OpenAI 后端配置"""

    base_url: str = field(default="http://127.0.0.1:1234/v1")
    model: str = field(default="qwen2.5-14b-instruct-1m")
    api_key: str = field(default="lm-studio")

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
class EulerCopilotConfig:
    """EulerCopilot 后端配置"""

    base_url: str = field(default="https://www.eulercopilot.com")
    api_key: str = field(default="your-eulercopilot-api-key")

    @classmethod
    def from_dict(cls, d: dict) -> "EulerCopilotConfig":
        """从字典初始化配置"""
        return cls(
            base_url=d.get("base_url", cls.base_url),
            api_key=d.get("api_key", cls.api_key),
        )

    def to_dict(self) -> dict:
        """转换为字典"""
        return {"base_url": self.base_url, "api_key": self.api_key}


@dataclass
class ConfigModel:
    """配置模型"""

    backend: Backend = field(default=Backend.OPENAI)
    openai: OpenAIConfig = field(default_factory=OpenAIConfig)
    eulercopilot: EulerCopilotConfig = field(default_factory=EulerCopilotConfig)

    @classmethod
    def from_dict(cls, d: dict) -> "ConfigModel":
        """从字典初始化配置模型"""
        return cls(
            backend=d.get("backend", Backend.OPENAI),
            openai=OpenAIConfig.from_dict(d.get("openai", {})),
            eulercopilot=EulerCopilotConfig.from_dict(d.get("eulercopilot", {})),
        )

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "backend": self.backend,
            "openai": self.openai.to_dict(),
            "eulercopilot": self.eulercopilot.to_dict(),
        }
