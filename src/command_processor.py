"""命令处理器"""

import shutil
import subprocess
from collections.abc import AsyncGenerator

from big_model import BigModelClient

# 定义危险命令黑名单
BLACKLIST = ["rm", "sudo", "shutdown", "reboot", "mkfs"]

def is_command_safe(command: str) -> bool:
    """检查命令是否安全

    检查命令是否安全，若包含黑名单中的子串则返回 False。
    """
    return all(dangerous not in command for dangerous in BLACKLIST)

def execute_command(command: str) -> tuple[bool, str]:
    """执行命令并返回结果

    尝试执行命令：
    返回 (True, 命令标准输出) 或 (False, 错误信息)。
    """
    try:
        result = subprocess.run(command, shell=True,  # noqa: S602
                                capture_output=True, text=True, timeout=600, check=False)
        if result.returncode != 0:
            return False, result.stderr
        return True, result.stdout
    except Exception as e:
        return False, str(e)

async def process_command(command: str, big_model_client: BigModelClient) -> AsyncGenerator[str, None]:
    """处理用户输入的命令

    1. 检查 PATH 中是否存在用户输入的命令（取输入字符串的第一个单词）；
    2. 若存在，则执行命令；若执行失败则将错误信息附带命令发送给大模型；
    3. 若不存在，则直接将命令内容发送给大模型生成建议。
    """
    tokens = command.split()
    if not tokens:
        yield "请输入有效命令或问题。"
        return

    prog = tokens[0]
    if shutil.which(prog) is not None:
        success, output = execute_command(command)
        if success:
            yield output
        else:
            # 执行失败，将错误信息反馈给大模型
            query = (
                f"命令 '{command}' 执行失败，错误信息如下：\n{output}\n"
                "请帮忙分析原因并提供解决建议。"
            )
            async for suggestion in big_model_client.generate_command_suggestion(query):
                yield suggestion
    else:
        # 不是已安装的命令，直接询问大模型
        async for suggestion in big_model_client.generate_command_suggestion(command):
            yield suggestion
