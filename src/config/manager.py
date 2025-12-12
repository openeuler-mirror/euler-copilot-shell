"""配置管理"""

import json
from pathlib import Path

from config.model import Backend, ConfigModel, LogLevel
from log.manager import get_logger


class ConfigManager:
    """
    配置管理器

    负责管理与持久化储存 base_url、模型及 api_key
    支持多用户环境，包括全局配置和用户私有配置
    """

    data = ConfigModel()

    # 全局配置路径（用于部署时创建的模板配置）
    GLOBAL_CONFIG_DIR = Path("/etc/witty-assistant")
    GLOBAL_CONFIG_PATH = GLOBAL_CONFIG_DIR / "config-template.json"

    # 用户配置目录和文件
    USER_CONFIG_DIR = Path.home() / ".config" / "witty"
    USER_CONFIG_PATH = USER_CONFIG_DIR / "config.json"

    def __init__(self) -> None:
        """
        初始化配置管理器

        默认使用用户配置，部署阶段使用专用的类方法创建全局配置管理器
        """
        self.config_path = self.USER_CONFIG_PATH
        self._load_settings()

        # 如果是普通用户且配置文件不存在，尝试从模板初始化
        if self.config_path == self.USER_CONFIG_PATH and not self.USER_CONFIG_PATH.exists():
            self.ensure_user_config_exists()

    @classmethod
    def create_deployment_manager(cls) -> "ConfigManager":
        """
        创建部署专用的配置管理器

        用于在部署阶段创建全局配置模板

        Returns:
            ConfigManager: 使用全局配置路径的配置管理器

        """
        manager = cls.__new__(cls)
        manager.data = ConfigModel()
        manager.config_path = cls.GLOBAL_CONFIG_PATH
        # 由于是类方法创建的实例，直接访问私有方法
        ConfigManager._load_settings(manager)
        return manager

    def ensure_user_config_exists(self) -> bool:
        """
        确保用户配置文件存在

        如果用户配置不存在，会尝试从全局模板复制；
        如果全局模板也不存在，则创建默认配置

        Returns:
            bool: 如果配置被创建或更新则返回 True，否则返回 False

        """
        logger = get_logger(__name__)

        # 如果用户配置已存在，直接返回
        if self.USER_CONFIG_PATH.exists():
            return False

        logger.info("用户配置文件不存在，尝试初始化配置")

        # 尝试从全局模板复制
        if self.GLOBAL_CONFIG_PATH.exists():
            try:
                # 确保用户配置目录存在
                self.USER_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)

                # 复制全局配置模板到用户目录
                with self.GLOBAL_CONFIG_PATH.open(encoding="utf-8") as global_file:
                    global_config = json.load(global_file)

                with self.USER_CONFIG_PATH.open("w", encoding="utf-8") as user_file:
                    json.dump(global_config, user_file, indent=4, ensure_ascii=False)

            except (OSError, json.JSONDecodeError) as e:
                logger.warning("复制全局配置模板失败: %s，将创建默认配置", e)
            else:
                logger.info("已从全局模板复制配置到用户目录")
                # 重新加载用户配置
                self._load_settings()
                return True

        # 如果无法从模板复制，创建默认配置
        logger.info("创建默认用户配置")
        self.data = ConfigModel()
        self._save_settings()
        return True

    def create_global_template(self) -> bool:
        """
        创建全局配置模板

        仅在部署阶段使用，将当前配置保存为全局模板

        Returns:
            bool: 创建成功返回 True，否则返回 False

        """
        logger = get_logger(__name__)

        try:
            # 确保全局配置目录存在
            self.GLOBAL_CONFIG_DIR.mkdir(parents=True, exist_ok=True)

            # 保存当前配置为全局模板
            with self.GLOBAL_CONFIG_PATH.open("w", encoding="utf-8") as f:
                json.dump(self.data.to_dict(), f, indent=4, ensure_ascii=False)

            # 设置文件权限，让所有用户都可以读取
            self.GLOBAL_CONFIG_PATH.chmod(0o644)

        except (OSError, PermissionError):
            logger.exception("创建全局配置模板失败")
            return False
        else:
            logger.info("全局配置模板已创建: %s", self.GLOBAL_CONFIG_PATH)
            return True

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

    def get_witty_url(self) -> str:
        """获取当前 Hermes base_url"""
        return self.data.witty.base_url

    def set_witty_url(self, url: str) -> None:
        """更新 Hermes base_url 并保存"""
        self.data.witty.base_url = url
        self._save_settings()

    def get_witty_key(self) -> str:
        """获取当前 Hermes api_key"""
        return self.data.witty.api_key

    def set_witty_key(self, key: str) -> None:
        """更新 Hermes api_key 并保存"""
        self.data.witty.api_key = key
        self._save_settings()

    def get_log_level(self) -> LogLevel:
        """获取当前日志级别"""
        return self.data.log_level

    def set_log_level(self, level: LogLevel) -> None:
        """更新日志级别并保存"""
        self.data.log_level = level
        self._save_settings()

    def get_default_app(self) -> str:
        """获取当前默认智能体 ID"""
        return self.data.witty.default_app

    def set_default_app(self, app_id: str) -> None:
        """更新默认智能体 ID 并保存"""
        self.data.witty.default_app = app_id
        self._save_settings()

    def get_llm_chat_model(self) -> str:
        """获取 Chat 模型的 llmId"""
        return self.data.witty.llm_chat

    def set_llm_chat_model(self, llm_id: str) -> None:
        """更新 Chat 模型的 llmId 并保存"""
        self.data.witty.llm_chat = llm_id
        self._save_settings()

    def get_locale(self) -> str:
        """获取当前语言环境"""
        return self.data.locale

    def set_locale(self, locale_code: str) -> None:
        """更新语言环境并保存"""
        self.data.locale = locale_code
        self._save_settings()

    def validate_and_update_config(self) -> bool:
        """
        检查配置文件完整性并更新缺失字段

        对于普通用户，会先尝试确保配置文件存在（从模板复制或创建默认）

        Returns:
            bool: 如果配置被更新则返回 True，否则返回 False

        """
        logger = get_logger(__name__)

        # 如果是用户配置路径，先确保配置文件存在
        if self.config_path == self.USER_CONFIG_PATH:
            config_created = self.ensure_user_config_exists()
            if config_created:
                return True

        # 如果配置文件仍然不存在，创建默认配置
        if not self.config_path.exists():
            logger.info("配置文件不存在，创建默认配置")
            self._save_settings()
            return True

        # 配置文件存在，检查完整性
        return self._validate_existing_config()

    def _validate_existing_config(self) -> bool:
        """验证现有配置文件的完整性"""
        logger = get_logger(__name__)

        try:
            # 读取现有配置文件
            with self.config_path.open(encoding="utf-8") as f:
                existing_config = json.load(f)

        except json.JSONDecodeError:
            logger.exception("配置文件格式错误，将重置为默认配置")
            self.data = ConfigModel()
            self._save_settings()
            return True

        except OSError:
            logger.exception("配置文件读取失败，将重置为默认配置")
            self.data = ConfigModel()
            self._save_settings()
            return True

        # 检查并补充缺失的字段
        return self._merge_and_update_config(existing_config)

    def _merge_and_update_config(self, existing_config: dict) -> bool:
        """合并并更新配置"""
        logger = get_logger(__name__)

        # 创建默认配置用于比较
        default_config = ConfigModel().to_dict()

        # 检查并补充缺失的字段
        def merge_config(existing: dict, default: dict, path: str = "") -> bool:
            """递归合并配置，返回是否有更新"""
            has_update = False
            for key, default_value in default.items():
                current_path = f"{path}.{key}" if path else key

                if key not in existing:
                    existing[key] = default_value
                    has_update = True
                    logger.info("添加缺失字段: %s = %s", current_path, default_value)
                elif isinstance(default_value, dict) and isinstance(existing[key], dict):
                    # 递归处理嵌套对象
                    nested_updated = merge_config(existing[key], default_value, current_path)
                    has_update = has_update or nested_updated

            return has_update

        updated = merge_config(existing_config, default_config)

        if updated:
            # 重新加载更新后的配置
            self.data = ConfigModel.from_dict(existing_config)
            # 保存更新后的配置
            self._save_settings()
            logger.info("配置文件已更新并保存")
        else:
            logger.info("配置文件完整，无需更新")

        return updated

    def _load_settings(self) -> None:
        """从文件载入设置"""
        if self.config_path.exists():
            try:
                with self.config_path.open(encoding="utf-8") as f:
                    self.data = ConfigModel.from_dict(json.load(f))
            except (json.JSONDecodeError, OSError):
                # 如果加载失败，使用默认配置
                self.data = ConfigModel()

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
    manager.set_model("qwen/qwen3-30b-a3b")
    manager.set_api_key("lm-studio")
    print("修改后的设置:", manager.data.to_dict())  # noqa: T201
