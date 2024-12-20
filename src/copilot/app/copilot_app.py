# Copyright (c) Huawei Technologies Co., Ltd. 2024-2024. All rights reserved.

# pylint: disable=W0611

import re
import readline  # noqa: F401
import shlex
import subprocess
from typing import Optional

from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text

from copilot.backends import framework_api, llm_service, openai_api, spark_api
from copilot.utilities import i18n, interact
from copilot.utilities.config_manager import CONFIG_ENTRY_NAME, config_to_markdown, load_config, update_config

selected_plugins: list = []


def check_shell_features(cmd: str) -> bool:
    patterns = [
        # 重定向
        r'\>|\<|\>\>|\<<',
        # 管道
        r'\|',
        # 通配符
        r'\*|\?',
        # 美元符号开头的环境变量
        r'\$[\w_]+',
        # 历史展开
        r'!',
        # 后台运行符号
        r'&',
        # 分号
        r';',
        # 括号命令分组
        r'\(|\)|\{|\}',
        # 逻辑操作符
        r'&&|\|\|',
        # Shell函数或变量赋值
        r'\b\w+\s*=\s*[^=\s]+'
    ]

    for pattern in patterns:
        if re.search(pattern, cmd):
            return True
    return False


def execute_shell_command(cmd: str) -> int:
    '''Execute a shell command and exit.'''
    if check_shell_features(cmd):
        try:
            process = subprocess.Popen(cmd, shell=True)
        except ValueError as e:
            print(i18n.main_exec_value_error.format(error=e))
            return 1
    else:
        try:
            process = subprocess.Popen(shlex.split(cmd))
        except FileNotFoundError as e:
            builtin_cmds = ['.', 'source', 'history', 'cd', 'export', 'alias', 'test']
            cmd_prefix = cmd.split()[0]
            if cmd_prefix in builtin_cmds:
                print(i18n.main_exec_builtin_cmd.format(cmd_prefix=cmd_prefix))
            else:
                print(i18n.main_exec_not_found_error.format(error=e))
            return 1
    exit_code = process.wait()
    return exit_code


def print_shell_commands(cmds: list):
    console = Console()
    with Live(console=console, vertical_overflow='visible') as live:
        live.update(
            Panel(
                Markdown(
                    '```bash\n' + '\n\n'.join(cmds) + '\n```',
                    code_theme='github-dark'
                ),
                border_style='gray50'
            )
        )


def command_interaction_loop(cmds: list, service: llm_service.LLMService) -> int:
    if not cmds:
        return -1
    print_shell_commands(cmds)
    while True:
        action = interact.select_action(len(cmds) > 1)
        if action in ('execute_all', 'execute_selected', 'execute'):
            exit_code: int = 0
            selected_cmds = get_selected_cmds(cmds, action)
            if not selected_cmds:
                return -1
            for cmd in selected_cmds:
                exit_code = execute_shell_command(cmd)
                if exit_code != 0:
                    print(
                        i18n.main_exec_cmd_failed_with_exit_code.format(
                            cmd=cmd,
                            exit_code=exit_code
                        )
                    )
                    break
            return -1
        if action == 'explain':
            service.explain_shell_command(select_one_cmd(cmds))
        elif action == 'edit':
            i = select_one_cmd_with_index(cmds)
            readline.set_startup_hook(lambda: readline.insert_text(cmds[i]))
            try:
                cmds[i] = input()
            finally:
                readline.set_startup_hook()
            print_shell_commands(cmds)
        elif action == 'cancel':
            return -1


def get_selected_cmds(cmds: list, action: str) -> list:
    if action in ('execute', 'execute_all'):
        return cmds
    if action == 'execute_selected':
        return interact.select_multiple_commands(cmds)
    return []


def select_one_cmd(cmds: list) -> str:
    if len(cmds) == 1:
        return cmds[0]
    return interact.select_command(cmds)


def select_one_cmd_with_index(cmds: list) -> int:
    if len(cmds) == 1:
        return 0
    return interact.select_command_with_index(cmds)


