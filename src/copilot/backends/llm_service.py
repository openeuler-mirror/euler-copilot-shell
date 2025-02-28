"""Module for LLM service abstract base class and related utilities.

Copyright (c) Huawei Technologies Co., Ltd. 2024-2025. All rights reserved.
"""

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from copilot.utilities.env_info import get_os_info, is_root
from copilot.utilities.i18n import (
    prompt_general_chat,
    prompt_general_explain_cmd,
    prompt_general_root_false,
    prompt_general_root_true,
    prompt_general_system,
    prompt_single_line_cmd,
)


class LLMService(ABC):
    """LLM Service Abstract Base Class"""

    @dataclass
    class LLMResult:
        """LLM Result"""

        cmds: Optional[list]
        code: Optional[str]

    @abstractmethod
    def get_llm_result(self, question: str, *, single_line_cmd: bool = False) -> LLMResult:
        """ "Get shell commands"""

    def explain_shell_command(self, cmd: str) -> None:
        """Explain shell command"""
        query = self._gen_explain_cmd_prompt(cmd)
        self._query_llm_service(query)

    @abstractmethod
    def _query_llm_service(self, question: str, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        """Query LLM service"""

    def _extract_shell_code_blocks(self, markdown_text: str) -> list:
        """Extract shell code blocks from markdown text"""
        pattern = r"```(bash|sh|shell)\n(.*?)(?=\n\s*```)"
        bash_blocks = re.findall(pattern, markdown_text, re.DOTALL | re.MULTILINE)
        cmds = list(dict.fromkeys("\n".join([block[1].strip() for block in bash_blocks]).splitlines()))
        return [cmd for cmd in cmds if cmd and not cmd.startswith("#")]  # remove comments and empty lines

    def _extract_python_code_blocks(self, markdown_text: str) -> str:
        """Extract Python code blocks from markdown text"""
        pattern = r"```python\n(.*?)(?=\n\s*```)"
        python_blocks = re.findall(pattern, markdown_text, re.DOTALL | re.MULTILINE)
        return "\n\n".join(python_blocks)

    def _get_context_length(self, context: list) -> int:
        length = 0
        for content in context:
            temp = content["content"]
            leng = len(temp)
            length += leng
        return length

    def _gen_sudo_prompt(self) -> str:
        if is_root():
            return prompt_general_root_true
        return prompt_general_root_false

    def _gen_system_prompt(self) -> str:
        return prompt_general_system.format(os=get_os_info(), prompt_general_root=self._gen_sudo_prompt())

    def _gen_shell_prompt(self, question: str) -> str:
        return f"{question}\n\n{prompt_single_line_cmd}"

    def _gen_chat_prompt(self, question: str) -> str:
        return prompt_general_chat.format(question=question, os=get_os_info())

    def _gen_explain_cmd_prompt(self, cmd: str) -> str:
        return prompt_general_explain_cmd.format(cmd=cmd)
