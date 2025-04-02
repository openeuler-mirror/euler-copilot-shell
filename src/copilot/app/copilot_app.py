# Copyright (c) Huawei Technologies Co., Ltd. 2024-2025. All rights reserved.

import re
import readline
import shlex
import subprocess
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text

from copilot.backends import framework_api, llm_service, openai_api, spark_api
from copilot.utilities import i18n, interact
from copilot.utilities.config_manager import CONFIG_ENTRY_NAME, Config

CONFIG: Config = Config()

selected_plugins: list = []


def check_shell_features(cmd: str) -> bool:
    """Check if the shell command contains special features."""
    patterns = [
        # 重定向
        r"\>|\<|\>\>|\<<",
        # 管道
        r"\|",
        # 通配符
        r"\*|\?",
        # 美元符号开头的环境变量
        r"\$[\w_]+",
        # 历史展开
        r"!",
        # 后台运行符号
        r"&",
        # 分号
        r";",
        # 括号命令分组
        r"\(|\)|\{|\}",
        # 逻辑操作符
        r"&&|\|\|",
        # Shell函数或变量赋值
        r"\b\w+\s*=\s*[^=\s]+",
    ]
    return any(re.search(pattern, cmd) for pattern in patterns)


def execute_shell_command(cmd: str) -> int:
    """Execute a shell command and exit."""
    if check_shell_features(cmd):
        try:
            process = subprocess.Popen(cmd, shell=True)  # noqa: S602
        except ValueError as e:
            print(i18n.main_exec_value_error.format(error=e))  # noqa: T201
            return 1
    else:
        try:
            process = subprocess.Popen(shlex.split(cmd))  # noqa: S603
        except FileNotFoundError as e:
            builtin_cmds = [".", "source", "history", "cd", "export", "alias", "test"]
            cmd_prefix = cmd.split()[0]
            if cmd_prefix in builtin_cmds:
                print(i18n.main_exec_builtin_cmd.format(cmd_prefix=cmd_prefix))  # noqa: T201
            else:
                print(i18n.main_exec_not_found_error.format(error=e))  # noqa: T201
            return 1
    return process.wait()


def print_shell_commands(cmds: list) -> None:
    """Display shell commands in a formatted panel."""
    console = Console()
    with Live(console=console, vertical_overflow="visible") as live:
        live.update(
            Panel(
                Markdown(
                    "```bash\n" + "\n\n".join(cmds) + "\n```",
                    code_theme="github-dark",
                ),
                border_style="gray50",
            ),
        )


def command_interaction_loop(cmds: list, service: llm_service.LLMService) -> int:
    """Interact with the user to select and execute shell commands."""
    if not cmds:
        return -1
    print_shell_commands(cmds)
    while True:
        action = interact.select_action(len(cmds) > 1)
        if action in ("execute_all", "execute_selected", "execute"):
            exit_code: int = 0
            selected_cmds = get_selected_cmds(cmds, action)
            if not selected_cmds:
                return -1
            for cmd in selected_cmds:
                exit_code = execute_shell_command(cmd)
                if exit_code != 0:
                    print(  # noqa: T201
                        i18n.main_exec_cmd_failed_with_exit_code.format(
                            cmd=cmd,
                            exit_code=exit_code,
                        ),
                    )
                    break
            return -1
        if action == "explain":
            service.explain_shell_command(select_one_cmd(cmds))
        elif action == "edit":
            selected_cmd_idx = select_one_cmd_with_index(cmds)
            readline.set_startup_hook(lambda idx=selected_cmd_idx: readline.insert_text(cmds[idx]))
            try:
                cmds[selected_cmd_idx] = input()
            finally:
                readline.set_startup_hook()
            print_shell_commands(cmds)
        elif action == "cancel":
            return -1


def handle_python_code_block(code: str) -> None:
    """Handle Python code blocks in Markdown."""
    console = Console()
    input_prompt = i18n.interact_question_input_file_name
    file_name = console.input(__stylized_input_prompt(input_prompt)).removesuffix(".py") + ".py"
    with Path(file_name).open("w", encoding="utf-8") as f:
        f.write(code)


def get_selected_cmds(cmds: list, action: str) -> list:
    """Retrieve commands based on the specified action."""
    if action in ("execute", "execute_all"):
        return cmds
    if action == "execute_selected":
        return interact.select_multiple_commands(cmds)
    return []


def select_one_cmd(cmds: list) -> str:
    """Select one command from the list based on user input."""
    if len(cmds) == 1:
        return cmds[0]
    return interact.select_command(cmds)


def select_one_cmd_with_index(cmds: list) -> int:
    """Select one command with its index from the list based on user input."""
    if len(cmds) == 1:
        return 0
    return interact.select_command_with_index(cmds)


