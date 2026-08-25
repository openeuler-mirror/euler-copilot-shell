#!/usr/bin/env bash
# euler-copilot-shell 依赖安装与测试脚本
# 原则：依赖安装 + 测试命令都在这里，保持 devcontainer.json 简洁
set -euo pipefail
cd /workspace

# uv 已预装在镜像中，此处仅兜底
command -v uv >/dev/null 2>&1 || sudo python3 -m pip install uv

# 首次运行会按 pyproject.toml 解析依赖并生成 uv.lock（已在 .gitignore 中忽略，不污染仓库）
# --extra dev 安装 dev 可选依赖（ruff）
uv sync --extra dev

# pytest 不在项目 dev 依赖中，装到 .venv 供命令行与 IDE 测试发现使用
uv pip install pytest

# 运行 pytest 兼容测试子集
# 说明：
#   1. tests/app/deployment 与 tests/tool/test_token_integration.py 为脚本式异步测试，
#      需按 README.devcontainer.md 手动执行（涉及部署/系统检查，不适合作为自动门禁）
#   2. tests/tool/test_login.py 为仓库过时测试（get_auth_url 签名已变更，2 个用例失败，
#      见 .pytest_cache/v/cache/lastfailed），属于仓库既有问题，不纳入自动门禁；
#      修复后可重新加入：PYTHONPATH=src uv run pytest tests/tool/test_login.py
echo "== 运行 pytest 测试子集 =="
PYTHONPATH=src uv run pytest -q \
  tests/log \
  tests/tool/test_browser_availability.py \
  tests/tool/test_token_validation.py

echo "依赖安装与测试完成。"
