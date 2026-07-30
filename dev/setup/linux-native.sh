#!/bin/bash
# Witty 开发环境一键搭建 — Linux 原生 openEuler（裸金属 / VM / SSH）
# 直接在 openEuler 系统中运行此脚本
# 用法: bash dev/setup/linux-native.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEPS_SCRIPT="${SCRIPT_DIR}/install-deps.sh"
if [ ! -f "$DEPS_SCRIPT" ]; then
  echo "❌ 找不到依赖安装脚本: ${DEPS_SCRIPT}"
  exit 1
fi

echo "=== Witty Dev Environment Setup (Linux native) ==="
echo ""

if [ ! -f /etc/openEuler-release ] 2>/dev/null; then
  if grep -qi openeuler /etc/os-release 2>/dev/null; then
    :
  else
    echo "⚠️  当前不是 openEuler 系统。请确保在 openEuler 服务器上运行此脚本。"
    echo "   检测到的系统:"
    cat /etc/os-release 2>/dev/null | head -3 || echo "  无法检测"
    echo ""
    echo "  继续安装？(y/n)"
    read -r CONTINUE
    [ "$CONTINUE" = "y" ] || exit 1
  fi
fi

bash "${DEPS_SCRIPT}"

echo ""
echo "=== 环境搭建完成 ==="
echo ""
echo "下一步操作:"
echo "  1. 配置 Agent 连接:"
echo "     cp .agents/config.template.yaml .agents/config.yaml"
echo "     # 编辑 .agents/config.yaml，将 active 设为 ssh"
echo ""
echo "  2. 验证构建（严禁 go build，必须用 build 脚本）:"
echo "     bash scripts/build.sh"
echo ""
echo "  3. 运行测试:"
echo "     go test -count=1 ./..."
echo ""
echo "  4. 试运行:"
echo "     build/linux-\$(uname -m | sed 's/x86_64/amd64/;s/aarch64/arm64/')/witty version"
