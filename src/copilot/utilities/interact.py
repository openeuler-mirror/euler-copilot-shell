# Copyright (c) Huawei Technologies Co., Ltd. 2024-2024. All rights reserved.

import questionary

from copilot.backends.framework_api import PluginData
from copilot.utilities import i18n

ACTIONS_SINGLE_CMD = [
    questionary.Choice(
        i18n.interact_action_explain,
        value='explain',
        shortcut_key='a'
    ),
    questionary.Choice(
        i18n.interact_action_edit,
        value='edit',
        shortcut_key='z'
    ),
    questionary.Choice(
        i18n.interact_action_execute,
        value='execute',
        shortcut_key='x'
    ),
    questionary.Choice(
        i18n.interact_cancel,
        value='cancel',
        shortcut_key='c'
    )
]

ACTIONS_MULTI_CMDS = [
    questionary.Choice(
        i18n.interact_action_explain_selected,
        value='explain',
        shortcut_key='a'
    ),
    questionary.Choice(
        i18n.interact_action_edit_selected,
        value='edit',
        shortcut_key='z'
    ),
    questionary.Choice(
        i18n.interact_action_execute_all,
        value='execute_all',
        shortcut_key='x'
    ),
    questionary.Choice(
        i18n.interact_action_execute_selected,
        value='execute_selected',
        shortcut_key='s'
    ),
    questionary.Choice(
        i18n.interact_cancel,
        value='cancel',
        shortcut_key='c'
    )
]

BACKEND_CHOICES = [
    questionary.Choice(
        i18n.interact_backend_framework.format(brand_name=i18n.BRAND_NAME),
        value='framework',
        shortcut_key='e'
    ),
    questionary.Choice(
        i18n.interact_backend_spark,
        value='spark',
        shortcut_key='s'
    ),
    questionary.Choice(
        i18n.interact_backend_openai,
        value='openai',
        shortcut_key='o'
    ),
    questionary.Choice(
        i18n.interact_cancel,
        value='cancel',
        shortcut_key='c'
    )
]

CUSTOM_STYLE_FANCY = questionary.Style(
    [
        ('separator', 'fg:#00afff'),
        ('qmark', 'fg:#005f87 bold'),
        ('question', 'bold'),
        ('selected', 'fg:#00afff bold'),
        ('pointer', 'fg:#005f87 bold'),
        ('highlighted', 'bold'),
        ('answer', 'fg:#00afff bold'),
        ('text', 'fg:#808080'),
        ('disabled', 'fg:#808080 italic'),
    ]
)


def select_backend() -> str:
    return questionary.select(
        i18n.interact_question_select_backend,
        choices=BACKEND_CHOICES,
        use_shortcuts=True,
        style=CUSTOM_STYLE_FANCY,
    ).ask()


def select_action(has_multi_cmds: bool) -> str:
    return questionary.select(
        i18n.interact_question_select_action,
        choices=ACTIONS_MULTI_CMDS if has_multi_cmds else ACTIONS_SINGLE_CMD,
        use_shortcuts=True,
        style=CUSTOM_STYLE_FANCY
    ).ask()


def select_command(commands: list) -> str:
    return questionary.select(
        i18n.interact_question_select_cmd,
        choices=commands,
        style=CUSTOM_STYLE_FANCY
    ).ask()


def select_command_with_index(commands: list) -> int:
    command = questionary.select(
        i18n.interact_question_select_cmd,
        choices=commands,
        style=CUSTOM_STYLE_FANCY
    ).ask()
    return commands.index(command)


def select_multiple_commands(commands: list) -> list:
    return questionary.checkbox(
        i18n.interact_question_select_cmd,
        choices=commands,
        style=CUSTOM_STYLE_FANCY
    ).ask()


def select_plugins(plugins: list[PluginData]) -> list:
    return questionary.checkbox(
        i18n.interact_question_select_plugin,
        choices=get_plugin_choices(plugins),
        validate=lambda a: (
            True if len(a) > 0 else i18n.interact_select_plugins_valiidate
        ),
        style=CUSTOM_STYLE_FANCY
    ).ask()


def get_plugin_choices(plugins: list[PluginData]) -> list:
    return [
        questionary.Choice(
            plugin.plugin_name,
            value=plugin.id
        ) for plugin in plugins
    ]
