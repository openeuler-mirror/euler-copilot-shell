"""工具模块入口，提供惰性导入以避免循环依赖。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .command_processor import is_command_safe, process_command
    from .oi_backend_init import backend_init
    from .oi_llm_config import llm_config
    from .oi_select_agent import select_agent

__all__ = [
    "backend_init",
    "is_command_safe",
    "llm_config",
    "process_command",
    "select_agent",
]


def _lazy_import(name: str) -> Any:
    if name == "backend_init":
        from .oi_backend_init import backend_init as target  # noqa: PLC0415

        return target
    if name == "is_command_safe":
        from .command_processor import is_command_safe as target  # noqa: PLC0415

        return target
    if name == "llm_config":
        from .oi_llm_config import llm_config as target  # noqa: PLC0415

        return target
    if name == "process_command":
        from .command_processor import process_command as target  # noqa: PLC0415

        return target
    if name == "select_agent":
        from .oi_select_agent import select_agent as target  # noqa: PLC0415

        return target
    msg = f"module {__name__!s} has no attribute {name!s}"
    raise AttributeError(msg)


def __getattr__(name: str) -> Any:
    # Textual TUI 组件和部署助手的体积较大，而且在导入 ``tool`` 包时
    # 常常只需要验证器等轻量模块。保持惰性加载可以避免测试收集时
    # 触发昂贵的副作用，同时彻底规避循环导入。
    target = _lazy_import(name)
    globals()[name] = target
    return target
