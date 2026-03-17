"""部署流程模态切换回归测试。"""

from __future__ import annotations

from typing import Any

import pytest
from textual.app import App

from app.deployment.components.env_check import EnvironmentCheckScreen
from app.deployment.components.modes import InitializationModeScreen


class _MountedScreenApp(App[None]):
    """用于挂载单个屏幕的测试应用。"""

    def __init__(self, screen: Any) -> None:
        super().__init__()
        self._initial_screen = screen

    def on_mount(self) -> None:
        """启动时显示目标屏幕。"""
        self.push_screen(self._initial_screen)


class _PushScreenRecorder:
    """兼容 await / 非 await 两种调用方式的 push_screen 记录器。"""

    def __init__(self) -> None:
        self.calls: list[Any] = []

    def __call__(self, screen: Any) -> _AwaitableNone:
        self.calls.append(screen)
        return _AwaitableNone()


class _AwaitableNone:
    """一个可等待但什么也不做的返回值。"""

    def __await__(self) -> Any:
        if False:
            yield None
        return None


@pytest.mark.asyncio
@pytest.mark.unit
async def test_initialization_mode_pushes_next_screen_without_dismiss(monkeypatch: pytest.MonkeyPatch) -> None:
    """初始化模式页切换到环境检查页时，不应提前 dismiss 自身。"""
    app = _MountedScreenApp(InitializationModeScreen())

    async with app.run_test() as pilot:
        await pilot.pause()
        screen = pilot.app.screen
        assert isinstance(screen, InitializationModeScreen)

        push_recorder = _PushScreenRecorder()
        dismiss_calls: list[bool] = []

        def fake_dismiss(*_args: Any, **_kwargs: Any) -> None:
            dismiss_calls.append(True)

        monkeypatch.setattr(pilot.app, "push_screen", push_recorder)
        monkeypatch.setattr(screen, "dismiss", fake_dismiss)

        await screen.on_deploy_new_pressed()

        assert len(push_recorder.calls) == 1
        assert isinstance(push_recorder.calls[0], EnvironmentCheckScreen)
        assert dismiss_calls == []

        await pilot.exit(None)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_environment_check_pushes_config_without_dismiss(monkeypatch: pytest.MonkeyPatch) -> None:
    """环境检查页进入部署配置页时，不应提前 dismiss 自身。"""
    async def fake_perform_environment_check(self: EnvironmentCheckScreen) -> None:  # noqa: ARG001
        return None

    monkeypatch.setattr(EnvironmentCheckScreen, "_perform_environment_check", fake_perform_environment_check)

    app = _MountedScreenApp(EnvironmentCheckScreen())

    async with app.run_test() as pilot:
        await pilot.pause()
        screen = pilot.app.screen
        assert isinstance(screen, EnvironmentCheckScreen)

        push_recorder = _PushScreenRecorder()
        dismiss_calls: list[bool] = []

        def fake_dismiss(*_args: Any, **_kwargs: Any) -> None:
            dismiss_calls.append(True)

        monkeypatch.setattr(pilot.app, "push_screen", push_recorder)
        monkeypatch.setattr(screen, "dismiss", fake_dismiss)

        await screen.on_continue_button_pressed()

        assert len(push_recorder.calls) == 1
        assert push_recorder.calls[0].__class__.__name__ == "DeploymentConfigScreen"
        assert dismiss_calls == []

        await pilot.exit(None)
