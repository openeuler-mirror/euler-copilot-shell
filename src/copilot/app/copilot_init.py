# Copyright (c) Huawei Technologies Co., Ltd. 2024-2024. All rights reserved.

# pylint: disable=W0611

import os
import readline  # noqa: F401

from copilot.utilities import config_manager


def setup_copilot():
    def _init_config():
        if not os.path.exists(config_manager.CONFIG_DIR):
            os.makedirs(config_manager.CONFIG_DIR)
        if not os.path.exists(config_manager.CONFIG_PATH):
            config_manager.init_config()

    def _prompt_for_config(config_key: str, prompt_text: str):
        config_value = input(prompt_text)
        config_manager.update_config(config_key, config_value)

    if not os.path.exists(config_manager.CONFIG_PATH):
        _init_config()

    config = config_manager.load_config()
    if config.get('backend') == 'spark':
        if config.get('spark_app_id') == '':
            _prompt_for_config('spark_app_id', '请输入你的星火大模型 App ID：')
        if config.get('spark_api_key') == '':
            _prompt_for_config('spark_api_key', '请输入你的星火大模型 API Key：')
        if config.get('spark_api_secret') == '':
            _prompt_for_config('spark_api_secret', '请输入你的星火大模型 App Secret：')
    if config.get('backend') == 'framework':
        if config.get('framework_url') == '':
            _prompt_for_config('framework_url', '请输入 NeoCopilot 智能体 URL：')
        if config.get('framework_api_key') == '':
            _prompt_for_config('framework_api_key', '请输入 NeoCopilot 智能体 API Key：')
    if config.get('backend') == 'openai':
        if config.get('model_url') == '':
            _prompt_for_config('model_url', '请输入你的大模型 URL：')
        if config.get('model_api_key') == '':
            _prompt_for_config('model_api_key', '请输入你的大模型 API Key：')
        if config.get('model_name') == '':
            _prompt_for_config('model_name', '请输入你的大模型名称：')
