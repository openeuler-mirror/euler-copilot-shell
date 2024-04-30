# Copyright (c) Huawei Technologies Co., Ltd. 2024-2024. All rights reserved.
# pylint: disable=W0611

import os
import readline  # noqa: F401
import shlex
import sys
import uuid
from typing import Union

from backends import framework_api, llm_service, spark_api, openai_api
from utilities import config_manager, interact

EXIT_MESSAGE = "\033[33m>>>\033[0m 很高兴为您服务，下次再见～"


def execute_shell_command(cmd: str) -> None:
    """Execute a shell command and exit."""
    shell = os.environ.get("SHELL", "/bin/sh")
    full_command = f"{shell} -c {shlex.quote(cmd)}"
    os.system(full_command)


def handle_user_input(service: llm_service.LLMService,
                      user_input: str, mode: str) -> None:
    """Process user input based on the given flag and backend configuration."""
    if mode == 'shell':
        cmd = service.get_shell_answer(user_input)
        if cmd and interact.query_yes_or_no("\033[33m是否执行命令？\033[0m "):
            execute_shell_command(cmd)
        sys.exit(0)
    elif mode == 'chat':
        service.get_general_answer(user_input)


def main(user_input: Union[str, None]):
    config = config_manager.load_config()
    backend = config.get('backend')
    mode = config.get('query_mode')
    service: llm_service.LLMService = None
    if backend == 'framework':
        service = framework_api.Framework(
            url=config.get('framework_url'),
            api_key=config.get('framework_api_key'),
            session_id=str(uuid.uuid4().hex)
        )
    elif backend == 'spark':
        service = spark_api.Spark(
            app_id=config.get('spark_app_id'),
            api_key=config.get('spark_api_key'),
            api_secret=config.get('spark_api_secret'),
            spark_url=config.get('spark_url'),
            domain=config.get('spark_domain')
        )
    elif backend == 'openai':
        service = openai_api.OpenAI(
            url=config.get('model_url'),
            api_key=config.get('model_api_key'),
            model=config.get('model_name')
        )

    if service is None:
        sys.stderr.write("\033[1;31m未正确配置 LLM 后端，请检查配置文件\033[0m")
        sys.exit(1)

    if mode == 'shell':
        print("\033[33m当前模式：Shell 命令生成\033[0m")
    if mode == 'chat':
        print("\033[33m当前模式：智能问答\033[0m 输入 \"exit\" 或按下 Ctrl+C 退出服务")

    try:
        while True:
            if user_input is None:
                user_input = input("\033[35m>>>\033[0m ")
            if user_input.lower().startswith('exit'):
                print(EXIT_MESSAGE)
                sys.exit(0)
            handle_user_input(service, user_input, mode)
            user_input = None  # Reset user_input for next iteration (only if continuing service)
    except KeyboardInterrupt:
        print()
        sys.exit(0)
