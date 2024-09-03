# Copyright (c) Huawei Technologies Co., Ltd. 2024-2024. All rights reserved.

import questionary

ACTIONS_SINGLE_CMD = [
    questionary.Choice('解释命令', value='explain', shortcut_key='a'),
    questionary.Choice('编辑命令', value='edit', shortcut_key='z'),
    questionary.Choice('执行命令', value='execute', shortcut_key='x'),
    questionary.Choice('取消', value='cancel', shortcut_key='c'),
]

ACTIONS_MULTI_CMDS = [
    questionary.Choice('解释指定命令', value='explain', shortcut_key='a'),
    questionary.Choice('编辑指定命令', value='edit', shortcut_key='z'),
    questionary.Choice('执行所有命令', value='execute_all', shortcut_key='x'),
    questionary.Choice('执行指定命令', value='execute_selected', shortcut_key='s'),
    questionary.Choice('取消', value='cancel', shortcut_key='c'),
]

QUESTIONS = [
    '选择要执行的操作：',
    '选择命令：'
]

CUSTOM_STYLE_FANCY = questionary.Style(
    [
        ('separator', 'fg:#cc5454'),
        ('qmark', 'fg:#673ab7 bold'),
        ('question', 'bold'),
        ('selected', 'fg:#cc5454'),
        ('pointer', 'fg:#673ab7 bold'),
        ('highlighted', 'fg:#673ab7 bold'),
        ('answer', 'fg:#f44336 bold'),
        ('text', 'fg:#FBE9E7'),
        ('disabled', 'fg:#858585 italic'),
    ]
)


def query_yes_or_no(question: str) -> bool:
    valid = {'yes': True, 'y': True, 'no': False, 'n': False}
    prompt = ' [Y/n] '

    while True:
        choice = input(question + prompt).lower()
        if choice == '':
            return valid['y']
        elif choice in valid:
            return valid[choice]
        print('请用 "yes (y)" 或 "no (n)" 回答')


def select_action(has_multi_cmds: bool) -> str:
    return questionary.select(
        QUESTIONS[0],
        choices=ACTIONS_MULTI_CMDS if has_multi_cmds else ACTIONS_SINGLE_CMD,
        pointer=None,
        use_shortcuts=True,
        use_indicator=True,
        style=CUSTOM_STYLE_FANCY
    ).ask()


def select_command(commands: list) -> str:
    return questionary.select(
        QUESTIONS[1],
        choices=commands,
        pointer=None,
        use_indicator=True,
        style=CUSTOM_STYLE_FANCY
    ).ask()


def select_command_with_index(commands: list) -> int:
    command = questionary.select(
        QUESTIONS[1],
        choices=commands,
        pointer=None,
        use_indicator=True,
        style=CUSTOM_STYLE_FANCY
    ).ask()
    return commands.index(command)


def select_multiple_commands(commands: list) -> list:
    return questionary.checkbox(
        QUESTIONS[1],
        choices=commands,
        pointer=None,
        use_indicator=True,
        style=CUSTOM_STYLE_FANCY
    ).ask()
