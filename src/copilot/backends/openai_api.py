# Copyright (c) Huawei Technologies Co., Ltd. 2024-2024. All rights reserved.

import json
from typing import Optional

import requests
from rich.console import Console
from rich.live import Live
from rich.spinner import Spinner

from copilot.backends.llm_service import LLMService
from copilot.utilities.i18n import (
    backend_general_request_failed,
    backend_openai_request_connection_error,
    backend_openai_request_exceptions,
    backend_openai_request_timeout,
)
from copilot.utilities.markdown_renderer import MarkdownRenderer


class ChatOpenAI(LLMService):
    def __init__(self, url: str, api_key: Optional[str], model: Optional[str], max_tokens = 2048):
        self.url: str = url
        self.api_key: Optional[str] = api_key
        self.model: Optional[str] = model
        self.max_tokens: int = max_tokens
        self.answer: str = ''
        self.history: list = []
        # 富文本显示
        self.console = Console()

    def get_shell_commands(self, question: str) -> list:
        query = self._gen_chat_prompt(question)
        self._query_llm_service(query)
        return self._extract_shell_code_blocks(self.answer)

    # pylint: disable=W0221
    def _query_llm_service(self, question: str):
        self._stream_response(question)

    def _check_len(self, context: list) -> list:
        while self._get_context_length(context) > self.max_tokens / 2:
            del context[0]
        return context

    def _gen_params(self, query: str, stream: bool = True):
        self.history.append({'content': query, 'role': 'user'})
        history = self._check_len(
            self.history if len(self.history) < 5 else self.history[-5:]
        )
        history.insert(0, {'content': self._gen_system_prompt(), 'role': 'system'})
        return {
            'messages': history,
            'model': self.model,
            'stream': stream,
            'max_tokens': self.max_tokens,
            'temperature': 0.1,
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
        with Live(console=self.console, vertical_overflow='visible') as live:
            live.update(spinner, refresh=True)
            try:
                response = requests.post(
                    self.url,
                    headers=self._gen_headers(),
                    data=json.dumps(self._gen_params(query)),
                    stream=True,
                    timeout=60
                )
            except requests.exceptions.ConnectionError:
                live.update(backend_openai_request_connection_error, refresh=True)
                return
            except requests.exceptions.Timeout:
                live.update(backend_openai_request_timeout, refresh=True)
                return
            except requests.exceptions.RequestException:
                live.update(backend_openai_request_exceptions, refresh=True)
                return
            if response.status_code != 200:
                live.update(backend_general_request_failed.format(code=response.status_code), refresh=True)
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
                    choices = jcontent.get('choices', [])
                    if choices:
                        delta = choices[0].get('delta', {})
                        chunk = delta.get('content', '')
                        finish_reason = choices[0].get('finish_reason')
                        self.answer += chunk
                        MarkdownRenderer.update(live, self.answer)
                        if finish_reason == 'stop':
                            self.history.append({'content': self.answer, 'role': 'assistant'})
                            break
