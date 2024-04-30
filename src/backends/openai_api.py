# Copyright (c) Huawei Technologies Co., Ltd. 2024-2024. All rights reserved.

import json
import sys
import re

import requests
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.spinner import Spinner
from utilities.os_info import get_os_info

from backends.llm_service import LLMService


class OpenAI(LLMService):
    def __init__(self, url, api_key, model = 'qwen-7b', max_tokens = 2048):
        self.url: str = url
        self.api_key: str = api_key
        self.model: str = model
        self.max_tokens: int = max_tokens
        self.answer: str = ''
        self.history: list = []
        # 富文本显示
        self.console = Console()

    def get_general_answer(self, question: str) -> str:
        self._stream_response(question)
        return self.answer

    def get_shell_answer(self, question: str) -> str:
        query = f'请用单行shell命令回答以下问题：\n{question}\n\
        \n要求：\n请直接回复命令，不要添加任何多余内容；\n\
        当前操作系统是：{get_os_info()}，请返回符合当前系统要求的命令。'
        return self._extract_shell_code_blocks(self.get_general_answer(query))

    def _get_length(self, context: list) -> int:
        length = 0
        for content in context:
            temp = content['content']
            leng = len(temp)
            length += leng
        return length

    def _check_len(self, context: list) -> list:
        while self._get_length(context) > self.max_tokens / 2:
            del context[0]
        return context

    def _gen_params(self, query: str, stream: bool = True):
        self.history.append({'content': query, 'role': 'user'})
        history = self._check_len(
            self.history if len(self.history) < 5 else self.history[-5:]
        )
        return {
            'messages': history,
            'model': self.model,
            'stream': stream,
            'max_tokens': self.max_tokens,
            'temperature': 0.7,
            'top_p': 0.95
        }

    def _gen_headers(self):
        return {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.api_key}'
        }

    def _stream_response(self, query: str):
        spinner = Spinner('material')
        self.answer = ''
        with Live(console=self.console) as live:
            live.update(spinner, refresh=True)
            response = requests.post(
                self.url,
                headers=self._gen_headers(),
                data=json.dumps(self._gen_params(query)),
                stream=True,
                timeout=60
            )
            if response.status_code != 200:
                sys.stderr.write(f'{response.status_code} 请求失败\n')
                return
            for line in response.iter_lines():
                if line is None:
                    continue
                content = line.decode('utf-8').strip('data: ')
                try:
                    jcontent = json.loads(content)
                except json.JSONDecodeError:
                    continue
                else:
                    chunk = jcontent['choices'][0]['delta']['content']
                    finish_reason = jcontent['choices'][0]['finish_reason']
                    self.answer += chunk
                    live.update(Markdown(self.answer, code_theme='github-dark'), refresh=True)
                    if finish_reason == 'stop':
                        self.history.append({'content': self.answer, 'role': 'assistant'})
                        break

    def _extract_shell_code_blocks(self, markdown_text):
        shell_code_pattern = re.compile(r'```shell\n(?P<code>(?:\n|.)*?)\n```', re.DOTALL)
        matches = shell_code_pattern.finditer(markdown_text)
        cmds: list = [match.group('code') for match in matches]
        if len(cmds) > 0:
            return cmds[0]
        return markdown_text.replace('`', '')
