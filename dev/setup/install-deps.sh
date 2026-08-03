#!/bin/bash
# Witty 开发依赖一键安装 — 公共脚本
# 由各平台 setup 脚本调用，在 openEuler 环境中安装 Go、ShellCheck、shfmt、OpenCode 等。
# 用法: bash dev/setup/install-deps.sh
set -euo pipefail

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

# Go 1.26 分支：运行时动态发现最新 patch（官方 API: https://go.dev/dl/?mode=json）
GO_MINOR_VERSION="1.26"
GO_VERSION=""
echo "  动态获取 Go ${GO_MINOR_VERSION} 分支最新版本..."
for _ in 1 2 3; do
    GO_VERSION=$(curl -fsS "https://go.dev/dl/?mode=json" 2>/dev/null \
        | grep -oE "\"version\": \"go${GO_MINOR_VERSION//./\\.}\.[0-9]+\"" \
        | head -n1 \
        | grep -oE "go[0-9]+\.[0-9]+\.[0-9]+" || true)
    [ -n "$GO_VERSION" ] && break
    echo "    ⚠️  获取失败，重试..."
    sleep 3
done
if [ -z "$GO_VERSION" ]; then
    GO_VERSION="go1.26.5"
    echo "  ⚠️  动态获取失败，回退到默认版本 ${GO_VERSION}"
fi
echo "  目标版本: ${GO_VERSION}"

CURRENT_GO=$(/usr/local/go/bin/go version 2>/dev/null | grep -oE "go[0-9]+\.[0-9]+\.[0-9]+" || true)
if [ -n "$CURRENT_GO" ] && [ "$CURRENT_GO" = "$GO_VERSION" ]; then
    echo "  ${GO_VERSION} 已安装，跳过"
else
    download "https://go.dev/dl/${GO_VERSION}.linux-${GO_ARCH}.tar.gz" /tmp/go.tar.gz
    rm -rf /usr/local/go
    tar -C /usr/local -xzf /tmp/go.tar.gz
    echo "  ✅ ${GO_VERSION} 安装完成"
fi
echo 'export PATH=/usr/local/go/bin:$PATH' > /etc/profile.d/go.sh
chmod 644 /etc/profile.d/go.sh
echo "  ✅ Go PATH 已写入 /etc/profile.d/go.sh"

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

echo ""
echo "  --- 版本验证 ---"
export PATH=/usr/local/go/bin:$PATH
go version 2>/dev/null || echo "  ⚠️  Go 未安装"
shellcheck --version 2>/dev/null | head -1 || echo "  ⚠️  shellcheck 未安装"
shfmt --version 2>/dev/null || echo "  ⚠️  shfmt 未安装"
