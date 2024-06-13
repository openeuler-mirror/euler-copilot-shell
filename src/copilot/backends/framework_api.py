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
            'user_selected_plugins': [
                {
                    'plugin_name': 'Diagnostic'
                }
            ]
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
            'user_selected_plugins': [
                {
                    'plugin_name': 'A-Tune'
                }
            ]
        }
        self._stream_response(headers, data)
        return self.content

    def _stream_response(self, headers, data):
        self.content = ''
        spinner = Spinner('material')
        with Live(console=self.console, vertical_overflow='visible') as live:
            live.update(spinner, refresh=True)
            try:
                response = requests.post(
                    self.endpoint,
                    headers=headers,
                    json=data,
                    stream=True,
                    timeout=300
                )
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
                    MarkdownRenderer.update(live, self.content)

    def _get_headers(self) -> dict:
        return {
            'Accept': '*/*',
            'Content-Type': 'application/json; charset=UTF-8',
            'Connection': 'keep-alive',
            'Authorization': f'Bearer {self.api_key}'
        }

    def _contains_valid_ip(self, text: str) -> bool:
        ip_pattern = r'\b((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b'
        match = re.search(ip_pattern, text)
        return bool(match)

    def _get_local_ip(self) -> str:
        try:
            process = subprocess.run(
                ['hostname', '-I'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True)
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
