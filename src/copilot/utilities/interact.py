# Copyright (c) Huawei Technologies Co., Ltd. 2024-2025. All rights reserved.

from typing import Optional

import questionary

from copilot.backends.framework_api import PluginData
from copilot.utilities import config_manager, i18n

ACTIONS_SINGLE_CMD = [
    questionary.Choice(
        i18n.interact_action_explain,
        value="explain",
        shortcut_key="a",
    ),
    questionary.Choice(
        i18n.interact_action_edit,
        value="edit",
        shortcut_key="z",
    ),
    questionary.Choice(
        i18n.interact_action_execute,
        value="execute",
        shortcut_key="x",
    ),
    questionary.Choice(
        i18n.interact_cancel,
        value="cancel",
        shortcut_key="c",
    ),
]

ACTIONS_MULTI_CMDS = [
    questionary.Choice(
        i18n.interact_action_explain_selected,
        value="explain",
        shortcut_key="a",
    ),
    questionary.Choice(
        i18n.interact_action_edit_selected,
        value="edit",
        shortcut_key="z",
    ),
    questionary.Choice(
        i18n.interact_action_execute_all,
        value="execute_all",
        shortcut_key="x",
    ),
    questionary.Choice(
        i18n.interact_action_execute_selected,
        value="execute_selected",
        shortcut_key="s",
    ),
    questionary.Choice(
        i18n.interact_cancel,
        value="cancel",
        shortcut_key="c",
    ),
]

BACKEND_CHOICES = [
    questionary.Choice(
        i18n.interact_backend_framework.format(brand_name=i18n.BRAND_NAME),
        value="framework",
        shortcut_key="e",
    ),
    questionary.Choice(
        i18n.interact_backend_spark,
        value="spark",
        shortcut_key="s",
    ),
    questionary.Choice(
        i18n.interact_backend_openai,
        value="openai",
        shortcut_key="o",
    ),
    questionary.Choice(
        i18n.interact_cancel,
        value="cancel",
        shortcut_key="c",
    ),
]

CUSTOM_STYLE_FANCY = questionary.Style(
    [
        ("separator", "fg:#00afff"),
        ("qmark", "fg:#005f87 bold"),
        ("question", "bold"),
        ("selected", "fg:#00afff bold"),
        ("pointer", "fg:#005f87 bold"),
        ("highlighted", "bold"),
        ("answer", "fg:#00afff bold"),
        ("text", "fg:#808080"),
        ("disabled", "fg:#808080 italic"),
    ],
)


def select_backend() -> str:
    """命令行交互：选择后端"""
    return questionary.select(
        i18n.interact_question_select_backend,
        choices=BACKEND_CHOICES,
        qmark="❯",
        use_shortcuts=True,
        style=CUSTOM_STYLE_FANCY,
    ).ask()


def select_action(has_multi_cmds: bool) -> str:
    """命令行交互：选择操作"""
    return questionary.select(
        i18n.interact_question_select_action,
        choices=ACTIONS_MULTI_CMDS if has_multi_cmds else ACTIONS_SINGLE_CMD,
        qmark="❯",
        use_shortcuts=True,
        style=CUSTOM_STYLE_FANCY,
    ).ask()


def select_command(commands: list) -> str:
    """命令行交互：选择命令"""
    return questionary.select(
        i18n.interact_question_select_cmd,
        choices=commands,
        qmark="❯",
        style=CUSTOM_STYLE_FANCY,
    ).ask()


def select_command_with_index(commands: list) -> int:
    """命令行交互：选择命令并返回索引"""
    command = questionary.select(
        i18n.interact_question_select_cmd,
        choices=commands,
        qmark="❯",
        style=CUSTOM_STYLE_FANCY,
    ).ask()
    return commands.index(command)


def select_multiple_commands(commands: list) -> list:
    """命令行交互：选择多个命令"""
    return questionary.checkbox(
        i18n.interact_question_select_cmd,
        choices=commands,
        qmark="❯",
        style=CUSTOM_STYLE_FANCY,
    ).ask()


def select_one_plugin(plugins: list[PluginData]) -> str:
    """命令行交互：选择一个插件"""
    return questionary.select(
        i18n.interact_question_select_plugin,
        choices=__get_plugin_choices(plugins),
        qmark="❯",
        style=CUSTOM_STYLE_FANCY,
    ).ask()


def select_settings_entry() -> str:
    """命令行交互：选择设置条目"""
    return questionary.select(
        i18n.interact_question_select_settings_entry,
        choices=__get_settings_entry_choices(),
        qmark="❯",
        style=CUSTOM_STYLE_FANCY,
    ).ask()


def select_query_mode(backend: str) -> str:
    """命令行交互：选择查询模式"""
    return questionary.select(
        i18n.interact_question_select_query_mode,
        choices=__get_query_mode_choices(backend),
        qmark="❯",
        style=CUSTOM_STYLE_FANCY,
    ).ask()


def ask_boolean(question: str) -> bool:
    """命令行交互：提问布尔型问题"""
    return questionary.confirm(question, default=False, style=CUSTOM_STYLE_FANCY).ask()


def __get_plugin_choices(plugins: list[PluginData]) -> list:
    return [
        questionary.Choice(
            plugin.plugin_name,
            value=plugin.id,
        )
        for plugin in plugins
    ]


def __get_settings_entry_choices() -> list:
    choices = [questionary.Choice(name, item) for item, name in config_manager.CONFIG_ENTRY_NAME.items()]
    choices.append(questionary.Choice(i18n.interact_cancel, value="cancel"))
    return choices


def __get_query_mode_choices(backend: str) -> list:
    def __disabled(name: str, item: str) -> Optional[str]:
        return (
            i18n.config_interact_query_mode_forbidden.format(mode=name)
            if backend != "framework" and item != "chat"
            else None
        )

    return [
        questionary.Choice(
            name,
            item,
            disabled=__disabled(name, item),
        )
        for item, name in config_manager.QUERY_MODE_NAME.items()
    ]
