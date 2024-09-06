# Copyright (c) Huawei Technologies Co., Ltd. 2024-2024. All rights reserved.

import json
import re
import socket
import subprocess
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urljoin

import requests
from rich.console import Console
from rich.live import Live
from rich.spinner import Spinner

from copilot.backends.llm_service import LLMService
from copilot.utilities.i18n import (
    BRAND_NAME,
    backend_framework_auth_invalid_api_key,
    backend_framework_request_connection_error,
    backend_framework_request_exceptions,
    backend_framework_request_timeout,
    backend_framework_request_too_many_requests,
    backend_framework_request_unauthorized,
    backend_framework_response_ended_prematurely,
    backend_framework_stream_error,
    backend_framework_stream_sensitive,
    backend_framework_stream_unknown,
    backend_framework_sugggestion,
    backend_general_request_failed,
    prompt_framework_extra_install,
    prompt_framework_keyword_install,
    prompt_framework_markdown_format,
    prompt_framework_plugin_ip,
    query_mode_chat,
    query_mode_diagnose,
    query_mode_flow,
    query_mode_tuning,
)
from copilot.utilities.markdown_renderer import MarkdownRenderer
from copilot.utilities.shell_script import write_shell_script

QUERY_MODE = {
    'chat': query_mode_chat,
    'flow': query_mode_flow,
    'diagnose': query_mode_diagnose,
    'tuning': query_mode_tuning,
}

FRAMEWORK_LLM_STREAM_BAD_REQUEST_MSG = {
    401: backend_framework_request_unauthorized,
    429: backend_framework_request_too_many_requests
}


