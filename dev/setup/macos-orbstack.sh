#!/bin/bash
# Witty 开发环境一键搭建 — macOS + OrbStack openEuler VM
# 用法: ./macos-orbstack.sh [vm_name] [openeuler_version] [arch]
#   arch: arm64 (默认) 或 amd64 (Apple Silicon 上通过 Rosetta 2 转译)
set -euo pipefail

VM_NAME="${1:-witty-openeuler}"
OPENEULER_VERSION="${2:-24.03}"
VM_ARCH="${3:-arm64}"

echo "=== Witty Dev Environment Setup (macOS + OrbStack) ==="
echo ""

# 1. 检查 OrbStack
if ! command -v orb &>/dev/null; then
    echo "❌ OrbStack 未安装。请从 https://orbstack.dev/download 下载安装后重试。"
    exit 1
fi
echo "✅ OrbStack 已安装"

# 2. 创建 openEuler VM
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

# 3. 安装开发依赖
echo "📦 在 VM 中安装开发依赖..."
orb -m "${VM_NAME}" -u root <<'DEPS'
set -euo pipefail

# 带重试的下载函数，防止 GitHub 间歇性 504
download() {
    local url="$1" out="$2" max_retries=3 retry=0 delay=5 http_code
    while [ $retry -lt $max_retries ]; do
        http_code=$(curl -sL -w "%{http_code}" -o "$out" "$url")
        if [ "$http_code" = "200" ]; then
            if file "$out" | grep -qi html; then
                echo "    ⚠️  下载到 HTML 错误页，重试..."
            else
                return 0
            fi
        else
            echo "    ⚠️  HTTP ${http_code}，${delay}s 后重试 ($((retry+1))/$max_retries)..."
        fi
        retry=$((retry+1))
        sleep $delay
        delay=$((delay*2))
    done
    echo "  ❌ 下载失败: $url"
    return 1
}

echo "  更新包索引..."
yum makecache -q 2>/dev/null || true

echo "  安装基础工具 (git, make)..."
yum install -y git make 2>/dev/null

# 动态检测 VM 内架构
HOST_ARCH=$(uname -m)
case "$HOST_ARCH" in
    aarch64)  GO_ARCH="arm64";  SC_ARCH="aarch64"; SF_ARCH="arm64"  ;;
    x86_64)   GO_ARCH="amd64";  SC_ARCH="x86_64";  SF_ARCH="amd64"  ;;
    *) echo "  ❌ 不支持的架构: $HOST_ARCH"; exit 1 ;;
esac
echo "  检测到架构: ${HOST_ARCH}"

# Go 1.26+
echo "  安装 Go 1.26+..."
if ! /usr/local/go/bin/go version 2>/dev/null | grep -q "go1.2[6-9]"; then
    download "https://go.dev/dl/go1.26.0.linux-${GO_ARCH}.tar.gz" /tmp/go.tar.gz
    rm -rf /usr/local/go
    tar -C /usr/local -xzf /tmp/go.tar.gz
    echo "  ✅ Go 1.26 安装完成"
else
    echo "  Go 1.26 已安装，跳过"
fi

# ShellCheck (从 GitHub 下载)
echo "  安装 ShellCheck..."
if ! command -v shellcheck &>/dev/null; then
    download "https://github.com/koalaman/shellcheck/releases/download/v0.11.0/shellcheck-v0.11.0.linux.${SC_ARCH}.tar.xz" /tmp/sc.tar.xz
    tar -xJf /tmp/sc.tar.xz -C /tmp
    cp /tmp/shellcheck-v0.11.0/shellcheck /usr/local/bin/
    rm -rf /tmp/sc.tar.xz /tmp/shellcheck-v0.11.0
    echo "  ✅ ShellCheck 安装完成"
else
    echo "  ShellCheck 已安装，跳过"
fi

# shfmt (从 GitHub 下载)
echo "  安装 shfmt..."
if ! command -v shfmt &>/dev/null; then
    download "https://github.com/mvdan/sh/releases/download/v3.13.1/shfmt_v3.13.1_linux_${SF_ARCH}" /usr/local/bin/shfmt
    chmod +x /usr/local/bin/shfmt
    echo "  ✅ shfmt 安装完成"
else
    echo "  shfmt 已安装，跳过"
fi

echo ""
echo "  --- 版本验证 ---"
export PATH=/usr/local/go/bin:$PATH
go version 2>/dev/null || echo "  ⚠️  Go 未安装"
shellcheck --version 2>/dev/null | head -1 || echo "  ⚠️  shellcheck 未安装"
shfmt --version 2>/dev/null || echo "  ⚠️  shfmt 未安装"
DEPS

# 4. 提示下一步
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
echo "     orb -m ${VM_NAME} -u root bash -c 'export PATH=/usr/local/go/bin:\$PATH && go version && shellcheck --version && shfmt --version'"
echo ""
echo "常用命令:"
echo "  orb -m ${VM_NAME}              # 进入 VM shell"
echo "  orb -m ${VM_NAME} '<command>'  # 在 VM 中执行命令"
echo "  orb list                       # 列出所有机器"
echo ""
echo "注意: VM 中需 export PATH=/usr/local/go/bin:\$PATH 以使用 Go 1.26"
