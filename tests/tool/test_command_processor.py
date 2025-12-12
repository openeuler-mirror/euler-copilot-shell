"""命令处理器测试"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, cast

import pytest

from backend.base import LLMClientBase
from i18n.manager import _
from tool import command_processor
from tool.command_processor import is_command_safe, process_command

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from backend.models import ModelInfo


class StubLLMClient(LLMClientBase):
    """最小实现，只提供 get_llm_response 所需行为"""

    def __init__(self, messages: list[str]) -> None:
        """Store canned responses for assertions."""
        self._messages = messages

    async def get_llm_response(self, prompt: str) -> AsyncGenerator[str, None]:  # noqa: D102
        for message in self._messages:
            yield message

    async def interrupt(self) -> None:  # noqa: D102
        return

    async def get_available_models(self) -> list[ModelInfo]:  # noqa: D102
        return []

    def reset_conversation(self) -> None:  # noqa: D102
        return

    async def close(self) -> None:  # noqa: D102
        return


class _StubProcess:
    """可控的 asyncio.subprocess.Process 替身"""

    def __init__(self, stdout_lines: list[bytes], stderr_bytes: bytes, returncode: int) -> None:
        self.stdout = _LineReader(stdout_lines)
        self.stderr = _BytesReader(stderr_bytes)
        self._returncode = returncode
        self.returncode = None

    async def wait(self) -> int:
        return self._returncode


class _LineReader:
    def __init__(self, lines: list[bytes]) -> None:
        self._lines = lines
        self._index = 0

    async def readline(self) -> bytes:
        if self._index >= len(self._lines):
            return b""
        line = self._lines[self._index]
        self._index += 1
        return line


class _BytesReader:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    async def read(self) -> bytes:
        return self._payload


@pytest.mark.unit
def test_is_command_safe_detects_blacklist() -> None:
    """黑名单词命令应被视为不安全"""
    assert is_command_safe("ls -la") is True
    assert is_command_safe("rm -rf /") is False


@pytest.mark.asyncio
async def test_process_command_with_empty_input() -> None:
    """空输入应提示用户重新输入"""
    llm_client = StubLLMClient(["unused"])
    result = [item async for item in process_command("   ", llm_client)]
    assert result == [(_("请输入有效命令或问题。"), True)]


@pytest.mark.asyncio
async def test_process_command_falls_back_to_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    """找不到系统命令时应调用大模型"""
    llm_client = StubLLMClient(["LLM output"])
    monkeypatch.setattr("tool.command_processor.shutil.which", lambda _: None)

    output = [item async for item in process_command("custom question", llm_client)]

    assert output == [("LLM output", True)]


@pytest.mark.asyncio
async def test_process_command_runs_safe_system_command(monkeypatch: pytest.MonkeyPatch) -> None:
    """检测到系统命令且安全时，应委托 _stream_system_command"""
    llm_client = StubLLMClient([])
    monkeypatch.setattr("tool.command_processor.shutil.which", lambda _: "/bin/echo")
    monkeypatch.setattr("tool.command_processor.is_command_safe", lambda _: True)

    async def fake_stream(
        command: str,
        client: StubLLMClient,
        logger: logging.Logger,
    ) -> AsyncGenerator[tuple[str, bool], None]:
        assert command == "echo hi"
        assert client is llm_client
        assert logger.name == "tool.command_processor"
        yield ("line", False)

    monkeypatch.setattr("tool.command_processor._stream_system_command", fake_stream)

    output = [item async for item in process_command("echo hi", llm_client)]

    assert output == [("line", False)]


@pytest.mark.asyncio
async def test_process_command_blocks_unsafe_system_command(monkeypatch: pytest.MonkeyPatch) -> None:
    """黑名单命令应被阻止并提示用户"""
    llm_client = StubLLMClient([])
    monkeypatch.setattr("tool.command_processor.shutil.which", lambda _: "/bin/rm")

    output = [item async for item in process_command("rm -rf /", llm_client)]

    assert output == [(_("检测到不安全命令，已阻止执行。"), True)]


@pytest.mark.asyncio
async def test_stream_system_command_handles_creation_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """子进程创建失败时应调用错误处理逻辑"""
    llm_client = StubLLMClient([])
    captured: list[tuple[str, StubLLMClient]] = []

    async def fake_create(command: str, logger: logging.Logger) -> _StubProcess | None:
        assert command == "ls"
        assert logger.name == "tool.command_processor"
        return None

    async def fake_handle_error(
        command: str,
        client: StubLLMClient,
    ) -> AsyncGenerator[tuple[str, bool], None]:
        captured.append((command, client))
        yield ("startup failure", False)

    monkeypatch.setattr(command_processor, "_create_subprocess", fake_create)
    monkeypatch.setattr(command_processor, "_handle_subprocess_creation_error", fake_handle_error)

    logger = logging.getLogger("tool.command_processor")
    output = [item async for item in command_processor._stream_system_command("ls", llm_client, logger)]  # noqa: SLF001

    assert output == [("startup failure", False)]
    assert captured == [("ls", llm_client)]


@pytest.mark.asyncio
async def test_stream_system_command_passes_through_execution(monkeypatch: pytest.MonkeyPatch) -> None:
    """正常创建子进程时应透传执行流"""
    llm_client = StubLLMClient([])
    proc = _StubProcess([], b"", 0)

    async def fake_create(command: str, logger: logging.Logger) -> _StubProcess:
        assert command == "echo hi"
        assert logger.name == "tool.command_processor"
        return proc

    async def fake_execute(
        proc_obj: _StubProcess,
        command: str,
        client: StubLLMClient,
        logger: logging.Logger,
    ) -> AsyncGenerator[tuple[str, bool], None]:
        assert proc_obj is proc
        assert command == "echo hi"
        assert client is llm_client
        assert logger.name == "tool.command_processor"
        yield ("from executor", False)

    monkeypatch.setattr(command_processor, "_create_subprocess", fake_create)
    monkeypatch.setattr(command_processor, "_execute_and_stream_output", fake_execute)

    logger = logging.getLogger("tool.command_processor")
    output = [item async for item in command_processor._stream_system_command("echo hi", llm_client, logger)]  # noqa: SLF001

    assert output == [("from executor", False)]


@pytest.mark.asyncio
async def test_execute_and_stream_output_success() -> None:
    """命令成功时应输出所有行并附带完成状态"""
    proc = _StubProcess([b"line1\r\n", b"line2\n"], b"", returncode=0)
    llm_client = StubLLMClient([])
    logger = logging.getLogger("tool.command_processor")

    proc_for_test = cast("Any", proc)
    output = [
        item
        async for item in command_processor._execute_and_stream_output(  # noqa: SLF001
            proc_for_test,
            "echo hi",
            llm_client,
            logger,
        )
    ]

    assert output == [
        ("line1\n", False),
        ("line2\n", False),
        (_("\n[命令完成] 退出码: {returncode}").format(returncode=0), False),
    ]


@pytest.mark.asyncio
async def test_execute_and_stream_output_failure_triggers_llm() -> None:
    """非零退出码会产出错误信息并继续流式大模型建议"""
    proc = _StubProcess([], b"permission denied", returncode=1)
    llm_client = StubLLMClient(["Try sudo"])
    logger = logging.getLogger("tool.command_processor")

    proc_for_test = cast("Any", proc)
    output = [
        item
        async for item in command_processor._execute_and_stream_output(  # noqa: SLF001
            proc_for_test,
            "touch secret",
            llm_client,
            logger,
        )
    ]

    assert output == [
        (_("[命令失败] 退出码: {returncode}").format(returncode=1), False),
        ("Try sudo", True),
    ]
