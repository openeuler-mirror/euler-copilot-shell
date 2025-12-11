"""Tests for log.manager.LogManager empty-log cleanup behaviour."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from log.manager import LogManager

if TYPE_CHECKING:
    import pytest


def _set_fake_home(monkeypatch: pytest.MonkeyPatch, fake_home: Path) -> None:
    """Force Path.home() to return the provided directory."""

    def _fake_home(cls: type[Path]) -> Path:
        del cls
        return fake_home

    monkeypatch.setattr(Path, "home", classmethod(_fake_home))


def _assert_no_extra_handlers() -> None:
    """Remove all handlers from the root logger to isolate tests."""
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        handler.close()
        root_logger.removeHandler(handler)


def test_stale_empty_logs_are_removed_during_init(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Ensure empty files from previous runs are deleted when the manager starts."""
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    _set_fake_home(monkeypatch, fake_home)

    log_dir = fake_home / ".cache" / "witty" / "logs"
    log_dir.mkdir(parents=True)

    date_prefix = datetime.now(tz=UTC).strftime("%Y%m%d")
    stale_empty = log_dir / f"witty-assistant-{date_prefix}-000000.log"
    stale_empty.touch()
    non_empty = log_dir / f"witty-assistant-{date_prefix}-010101.log"
    non_empty.write_text("active log entry")

    _assert_no_extra_handlers()
    manager = LogManager()

    assert not stale_empty.exists()
    assert non_empty.exists()
    assert manager.current_log_file is not None
    assert manager.current_log_file.exists()

    logging.shutdown()
    _assert_no_extra_handlers()


def test_cleanup_empty_logs_removes_current_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """cleanup_empty_logs should delete the active file when it stayed empty."""
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    _set_fake_home(monkeypatch, fake_home)

    _assert_no_extra_handlers()
    manager = LogManager()

    current_file = manager.current_log_file
    assert current_file is not None
    assert current_file.exists()

    logging.shutdown()
    _assert_no_extra_handlers()
    manager.cleanup_empty_logs()

    assert not current_file.exists()

    _assert_no_extra_handlers()
