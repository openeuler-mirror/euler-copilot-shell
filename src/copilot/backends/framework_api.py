# Copyright (c) Huawei Technologies Co., Ltd. 2024-2025. All rights reserved.

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
    backend_framework_stream_stop,
    backend_framework_stream_unknown,
    backend_framework_sugggestion,
    backend_general_request_failed,
    prompt_framework_extra_install,
    prompt_framework_keyword_install,
    prompt_framework_markdown_format,
    prompt_framework_plugin_ip,
)
from copilot.utilities.markdown_renderer import MarkdownRenderer
from copilot.utilities.shell_script import write_shell_script

FRAMEWORK_LLM_STREAM_BAD_REQUEST_MSG = {
    401: backend_framework_request_unauthorized,
    429: backend_framework_request_too_many_requests,
}

HTTP_OK = 200
HTTP_AUTH_ERROR = 401


class Framework(LLMService):
    """EulerCopilot Framework Service"""

    def __init__(self, url: str, api_key: str, *, debug_mode: bool = False) -> None:
        """Initialize EulerCopilot Framework Service"""
        self.endpoint: str = url
        self.api_key: str = api_key
        self.debug_mode: bool = debug_mode
        # 临时数据 (本轮对话)  # noqa: ERA001
        self.session_id: str = ""
        self.plugins: list = []
        self.conversation_id: str = ""
        # 临时数据 (本次问答)  # noqa: ERA001
        self.content: str = ""
        self.commands: list = []
        self.sugggestion: str = ""
        # 富文本显示
        self.console = Console()

    def get_llm_result(self, question: str, *, single_line_cmd: bool = False) -> LLMService.LLMResult:
        """获取 Shell 命令"""
        query = self._gen_shell_prompt(question) if single_line_cmd else self.__add_extra_prompt(question)
        if prompt_framework_keyword_install in question.lower():
            query = self.__add_software_install_prompt(query)
        self._query_llm_service(query)
        if self.commands:
            return LLMService.LLMResult(cmds=self.commands, code=None)
        return LLMService.LLMResult(
            cmds=self._extract_shell_code_blocks(self.content),
            code=self._extract_python_code_blocks(self.content),
        )

    def explain_shell_command(self, cmd: str) -> None:
        """解释 Shell 命令"""
        query = self._gen_explain_cmd_prompt(cmd)
        self._query_llm_service(query, show_suggestion=False)

    def update_session_id(self) -> bool:
        """更新会话 ID"""
        headers = self.__get_headers()
        try:
            response = requests.post(
                urljoin(self.endpoint, "api/client/session"),
                json={"session_id": self.session_id} if self.session_id else {},
                headers=headers,
                timeout=30,
            )
        except requests.exceptions.RequestException:
            self.console.print(backend_framework_request_exceptions.format(brand_name=BRAND_NAME))
            return False
        if response.status_code == HTTP_AUTH_ERROR:
            self.console.print(backend_framework_auth_invalid_api_key.format(brand_name=BRAND_NAME))
            return False
        if response.status_code != HTTP_OK:
            self.console.print(backend_general_request_failed.format(code=response.status_code))
            return False
        self.session_id = response.json().get("result", {}).get("session_id", "")
        return True

    def create_new_conversation(self) -> bool:
        """新建对话"""
        headers = self.__get_headers()
        try:
            response = requests.post(
                urljoin(self.endpoint, "api/client/conversation"),
                headers=headers,
                timeout=30,
            )
        except requests.exceptions.RequestException:
            self.console.print(backend_framework_request_exceptions.format(brand_name=BRAND_NAME))
            return False
        if response.status_code == HTTP_AUTH_ERROR:
            self.console.print(backend_framework_auth_invalid_api_key.format(brand_name=BRAND_NAME))
            return False
        if response.status_code != HTTP_OK:
            self.console.print(backend_general_request_failed.format(code=response.status_code))
            return False
        self.conversation_id = response.json().get("result", {}).get("conversation_id", "")
        return True

    def get_plugins(self) -> list:
        """获取插件列表"""
        headers = self.__get_headers()
        try:
            response = requests.get(
                urljoin(self.endpoint, "api/client/plugin"),
                headers=headers,
                timeout=30,
            )
        except requests.exceptions.RequestException:
            self.console.print(backend_framework_request_exceptions.format(brand_name=BRAND_NAME))
            return []
        if response.status_code == HTTP_AUTH_ERROR:
            self.console.print(backend_framework_auth_invalid_api_key.format(brand_name=BRAND_NAME))
            return []
        if response.status_code != HTTP_OK:
            self.console.print(backend_general_request_failed.format(code=response.status_code))
            return []
        self.session_id = self.__reset_session_from_cookie(response.headers.get("set-cookie", ""))
        plugins = response.json().get("result", [])
        if plugins:
            self.plugins = [PluginData(**plugin) for plugin in plugins]
        return self.plugins

    def plugin(self, question: str, plugins: list) -> LLMService.LLMResult:
        """智能插件"""
        self._query_llm_service(question, user_selected_plugins=plugins)
        if self.commands:
            return LLMService.LLMResult(cmds=self.commands, code=None)
        return LLMService.LLMResult(
            cmds=self._extract_shell_code_blocks(self.content),
            code=self._extract_python_code_blocks(self.content),
        )

    def diagnose(self, question: str) -> LLMService.LLMResult:
        """智能诊断

        确保用户输入的问题中包含有效的IP地址，若没有，则诊断本机
        """
        if not self.__contains_valid_ip(question):
            local_ip = self.__get_local_ip()
            if local_ip:
                question = f"{prompt_framework_plugin_ip} {local_ip}，" + question
        self._query_llm_service(question, user_selected_plugins=["euler-copilot-rca"])
        if self.commands:
            return LLMService.LLMResult(cmds=self.commands, code=None)
        return LLMService.LLMResult(
            cmds=self._extract_shell_code_blocks(self.content),
            code=self._extract_python_code_blocks(self.content),
        )

    def tuning(self, question: str) -> LLMService.LLMResult:
        """智能调优

        确保用户输入的问题中包含有效的IP地址，若没有，则调优本机
        """
        if not self.__contains_valid_ip(question):
            local_ip = self.__get_local_ip()
            if local_ip:
                question = f"{prompt_framework_plugin_ip} {local_ip}，" + question
        self._query_llm_service(question, user_selected_plugins=["euler-copilot-tune"])
        if self.commands:
            return LLMService.LLMResult(cmds=self.commands, code=None)
        return LLMService.LLMResult(
            cmds=self._extract_shell_code_blocks(self.content),
            code=self._extract_python_code_blocks(self.content),
        )

    def stop(self) -> None:
        """停止回答"""
        headers = self.__get_headers()
        try:
            response = requests.post(
                urljoin(self.endpoint, "api/client/stop"),
                headers=headers,
                timeout=30,
            )
        except requests.exceptions.RequestException:
            return
        if response.status_code == HTTP_OK:
            self.console.print(backend_framework_stream_stop.format(brand_name=BRAND_NAME))

    def _query_llm_service(
        self,
        question: str,
        user_selected_plugins: Optional[list] = None,
        *,
        show_suggestion: bool = True,
    ) -> None:
        """Query LLM Service"""
        if not user_selected_plugins:
            user_selected_plugins = []
        headers = self.__get_headers()
        self.update_session_id()
        data = {
            "session_id": self.session_id,
            "question": question,
            "language": "zh",
            "conversation_id": self.conversation_id,
            "user_selected_plugins": user_selected_plugins,
        }
        self.__stream_response(headers, data, show_suggestion=show_suggestion)

    def __stream_response(self, headers: dict, data: dict, *, show_suggestion: bool = True) -> None:
        """流式响应输出"""
        self.__clear_previous_data()
        spinner = Spinner("material")
        with Live(console=self.console) as live:
            live.update(spinner, refresh=True)
            try:
                response = requests.post(
                    urljoin(self.endpoint, "api/client/chat"),
                    headers=headers,
                    json=data,
                    stream=True,
                    timeout=300,
                )
            except requests.exceptions.ConnectionError:
                live.update(backend_framework_request_connection_error.format(brand_name=BRAND_NAME), refresh=True)
                return
            except requests.exceptions.Timeout:
                live.update(backend_framework_request_timeout.format(brand_name=BRAND_NAME), refresh=True)
                return
            except requests.exceptions.RequestException:
                live.update(backend_framework_request_exceptions.format(brand_name=BRAND_NAME), refresh=True)
                return
            if response.status_code != HTTP_OK:
                msg = FRAMEWORK_LLM_STREAM_BAD_REQUEST_MSG.get(
                    response.status_code,
                    backend_general_request_failed.format(code=response.status_code),
                )
                live.update(msg, refresh=True)
                return
            self.session_id = self.__reset_session_from_cookie(response.headers.get("set-cookie", ""))
            try:
                self.__handle_response_stream(live, response, show_suggestion=show_suggestion)
            except requests.exceptions.ChunkedEncodingError:
                live.update(backend_framework_response_ended_prematurely, refresh=True)

    def __clear_previous_data(self) -> None:
        """清空上一次的数据"""
        self.content = ""
        self.commands = []
        self.sugggestion = ""

    def __handle_response_stream(
        self,
        live: Live,
        response: requests.Response,
        *,
        show_suggestion: bool,
    ) -> None:
        """处理流式响应"""
        for line in response.iter_lines():
            if line is None:
                continue
            content = line.decode("utf-8").removeprefix("data: ")
            try:
                jcontent = json.loads(content)
            except json.JSONDecodeError:
                if self.__break_on_json_error(content, live):
                    break
            else:
                self.__handle_json_chunk(jcontent, live, show_suggestion=show_suggestion)

    def __break_on_json_error(self, content: str, live: Live) -> bool:
        """处理 JSON 错误"""
        if content == "":
            return False
        if content == "[ERROR]":
            if not self.content:
                MarkdownRenderer.update(
                    live,
                    backend_framework_stream_error.format(brand_name=BRAND_NAME),
                )
            return True
        if content == "[SENSITIVE]":
            MarkdownRenderer.update(live, backend_framework_stream_sensitive)
            self.content = ""
            return True
        if content != "[DONE]":
            if not self.debug_mode:
                return False
            MarkdownRenderer.update(
                live,
                backend_framework_stream_unknown.format(
                    brand_name=BRAND_NAME,
                    content=content,
                ),
            )
            return True
        return True

    def __handle_json_chunk(self, jcontent: dict, live: Live, *, show_suggestion: bool) -> None:
        """处理 JSON 数据块"""
        chunk = jcontent.get("content", "")
        self.content += chunk
        self.__process_suggestions(jcontent, show_suggestion=show_suggestion)
        self.__process_plugin_data(jcontent)
        self.__update_render(live)

    def __process_suggestions(self, jcontent: dict, *, show_suggestion: bool) -> None:
        """处理推荐问题"""
        if show_suggestion:
            suggestions = jcontent.get("search_suggestions", [])
            if suggestions:
                suggested_plugin = suggestions[0].get("name", "")
                suggested_question = suggestions[0].get("question", "")
                if suggested_plugin and suggested_question:
                    self.sugggestion = f"**{suggested_plugin}** {suggested_question}"
                elif suggested_question:
                    self.sugggestion = suggested_question

    def __process_plugin_data(self, jcontent: dict) -> None:
        """处理插件返回数据"""
        plugin_tool_type = jcontent.get("type", "")
        if plugin_tool_type == "extract":
            data = jcontent.get("data", "")
            if data:
                if isinstance(data, str):
                    try:
                        data = json.loads(data)
                    except json.JSONDecodeError:
                        return
                # 返回 Markdown 报告
                output = data.get("output", "")
                if output:
                    self.content = output
                # 返回单行 Shell 命令
                cmd = data.get("shell", "")
                if cmd:
                    self.commands.append(cmd)
                # 返回 Shell 脚本
                script = data.get("script", "")
                if script:
                    self.commands.append(write_shell_script(script))

    def __update_render(self, live: Live) -> None:
        """更新终端显示"""
        if not self.sugggestion:
            MarkdownRenderer.update(live, self.content)
        else:
            MarkdownRenderer.update(
                live,
                content=self.content,
                sugggestion=backend_framework_sugggestion.format(sugggestion=self.sugggestion),
            )

    def __get_headers(self) -> dict:
        """生成请求头"""
        host = self.endpoint.removeprefix("http://").removeprefix("https://").strip("/")
        headers = {
            "Host": host,
            "Accept": "*/*",
            "Content-Type": "application/json; charset=UTF-8",
            "Connection": "keep-alive",
            "Authorization": f"Bearer {self.api_key}",
        }
        if self.session_id:
            headers["Cookie"] = f"ECSESSION={self.session_id};"
        return headers

    def __reset_session_from_cookie(self, cookie: str) -> str:
        if not cookie:
            return ""
        for cookie_item in cookie.split(";"):
            item = cookie_item.strip()
            if item.startswith("ECSESSION"):
                return item.split("=")[1]
        return ""

    def __contains_valid_ip(self, text: str) -> bool:
        ip_pattern = re.compile(
            r"(?<![\.\d])(([1-9]?\d|1\d\d|2[0-4]\d|25[0-5])\.){3}([1-9]?\d|1\d\d|2[0-4]\d|25[0-5])(?![\.\d])",
        )
        match = re.search(ip_pattern, text)
        return bool(match)

    def __get_local_ip(self) -> str:
        try:
            process = subprocess.run(  # noqa: S603
                ["hostname", "-I"],  # noqa: S607
                capture_output=True,
                check=True,
            )
        except (FileNotFoundError, subprocess.CalledProcessError):
            try:
                ip_list = socket.gethostbyname_ex(socket.gethostname())[2]
            except socket.gaierror:
                return ""
            return ip_list[-1]
        if process.stdout:
            return process.stdout.decode("utf-8").strip().split(" ", maxsplit=1)[0]
        return ""

    def __add_extra_prompt(self, query: str) -> str:
        return query + "\n\n" + prompt_framework_markdown_format

    def __add_software_install_prompt(self, query: str) -> str:
        return query + "\n\n" + prompt_framework_extra_install.format(prompt_general_root=self._gen_sudo_prompt())


@dataclass
class PluginData:
    """插件数据结构"""

    id: str
    plugin_name: str
    plugin_description: str
    plugin_auth: Optional[dict] = None
