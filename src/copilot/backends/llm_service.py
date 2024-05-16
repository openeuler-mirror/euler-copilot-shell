# Copyright (c) Huawei Technologies Co., Ltd. 2024-2024. All rights reserved.

import re
from abc import ABC, abstractmethod

from copilot.utilities.env_info import get_os_info, is_root


class LLMService(ABC):
    @abstractmethod
    def get_general_answer(self, question: str) -> str:
        pass

    @abstractmethod
    def get_shell_answer(self, question: str) -> str:
        pass

    def _extract_shell_code_blocks(self, markdown_text):
        shell_code_pattern = re.compile(r'```(?:bash|sh|shell)\n(?P<code>(?:\n|.)*?)\n```', re.DOTALL)
        matches = shell_code_pattern.finditer(markdown_text)
        cmds = [match.group('code') for match in matches]
        if cmds:
            return cmds[0]
        return markdown_text.replace('`', '')

    def _get_context_length(self, context: list) -> int:
        length = 0
        for content in context:
            temp = content['content']
            leng = len(temp)
            length += leng
        return length
    
    def _gen_sudo_prompt(self) -> str:
        if is_root():
            return '当前用户为 root 用户，你生成的 shell 命令不能包涵 sudo'
        else:
            return '当前用户为普通用户，若你生成的 shell 命令需要 root 权限，需要包含 sudo'

    def _gen_system_prompt(self) -> str:
        return f'''你是操作系统 {get_os_info()} 的运维助理，你精通当前操作系统的管理和运维，熟悉运维脚本的编写。
        你的任务是：
        根据用户输入的问题，提供相应的操作系统的管理和运维解决方案，并使用 shell 脚本或其它常用编程语言实现。
        你给出的答案必须符合当前操作系统要求，你不能使用当前操作系统没有的功能。
        除非有特殊要求，你的回答必须使用 Markdown 格式，并使用中文标点符号；
        但如果用户要求你只输出单行 shell 命令，你就不能输出多余的格式或文字。

        用户可能问你一些操作系统相关的问题，你尤其需要注意安装软件包的情景：
        openEuler 使用 dnf 或 yum 管理软件包，你不能在回答中使用 apt 或其他命令；
        Debian 和 Ubuntu 使用 apt 管理软件包，你也不能在回答中使用 dnf 或 yum 命令；
        你可能还会遇到使用其他类 unix 系统的情景，比如 macOS 要使用 Homebrew 安装软件包。

        请特别注意当前用户的权限：
        {self._gen_sudo_prompt()}

        在给用户返回 shell 命令时，你必须返回安全的命令，不能进行任何危险操作！
        如果涉及到删除文件、清理缓存、删除用户、卸载软件、wget下载文件等敏感操作，你必须生成安全的命令
        危险操作举例：
        `rm -rf /path/to/sth`
        `dnf remove -y package_name`
        你不能输出类似于上述例子的命令！

        由于用户使用命令行与你交互，你需要避免长篇大论，请使用简洁的语言，一般情况下你的回答不应超过300字。
        '''

    def _gen_shell_prompt(self, question: str) -> str:
        return f'''根据用户输入的问题，生成单行 shell 命令，并使用 Markdown 格式输出。

        用户的问题：
        {question}

        要求：
        1. 请用单行 shell 命令输出你的回答，不能使用多行 shell 命令
        2. 请用 Markdown 代码块输出 shell 命令
        3. 请解释你的回答，你要将你的解释附在命令代码块下方，你要有条理地解释命令中的每个步骤
        4. 当前操作系统是 {get_os_info()}，你的回答必须符合当前系统要求，不能使用当前系统没有的功能
        '''
