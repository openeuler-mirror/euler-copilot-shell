"""应用入口点"""

import sys

from app.tui import EulerCopilot


def main() -> None:
    """主函数"""
    app = EulerCopilot()
    app.run()


if __name__ == "__main__":
    sys.exit(main() or 0)
