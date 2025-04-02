# Copyright (c) Huawei Technologies Co., Ltd. 2024-2025. All rights reserved.

import readline  # noqa: F401

from rich import print as rprint

from copilot.utilities import config_manager, i18n


def setup_copilot() -> None:
    config = config_manager.Config()

    def _prompt_for_config(config_key: str, prompt_text: str) -> str:
        config_value = input(prompt_text)
        config.update(config_key, config_value)
        return config_value

    rprint(f"\n[bold]{i18n.init_welcome_msg.format(brand_name=i18n.BRAND_NAME)}[/bold]\n")
    rprint(i18n.init_welcome_usage_guide + "\n")
    rprint(i18n.init_welcome_help_hint)
    rprint(i18n.init_welcome_docs_link.format(url=i18n.DOCS_URL) + "\n")
    rprint(i18n.init_welcome_alpha_warning.format(brand_name=i18n.BRAND_NAME) + "\n")

    if config.data.backend == "spark":
        if config.data.spark_app_id == "":
            _prompt_for_config(
                "spark_app_id", i18n.interact_question_input_text.format(question_body=i18n.config_entry_spark_app_id)
            )
        if config.data.spark_api_key == "":
            _prompt_for_config(
                "spark_api_key", i18n.interact_question_input_text.format(question_body=i18n.config_entry_spark_api_key)
            )
        if config.data.spark_api_secret == "":
            _prompt_for_config(
                "spark_api_secret",
                i18n.interact_question_input_text.format(question_body=i18n.config_entry_spark_api_secret),
            )
    if config.data.backend == "framework":
        framework_url = config.data.framework_url
        if framework_url == "":
            framework_url = _prompt_for_config(
                "framework_url", i18n.interact_question_input_text.format(question_body=i18n.config_entry_framework_url)
            )
        if config.data.framework_api_key == "":
            title = i18n.init_framework_api_key_notice_title.format(brand_name=i18n.BRAND_NAME)
            rprint(f"[bold]{title}[/bold]")
            rprint(i18n.init_framework_api_key_notice_content.format(url=framework_url))
            _prompt_for_config(
                "framework_api_key",
                i18n.interact_question_input_text.format(
                    question_body=i18n.config_entry_framework_api_key.format(brand_name=i18n.BRAND_NAME)
                ),
            )
    if config.data.backend == "openai":
        if config.data.model_url == "":
            _prompt_for_config(
                "model_url", i18n.interact_question_input_text.format(question_body=i18n.config_entry_model_url)
            )
        if config.data.model_api_key == "":
            _prompt_for_config(
                "model_api_key", i18n.interact_question_input_text.format(question_body=i18n.config_entry_model_api_key)
            )
        if config.data.model_name == "":
            _prompt_for_config(
                "model_name", i18n.interact_question_input_text.format(question_body=i18n.config_entry_model_name)
            )
