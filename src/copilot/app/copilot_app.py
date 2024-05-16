# Copyright (c) Huawei Technologies Co., Ltd. 2024-2024. All rights reserved.

# pylint: disable=W0611

import re
import readline  # noqa: F401
import shlex
import subprocess
import sys
import uuid
from typing import Union

from copilot.backends import framework_api, llm_service, openai_api, spark_api
from copilot.utilities import interact


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
            print(f'执行命令时出错：{e}')
            return 1
    else:
        try:
            process = subprocess.Popen(shlex.split(cmd))
        except FileNotFoundError as e:
            print(f'命令不存在：{e}')
            return 1
    exit_code = process.wait()
    return exit_code


def handle_user_input(service: llm_service.LLMService,
                      user_input: str, mode: str) -> None:
    '''Process user input based on the given flag and backend configuration.'''
    if mode == 'shell':
        cmd = service.get_shell_answer(user_input)
        exit_code: int = 0
        if cmd and interact.query_yes_or_no('\n\033[33m是否执行命令？\033[0m '):
            exit_code = execute_shell_command(cmd)
        sys.exit(exit_code)
    elif mode == 'chat':
        service.get_general_answer(user_input)


def exit_copilot(msg: str = '', code: int = 0):
    '''Exit the program with a message.'''
    print(msg)
    sys.exit(code)


def main(user_input: Union[str, None], config: dict):
    backend = config.get('backend')
    mode = str(config.get('query_mode'))
    service: Union[llm_service.LLMService, None] = None
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
        service = openai_api.ChatOpenAI(
            url=str(config.get('model_url')),
            api_key=config.get('model_api_key'),
            model=config.get('model_name')
        )

    if service is None:
        exit_copilot('\033[1;31m未正确配置 LLM 后端，请检查配置文件\033[0m', 1)
    else:
        if mode == 'shell':
            print('\033[33m当前模式：Shell 命令生成\033[0m')
        if mode == 'chat':
            print('\033[33m当前模式：智能问答\033[0m 输入 \'exit\' 或按下 Ctrl+C 退出服务')
        try:
            while True:
                if user_input is None:
                    user_input = input('\033[35m>>>\033[0m ')
                if user_input.lower().startswith('exit'):
                    exit_copilot()
                handle_user_input(service, user_input, mode)
                user_input = None  # Reset user_input for next iteration (only if continuing service)
        except KeyboardInterrupt:
            exit_copilot()
