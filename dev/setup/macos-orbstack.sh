#!/bin/bash
# Witty 开发环境一键搭建 — macOS + OrbStack openEuler VM
# 用法: ./macos-orbstack.sh [vm_name] [openeuler_version] [arch]
#   arch: arm64 (默认) 或 amd64 (Apple Silicon 上通过 Rosetta 2 转译)
set -euo pipefail

VM_NAME="${1:-witty-openeuler}"
OPENEULER_VERSION="${2:-24.03}"
VM_ARCH="${3:-arm64}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEPS_SCRIPT="${SCRIPT_DIR}/install-deps.sh"
if [ ! -f "$DEPS_SCRIPT" ]; then
  echo "❌ 找不到依赖安装脚本: ${DEPS_SCRIPT}"
  exit 1
fi

echo "=== Witty Dev Environment Setup (macOS + OrbStack) ==="
echo ""

if ! command -v orb &>/dev/null; then
  echo "❌ OrbStack 未安装。请从 https://orbstack.dev/download 下载安装后重试。"
  exit 1
fi
echo "✅ OrbStack 已安装"

if orb list 2>/dev/null | grep -q "^${VM_NAME} "; then
  echo "✅ VM '${VM_NAME}' 已存在，跳过创建"
else
  echo "📦 创建 openEuler VM: ${VM_NAME}（版本: ${OPENEULER_VERSION}，架构: ${VM_ARCH}）..."
  if [ "${VM_ARCH}" = "amd64" ]; then
    orb create --arch amd64 "openeuler:${OPENEULER_VERSION}" "${VM_NAME}"
  else
    orb create "openeuler:${OPENEULER_VERSION}" "${VM_NAME}"
  fi
  echo "✅ VM 创建完成"
fi

echo "📦 在 VM 中安装开发依赖..."
orb -m "${VM_NAME}" -u root bash "${DEPS_SCRIPT}"

echo ""
echo "=== 环境搭建完成 ==="
echo ""
echo "下一步操作:"
echo "  1. OrbStack VM 可直接访问 macOS 文件系统"
echo "     在 VM 中 cd 到你的项目路径即可（如 /Users/<yourname>/path/to/witty）"
echo ""
echo "  2. 配置 Agent 连接:"
echo "     cp .agents/config.template.yaml .agents/config.yaml"
echo "     # 编辑 .agents/config.yaml，确认 active 为 orbstack"
echo ""
echo "  3. 验证工具链:"
echo "     orb -m ${VM_NAME} -u root bash -c 'source /etc/profile.d/go.sh && go version && shellcheck --version && shfmt --version'"
echo ""
echo "常用命令:"
echo "  orb -m ${VM_NAME}              # 进入 VM shell"
echo "  orb -m ${VM_NAME} '<command>'  # 在 VM 中执行命令"
echo "  orb list                       # 列出所有机器"
