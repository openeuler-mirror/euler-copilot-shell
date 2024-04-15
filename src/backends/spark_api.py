# Copyright (c) Huawei Technologies Co., Ltd. 2024-2024. All rights reserved.

import asyncio
import base64
import hashlib
import hmac
import json
import re
import sys
from datetime import datetime
from time import mktime
from urllib.parse import urlencode, urlparse
from wsgiref.handlers import format_date_time

import websockets
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.spinner import Spinner
from utilities.os_info import get_os_info

from backends.llm_service import LLMService


class Spark(LLMService):
    def __init__(self, app_id, api_key, api_secret, spark_url, domain, max_tokens=4096):
        self.app_id: str = app_id
        self.api_key: str = api_key
        self.api_secret: str = api_secret
        self.spark_url: str = spark_url
        self.host = urlparse(spark_url).netloc
        self.path = urlparse(spark_url).path
        self.domain: str = domain
        self.max_tokens: int = max_tokens
        self.answer: str = ''
        self.history: list = []
        # 富文本显示
        self.console = Console()

    def get_general_answer(self, question: str) -> str:
        asyncio.get_event_loop().run_until_complete(
            self._query_spark_ai(question)
        )
        return self.answer

    def get_shell_answer(self, question: str) -> str:
        query = f'请用单行shell命令回答以下问题：\n{question}\n\
        \n要求：\n请直接回复命令，不要添加任何多余内容；\n\
        当前操作系统是：{get_os_info()}，请返回符合当前系统要求的命令。'
        return self._extract_shell_code_blocks(self.get_general_answer(query))

    async def _query_spark_ai(self, query: str):
        url = self._create_url()
        self.answer = ''
        spinner = Spinner('material')
        try:
            with Live(console=self.console) as live:
                live.update(spinner, refresh=True)
                async with websockets.connect(url) as websocket:
                    data = json.dumps(self._gen_params(query))
                    await websocket.send(data)

                    while True:
                        try:
                            message = await websocket.recv()
                            data = json.loads(message)
                            code = data['header']['code']
                            if code != 0:
                                message = data['header']['message']
                                live.update(f'请求错误: {code}\n{message}', refresh=True)
                                await websocket.close()
                            else:
                                choices = data["payload"]["choices"]
                                status = choices["status"]
                                content = choices["text"][0]["content"]
                                self.answer += content
                                live.update(Markdown(self.answer, code_theme='github-dark'), refresh=True)
                                if status == 2:
                                    self.history.append({"role": "assistant", "content": self.answer})
                                    break
                        except websockets.exceptions.ConnectionClosed:
                            break

        except websockets.exceptions.InvalidStatusCode:
            sys.stderr.write('\033[1;31m请求错误！\033[0m\n请检查 appid 和 api_key 是否正确，或检查网络连接是否正常。')
            print('输入 "copilot --settings" 来查看和编辑配置')

    def _create_url(self):
        now = datetime.now()  # 生成RFC1123格式的时间戳
        date = format_date_time(mktime(now.timetuple()))

        signature_origin = f'host: {self.host}\ndate: {date}\nGET {self.path} HTTP/1.1'

        # 进行hmac-sha256进行加密
        signature_sha = hmac.new(self.api_secret.encode('utf-8'),
                                 signature_origin.encode('utf-8'),
                                 digestmod=hashlib.sha256).digest()

        signature_sha_base64 = base64.b64encode(signature_sha).decode(encoding='utf-8')

        authorization_origin = f'api_key="{self.api_key}", algorithm="hmac-sha256", ' + \
                               f'headers="host date request-line", signature="{signature_sha_base64}"'

        authorization = base64.b64encode(authorization_origin.encode('utf-8')).decode(encoding='utf-8')

        # 将请求的鉴权参数组合为字典
        v = {
            "authorization": authorization,
            "date": date,
            "host": self.host
        }
        # 拼接鉴权参数，生成url
        url = self.spark_url + '?' + urlencode(v)
        # 此处打印出建立连接时候的url,参考本demo的时候可取消上方打印的注释，比对相同参数时生成的url与自己代码生成的url是否一致
        return url

    def _get_length(self, context: list) -> int:
        length = 0
        for content in context:
            temp = content["content"]
            leng = len(temp)
            length += leng
        return length

    def _check_len(self, context: list) -> list:
        while self._get_length(context) > self.max_tokens / 2:
            del context[0]
        return context

    def _gen_params(self, query: str):
        """
        通过appid和用户的提问来生成请参数
        """
        self.history.append({"role": "user", "content": query})
        history = self._check_len(
            self.history if len(self.history) < 5 else self.history[-5:]
        )
        data = {
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
                }
            },
            "payload": {
                "message": {
                    "text": history
                }
            }
        }
        return data

    def _extract_shell_code_blocks(self, markdown_text):
        shell_code_pattern = re.compile(r'```shell\n(?P<code>(?:\n|.)*?)\n```', re.DOTALL)
        matches = shell_code_pattern.finditer(markdown_text)
        cmds: list = [match.group('code') for match in matches]
        if len(cmds) > 0:
            return cmds[0]
        return markdown_text.replace('`', '')
