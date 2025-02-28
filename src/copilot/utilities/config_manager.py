# Copyright (c) Huawei Technologies Co., Ltd. 2024-2025. All rights reserved.

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from copilot.utilities import i18n, interact

CONFIG_ENTRY_NAME = {
    "backend": i18n.config_entry_backend,
    "query_mode": i18n.config_entry_query_mode,
    "advanced_mode": i18n.config_entry_advanced_mode,
    "debug_mode": i18n.config_entry_debug_mode,
    "spark_app_id": i18n.config_entry_spark_app_id,
    "spark_api_key": i18n.config_entry_spark_api_key,
    "spark_api_secret": i18n.config_entry_spark_api_secret,
    "spark_url": i18n.config_entry_spark_url,
    "spark_domain": i18n.config_entry_spark_domain,
    "framework_url": i18n.config_entry_framework_url.format(brand_name=i18n.BRAND_NAME),
    "framework_api_key": i18n.config_entry_framework_api_key.format(brand_name=i18n.BRAND_NAME),
    "model_url": i18n.config_entry_model_url,
    "model_api_key": i18n.config_entry_model_api_key,
    "model_name": i18n.config_entry_model_name,
}

BACKEND_NAME = {
    "framework": i18n.interact_backend_framework.format(brand_name=i18n.BRAND_NAME),
    "spark": i18n.interact_backend_spark,
    "openai": i18n.interact_backend_openai,
}

QUERY_MODE_NAME = {
    "chat": i18n.query_mode_chat,
    "shell": i18n.query_mode_shell,
    "plugin": i18n.query_mode_plugin,
    "diagnose": i18n.query_mode_diagnose,
    "tuning": i18n.query_mode_tuning,
}


@dataclass
class ConfigModel:
    """配置模型"""

    backend: str = field(default="framework")
    query_mode: str = field(default="chat")
    advanced_mode: bool = field(default=True)
    debug_mode: bool = field(default=False)
    spark_app_id: str = field(default="")
    spark_api_key: str = field(default="")
    spark_api_secret: str = field(default="")
    spark_url: str = field(default="wss://spark-api.xf-yun.com/v3.5/chat")
    spark_domain: str = field(default="generalv3.5")
    framework_url: str = field(default="https://www.eulercopilot.com (CHANGE_ME!!!)")
    framework_api_key: str = field(default="")
    model_url: str = field(default="")
    model_api_key: str = field(default="")
    model_name: str = field(default="")

    def to_dict(self) -> dict:
        """将ConfigModel对象转换为字典"""
        return self.__dict__

    @staticmethod
    def from_dict(data: dict) -> "ConfigModel":
        """从字典创建ConfigModel对象"""
        return ConfigModel(**data)

    @staticmethod
    def metadata_dict() -> dict:
        """获取配置项的 field 元数据"""
        return {field.name: field.metadata for field in ConfigModel.__dataclass_fields__.values()}


class Config:
    """配置管理器"""

    config_dir = Path.home() / ".config" / "eulercopilot"
    config_path = config_dir / "config.json"

    data: ConfigModel

    def __init__(self) -> None:
        """初始化配置"""
        try:
            with self.config_path.open(encoding="utf-8") as file:
                config_data = json.load(file)
                self.data = ConfigModel.from_dict(config_data)
        except FileNotFoundError:
            self.data = ConfigModel()
            if not self.config_dir.exists():
                self.config_dir.mkdir(parents=True)
            self.__save()

    def update(self, key: str, value: Any) -> None:
        """更新配置"""
        setattr(self.data, key, value)
        self.__save()

    def select_query_mode(self, mode: int) -> None:
        """选择问答模式"""
        modes = list(QUERY_MODE_NAME.keys())
        if mode < len(modes):
            self.update("query_mode", modes[mode])

    def select_backend(self) -> None:
        """选择后端"""
        backend = interact.select_backend()
        if backend in ["framework", "spark", "openai"]:
            self.update("backend", backend)

    def to_markdown(self) -> str:
        """以 Markdown 格式输出当前配置"""
        config_items = self.data.to_dict()
        config_table = "\n".join(
            f"| {CONFIG_ENTRY_NAME.get(key)} | {self.__get_config_item_display_name(key, value)} |"
            for key, value in config_items.items()
        )
        return f"# {i18n.config_md_title}\n\n| {i18n.config_md_header_key} | {i18n.config_md_header_value} |\n| ---- | ---- |\n{config_table}"

    def __get_config_item_display_name(self, key: str, value: str) -> str:
        if key == "backend":
            return BACKEND_NAME.get(value, value)
        if key == "query_mode":
            return QUERY_MODE_NAME.get(value, value)
        return value

    def __save(self) -> None:
        """写入配置"""
        with self.config_path.open("w", encoding="utf-8") as json_file:
            json.dump(self.data.to_dict(), json_file, indent=4)
