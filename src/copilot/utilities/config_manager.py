# Copyright (c) Huawei Technologies Co., Ltd. 2024-2024. All rights reserved.

import json
import os

from copilot.backends.framework_api import QUERY_MODS
from copilot.utilities import interact

CONFIG_DIR = os.path.join(os.path.expanduser('~'), '.config/eulercopilot')
CONFIG_PATH = os.path.join(CONFIG_DIR, 'config.json')

DEFAULT_CONFIG = {
    'backend': 'framework',
    'query_mode': 'chat',
    'advanced_mode': False,
    'debug_mode': False,
    'spark_app_id': '',
    'spark_api_key': '',
    'spark_api_secret': '',
    'spark_url': 'wss://spark-api.xf-yun.com/v3.5/chat',
    'spark_domain': 'generalv3.5',
    'framework_url': '',
    'framework_api_key': '',
    'model_url': '',
    'model_api_key': '',
    'model_name': ''
}


def load_config() -> dict:
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as file:
            config = json.load(file)
    except FileNotFoundError:
        init_config()
        config = load_config()
    return config


def write_config(config):
    with open(CONFIG_PATH, 'w', encoding='utf-8') as json_file:
        json.dump(config, json_file, indent=4)
        json_file.write('\n')  # 追加一行空行


def init_config():
    if not os.path.exists(CONFIG_DIR):
        os.makedirs(CONFIG_DIR)
    write_config(DEFAULT_CONFIG)


def update_config(key: str, value):
    if key not in DEFAULT_CONFIG:
        return
    config = load_config()
    config.update({key: value})
    write_config(config)


def select_query_mode(mode: int):
    modes = list(QUERY_MODS.keys())
    if mode < len(modes):
        update_config('query_mode', modes[mode])


def select_backend():
    backend = interact.select_backend()
    if backend in ['framework', 'spark', 'openai']:
        update_config('backend', backend)


def edit_config():
    config = load_config()
    print('\n\033[1;33m当前设置：\033[0m')
    format_string = '{:<32} {}'.format
    for key, value in config.items():
        print(f'- {format_string(key, value)}')

    print('\n\033[33m输入要修改的设置项以修改设置：\033[0m')
    print('示例：')
    print('>>> spark_api_key（按下回车）')
    print('<<< （在此处输入你的星火大模型 API Key）')
    print('* 输入空白值以退出程序')
    print('* 建议在管理员指导下操作')
    try:
        while True:
            key = input('\033[35m>>>\033[0m ')
            if key in config:
                value = input('\033[33m<<<\033[0m ')
                if value == '':
                    break
                config[key] = value
            elif key == '':
                break
            else:
                print('输入有误，请重试')
    except KeyboardInterrupt:
        print('\n\033[1;31m用户已取消编辑\033[0m\n')
