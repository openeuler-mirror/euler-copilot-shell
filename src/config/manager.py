"""配置管理"""

import json
from pathlib import Path

from config.model import Backend, ConfigModel


class ConfigManager:
    """配置管理器

    负责管理与持久化储存 base_url、模型及 api_key
    """

    data = ConfigModel()
    config_path = Path.home() / ".config" / "eulercopilot" / "smart-shell.json"

    def __init__(self) -> None:
        """初始化配置管理器"""
        self._load_settings()

    def set_base_url(self, url: str) -> None:
        """更新 base_url 并保存"""
        self.data.openai.base_url = url
        self._save_settings()

    def get_base_url(self) -> str:
        """获取当前 base_url"""
        return self.data.openai.base_url

    def set_model(self, model: str) -> None:
        """更新模型并保存"""
        self.data.openai.model = model
        self._save_settings()

    def get_model(self) -> str:
        """获取当前模型"""
        return self.data.openai.model

    def set_api_key(self, key: str) -> None:
        """更新 api_key 并保存"""
        self.data.openai.api_key = key
        self._save_settings()

    def get_api_key(self) -> str:
        """获取当前 api_key"""
        return self.data.openai.api_key

    def get_backend(self) -> Backend:
        """获取当前后端"""
        return self.data.backend

    def set_backend(self, backend: Backend) -> None:
        """更新后端并保存"""
        self.data.backend = backend
        self._save_settings()

    def get_eulercopilot_url(self) -> str:
        """获取当前 EulerCopilot base_url"""
        return self.data.eulercopilot.base_url

    def set_eulercopilot_url(self, url: str) -> None:
        """更新 EulerCopilot base_url 并保存"""
        self.data.eulercopilot.base_url = url
        self._save_settings()

    def get_eulercopilot_key(self) -> str:
        """获取当前 EulerCopilot api_key"""
        return self.data.eulercopilot.api_key

    def set_eulercopilot_key(self, key: str) -> None:
        """更新 EulerCopilot api_key 并保存"""
        self.data.eulercopilot.api_key = key
        self._save_settings()

    def _load_settings(self) -> None:
        """从文件载入设置"""
        if self.config_path.exists():
            try:
                with self.config_path.open(encoding="utf-8") as f:
                    self.data = ConfigModel.from_dict(json.load(f))
            except json.JSONDecodeError:
                pass

    def _save_settings(self) -> None:
        """将设置保存到文件"""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with self.config_path.open("w", encoding="utf-8") as f:
            json.dump(self.data.to_dict(), f, indent=4, ensure_ascii=False)


if __name__ == "__main__":
    # 示例用法
    manager = ConfigManager()
    print("当前设置:", manager.data.to_dict())  # noqa: T201
    manager.set_base_url("http://127.0.0.1:1234/v1")
    manager.set_model("qwen2.5-14b-instruct-1m")
    manager.set_api_key("lm-studio")
    print("修改后的设置:", manager.data.to_dict())  # noqa: T201