# pylint: disable=R0902
class Framework(LLMService):
    def __init__(self, url, api_key, debug_mode=False):
        self.endpoint: str = url
        self.api_key: str = api_key
        self.debug_mode: bool = debug_mode
        # 临时数据 (本轮对话)
        self.session_id: str = ''
        self.plugins: list = []
        self.conversation_id: str = ''
        # 临时数据 (本次问答)
        self.content: str = ''
        self.commands: list = []
        self.sugggestion: str = ''
        # 富文本显示
        self.console = Console()

    def get_shell_commands(self, question: str) -> list:
        query = self._add_framework_extra_prompt(self._gen_chat_prompt(question))
        if prompt_framework_keyword_install in question.lower():
            query = self._add_framework_software_install_prompt(query)
        self._query_llm_service(query)
        if self.commands:
            return self.commands
        return self._extract_shell_code_blocks(self.content)

    def explain_shell_command(self, cmd: str):
        query = self._gen_explain_cmd_prompt(cmd)
        self._query_llm_service(query, show_suggestion=False)

    def update_session_id(self):
        headers = self._get_headers()
        try:
            response = requests.get(
                urljoin(self.endpoint, 'api/client/session'),
                headers=headers,
                timeout=30
            )
        except requests.exceptions.RequestException:
            self.console.print(backend_framework_request_exceptions.format(brand_name=BRAND_NAME))
            return
        if response.status_code == 401:
            self.console.print(backend_framework_auth_invalid_api_key.format(brand_name=BRAND_NAME))
            return
        if response.status_code != 200:
            self.console.print(backend_general_request_failed.format(code=response.status_code))
            return
        self.session_id = response.json().get('result', {}).get('session_id', '')

    def create_new_conversation(self):
        headers = self._get_headers()
        try:
            response = requests.post(
                urljoin(self.endpoint, 'api/client/conversation'),
                headers=headers,
                timeout=30
            )
        except requests.exceptions.RequestException:
            self.console.print(backend_framework_request_exceptions.format(brand_name=BRAND_NAME))
            return
        if response.status_code == 401:
            self.console.print(backend_framework_auth_invalid_api_key.format(brand_name=BRAND_NAME))
            return
        if response.status_code != 200:
            self.console.print(backend_general_request_failed.format(code=response.status_code))
            return
        self.conversation_id = response.json().get('result', {}).get('conversation_id', '')

    def get_plugins(self) -> list:
        headers = self._get_headers()
        try:
            response = requests.get(
                urljoin(self.endpoint, 'api/client/plugin'),
                headers=headers,
                timeout=30
            )
        except requests.exceptions.RequestException:
            self.console.print(backend_framework_request_exceptions.format(brand_name=BRAND_NAME))
            return []
        if response.status_code == 401:
            self.console.print(backend_framework_auth_invalid_api_key.format(brand_name=BRAND_NAME))
            return []
        if response.status_code != 200:
            self.console.print(backend_general_request_failed.format(code=response.status_code))
            return []
        self.session_id = self._reset_session_from_cookie(response.headers.get('set-cookie', ''))
        plugins = response.json().get('result', [])
        if plugins:
            self.plugins = [PluginData(**plugin) for plugin in plugins]
        return self.plugins

    def flow(self, question: str, plugins: list) -> list:
        self._query_llm_service(question, user_selected_plugins=plugins)
        if self.commands:
            return self.commands
        return self._extract_shell_code_blocks(self.content)

    def diagnose(self, question: str) -> list:
        # 确保用户输入的问题中包含有效的IP地址，若没有，则诊断本机
        if not self._contains_valid_ip(question):
            local_ip = self._get_local_ip()
            if local_ip:
                question = f'{prompt_framework_plugin_ip} {local_ip}，' + question
        self._query_llm_service(question, user_selected_plugins=['euler-copilot-rca'])
        return self._extract_shell_code_blocks(self.content)

    def tuning(self, question: str) -> list:
        # 确保用户输入的问题中包含有效的IP地址，若没有，则调优本机
        if not self._contains_valid_ip(question):
            local_ip = self._get_local_ip()
            if local_ip:
                question = f'{prompt_framework_plugin_ip} {local_ip}，' + question
        self._query_llm_service(question, user_selected_plugins=['euler-copilot-tune'])
        return self._extract_shell_code_blocks(self.content)

    # pylint: disable=W0221
    def _query_llm_service(
        self,
        question: str,
        user_selected_plugins: Optional[list] = None,
        show_suggestion: bool = True
    ):
        if not user_selected_plugins:
            user_selected_plugins = ['auto']
        headers = self._get_headers()
        data = {
            'question': question, 
            'conversation_id': self.conversation_id,
            'user_selected_plugins': user_selected_plugins
        }
        self._stream_response(headers, data, show_suggestion)

    def _stream_response(self, headers, data, show_suggestion: bool = True):
        self._clear_previous_data()
        spinner = Spinner('material')
        with Live(console=self.console) as live:
            live.update(spinner, refresh=True)
            try:
                response = requests.post(
                    urljoin(self.endpoint, 'api/client/chat'),
                    headers=headers,
                    json=data,
                    stream=True,
                    timeout=300
                )
            except requests.exceptions.ConnectionError:
                live.update(
                    backend_framework_request_connection_error.format(brand_name=BRAND_NAME), refresh=True)
                return
            except requests.exceptions.Timeout:
                live.update(
                    backend_framework_request_timeout.format(brand_name=BRAND_NAME), refresh=True)
                return
            except requests.exceptions.RequestException:
                live.update(
                    backend_framework_request_exceptions.format(brand_name=BRAND_NAME), refresh=True)
                return
            if response.status_code != 200:
                msg = FRAMEWORK_LLM_STREAM_BAD_REQUEST_MSG.get(
                    response.status_code,
                    backend_general_request_failed.format(code=response.status_code)
                )
                live.update(msg, refresh=True)
                return
            self.session_id = self._reset_session_from_cookie(response.headers.get('set-cookie', ''))
            try:
                self._handle_response_stream(live, response, show_suggestion)
            except requests.exceptions.ChunkedEncodingError:
                live.update(backend_framework_response_ended_prematurely, refresh=True)

    def _clear_previous_data(self):
        self.content = ''
        self.commands = []
        self.sugggestion = ''

    def _handle_response_stream(
        self,
        live: Live,
        response: requests.Response,
        show_suggestion: bool
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
                        MarkdownRenderer.update(
                            live,
                            backend_framework_stream_error.format(brand_name=BRAND_NAME)
                        )
                elif content == '[SENSITIVE]':
                    MarkdownRenderer.update(live, backend_framework_stream_sensitive)
                    self.content = ''
                elif content != '[DONE]':
                    if not self.debug_mode:
                        continue
                    MarkdownRenderer.update(
                        live,
                        backend_framework_stream_unknown.format(
                            brand_name=BRAND_NAME,
                            content=content
                        )
                    )
                break
            else:
                self._handle_json_chunk(jcontent, live, show_suggestion)

    def _handle_json_chunk(self, jcontent, live: Live, show_suggestion: bool):
        chunk = jcontent.get('content', '')
        self.content += chunk
        # 获取推荐问题
        if show_suggestion:
            suggestions = jcontent.get('search_suggestions', [])
            if suggestions:
                suggested_plugin = suggestions[0].get('name', '')
                suggested_question = suggestions[0].get('question', '')
                if suggested_plugin and suggested_question:
                    self.sugggestion = f'**{suggested_plugin}** {suggested_question}'
                elif suggested_question:
                    self.sugggestion = suggested_question
        # 获取插件返回数据
        plugin_tool_type = jcontent.get('type', '')
        if plugin_tool_type == 'extract':
            data_str = jcontent.get('data', '')
            if data_str:
                try:
                    data = json.loads(data_str)
                except json.JSONDecodeError:
                    return
                # 返回 Markdown 报告
                output = data.get('output', '')
                if output:
                    self.content += output
                # 返回单行 Shell 命令
                cmd = data.get('shell', '')
                if cmd:
                    self.commands.append(cmd)
                # 返回 Shell 脚本
                script = data.get('script', '')
                if script:
                    self.commands.append(write_shell_script(script))
        # 刷新终端
        if not self.sugggestion:
            MarkdownRenderer.update(live, self.content)
        else:
            MarkdownRenderer.update(
                live,
                content=self.content,
                sugggestion=backend_framework_sugggestion.format(sugggestion=self.sugggestion),
            )

    def _get_headers(self) -> dict:
        return {
            'Accept': '*/*',
            'Content-Type': 'application/json; charset=UTF-8',
            'Connection': 'keep-alive',
            'Authorization': f'Bearer {self.api_key}',
            'Cookie': f'ECSESSION={self.session_id};' if self.session_id else '',
        }

    def _reset_session_from_cookie(self, cookie: str) -> str:
        if not cookie:
            return ''
        for item in cookie.split(';'):
            item = item.strip()
            if item.startswith('ECSESSION'):
                return item.split('=')[1]
        return ''

    def _contains_valid_ip(self, text: str) -> bool:
        ip_pattern = re.compile(
            r'(?<![\.\d])(([1-9]?\d|1\d\d|2[0-4]\d|25[0-5])\.){3}([1-9]?\d|1\d\d|2[0-4]\d|25[0-5])(?![\.\d])'
        )
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

    def _add_framework_extra_prompt(self, query: str) -> str:
        return query + '\n\n' + prompt_framework_markdown_format

    def _add_framework_software_install_prompt(self, query: str) -> str:
        return query + '\n\n' + prompt_framework_extra_install.format(
            prompt_general_root=self._gen_sudo_prompt())


@dataclass
class PluginData:
    id: str
    plugin_name: str
    plugin_description: str
    plugin_auth: Optional[dict] = None
