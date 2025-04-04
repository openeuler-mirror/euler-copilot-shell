# Copyright (c) Huawei Technologies Co., Ltd. 2024-2025. All rights reserved.

import asyncio
import base64
import hashlib
import hmac
import json
from datetime import datetime
from time import mktime
from urllib.parse import urlencode, urlparse
from wsgiref.handlers import format_date_time

import websockets
from rich.console import Console
from rich.live import Live
from rich.spinner import Spinner
from rich.text import Text

from copilot.backends.llm_service import LLMService
from copilot.utilities.i18n import (
    backend_spark_network_error,
    backend_spark_stream_error,
    backend_spark_websockets_exceptions_msg_a,
    backend_spark_websockets_exceptions_msg_b,
    backend_spark_websockets_exceptions_msg_c,
    backend_spark_websockets_exceptions_msg_title,
)
from copilot.utilities.markdown_renderer import MarkdownRenderer


class Spark(LLMService):
    def __init__(  # noqa: PLR0913
        self,
        app_id: str,
        api_key: str,
        api_secret: str,
        spark_url: str,
        domain: str,
        max_tokens: int = 4096,
    ) -> None:
        self.app_id: str = app_id
        self.api_key: str = api_key
        self.api_secret: str = api_secret
        self.spark_url: str = spark_url
        self.host = urlparse(spark_url).netloc
        self.path = urlparse(spark_url).path
        self.domain: str = domain
        self.max_tokens: int = max_tokens
        self.answer: str = ""
        self.history: list = []
        # 富文本显示
        self.console = Console()

    def get_llm_result(self, question: str, *, single_line_cmd: bool = False) -> LLMService.LLMResult:
        query = self._gen_shell_prompt(question) if single_line_cmd else self._gen_chat_prompt(question)
        self._query_llm_service(query)
        return LLMService.LLMResult(
            cmds=self._extract_shell_code_blocks(self.answer), code=self._extract_python_code_blocks(self.answer)
        )

    # pylint: disable=W0221
    def _query_llm_service(self, question: str):
        asyncio.get_event_loop().run_until_complete(
            self._query_spark_ai(question),
        )

    async def _query_spark_ai(self, query: str):
        url = self._create_url()
        self.answer = ""
        spinner = Spinner("material")
        with Live(console=self.console) as live:
            live.update(spinner, refresh=True)
            try:
                async with websockets.connect(url) as websocket:
                    data = json.dumps(self._gen_params(query))
                    await websocket.send(data)

                    while True:
                        try:
                            message = await websocket.recv()
                            data = json.loads(message)
                            code = data["header"]["code"]
                            if code != 0:
                                message = data["header"]["message"]
                                live.update(
                                    backend_spark_stream_error.format(
                                        code=code,
                                        message=message,
                                    ),
                                    refresh=True,
                                )
                                await websocket.close()
                            else:
                                choices = data["payload"]["choices"]
                                status = choices["status"]
                                content = choices["text"][0]["content"]
                                self.answer += content
                                MarkdownRenderer.update(live, self.answer)
                                if status == 2:
                                    self.history.append({"role": "assistant", "content": self.answer})
                                    break
                        except websockets.exceptions.ConnectionClosed:
                            break

            except websockets.exceptions.InvalidStatus:
                live.update(
                    Text.from_ansi(f"\033[1;31m{backend_spark_websockets_exceptions_msg_title}\033[0m\n\n")
                    .append(backend_spark_websockets_exceptions_msg_a)
                    .append(backend_spark_websockets_exceptions_msg_b)
                    .append(backend_spark_websockets_exceptions_msg_c.format(spark_url=self.spark_url)),
                    refresh=True,
                )
            except Exception:
                live.update(backend_spark_network_error)

    def _create_url(self) -> str:
        now = datetime.now()  # 生成RFC1123格式的时间戳
        date = format_date_time(mktime(now.timetuple()))

        signature_origin = f"host: {self.host}\ndate: {date}\nGET {self.path} HTTP/1.1"

        # 进行hmac-sha256进行加密
        signature_sha = hmac.new(
            self.api_secret.encode("utf-8"), signature_origin.encode("utf-8"), digestmod=hashlib.sha256
        ).digest()

        signature_sha_base64 = base64.b64encode(signature_sha).decode(encoding="utf-8")

        authorization_origin = (
            f'api_key="{self.api_key}", algorithm="hmac-sha256", '
            + f'headers="host date request-line", signature="{signature_sha_base64}"'
        )

        authorization = base64.b64encode(authorization_origin.encode("utf-8")).decode(encoding="utf-8")

        # 将请求的鉴权参数组合为字典
        v = {
            "authorization": authorization,
            "date": date,
            "host": self.host,
        }
        # 拼接鉴权参数，生成url
        return self.spark_url + "?" + urlencode(v)
        # 此处打印出建立连接时候的url,参考本demo的时候可取消上方打印的注释，比对相同参数时生成的url与自己代码生成的url是否一致

    def _check_len(self, context: list) -> list:
        while self._get_context_length(context) > self.max_tokens / 2:
            del context[0]
        return context

    def _gen_params(self, query: str):
        """通过appid和用户的提问来生成请参数"""
        self.history.append({"role": "user", "content": query})
        history = self._check_len(
            self.history if len(self.history) < 5 else self.history[-5:],
        )
        if self.domain == "generalv3.5":
            history.insert(0, {"role": "system", "content": self._gen_system_prompt()})
        return {
            "header": {
                "app_id": self.app_id,
                "uid": "1234",
            },
            "parameter": {
                "chat": {
                    "domain": self.domain,
                    "temperature": 0.5,
                    "max_tokens": self.max_tokens,
                    "auditing": "default",
                },
            },
            "payload": {
                "message": {
                    "text": history,
                },
            },
        }
