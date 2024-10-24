# Copyright (c) Huawei Technologies Co., Ltd. 2024-2024. All rights reserved.

import json
import os

from copilot.utilities import i18n, interact

CONFIG_DIR = os.path.join(os.path.expanduser('~'), '.config/eulercopilot')
CONFIG_PATH = os.path.join(CONFIG_DIR, 'config.json')

CONFIG_ENTRY_NAME = {
    'backend': i18n.settings_config_entry_backend,
    'query_mode': i18n.settings_config_entry_query_mode,
    'advanced_mode': i18n.settings_config_entry_advanced_mode,
    'debug_mode': i18n.settings_config_entry_debug_mode,
    'spark_app_id': i18n.settings_config_entry_spark_app_id,
    'spark_api_key': i18n.settings_config_entry_spark_api_key,
    'spark_api_secret': i18n.settings_config_entry_spark_api_secret,
    'spark_url': i18n.settings_config_entry_spark_url,
    'spark_domain': i18n.settings_config_entry_spark_domain,
    'framework_url': i18n.settings_config_entry_framework_url.format(brand_name=i18n.BRAND_NAME),
    'framework_api_key': i18n.settings_config_entry_framework_api_key.format(brand_name=i18n.BRAND_NAME),
    'model_url': i18n.settings_config_entry_model_url,
    'model_api_key': i18n.settings_config_entry_model_api_key,
    'model_name': i18n.settings_config_entry_model_name
}

BACKEND_NAME = {
    'framework': i18n.interact_backend_framework.format(brand_name=i18n.BRAND_NAME),
    'spark': i18n.interact_backend_spark,
    'openai': i18n.interact_backend_openai
}

QUERY_MODE_NAME = {
    'chat': i18n.query_mode_chat,
    'flow': i18n.query_mode_flow,
    'diagnose': i18n.query_mode_diagnose,
    'tuning': i18n.query_mode_tuning,
}

DEFAULT_CONFIG = {
    'backend': 'framework',
    'query_mode': 'chat',
    'advanced_mode': False,
    'debug_mode': False,
    'spark_app_id': '',
    'spark_api_key': '',
    'spark_api_secret': '',
    'spark_url': 'wss://spark-api.xf-yun.com/v3.5/chat',
    'spark_domain': 'generalv3.5',
    'framework_url': 'https://eulercopilot.gitee.com',
    'framework_api_key': '',
    'model_url': '',
    'model_api_key': '',
    'model_name': ''
}


def load_config() -> dict:
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as file:
            config = json.load(file)
    except FileNotFoundError:
        init_config()
        config = load_config()
    return config


def write_config(config: dict):
    with open(CONFIG_PATH, 'w', encoding='utf-8') as json_file:
        json.dump(config, json_file, indent=4)
        json_file.write('\n')  # 追加一行空行


def init_config():
    if not os.path.exists(CONFIG_DIR):
        os.makedirs(CONFIG_DIR)
    write_config(DEFAULT_CONFIG)


def update_config(key: str, value):
    if key not in DEFAULT_CONFIG:
        return
    config = load_config()
    config.update({key: value})
    write_config(config)


def select_query_mode(mode: int):
    modes = list(QUERY_MODE_NAME.keys())
    if mode < len(modes):
        update_config('query_mode', modes[mode])


def select_backend():
    backend = interact.select_backend()
    if backend in ['framework', 'spark', 'openai']:
        update_config('backend', backend)


def config_to_markdown() -> str:
    config = load_config()
    config_table = '\n'.join([
        f'| {CONFIG_ENTRY_NAME.get(key)} | {__get_config_item_display_name(key, value)} |'
        for key, value in config.items()
    ])
    return f'# {i18n.settings_markdown_title}\n\
| {i18n.settings_markdown_header_key} \
| {i18n.settings_markdown_header_value} |\n\
| ----------- | ----------- |\n{config_table}'


def __get_config_item_display_name(key, value):
    if key == 'backend':
        return BACKEND_NAME.get(value, value)
    if key == 'query_mode':
        return QUERY_MODE_NAME.get(value, value)
    return value
