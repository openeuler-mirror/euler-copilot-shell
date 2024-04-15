# Copyright (c) Huawei Technologies Co., Ltd. 2024-2024. All rights reserved.

import json
import os
import sys

import requests
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.spinner import Spinner

from backends.llm_service import LLMService

CONFIG_PATH = "/eulercopilot"
COOKIE_CONFIG = os.path.join(CONFIG_PATH, "cookie")
CSRF_CONFIG = os.path.join(CONFIG_PATH, "csrf")

BASE_DOMAIN = "qa-robot-openeuler.test.osinfra.cn"
BASE_URL = f"https://{BASE_DOMAIN}"


class Framework(LLMService):
    def __init__(self, url, api_key, session_id):
        self.endpoint: str = url
        self.api_key: str = api_key
        self.session_id: str = session_id
        self.content: str = ""
        # 富文本显示
        self.console = Console()

    def get_general_answer(self, question: str) -> str:
        self.endpoint = f"{BASE_URL}/stream/get_stream_answer"
        cookie = self._read_config(COOKIE_CONFIG)
        csrf_token = self._read_config(CSRF_CONFIG)

        headers = self._get_headers(cookie, csrf_token)

        user_url = f"{BASE_URL}/rag/authorize/user"
        r = requests.request("GET", user_url, data="", headers=headers, timeout=10)
        if r.status_code != 200:
            sys.stderr.write(f"{r.status_code} 登录凭证已过期，请重新登录\n")

        data = {"question": question, "session_id": self.session_id}
        self._stream_response(headers, data)

        return self.content

    def get_shell_answer(self, question: str) -> str:
        question = "请用单行shell命令回答以下问题：\n" + question + \
            "\n\n请直接以纯文本形式回复shell命令，不要添加任何多余内容。\n" + \
            "请注意你是 openEuler 的小助手，你所回答的命令必须被 openEuler 系统支持"
        return self.get_general_answer(question).replace("`", "")

    def _stream_response(self, headers, data):
        spinner = Spinner('material')
        with Live(console=self.console) as live:
            live.update(spinner, refresh=True)
            response = requests.post(
                self.endpoint,
                headers=headers,
                json=data,
                stream=True,
                timeout=60
            )
            if response.status_code != 200:
                sys.stderr.write(f"{response.status_code} 请求失败\n")
                return
            for line in response.iter_lines():
                if line is None:
                    continue
                content = line.decode('utf-8').strip("data: ")
                try:
                    jcontent = json.loads(content)
                except json.JSONDecodeError:
                    continue
                else:
                    chunk = jcontent.get("content", "")
                    self.content += chunk
                    live.update(Markdown(self.content, code_theme='github-dark'), refresh=True)

    def _read_config(self, config_name: str) -> str:
        try:
            with open(config_name, "r", encoding="utf-8") as c:
                return c.read().strip()
        except FileNotFoundError:
            with open(config_name, "w", encoding="utf-8") as c:
                return ""

    def _get_headers(self, cookie: str, csrf_token: str) -> dict:
        return {
            "Accept": "application/json",
            "Accept-Language": "zh-CN,zh-Hans,en-US;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Content-Type": "application/json",
            "Cookie": cookie,
            "X-CSRF-Token": csrf_token
        }
