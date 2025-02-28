# Copyright (c) Huawei Technologies Co., Ltd. 2024-2025. All rights reserved.

import sys
from pathlib import Path
from typing import Optional

import typer

from copilot.app.copilot_app import edit_config, main
from copilot.app.copilot_init import setup_copilot
from copilot.utilities.config_manager import (
    QUERY_MODE_NAME,
    Config,
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

CONFIG: Config = Config()
BACKEND: str = CONFIG.data.backend
ADVANCED_MODE: bool = CONFIG.data.advanced_mode
DEBUG_MODE: bool = CONFIG.data.debug_mode
CONFIG_INITIALIZED: bool = Path(CONFIG.config_path).exists()

app = typer.Typer(
    context_settings={
        "help_option_names": ["-h", "--help"],
        "allow_interspersed_args": True,
    },
    pretty_exceptions_show_locals=DEBUG_MODE,
    add_completion=False,
)


@app.command(help=f"{BRAND_NAME} CLI\n\n{cli_help_prompt_intro}")
def cli(
    question: Optional[str] = typer.Argument(None, show_default=False, help=cli_help_prompt_question),
    chat: bool = typer.Option(
        False,
        "--chat",
        "-c",
        help=cli_help_prompt_switch_mode.format(mode=QUERY_MODE_NAME["chat"]),
        rich_help_panel=cli_help_panel_switch_mode,
    ),
    shell: bool = typer.Option(
        False,
        "--shell",
        "-s",
        help=cli_help_prompt_switch_mode.format(mode=QUERY_MODE_NAME["shell"]),
        rich_help_panel=cli_help_panel_switch_mode,
    ),
    plugin: bool = typer.Option(
        False,
        "--plugin",
        "-p",
        help=cli_help_prompt_switch_mode.format(mode=QUERY_MODE_NAME["plugin"]),
        rich_help_panel=cli_help_panel_switch_mode,
        hidden=(BACKEND != "framework"),
    ),
    diagnose: bool = typer.Option(
        False,
        "--diagnose",
        "-d",
        help=cli_help_prompt_switch_mode.format(mode=QUERY_MODE_NAME["diagnose"]),
        rich_help_panel=cli_help_panel_switch_mode,
        hidden=(BACKEND != "framework"),
    ),
    tuning: bool = typer.Option(
        False,
        "--tuning",
        "-t",
        help=cli_help_prompt_switch_mode.format(mode=QUERY_MODE_NAME["tuning"]),
        rich_help_panel=cli_help_panel_switch_mode,
        hidden=(BACKEND != "framework"),
    ),
    init: bool = typer.Option(
        False,
        "--init",
        help=cli_help_prompt_init_settings,
        hidden=(CONFIG_INITIALIZED),
    ),
    backend: bool = typer.Option(
        False,
        "--backend",
        help=cli_help_prompt_select_backend,
        rich_help_panel=cli_help_panel_advanced_options,
        hidden=(not ADVANCED_MODE),
    ),
    settings: bool = typer.Option(
        False,
        "--settings",
        help=cli_help_prompt_edit_settings,
        rich_help_panel=cli_help_panel_advanced_options,
        hidden=(not ADVANCED_MODE),
    ),
) -> int:
    if init:
        setup_copilot()
        return 0
    if not CONFIG_INITIALIZED:
        print(f"\033[1;31m{cli_notif_no_config}\033[0m")
        return 1
    if backend:
        if ADVANCED_MODE:
            CONFIG.select_backend()
        return 0
    if settings:
        if ADVANCED_MODE:
            edit_config()
        return 0

    if sum(map(bool, [chat, plugin, diagnose, tuning])) > 1:
        print(f"\033[1;31m{cli_notif_select_one_mode}\033[0m")
        return 1

    if chat:
        CONFIG.select_query_mode(0)
        if not question:
            return 0
    elif shell:
        CONFIG.select_query_mode(1)
        if not question:
            return 0
    elif plugin:
        if BACKEND == "framework":
            CONFIG.select_query_mode(2)
            if not question:
                return 0
        else:
            compatibility_notification(QUERY_MODE_NAME["plugin"])
            return 1
    elif diagnose:
        if BACKEND == "framework":
            CONFIG.select_query_mode(3)
            if not question:
                return 0
        else:
            compatibility_notification(QUERY_MODE_NAME["diagnose"])
            return 1
    elif tuning:
        if BACKEND == "framework":
            CONFIG.select_query_mode(4)
            if not question:
                return 0
        else:
            compatibility_notification(QUERY_MODE_NAME["tuning"])
            return 1

    if question:
        question = question.strip()

    return main(question)


def compatibility_notification(mode: str) -> None:
    print("\033[33m", cli_notif_compatibility.format(mode=mode, brand_name=BRAND_NAME), "\033[0m", sep="")


def entry_point() -> int:
    return app()


if __name__ == "__main__":
    code = entry_point()
    sys.exit(code)
