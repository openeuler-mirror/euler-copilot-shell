# Copyright (c) Huawei Technologies Co., Ltd. 2024-2025. All rights reserved.

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

MAX_HISTORY_LENGTH = 5
HTTP_STATUS_OK = 200


class ChatOpenAI(LLMService):
    """OpenAI Chat Service"""

    def __init__(self, url: str, api_key: Optional[str], model: Optional[str], max_tokens: int = 2048) -> None:
        """Initialize OpenAI Chat Service"""
        self.url: str = url
        self.api_key: Optional[str] = api_key
        self.model: Optional[str] = model
        self.max_tokens: int = max_tokens
        self.answer: str = ""
        self.history: list = []
        # 富文本显示
        self.console = Console()

    def get_llm_result(self, question: str, *, single_line_cmd: bool = False) -> LLMService.LLMResult:
        """Get shell commands"""
        query = self._gen_shell_prompt(question) if single_line_cmd else self._gen_chat_prompt(question)
        self._query_llm_service(query)
        return LLMService.LLMResult(
            cmds=self._extract_shell_code_blocks(self.answer), code=self._extract_python_code_blocks(self.answer)
        )

    def _query_llm_service(self, question: str) -> None:
        """Query LLM Service"""
        self.__stream_response(question)

    def __check_len(self, context: list) -> list:
        while self._get_context_length(context) > self.max_tokens / 2:
            del context[0]
        return context

    def __gen_params(self, query: str, *, stream: bool = True) -> dict:
        """Generate parameters"""
        self.history.append({"content": query, "role": "user"})
        history = self.__check_len(
            self.history if len(self.history) < MAX_HISTORY_LENGTH else self.history[-MAX_HISTORY_LENGTH:],
        )
        history.insert(0, {"content": self._gen_system_prompt(), "role": "system"})
        return {
            "messages": history,
            "model": self.model,
            "stream": stream,
            "max_tokens": self.max_tokens,
            "temperature": 0.1,
            "top_p": 0.95,
        }

    def __gen_headers(self) -> dict:
        """Generate headers"""
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

    def __stream_response(self, query: str) -> None:
        spinner = Spinner("material")
        self.answer = ""
        with Live(console=self.console) as live:
            live.update(spinner, refresh=True)
            response = self.__make_request(query, live)
            if not response:
                return
            self.__process_response(response, live)

    def __make_request(self, query: str, live: Live) -> Optional[requests.Response]:
        try:
            response = requests.post(
                self.url,
                headers=self.__gen_headers(),
                data=json.dumps(self.__gen_params(query)),
                stream=True,
                timeout=60,
            )
        except requests.exceptions.ConnectionError:
            live.update(backend_openai_request_connection_error, refresh=True)
            return None
        except requests.exceptions.Timeout:
            live.update(backend_openai_request_timeout, refresh=True)
            return None
        except requests.exceptions.RequestException:
            live.update(backend_openai_request_exceptions, refresh=True)
            return None
        if response.status_code != HTTP_STATUS_OK:
            live.update(backend_general_request_failed.format(code=response.status_code), refresh=True)
            return None
        return response

    def __process_response(self, response: requests.Response, live: Live) -> None:
        for line in response.iter_lines():
            if line is None:
                continue
            content = line.decode("utf-8").removeprefix("data: ")
            try:
                jcontent = json.loads(content)
            except json.JSONDecodeError:
                continue
            else:
                choices = jcontent.get("choices", [])
                if choices:
                    delta = choices[0].get("delta", {})
                    chunk = delta.get("content", "")
                    finish_reason = choices[0].get("finish_reason")
                    self.answer += chunk
                    MarkdownRenderer.update(live, self.answer)
                    if finish_reason == "stop":
                        self.history.append({"content": self.answer, "role": "assistant"})
                        break