def handle_user_input(service: llm_service.LLMService, user_input: str, mode: str) -> int:
    """Process user input based on the given flag and backend configuration."""
    result: llm_service.LLMService.LLMResult = llm_service.LLMService.LLMResult(None, None)
    if mode == "chat":
        result = service.get_llm_result(user_input)
    if mode == "shell":
        result = service.get_llm_result(user_input, single_line_cmd=True)
    if isinstance(service, framework_api.Framework):
        if mode == "plugin":
            result = service.plugin(user_input, selected_plugins)
        if mode == "diagnose":
            result = service.diagnose(user_input)
        if mode == "tuning":
            result = service.tuning(user_input)
    if result.code and interact.ask_boolean(i18n.interact_question_save_python_code):
        handle_python_code_block(result.code)
    if result.cmds:
        return command_interaction_loop(result.cmds, service)
    return -1


def edit_config() -> None:
    """Edit the configuration settings."""
    console = Console()
    with Live(console=console) as live:
        live.update(Panel(Markdown(CONFIG.to_markdown(), code_theme="github-dark"), border_style="gray50"))
    while True:
        selected_entry = interact.select_settings_entry()
        if selected_entry == "cancel":
            return
        if selected_entry == "backend":
            backend = interact.select_backend()
            if selected_entry != "cancel":
                CONFIG.update(selected_entry, backend)
        elif selected_entry == "query_mode":
            CONFIG.update(selected_entry, interact.select_query_mode(CONFIG.data.backend))
        elif selected_entry in ("advanced_mode", "debug_mode"):
            input_prompt = i18n.interact_question_yes_or_no.format(question_body=CONFIG_ENTRY_NAME.get(selected_entry))
            CONFIG.update(selected_entry, interact.ask_boolean(input_prompt))
        else:
            original_text: str = CONFIG.data.to_dict().get(selected_entry, "")
            new_text = ""
            input_prompt = i18n.interact_question_input_text.format(question_body=CONFIG_ENTRY_NAME.get(selected_entry))
            readline.set_startup_hook(lambda text=original_text: readline.insert_text(text))
            try:
                new_text = console.input(__stylized_input_prompt(input_prompt))
            finally:
                readline.set_startup_hook()
                CONFIG.update(selected_entry, new_text)


def main(user_input: Optional[str]) -> int:
    """Handle user input and interact with the backend service.

    :param user_input: The user input string.
    :return: The exit code.
    """
    backend = CONFIG.data.backend
    mode = CONFIG.data.query_mode
    service: Optional[llm_service.LLMService] = __create_llm_service(backend)
    if service is None:
        print(f"\033[1;31m{i18n.main_service_is_none}\033[0m")  # noqa: T201
        return 1

    if not __initialize_service(service, mode):
        return 1

    print(f"\033[33m{i18n.main_exit_prompt}\033[0m")  # noqa: T201

    return __process_user_input(service, user_input, mode)


def __initialize_service(service: llm_service.LLMService, mode: str) -> bool:
    """Initialize the service and handle plugin selection if needed."""
    global selected_plugins
    if isinstance(service, framework_api.Framework):
        if not service.update_session_id() or not service.create_new_conversation():
            return False
        if mode == "plugin":  # get plugin list from current backend
            plugins: list[framework_api.PluginData] = service.get_plugins()
            if not plugins:
                print(f"\033[1;31m{i18n.main_service_framework_plugin_is_none}\033[0m")  # noqa: T201
                return False
            selected_plugins = [interact.select_one_plugin(plugins)]
    return True


def __process_user_input(service: llm_service.LLMService, user_input: Optional[str], mode: str) -> int:
    """Process the user input and interact with the service."""
    try:
        while True:
            if user_input is None:
                user_input = input("\033[35m❯\033[0m ")
            if user_input.lower().startswith("exit"):
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


def __create_llm_service(backend: str) -> Optional[llm_service.LLMService]:
    if backend == "framework":
        return framework_api.Framework(
            url=CONFIG.data.framework_url,
            api_key=CONFIG.data.framework_api_key,
            debug_mode=CONFIG.data.debug_mode,
        )
    if backend == "spark":
        return spark_api.Spark(
            app_id=CONFIG.data.spark_app_id,
            api_key=CONFIG.data.spark_api_key,
            api_secret=CONFIG.data.spark_api_secret,
            spark_url=CONFIG.data.spark_url,
            domain=CONFIG.data.spark_domain,
        )
    if backend == "openai":
        return openai_api.ChatOpenAI(
            url=str(CONFIG.data.model_url),
            api_key=CONFIG.data.model_api_key,
            model=CONFIG.data.model_name,
        )
    return None


def __stylized_input_prompt(prompt_text: str) -> Text:
    return Text("❯ ", style="#005f87 bold").append(prompt_text, style="bold")
