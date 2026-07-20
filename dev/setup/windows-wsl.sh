#!/bin/bash
# Witty 开发环境一键搭建 — Windows + WSL openEuler
# 在 WSL openEuler 发行版中运行此脚本
# 用法: bash dev/setup/windows-wsl.sh
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

# 2. 带重试的下载函数
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
dnf makecache -q 2>/dev/null || true

echo "  安装基础工具 (git, make, gcc, gdb)..."
dnf install -y git make gcc gdb 2>/dev/null

# 动态检测架构
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

# ShellCheck
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

# shfmt
echo "  安装 shfmt..."
if ! command -v shfmt &>/dev/null; then
    download "https://github.com/mvdan/sh/releases/download/v3.13.1/shfmt_v3.13.1_linux_${SF_ARCH}" /usr/local/bin/shfmt
    chmod +x /usr/local/bin/shfmt
    echo "  ✅ shfmt 安装完成"
else
    echo "  shfmt 已安装，跳过"
fi

# Witty-Builder yum repo (OpenCode RPM)
echo "  配置 Witty-Builder yum repo..."
cat > /etc/yum.repos.d/Witty-Builder.repo <<'YUMREPO'
[Witty-Builder]
name=EulerMaker Witty Builder
baseurl=https://eulermaker.openeuler.openatom.cn/api/ems5/repositories/witty-builder/openEuler:24.03-LTS-SP3/$basearch/
metadata_expire=60
enabled=1
gpgcheck=1
gpgkey=https://eulermaker.openeuler.openatom.cn/api/ems5/repositories/witty-builder/openEuler:24.03-LTS-SP3/$basearch/RPM-GPG-KEY-openEuler
YUMREPO
dnf makecache -q
echo "  ✅ Witty-Builder repo 已配置"

echo "  安装 OpenCode..."
dnf install -y opencode
echo "  ✅ OpenCode 安装完成"

# 3. 验证
echo ""
echo "  --- 版本验证 ---"
export PATH=/usr/local/go/bin:$PATH
go version 2>/dev/null || echo "  ⚠️  Go 未安装"
shellcheck --version 2>/dev/null | head -1 || echo "  ⚠️  shellcheck 未安装"
shfmt --version 2>/dev/null || echo "  ⚠️  shfmt 未安装"

# 4. 提示下一步
echo ""
echo "=== 环境搭建完成 ==="
echo ""
echo "注意: 需 export PATH=/usr/local/go/bin:\$PATH 以使用 Go 1.26"
echo ""
echo "下一步操作:"
echo "  1. 配置 Agent 连接:"
echo "     cp .agents/config.template.yaml .agents/config.yaml"
echo "     # 编辑 .agents/config.yaml，将 active 设为 wsl"
echo ""
echo "  2. 验证构建（严禁 go build，必须用 build 脚本）:"
echo "     bash scripts/build.sh"
echo ""
echo "  3. 运行测试:"
echo "     go test -count=1 ./..."
echo ""
echo "  4. 试运行:"
echo "     build/linux-\$(uname -m | sed 's/x86_64/amd64/;s/aarch64/arm64/')/witty version"
