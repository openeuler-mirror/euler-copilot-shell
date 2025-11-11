"""
浏览器登录功能

实现通过浏览器跳转进行 openEuler Intelligence 登录
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
import webbrowser

from config.manager import ConfigManager
from i18n.manager import _
from log.manager import get_logger
from tool.callback_server import CallbackServer
from tool.validators import is_browser_available

logger = get_logger(__name__)

# HTTP 状态码常量
HTTP_OK = 200


def get_auth_url(base_url: str) -> tuple[str | None, str | None]:
    """
    从后端获取授权 URL 和登录令牌

    Args:
        base_url: openEuler Intelligence 的基础 URL

    Returns:
        (授权 URL, 登录令牌) 元组，如果获取失败则返回 (None, None)

    """
    base_url = base_url.rstrip("/")
    request_url = f"{base_url}/api/auth/redirect?action=login"
    logger.info("请求授权 URL: %s", request_url)

    if not request_url.startswith(("http://", "https://")):
        logger.error("无效的 URL 协议: %s", request_url)
        return None, None

    try:
        with urllib.request.urlopen(request_url, timeout=10) as response:  # noqa: S310
            data = json.loads(response.read().decode("utf-8"))
            logger.debug("后端响应: %s", data)

            if data.get("code") == HTTP_OK and "result" in data:
                result = data["result"]
                auth_url = result.get("url")
                login_token = result.get("token")  # 后端可能返回一个临时令牌用于验证

                if auth_url:
                    logger.info("获取到授权 URL: %s", auth_url)
                    return auth_url, login_token

                logger.error("响应中缺少 result.url 字段")
                return None, None

            logger.error("后端返回错误: %s", data.get("message", "未知错误"))
            return None, None

    except Exception as e:
        logger.exception("获取授权 URL 失败")
        sys.stderr.write(_("✗ Failed to get authorization URL: {error}\n").format(error=e))
        return None, None


def poll_login_status(base_url: str, max_attempts: int = 60, interval: int = 2) -> str | None:
    """
    轮询检查登录状态并获取 session

    Args:
        base_url: openEuler Intelligence 的基础 URL
        max_attempts: 最大尝试次数，默认 60 次（2 分钟）
        interval: 轮询间隔（秒），默认 2 秒

    Returns:
        ECSESSION（API Key），如果登录失败或超时则返回 None

    """
    base_url = base_url.rstrip("/")
    check_url = f"{base_url}/api/user/session"

    logger.info("开始轮询登录状态...")

    for attempt in range(1, max_attempts + 1):
        try:
            # 尝试获取当前 session
            with urllib.request.urlopen(check_url, timeout=5) as response:  # noqa: S310
                data = json.loads(response.read().decode("utf-8"))

                if data.get("code") == HTTP_OK and "result" in data:
                    result = data["result"]
                    session_id = result.get("sessionId")
                    if session_id:
                        logger.info("检测到登录成功，获得 session")
                        return session_id

        except urllib.error.HTTPError:
            # HTTP 错误，可能还未登录
            pass
        except Exception:
            # 其他错误，继续尝试
            logger.exception("轮询出错:")

        # 显示进度
        _print_progress(attempt, max_attempts)

        # 等待后再次尝试
        if attempt < max_attempts:
            time.sleep(interval)

    logger.error("登录超时")
    return None


def browser_login() -> None:
    """
    执行浏览器登录流程

    1. 从配置读取 openEuler Intelligence 的地址
    2. 获取授权 URL
    3. 启动本地回调服务器
    4. 打开浏览器访问 launcher 页面
    5. launcher 页面打开授权 URL 并接收 postMessage
    6. 接收 sessionId 并保存到配置

    """
    logger.info("开始浏览器登录流程")

    # 检查浏览器是否可用
    if not is_browser_available():
        sys.stdout.write(_("✗ Error: Browser is not available in current environment\n"))
        sys.stdout.write(_("This feature requires a graphical environment with browser support.\n"))
        sys.stdout.write(_("If you are using SSH, please run this command on the server directly\n"))
        sys.stdout.write(_("or use X11 forwarding / VNC to enable graphical access.\n"))
        sys.exit(1)

    config_manager = _load_config_and_check_url()
    callback_server = CallbackServer()

    try:
        _initiate_login_flow(config_manager, callback_server)
        auth_result = callback_server.wait_for_auth(timeout=300)
        _handle_auth_result(auth_result, config_manager)
    except KeyboardInterrupt:
        logger.info("用户取消登录")
        sys.stdout.write(_("\n\n✗ Login cancelled by user\n"))
        sys.exit(130)  # 标准的 SIGINT 退出码
    except Exception as e:
        logger.exception("登录过程中发生错误")
        sys.stdout.write(_("\n✗ An error occurred during login: {error}\n").format(error=e))
        sys.exit(1)
    finally:
        # 确保关闭服务器
        callback_server.stop()


def _load_config_and_check_url() -> ConfigManager:
    """加载配置并检查 openEuler Intelligence URL。"""
    config_manager = ConfigManager()
    base_url = config_manager.get_eulerintelli_url()

    if not base_url:
        sys.stdout.write(
            _("✗ Error: openEuler Intelligence URL not configured\n")
            + _("Please run deployment initialization first: oi --init\n"),
        )
        sys.exit(1)

    logger.info("使用 openEuler Intelligence URL: %s", base_url)
    return config_manager


def _initiate_login_flow(config_manager: ConfigManager, callback_server: CallbackServer) -> None:
    """获取授权 URL，启动服务器并打开浏览器。"""
    base_url = config_manager.get_eulerintelli_url()
    sys.stdout.write(_("Getting authorization URL from server...\n"))
    auth_url, _token = get_auth_url(base_url)

    if not auth_url:
        sys.stdout.write(_("✗ Failed to get authorization URL\n"))
        sys.exit(1)

    logger.info("授权 URL: %s", auth_url)

    # 启动回调服务器并获取 launcher URL
    launcher_url = callback_server.start(auth_url)

    # 打开浏览器访问 launcher 页面
    sys.stdout.write(_("Opening browser for login...\n"))
    sys.stdout.write(_("If the browser doesn't open automatically, please visit:\n"))
    sys.stdout.write(f"  {launcher_url}\n\n")
    sys.stdout.flush()

    webbrowser.open(launcher_url)

    # 等待回调
    sys.stdout.write(_("Waiting for login to complete...\n"))


def _handle_auth_result(auth_result: dict, config_manager: ConfigManager) -> None:
    """处理认证结果并保存 session。"""
    result_type = auth_result.get("type")

    if result_type == "session":
        session_id = auth_result.get("sessionId")
        if session_id:
            config_manager.set_eulerintelli_key(session_id)
            logger.info("已保存 API Key 到配置")

            sys.stdout.write(_("\n✓ Login successful!\n"))
            sys.stdout.write(_("✓ API Key has been saved to configuration\n"))
            sys.exit(0)
        else:
            sys.stdout.write(_("\n✗ Login failed: No session ID received\n"))
            sys.exit(1)
    elif result_type == "error":
        error_desc = auth_result.get("error_description", "未知错误")
        sys.stdout.write(_("\n✗ Login failed: {error}\n").format(error=error_desc))
        sys.exit(1)
    else:
        sys.stdout.write(_("\n✗ Login failed: Unknown result\n"))
        sys.exit(1)


def _print_progress(attempt: int, max_attempts: int) -> None:
    """打印轮询进度"""
    if attempt % 5 == 0:
        sys.stdout.write(f"  等待登录... ({attempt}/{max_attempts})\n")
        sys.stdout.flush()
