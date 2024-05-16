# Copyright (c) Huawei Technologies Co., Ltd. 2024-2024. All rights reserved.

import os
from typing import Optional

import typer
from rich import print
from utilities.config_manager import (
    CONFIG_PATH,
    DEFAULT_CONFIG,
    edit_config,
    load_config,
    select_backend,
    select_query_mode,
)

from app.copilot_app import main
from app.copilot_init import setup_copilot

config: dict = load_config()
BACKEND: str = config.get('backend', DEFAULT_CONFIG['backend'])
ADVANCED_MODE: bool = config.get('advanced_mode', DEFAULT_CONFIG['advanced_mode'])
CONFIG_INITIALIZED: bool = os.path.exists(CONFIG_PATH)

app = typer.Typer(
    context_settings={"help_option_names": ["-h", "--help"]},
    add_completion=False
)


@app.command()
def cli(
    question: Optional[str] = typer.Argument(
        None, show_default=False,
        help='通过自然语言提问'),
    shell: bool = typer.Option(
        False, '--shell', '-s',
        help='切换到 Shell 命令模式',
        rich_help_panel='选择问答模式'
    ),
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
) -> None:
    '''EulerCopilot 命令行助手'''
    if init:
        setup_copilot()
        return
    if backend:
        select_backend()
        return
    if settings:
        edit_config()
        return

    if sum(map(bool, [shell, chat, diagnose, tuning])) > 1:
        print('只能选择一种模式')
        return

    if shell:
        select_query_mode(0)
        if not question:
            return
    elif chat:
        select_query_mode(1)
        if not question:
            return
    elif diagnose and BACKEND == 'framework':
        select_query_mode(2)
        if not question:
            return
    elif tuning and BACKEND == 'framework':
        select_query_mode(3)
        if not question:
            return

    if question:
        question = question.strip()

    config = load_config()
    main(question, config)


def entry_point() -> None:
    app()


if __name__ == '__main__':
    entry_point()
