"""系统初始化工具模块"""

from __future__ import annotations

from pathlib import Path

from textual.app import App

from app.deployment import InitializationModeScreen
from config.manager import ConfigManager
from i18n.manager import _
from log.manager import get_logger


def backend_init() -> None:
    """初始化后端系统 - 启动 TUI 部署助手"""
    logger = get_logger(__name__)

    try:
        # 首先检查和更新配置文件
        logger.info("检查配置文件...")

        config_manager = ConfigManager()
        config_updated = config_manager.validate_and_update_config()

        if config_updated:
            logger.info("配置文件已更新")
        else:
            logger.info("配置文件检查完成")

        # 获取项目根目录的绝对路径
        project_root = Path(__file__).parent.parent
        css_path = str(project_root / "app" / "css" / "styles.tcss")

        class DeploymentApp(App):
            """部署 TUI 应用"""

            CSS_PATH = css_path
            TITLE = _("Witty Assistant 部署助手")

            def on_mount(self) -> None:
                """启动时先显示初始化模式选择界面"""
                self.push_screen(InitializationModeScreen())

        app = DeploymentApp()
        result = app.run()
        logger.info("部署结果: %s", result)

    except KeyboardInterrupt:
        logger.warning("用户中断部署")
    except ImportError:
        logger.exception("导入模块失败")
    except RuntimeError:
        logger.exception("部署过程中发生错误")
    except Exception:
        logger.exception("未预期的错误")
        raise
