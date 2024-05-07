# Copyright (c) Huawei Technologies Co., Ltd. 2024-2024. All rights reserved.

import json
import sys

import requests
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.spinner import Spinner

from backends.llm_service import LLMService


class Framework(LLMService):
    def __init__(self, url, api_key, session_id):
        self.endpoint: str = url
        self.api_key: str = api_key
        self.session_id: str = session_id
        self.content: str = ""
        # 富文本显示
        self.console = Console()

    def get_general_answer(self, question: str) -> str:
        headers = self._get_headers()
        data = {"question": question, "session_id": self.session_id}
        self._stream_response(headers, data)
        return self.content

    def get_shell_answer(self, question: str) -> str:
        query = "请用单行shell命令回答以下问题：\n" + question + \
            "\n\n请直接以纯文本形式回复shell命令，不要添加任何多余内容。\n" + \
            "请注意你是 openEuler 的小助手，你所回答的命令必须被 openEuler 系统支持"
        return self._extract_shell_code_blocks(self.get_general_answer(query))

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

    def _get_headers(self) -> dict:
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
            'Authorization': f'Bearer {self.api_key}'
        }
