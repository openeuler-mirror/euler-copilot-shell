#!/bin/bash
# Witty 开发环境一键搭建 — Windows + WSL
# 在 WSL openEuler 发行版中运行此脚本
set -euo pipefail

echo "=== Witty Dev Environment Setup (WSL) ==="
echo ""

# 1. 检查是否在 openEuler 环境中
if [ ! -f /etc/openEuler-release ] 2>/dev/null; then
  if grep -qi openeuler /etc/os-release 2>/dev/null; then
    :
  else
    echo "⚠️  当前不是 openEuler 系统。请确保在 openEuler WSL 发行版中运行此脚本。"
    echo "   检测到的系统:"
    cat /etc/os-release 2>/dev/null | head -3 || echo "  无法检测"
    echo ""
    echo "  继续安装？(y/n)"
    read -r CONTINUE
    [ "$CONTINUE" = "y" ] || exit 1
  fi
fi

# 2. 安装开发依赖
echo "📦 更新包索引..."
yum makecache -q 2>/dev/null || true

echo "📦 安装 Go..."
yum install -y golang 2>/dev/null || {
  echo "⚠️  go 不在默认仓库中，请手动安装 Go 1.26+"
  echo "   参考: https://go.dev/doc/install"
}

echo "📦 安装开发工具..."
yum install -y git make ShellCheck shfmt 2>/dev/null || {
  echo "⚠️  部分工具安装失败，请手动检查"
}

# 3. 验证
echo ""
echo "--- 版本验证 ---"
go version 2>/dev/null || echo "⚠️  Go 未安装"
shellcheck --version 2>/dev/null || echo "⚠️  shellcheck 未安装"
shfmt --version 2>/dev/null || echo "⚠️  shfmt 未安装"

# 4. 提示下一步
echo ""
echo "=== 环境搭建完成 ==="
echo ""
echo "下一步操作:"
echo "  1. 克隆仓库:"
echo "     git clone <repo-url> ~/witty && cd ~/witty"
echo ""
echo "  2. 初始化 Go modules:"
echo "     go mod download"
echo ""
echo "  3. 配置 Agent 连接:"
echo "     cp .agents/config.template.yaml .agents/config.yaml"
echo "     # 编辑 .agents/config.yaml，将 active 设为 wsl"
echo ""
echo "  4. 验证构建:"
echo "     go build ./cmd/witty"
echo ""
echo "  5. 运行测试:"
echo "     go test ./..."
