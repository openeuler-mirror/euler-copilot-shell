# Copyright (c) Huawei Technologies Co., Ltd. 2024-2024. All rights reserved.

import json
import re
import socket
import subprocess

import requests
from rich.console import Console
from rich.live import Live
from rich.spinner import Spinner

from copilot.backends.llm_service import LLMService
from copilot.utilities.markdown_renderer import MarkdownRenderer


class Framework(LLMService):
    def __init__(self, url, api_key, session_id, debug_mode=False):
        self.endpoint: str = url
        self.api_key: str = api_key
        self.session_id: str = session_id
        self.debug_mode: bool = debug_mode
        # 缓存
        self.content: str = ''
        self.sugggestion: str = ''
        # 富文本显示
        self.console = Console()

    def get_model_output(self, question: str) -> str:
        headers = self._get_headers()
        data = {'question': question, 'session_id': self.session_id}
        self._stream_response(headers, data)
        return self.content

    def get_shell_commands(self, question: str) -> list:
        query = self._gen_chat_prompt(question) + self._gen_framework_extra_prompt()
        return self._extract_shell_code_blocks(self.get_model_output(query))

    def diagnose(self, question: str) -> str:
        # 确保用户输入的问题中包含有效的IP地址，若没有，则诊断本机
        if not self._contains_valid_ip(question):
            local_ip = self._get_local_ip()
            if local_ip:
                question = f'当前机器的IP为 {local_ip}，' + question
        headers = self._get_headers()
        data = {
            'question': question,
            'session_id': self.session_id,
            'user_selected_plugins': [{'plugin_name': 'Diagnostic'}],
        }
        self._stream_response(headers, data)
        return self.content

    def tuning(self, question: str) -> str:
        # 确保用户输入的问题中包含有效的IP地址，若没有，则调优本机
        if not self._contains_valid_ip(question):
            local_ip = self._get_local_ip()
            if local_ip:
                question = f'当前机器的IP为 {local_ip}，' + question
        headers = self._get_headers()
        data = {
            'question': question,
            'session_id': self.session_id,
            'user_selected_plugins': [{'plugin_name': 'A-Tune'}],
        }
        self._stream_response(headers, data)
        return self.content

    def _stream_response(self, headers, data):
        self.content = ''
        self.sugggestion = ''
        spinner = Spinner('material')
        with Live(console=self.console, vertical_overflow='visible') as live:
            live.update(spinner, refresh=True)
            try:
                response = requests.post(self.endpoint, headers=headers, json=data, stream=True, timeout=300)
            except requests.exceptions.ConnectionError:
                live.update('EulerCopilot 智能体连接失败', refresh=True)
                return
            except requests.exceptions.Timeout:
                live.update('EulerCopilot 智能体请求超时', refresh=True)
                return
            except requests.exceptions.RequestException:
                live.update('EulerCopilot 智能体请求异常', refresh=True)
                return
            if response.status_code != 200:
                live.update(f'请求失败: {response.status_code}', refresh=True)
                return
            self._handle_response_content(response, live)

    # pylint: disable=R0912
    def _handle_response_content(
        self,
        response: requests.Response,
        live: Live
    ):
        for line in response.iter_lines():
            if line is None:
                continue
            content = line.decode('utf-8').strip('data: ')
            try:
                jcontent = json.loads(content)
            except json.JSONDecodeError:
                if content == '':
                    continue
                if content == '[ERROR]':
                    if not self.content:
                        MarkdownRenderer.update(live, 'EulerCopilot 智能体遇到错误，请联系管理员定位问题')
                elif content == '[SENSITIVE]':
                    MarkdownRenderer.update(live, '检测到违规信息，请重新提问')
                    self.content = ''
                elif content != '[DONE]':
                    if not self.debug_mode:
                        continue
                    MarkdownRenderer.update(live, f'EulerCopilot 智能体返回了未知内容：\n```json\n{content}\n```')
                break
            else:
                chunk = jcontent.get('content', '')
                self.content += chunk
                suggestions = jcontent.get('search_suggestions', [])
                if suggestions:
                    self.sugggestion = suggestions[0].strip()
                if not self.sugggestion:
                    MarkdownRenderer.update(live, self.content)
                else:
                    MarkdownRenderer.update(
                        live,
                        content=self.content,
                        sugggestion=f'**你可以继续问** {self.sugggestion}'
                    )

    def _get_headers(self) -> dict:
        return {
            'Accept': '*/*',
            'Content-Type': 'application/json; charset=UTF-8',
            'Connection': 'keep-alive',
            'Authorization': f'Bearer {self.api_key}',
        }

    def _contains_valid_ip(self, text: str) -> bool:
        ip_pattern = re.compile(
            r'(?<![\.\d])(([1-9]?\d|1\d\d|2[0-4]\d|25[0-5])\.){3}([1-9]?\d|1\d\d|2[0-4]\d|25[0-5])(?![\.\d])'
        )
        match = re.search(ip_pattern, text)
        return bool(match)

    def _get_local_ip(self) -> str:
        try:
            process = subprocess.run(['hostname', '-I'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        except (FileNotFoundError, subprocess.CalledProcessError):
            try:
                ip_list = socket.gethostbyname_ex(socket.gethostname())[2]
            except socket.gaierror:
                return ''
            return ip_list[-1]
        if process.stdout:
            ip_address = process.stdout.decode('utf-8').strip().split(' ', maxsplit=1)[0]
            return ip_address
        return ''

    def _gen_framework_extra_prompt(self) -> str:
        return f'''\n
你的任务是：
根据用户输入的问题，提供相应的操作系统的管理和运维解决方案。
你给出的答案必须符合当前操作系统要求，你不能使用当前操作系统没有的功能。

格式要求：
+ 你的回答必须使用 Markdown 格式，代码块和表格都必须用 Markdown 呈现；
+ 你需要用中文回答问题，除了代码，其他内容都要符合汉语的规范。

其他要求：
+ 如果用户要求安装软件包，请注意 openEuler 使用 dnf 管理软件包，你不能在回答中使用 apt 或其他软件包管理器
+ 请特别注意当前用户的权限：{self._gen_sudo_prompt()}

在给用户返回 shell 命令时，你必须返回安全的命令，不能进行任何危险操作！
如果涉及到删除文件、清理缓存、删除用户、卸载软件、wget下载文件等敏感操作，你必须生成安全的命令\n
危险操作举例：\n
+ 例1: 强制删除
  ```bash
  rm -rf /path/to/sth
  ```
+ 例2: 卸载软件包时默认同意
  ```bash
  dnf remove -y package_name
  ```
你不能输出类似于上述例子的命令！

由于用户使用命令行与你交互，你需要避免长篇大论，请使用简洁的语言，一般情况下你的回答不应超过1000字。
'''
