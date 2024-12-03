# Copyright (c) Huawei Technologies Co., Ltd. 2024-2024. All rights reserved.

# pylint: disable=W0611

import os
import readline  # noqa: F401

from rich import print as rprint

from copilot.utilities import config_manager, i18n


def setup_copilot():
    def _init_config():
        if not os.path.exists(config_manager.CONFIG_DIR):
            os.makedirs(config_manager.CONFIG_DIR)
        if not os.path.exists(config_manager.CONFIG_PATH):
            config_manager.init_config()

    def _prompt_for_config(config_key: str, prompt_text: str) -> str:
        config_value = input(prompt_text)
        config_manager.update_config(config_key, config_value)
        return config_value

    if not os.path.exists(config_manager.CONFIG_PATH):
        _init_config()

    rprint(f'\n[bold]{i18n.settings_init_welcome_msg.format(brand_name=i18n.BRAND_NAME)}[/bold]\n')
    rprint(i18n.settings_init_welcome_usage_guide + '\n')
    rprint(i18n.settings_init_welcome_help_hint)
    rprint(i18n.settings_init_welcome_docs_link.format(url=i18n.DOCS_URL) + '\n')

    config = config_manager.load_config()
    if config.get('backend') == 'spark':
        if config.get('spark_app_id') == '':
            _prompt_for_config('spark_app_id', i18n.interact_question_input_text.format(
                question_body=i18n.settings_config_entry_spark_app_id))
        if config.get('spark_api_key') == '':
            _prompt_for_config('spark_api_key', i18n.interact_question_input_text.format(
                question_body=i18n.settings_config_entry_spark_api_key))
        if config.get('spark_api_secret') == '':
            _prompt_for_config('spark_api_secret', i18n.interact_question_input_text.format(
                question_body=i18n.settings_config_entry_spark_api_secret))
    if config.get('backend') == 'framework':
        framework_url = config.get('framework_url')
        if framework_url == '':
            framework_url = _prompt_for_config('framework_url', i18n.interact_question_input_text.format(
                question_body=i18n.settings_config_entry_framework_url))
        if config.get('framework_api_key') == '':
            title = i18n.settings_init_framework_api_key_notice_title.format(brand_name=i18n.BRAND_NAME)
            rprint(f'[bold]{title}[/bold]')
            rprint(i18n.settings_init_framework_api_key_notice_content.format(url=framework_url))
            _prompt_for_config('framework_api_key', i18n.interact_question_input_text.format(
                question_body=i18n.settings_config_entry_framework_api_key.format(brand_name=i18n.BRAND_NAME)))
    if config.get('backend') == 'openai':
        if config.get('model_url') == '':
            _prompt_for_config('model_url', i18n.interact_question_input_text.format(
                question_body=i18n.settings_config_entry_model_url))
        if config.get('model_api_key') == '':
            _prompt_for_config('model_api_key', i18n.interact_question_input_text.format(
                question_body=i18n.settings_config_entry_model_api_key))
        if config.get('model_name') == '':
            _prompt_for_config('model_name', i18n.interact_question_input_text.format(
                question_body=i18n.settings_config_entry_model_name))
