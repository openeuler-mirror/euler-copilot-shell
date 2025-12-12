"""
HTTP 回调服务器

用于接收 OAuth2/OIDC 认证流程的回调
通过本地 HTML 页面启动浏览器登录，并接收 postMessage 传递的 sessionId
"""

import socket
import socketserver
import threading
from http.server import BaseHTTPRequestHandler
from threading import Thread
from typing import ClassVar
from urllib.parse import parse_qs, urlparse

from log.manager import get_logger

logger = get_logger(__name__)


class CallbackHandler(BaseHTTPRequestHandler):
    """处理 OAuth2/OIDC 回调请求"""

    auth_result: ClassVar[dict] = {}
    auth_event: ClassVar[threading.Event] = threading.Event()
    auth_url: ClassVar[str] = ""  # 存储授权 URL

    def do_GET(self) -> None:
        """处理 GET 请求"""
        parsed = urlparse(self.path)

        if parsed.path in {"/", "/launcher"}:
            # 返回启动器页面
            self._send_launcher_page()
        elif parsed.path == "/callback":
            # 接收来自前端页面的 sessionId
            params = parse_qs(parsed.query)
            session_id = params.get("sessionId", [None])[0]

            if session_id:
                CallbackHandler.auth_result = {
                    "type": "session",
                    "sessionId": session_id,
                }
                self._send_success_page()
                # 设置事件，通知主线程认证完成
                CallbackHandler.auth_event.set()
            else:
                CallbackHandler.auth_result = {
                    "type": "error",
                    "error": "missing_session",
                    "error_description": "未收到 session ID",
                }
                self._send_error_page()
        else:
            # 其他路径返回 404
            self.send_response(404)
            self.end_headers()

    def _send_launcher_page(self) -> None:
        """发送启动器页面，用于打开授权 URL 并接收 postMessage"""
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Witty Assistant - 浏览器登录</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    text-align: center;
                    margin-top: 100px;
                    background-color: #f5f5f5;
                }}
                .container {{
                    background: white;
                    padding: 40px;
                    border-radius: 8px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                    max-width: 500px;
                    margin: 0 auto;
                }}
                .title {{
                    color: #333;
                    font-size: 1.5em;
                    margin-bottom: 20px;
                }}
                .status {{
                    color: #666;
                    margin: 20px 0;
                }}
                .loading {{
                    display: inline-block;
                    width: 20px;
                    height: 20px;
                    border: 3px solid #f3f3f3;
                    border-top: 3px solid #3498db;
                    border-radius: 50%;
                    animation: spin 1s linear infinite;
                }}
                @keyframes spin {{
                    0% {{ transform: rotate(0deg); }}
                    100% {{ transform: rotate(360deg); }}
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="title">Witty Assistant 浏览器登录</div>
                <div class="status" id="status">
                    <div class="loading"></div>
                    <p>正在打开登录窗口...</p>
                </div>
            </div>
            <script>
                // 打开授权 URL
                const authUrl = "{CallbackHandler.auth_url}";
                const authWindow = window.open(authUrl, "_blank", "width=800,height=600");

                if (!authWindow) {{
                    document.getElementById('status').innerHTML =
                        '<p style="color: #f44336;">无法打开登录窗口，请允许浏览器弹出窗口</p>';
                }} else {{
                    document.getElementById('status').innerHTML =
                        '<p>请在新窗口中完成登录...</p>';
                }}

                // 监听来自登录窗口的 postMessage
                window.addEventListener('message', function(event) {{
                    console.log('Received postMessage:', event.data);

                    if (event.data && event.data.type === 'auth_success') {{
                        const sessionId = event.data.sessionId;
                        console.log('Login successful, sessionId:', sessionId);

                        // 更新状态
                        document.getElementById('status').innerHTML =
                            '<p style="color: #4CAF50;">✓ 登录成功！</p>' +
                            '<p>正在保存认证信息...</p>';

                        // 发送 sessionId 到本地服务器
                        fetch('/callback?sessionId=' + encodeURIComponent(sessionId))
                            .then(response => response.text())
                            .then(() => {{
                                document.getElementById('status').innerHTML =
                                    '<p style="color: #4CAF50;">✓ 登录成功！</p>' +
                                    '<p>请返回终端查看结果</p>';

                                // 关闭授权窗口
                                if (authWindow && !authWindow.closed) {{
                                    authWindow.close();
                                }}

                                // 2秒后关闭当前窗口
                                setTimeout(function() {{
                                    window.close();
                                }}, 2000);
                            }})
                            .catch(error => {{
                                console.error('Failed to send sessionId:', error);
                                document.getElementById('status').innerHTML =
                                    '<p style="color: #f44336;">发送认证信息失败</p>';
                            }});
                    }}
                }}, false);

                // 检查授权窗口是否被关闭
                const checkInterval = setInterval(function() {{
                    if (authWindow && authWindow.closed) {{
                        clearInterval(checkInterval);
                        document.getElementById('status').innerHTML =
                            '<p style="color: #ff9800;">登录窗口已关闭</p>' +
                            '<p>如果您已完成登录，请等待...</p>' +
                            '<p>否则请返回终端重试</p>';
                    }}
                }}, 1000);
            </script>
        </body>
        </html>
        """
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))

    def _send_success_page(self) -> None:
        """发送成功页面"""
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>登录成功</title>
            <style>
                body { font-family: Arial, sans-serif; text-align: center; margin-top: 100px; }
                .success { color: #4CAF50; font-size: 2em; }
            </style>
        </head>
        <body>
            <div class="success">✓ 登录成功！</div>
            <p>认证信息已保存，您可以关闭此窗口。</p>
        </body>
        </html>
        """
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))

    def _send_error_page(self) -> None:
        """发送错误页面"""
        error = CallbackHandler.auth_result.get("error", "unknown")
        error_desc = CallbackHandler.auth_result.get("error_description", "未知错误")

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>登录失败</title>
            <style>
                body {{ font-family: Arial, sans-serif; text-align: center; margin-top: 100px; }}
                .error {{ color: #f44336; font-size: 2em; }}
            </style>
        </head>
        <body>
            <div class="error">✗ 登录失败</div>
            <p>错误: {error}</p>
            <p>描述: {error_desc}</p>
            <p>您可以关闭此窗口并返回终端重试。</p>
        </body>
        </html>
        """
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        """重写日志方法，使用我们的 logger"""
        logger.debug(format, *args)


class CallbackServer:
    """回调服务器管理类"""

    def __init__(self, start_port: int = 8081, max_attempts: int = 20) -> None:
        """
        初始化回调服务器

        Args:
            start_port: 起始端口号，默认 8081
            max_attempts: 最大尝试次数，默认 20

        """
        self.start_port = start_port
        self.max_attempts = max_attempts
        self.port = None
        self.server = None
        self.thread = None

    def _find_available_port(self) -> int:
        """
        查找可用端口

        Returns:
            可用的端口号

        Raises:
            RuntimeError: 如果找不到可用端口

        """
        for port in range(self.start_port, self.start_port + self.max_attempts):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                try:
                    sock.bind(("127.0.0.1", port))
                except OSError:
                    logger.debug("端口 %d 被占用，尝试下一个", port)
                    continue
                else:
                    logger.info("找到可用端口: %d", port)
                    return port

        msg = f"无法找到可用端口 ({self.start_port}-{self.start_port + self.max_attempts})"
        raise RuntimeError(msg)

    def start(self, auth_url: str) -> str:
        """
        启动服务器，返回 launcher URL

        Args:
            auth_url: 授权 URL（从后端获取）

        Returns:
            launcher 页面的 URL

        """
        # 重置状态
        CallbackHandler.auth_result = {}
        CallbackHandler.auth_event.clear()
        CallbackHandler.auth_url = auth_url

        # 查找可用端口
        self.port = self._find_available_port()

        # 创建服务器
        self.server = socketserver.TCPServer(("127.0.0.1", self.port), CallbackHandler)

        # 在新线程中启动服务器
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

        launcher_url = f"http://127.0.0.1:{self.port}/launcher"
        logger.info("回调服务器已启动: %s", launcher_url)
        return launcher_url

    def wait_for_auth(self, timeout: int = 300) -> dict:
        """
        等待接收认证结果

        Args:
            timeout: 超时时间(秒)，默认 5 分钟

        Returns:
            认证结果字典

        """
        logger.info("等待用户完成登录...")
        success = CallbackHandler.auth_event.wait(timeout=timeout)

        if not success:
            logger.error("等待登录超时")
            return {"type": "error", "error": "timeout", "error_description": "登录超时"}

        return CallbackHandler.auth_result

    def stop(self) -> None:
        """停止服务器"""
        if self.server:
            logger.info("正在关闭回调服务器...")
            self.server.shutdown()
            self.server.server_close()
            if self.thread:
                self.thread.join(timeout=2)
            logger.info("回调服务器已关闭")
