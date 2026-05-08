"""
命令处理器

功能说明:
1. 异步流式执行系统命令: 逐行输出 STDOUT。
2. 结束后输出总结状态(退出码，成功/失败)。
3. 失败时自动向 LLM 请求分析建议并继续流式输出建议。
"""

from __future__ import annotations

import asyncio
import shutil
from typing import TYPE_CHECKING

from backend.hermes.mcp_helpers import is_mcp_message
from i18n.manager import _
from log.manager import get_logger

if TYPE_CHECKING:
    import logging
    from collections.abc import AsyncGenerator

    from backend import LLMClientBase

# 定义危险命令黑名单
BLACKLIST = ["rm", "sudo", "shutdown", "reboot", "mkfs"]


def is_command_safe(command: str) -> bool:
    """
    检查命令是否安全

    检查命令是否安全，若包含黑名单中的子串则返回 False。
    """
    return all(dangerous not in command for dangerous in BLACKLIST)


async def process_command(command: str, llm_client: LLMClientBase) -> AsyncGenerator[tuple[str, bool], None]:
    """
    处理用户输入的命令

    1. 检查 PATH 中是否存在用户输入的命令（取输入字符串的第一个单词）；
    2. 若存在，则检查命令安全性，安全时执行命令；若执行失败则将错误信息附带命令发送给大模型；
    3. 若不存在，则直接将命令内容发送给大模型生成建议。

    返回一个元组 (content, is_llm_output)，其中：
    - content: 输出内容
    - is_llm_output: 是否是LLM输出（True表示LLM输出，应使用富文本；False表示命令输出，应使用纯文本）
    """
    logger = get_logger(__name__)
    logger.debug("开始处理命令: %s", command)

    tokens = command.split()
    if not tokens:
        yield (_("请输入有效命令或问题。"), True)  # 作为LLM输出处理
        return

    prog = tokens[0]
    if shutil.which(prog) is None:
        # 非系统命令 -> 直接走 LLM
        logger.debug("向 LLM 发送问题: %s", command)
        try:
            async for suggestion in llm_client.get_llm_response(command):
                is_mcp_message_flag = is_mcp_message(suggestion)
                yield (suggestion, not is_mcp_message_flag)
        except asyncio.CancelledError:
            logger.info("LLM 响应被用户中断")
            raise
        return

    logger.info("检测到系统命令: %s", prog)
    if not is_command_safe(command):
        logger.warning("命令被安全检查阻止: %s", command)
        yield (_("检测到不安全命令，已阻止执行。"), True)
        return

    # 流式执行
    try:
        async for item in _stream_system_command(command, llm_client, logger):
            yield item
    except asyncio.CancelledError:
        logger.info("命令执行被用户中断")
        raise


async def _stream_system_command(
    command: str,
    llm_client: LLMClientBase,
    logger: logging.Logger,
) -> AsyncGenerator[tuple[str, bool], None]:
    """
    流式执行系统命令。

    逐行产出 STDOUT (is_llm_output=False)。结束后追加一条状态行: 成功 / 失败。
    若失败随后继续产出 LLM 建议 (is_llm_output=True，除非是 MCP 消息)。
    支持中断处理，会正确终止子进程。
    """
    # 创建子进程
    proc = await _create_subprocess(command, logger)
    if proc is None:
        async for item in _handle_subprocess_creation_error(command, llm_client):
            yield item
        return

    # 执行命令并处理输出
    try:
        async for item in _execute_and_stream_output(proc, command, llm_client, logger):
            yield item
    except asyncio.CancelledError:
        await _handle_process_interruption(proc, logger)
        raise


async def _create_subprocess(command: str, logger: logging.Logger) -> asyncio.subprocess.Process | None:
    """创建子进程，返回 None 表示创建失败"""
    try:
        return await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except OSError:
        logger.exception("创建子进程失败")
        return None


async def _handle_subprocess_creation_error(
    command: str,
    llm_client: LLMClientBase,
) -> AsyncGenerator[tuple[str, bool], None]:
    """处理子进程创建失败的情况"""
    yield (_("[命令启动失败] 无法创建子进程"), False)
    query = _("无法启动命令 '{command}'，请分析可能原因并给出解决建议。").format(command=command)
    async for suggestion in llm_client.get_llm_response(query):
        is_mcp_message_flag = is_mcp_message(suggestion)
        yield (suggestion, not is_mcp_message_flag)


async def _execute_and_stream_output(
    proc: asyncio.subprocess.Process,
    command: str,
    llm_client: LLMClientBase,
    logger: logging.Logger,
) -> AsyncGenerator[tuple[str, bool], None]:
    """执行命令并流式输出结果"""
    assert proc.stdout is not None  # 类型提示

    # 流式读取输出
    while True:
        line = await proc.stdout.readline()
        if not line:
            break
        # CR -> LF 规范化
        text = line.decode(errors="replace").replace("\r\n", "\n").replace("\r", "\n")
        yield (text, False)

    # 等待进程结束
    returncode = await proc.wait()
    success = returncode == 0

    if success:
        yield (_("\n[命令完成] 退出码: {returncode}").format(returncode=returncode), False)
        return

    # 处理命令失败的情况
    async for item in _handle_command_failure(proc, command, returncode, llm_client, logger):
        yield item


async def _handle_command_failure(
    proc: asyncio.subprocess.Process,
    command: str,
    returncode: int,
    llm_client: LLMClientBase,
    logger: logging.Logger,
) -> AsyncGenerator[tuple[str, bool], None]:
    """处理命令执行失败的情况"""
    # 读取 stderr
    stderr_text = await _read_stderr(proc)
    yield (_("[命令失败] 退出码: {returncode}").format(returncode=returncode), False)

    # 获取 LLM 建议
    logger.info("命令执行失败(returncode=%s)，向 LLM 请求建议", returncode)
    query = _(
        "命令 '{command}' 以非零状态 {returncode} 退出。\n"
        "标准错误输出如下：\n{stderr_text}\n"
        "请分析原因并提供解决建议。",
    ).format(command=command, returncode=returncode, stderr_text=stderr_text)
    async for suggestion in llm_client.get_llm_response(query):
        is_mcp_message_flag = is_mcp_message(suggestion)
        yield (suggestion, not is_mcp_message_flag)


async def _read_stderr(proc: asyncio.subprocess.Process) -> str:
    """读取进程的标准错误输出"""
    if proc.stderr is None:
        return ""

    try:
        stderr_bytes = await proc.stderr.read()
        return stderr_bytes.decode(errors="replace")
    except (OSError, asyncio.CancelledError):
        return _("读取 stderr 失败")


async def _handle_process_interruption(proc: asyncio.subprocess.Process, logger: logging.Logger) -> None:
    """处理进程中断，确保正确终止子进程"""
    logger.info("命令执行被中断，正在终止子进程")

    if proc.returncode is not None:
        return  # 进程已经结束

    # 尝试正常终止进程
    proc.terminate()
    try:
        await asyncio.wait_for(proc.wait(), timeout=5.0)
        logger.info("子进程已正常终止")
    except TimeoutError:
        # 强制杀死进程
        logger.warning("子进程未在5秒内终止，强制杀死")
        proc.kill()
        try:
            await asyncio.wait_for(proc.wait(), timeout=2.0)
        except TimeoutError:
            logger.exception("无法强制终止子进程")
