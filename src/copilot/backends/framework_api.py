# Copyright (c) Huawei Technologies Co., Ltd. 2024-2024. All rights reserved.

import json

import requests
from rich.console import Console
from rich.live import Live
from rich.spinner import Spinner

from copilot.backends.llm_service import LLMService
from copilot.utilities.markdown_renderer import MarkdownRenderer


class Framework(LLMService):
    def __init__(self, url, api_key, session_id):
        self.endpoint: str = url
        self.api_key: str = api_key
        self.session_id: str = session_id
        self.content: str = ''
        # 富文本显示
        self.console = Console()

    def get_general_answer(self, question: str) -> str:
        headers = self._get_headers()
        data = {'question': question, 'session_id': self.session_id}
        self._stream_response(headers, data)
        return self.content

    def get_shell_answer(self, question: str) -> str:
        query = self._gen_shell_prompt(question)
        return self._extract_shell_code_blocks(self.get_general_answer(query))

    def _stream_response(self, headers, data):
        spinner = Spinner('material')
        with Live(console=self.console, vertical_overflow='visible') as live:
            live.update(spinner, refresh=True)
            try:
                response = requests.post(
                    self.endpoint,
                    headers=headers,
                    json=data,
                    stream=True,
                    timeout=60
                )
            except requests.exceptions.ConnectionError:
                live.update('NeoCopilot 智能体连接失败', refresh=True)
                return
            except requests.exceptions.Timeout:
                live.update('NeoCopilot 智能体请求超时', refresh=True)
                return
            except requests.exceptions.RequestException:
                live.update('NeoCopilot 智能体请求异常', refresh=True)
                return
            if response.status_code != 200:
                live.update(f'请求失败: {response.status_code}', refresh=True)
                return
            for line in response.iter_lines():
                if line is None:
                    continue
                content = line.decode('utf-8').strip('data: ')
                try:
                    jcontent = json.loads(content)
                except json.JSONDecodeError:
                    if content == '[ERROR]':
                        MarkdownRenderer.update(live, 'NeoCopilot 智能体系统繁忙，请稍候再试')
                        self.content = ''
                    elif content == '[SENSITIVE]':
                        MarkdownRenderer.update(live, '检测到违规信息，请重新提问')
                        self.content = ''
                    elif content != '[DONE]':
                        MarkdownRenderer.update(live, f'NeoCopilot 智能体返回了未知内容：{content}')
                    break
                else:
                    chunk = jcontent.get('content', '')
                    self.content += chunk
                    MarkdownRenderer.update(live, self.content)

    def _get_headers(self) -> dict:
        return {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.api_key}'
        }
