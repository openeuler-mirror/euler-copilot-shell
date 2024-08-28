# Copyright (c) Huawei Technologies Co., Ltd. 2024-2024. All rights reserved.

# pylint: disable=R0911,R0912,R0913

import os
import sys
from typing import Optional

import typer

from copilot.app.copilot_app import main
from copilot.app.copilot_init import setup_copilot
from copilot.utilities.config_manager import (
    CONFIG_PATH,
    DEFAULT_CONFIG,
    edit_config,
    load_config,
    select_backend,
    select_query_mode,
)

CONFIG: dict = load_config()
BACKEND: str = CONFIG.get('backend', DEFAULT_CONFIG['backend'])
ADVANCED_MODE: bool = CONFIG.get('advanced_mode', DEFAULT_CONFIG['advanced_mode'])
CONFIG_INITIALIZED: bool = os.path.exists(CONFIG_PATH)

app = typer.Typer(
    context_settings={
        'help_option_names': ['-h', '--help'],
        'allow_interspersed_args': True
    },
    add_completion=False
)


@app.command()
def cli(
    question: Optional[str] = typer.Argument(
        None, show_default=False,
        help='通过自然语言提问'),
    chat: bool = typer.Option(
        False, '--chat', '-c',
        help='切换到智能问答模式',
        rich_help_panel='选择问答模式'
    ),
    diagnose: bool = typer.Option(
        False, '--diagnose', '-d',
        help='切换到智能诊断模式',
        rich_help_panel='选择问答模式',
        hidden=(BACKEND != 'framework')
    ),
    tuning: bool = typer.Option(
        False, '--tuning', '-t',
        help='切换到智能调优模式',
        rich_help_panel='选择问答模式',
        hidden=(BACKEND != 'framework')
    ),
    init: bool = typer.Option(
        False, '--init',
        help='初始化 copilot 设置',
        hidden=(CONFIG_INITIALIZED)
    ),
    backend: bool = typer.Option(
        False, '--backend',
        help='选择大语言模型后端',
        rich_help_panel='高级选项',
        hidden=(not ADVANCED_MODE)
    ),
    settings: bool = typer.Option(
        False, '--settings',
        help='编辑 copilot 设置',
        rich_help_panel='高级选项',
        hidden=(not ADVANCED_MODE)
    )
) -> int:
    '''EulerCopilot 命令行助手'''
    if init:
        setup_copilot()
        return 0
    if not CONFIG_INITIALIZED:
        print('\033[1;31m请先初始化 copilot 设置\033[0m')
        print('\033[33m请使用 "copilot --init" 命令初始化\033[0m')
        return 1
    if backend:
        if ADVANCED_MODE:
            select_backend()
        return 0
    if settings:
        if ADVANCED_MODE:
            edit_config()
        return 0

    if sum(map(bool, [chat, diagnose, tuning])) > 1:
        print('\033[1;31m当前版本只能选择一种问答模式\033[0m')
        return 1

    if chat:
        select_query_mode(1)
        if not question:
            return 0
    elif diagnose:
        if BACKEND == 'framework':
            select_query_mode(2)
            if not question:
                return 0
        else:
            print('\033[33m当前大模型后端不支持智能诊断功能\033[0m')
            print('\033[33m推荐使用 EulerCopilot 智能体框架\033[0m')
            return 1
    elif tuning:
        if BACKEND == 'framework':
            select_query_mode(3)
            if not question:
                return 0
        else:
            print('\033[33m当前大模型后端不支持智能调参功能\033[0m')
            print('\033[33m推荐使用 EulerCopilot 智能体框架\033[0m')
            return 1

    if question:
        question = question.strip()

    return main(question, load_config())


def entry_point() -> int:
    return app()


if __name__ == '__main__':
    code = entry_point()
    sys.exit(code)
