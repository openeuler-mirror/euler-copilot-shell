# Copyright (c) Huawei Technologies Co., Ltd. 2024-2024. All rights reserved.

import argparse

from app.copilot_app import main
from app.copilot_init import setup_copilot
from utilities.config_manager import edit_config, load_config, select_backend, select_query_mode, DEFAULT_CONFIG

CONFIG: dict = load_config()
BACKEND: str = CONFIG.get('backend', DEFAULT_CONFIG['backend'])
ADVANCED_MODE: bool = CONFIG.get('advanced_mode', DEFAULT_CONFIG['advanced_mode'])


def _parse_arguments():
    parser = argparse.ArgumentParser(prog="copilot", description="EulerCopilot 命令行助手")
    parser.add_argument("user_input", nargs="?", default=None, help="用自然语言提问")
    parser.add_argument("--init", action="store_true", help="初始化 copilot 设置")
    parser.add_argument("--shell", "-s", action="store_true", help="切换到 Shell 命令模式")
    parser.add_argument("--chat", "-c", action="store_true", help="切换到智能问答模式")
    if BACKEND == 'framework':
        parser.add_argument("--diagnose", "-d", action="store_true", help="切换到智能诊断模式")
        parser.add_argument("--tuning", "-t", action="store_true", help="切换到智能调优模式")
    if ADVANCED_MODE:
        parser.add_argument("--backend", action="store_true", help="选择大语言模型后端")
        parser.add_argument("--settings", action="store_true", help="编辑 copilot 设置")
    return parser.parse_args()


def run_command_line():
    args = _parse_arguments()

    if args.init:
        setup_copilot()
    elif args.shell:
        select_query_mode(0)
    elif args.chat:
        select_query_mode(1)
    elif BACKEND == 'framework':
        if args.diagnose:
            select_query_mode(2)
        elif args.tuning:
            select_query_mode(3)
    elif ADVANCED_MODE:
        if args.backend:
            select_backend()
        elif args.settings:
            edit_config()
    else:
        main(args.user_input, CONFIG)