def handle_user_input(service: llm_service.LLMService,
                      user_input: str, mode: str) -> int:
    '''Process user input based on the given flag and backend configuration.'''
    cmds: list = []
    if mode == 'chat':
        cmds = service.get_shell_commands(user_input)
    if isinstance(service, framework_api.Framework):
        if mode == 'flow':
            cmds = service.flow(user_input, selected_plugins)
        if mode == 'diagnose':
            cmds = service.diagnose(user_input)
        if mode == 'tuning':
            cmds = service.tuning(user_input)
    if cmds:
        return command_interaction_loop(cmds, service)
    return -1


def edit_config():
    console = Console()
    with Live(console=console) as live:
        live.update(
            Panel(Markdown(config_to_markdown(), code_theme='github-dark'),
                  border_style='gray50'))
    while True:
        selected_entry = interact.select_settings_entry()
        if selected_entry == 'cancel':
            return
        if selected_entry == 'backend':
            backend = interact.select_backend()
            if selected_entry != 'cancel':
                update_config(selected_entry, backend)
        elif selected_entry == 'query_mode':
            backend = load_config().get('backend', '')
            update_config(selected_entry, interact.select_query_mode(backend))
        elif selected_entry in ('advanced_mode', 'debug_mode'):
            input_prompt = i18n.interact_question_yes_or_no.format(
                question_body=CONFIG_ENTRY_NAME.get(selected_entry))
            update_config(selected_entry, interact.ask_boolean(input_prompt))
        else:
            original_text: str = load_config().get(selected_entry, '')
            new_text = ''
            input_prompt = i18n.interact_question_input_text.format(
                question_body=CONFIG_ENTRY_NAME.get(selected_entry))
            stylized_input_prompt = Text('❯ ', style='#005f87 bold')\
                .append(input_prompt, style='bold')
            readline.set_startup_hook(lambda: readline.insert_text(original_text))
            try:
                new_text = console.input(stylized_input_prompt)
            finally:
                readline.set_startup_hook()
                update_config(selected_entry, new_text)


# pylint: disable=W0603
def main(user_input: Optional[str], config: dict) -> int:
    global selected_plugins
    backend = config.get('backend')
    mode = str(config.get('query_mode'))
    service: Optional[llm_service.LLMService] = None
    if backend == 'framework':
        service = framework_api.Framework(
            url=config.get('framework_url'),
            api_key=config.get('framework_api_key'),
            debug_mode=config.get('debug_mode', False)
        )
        service.update_session_id()  # get "ECSESSION" cookie
        service.create_new_conversation()  # get conversation_id from backend
        if mode == 'flow':  # get plugin list from current backend
            plugins: list[framework_api.PluginData] = service.get_plugins()
            if not plugins:
                print(f'\033[1;31m{i18n.main_service_framework_plugin_is_none}\033[0m')
                return 1
            selected_plugins = [interact.select_one_plugin(plugins)]
    elif backend == 'spark':
        service = spark_api.Spark(
            app_id=config.get('spark_app_id'),
            api_key=config.get('spark_api_key'),
            api_secret=config.get('spark_api_secret'),
            spark_url=config.get('spark_url'),
            domain=config.get('spark_domain')
        )
    elif backend == 'openai':
        service = openai_api.ChatOpenAI(
            url=str(config.get('model_url')),
            api_key=config.get('model_api_key'),
            model=config.get('model_name')
        )

    if service is None:
        print(f'\033[1;31m{i18n.main_service_is_none}\033[0m')
        return 1

    print(f'\033[33m{i18n.main_exit_prompt}\033[0m')

    try:
        while True:
            if user_input is None:
                user_input = input('\033[35m❯\033[0m ')
            if user_input.lower().startswith('exit'):
                return 0
            exit_code = handle_user_input(service, user_input, mode)
            if exit_code != -1:
                return exit_code
            user_input = None  # Reset user_input for next iteration (only if continuing service)
    except KeyboardInterrupt:
        if isinstance(service, framework_api.Framework):
            service.stop()
        print()
        return 0
