# Copyright (c) Huawei Technologies Co., Ltd. 2024-2024. All rights reserved.

# pylint: disable=R0911,R0912,R0913

import os
import sys
from typing import Optional

import typer

from copilot.app.copilot_app import edit_config, main
from copilot.app.copilot_init import setup_copilot
from copilot.utilities.config_manager import (
    CONFIG_PATH,
    DEFAULT_CONFIG,
    QUERY_MODE_NAME,
    load_config,
    select_backend,
    select_query_mode,
)
from copilot.utilities.i18n import (
    BRAND_NAME,
    cli_help_panel_advanced_options,
    cli_help_panel_switch_mode,
    cli_help_prompt_edit_settings,
    cli_help_prompt_init_settings,
    cli_help_prompt_intro,
    cli_help_prompt_question,
    cli_help_prompt_select_backend,
    cli_help_prompt_switch_mode,
    cli_notif_compatibility,
    cli_notif_no_config,
    cli_notif_select_one_mode,
)

CONFIG: dict = load_config()
BACKEND: str = CONFIG.get('backend', DEFAULT_CONFIG['backend'])
ADVANCED_MODE: bool = CONFIG.get('advanced_mode', DEFAULT_CONFIG['advanced_mode'])
DEBUG_MODE: bool = CONFIG.get('debug_mode', DEFAULT_CONFIG['debug_mode'])
CONFIG_INITIALIZED: bool = os.path.exists(CONFIG_PATH)

app = typer.Typer(
    context_settings={
        'help_option_names': ['-h', '--help'],
        'allow_interspersed_args': True
    },
    pretty_exceptions_show_locals=DEBUG_MODE,
    add_completion=False
)


@app.command(help=f'{BRAND_NAME} CLI\n\n{cli_help_prompt_intro}')
def cli(
    question: Optional[str] = typer.Argument(
        None, show_default=False,
        help=cli_help_prompt_question),
    chat: bool = typer.Option(
        False, '--chat', '-c',
        help=cli_help_prompt_switch_mode.format(mode=QUERY_MODE_NAME["chat"]),
        rich_help_panel=cli_help_panel_switch_mode
    ),
    shell: bool = typer.Option(
        False, '--shell', '-s',
        help=cli_help_prompt_switch_mode.format(mode=QUERY_MODE_NAME["shell"]),
        rich_help_panel=cli_help_panel_switch_mode
    ),
    flow: bool = typer.Option(
        False, '--plugin', '-p',
        help=cli_help_prompt_switch_mode.format(mode=QUERY_MODE_NAME["flow"]),
        rich_help_panel=cli_help_panel_switch_mode,
        hidden=(BACKEND != 'framework'),
    ),
    diagnose: bool = typer.Option(
        False, '--diagnose', '-d',
        help=cli_help_prompt_switch_mode.format(mode=QUERY_MODE_NAME["diagnose"]),
        rich_help_panel=cli_help_panel_switch_mode,
        hidden=(BACKEND != 'framework')
    ),
    tuning: bool = typer.Option(
        False, '--tuning', '-t',
        help=cli_help_prompt_switch_mode.format(mode=QUERY_MODE_NAME["tuning"]),
        rich_help_panel=cli_help_panel_switch_mode,
        hidden=(BACKEND != 'framework')
    ),
    init: bool = typer.Option(
        False, '--init',
        help=cli_help_prompt_init_settings,
        hidden=(CONFIG_INITIALIZED)
    ),
    backend: bool = typer.Option(
        False, '--backend',
        help=cli_help_prompt_select_backend,
        rich_help_panel=cli_help_panel_advanced_options,
        hidden=(not ADVANCED_MODE)
    ),
    settings: bool = typer.Option(
        False, '--settings',
        help=cli_help_prompt_edit_settings,
        rich_help_panel=cli_help_panel_advanced_options,
        hidden=(not ADVANCED_MODE)
    )
) -> int:
    if init:
        setup_copilot()
        return 0
    if not CONFIG_INITIALIZED:
        print(f'\033[1;31m{cli_notif_no_config}\033[0m')
        return 1
    if backend:
        if ADVANCED_MODE:
            select_backend()
        return 0
    if settings:
        if ADVANCED_MODE:
            edit_config()
        return 0

    if sum(map(bool, [chat, flow, diagnose, tuning])) > 1:
        print(f'\033[1;31m{cli_notif_select_one_mode}\033[0m')
        return 1

    if chat:
        select_query_mode(0)
        if not question:
            return 0
    elif shell:
        select_query_mode(1)
        if not question:
            return 0
    elif flow:
        if BACKEND == 'framework':
            select_query_mode(2)
            if not question:
                return 0
        else:
            compatibility_notification(QUERY_MODE_NAME['flow'])
            return 1
    elif diagnose:
        if BACKEND == 'framework':
            select_query_mode(3)
            if not question:
                return 0
        else:
            compatibility_notification(QUERY_MODE_NAME['diagnose'])
            return 1
    elif tuning:
        if BACKEND == 'framework':
            select_query_mode(4)
            if not question:
                return 0
        else:
            compatibility_notification(QUERY_MODE_NAME['tuning'])
            return 1

    if question:
        question = question.strip()

    return main(question, load_config())


def compatibility_notification(mode: str):
    print('\033[33m', cli_notif_compatibility.format(mode=mode, brand_name=BRAND_NAME),
          '\033[0m', sep='')


def entry_point() -> int:
    return app()


if __name__ == '__main__':
    code = entry_point()
    sys.exit(code)
