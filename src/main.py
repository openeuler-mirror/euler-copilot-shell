"""TUI 应用"""

import contextlib

from app.tui import TUIApplication


def main() -> None:
    """主函数"""
    app = TUIApplication()
    with contextlib.suppress(KeyboardInterrupt):
        app.run()

if __name__ == "__main__":
    main()
