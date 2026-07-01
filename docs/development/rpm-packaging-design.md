# Witty RPM 打包方案设计

> 版本: 1.0 | 日期: 2026-06-23 | 状态: 草案

## 1. 背景与约束

### 1.1 核心约束

| 约束 | 说明 |
| --- | --- |
| openEuler CI 打包方式 | **仅支持源码仓 tarball + RPM spec**，通过 Source0..N 本地提供所有文件 |
| 网络隔离 | CI 构建环境**不能访问海外网站**（github.com、go.dev 等均不可达） |
| Go 版本 | Witty 要求 **Go 1.26+**（`go.mod` 声明 `go 1.26`） |
| 交付架构 | openEuler **linux/amd64** 和 **linux/arm64** |
| 静态链接 | `CGO_ENABLED=0`，不需要 C 编译器 |

### 1.2 openEuler Go 版本现状

当前 openEuler 仓库中可用的 Go 版本：

| 版本 | 来源 | 状态 |
| --- | --- | --- |
| go 1.21.4 | `openEuler-24.03-LTS-SP2` 主仓库 | 可用但不满足需求 |
| go 1.25.x | Docker 镜像 `openeuler/go:1.25.6-oe2403sp3` | 可用于本地开发 |
| go 1.26.x | **未进入 openEuler 仓库** | 需自备 |

**结论**：Go 1.26 工具链必须作为 Source 文件本地提供。

### 1.3 依赖规模

```bash
$ wc -l go.sum
115 go.sum   # 115 行 = ~55 个独立模块（含间接依赖）
```

若采用 Fedora 经典「非 vendored」方式，需要将每个 Go module 单独打包为 `golang-*-devel` RPM 包，产生约 50-100+ 个子包。**Fedora 自 F43 起已废弃此方式**，改为默认 vendored。

## 2. 方案对比

### 方案 A：预构建二进制 RPM（最简单）

**思路**：在外部环境（macOS/CI）用 GoReleaser 交叉编译出二进制，直接将二进制打包为 RPM。

```spec
Source0: witty-v{version}-linux-amd64   # 预编译二进制 (amd64)
Source1: witty-v{version}-linux-arm64   # 预编译二进制 (arm64)
```

| 优点 | 缺点 |
| --- | --- |
| 不依赖 Go 工具链 | 不是「从源码构建」，审计困难 |
| RPM spec 极简 | 与 openEuler 开源理念冲突 |
| 构建速度快 | 二进制不可复现（依赖编译环境） |
| | 无法打补丁后重新构建 |

**不推荐**。不符合 openEuler「源码仓」基本原则。

### 方案 B：GoReleaser + nFPM 生成 RPM

**思路**：使用 GoReleaser 的 nFPM 模块直接生成 RPM。

```yaml
.goreleaser.yaml:
  nfpms:
    - formats: [rpm]
      builds: [witty]
```

| 优点 | 缺点 |
| --- | --- |
| 与项目现有构建流程一致 | nFPM 在打包时仍需 `go build`（需 Go 工具链 + 网络下载依赖） |
| 配置文件简洁 | openEuler CI 不可直接使用 goreleaser |
| 可注入 version/commit/date | 生成的 RPM 是二进制的，非源码 RPM |

**不推荐**。openEuler CI 不支持运行 goreleaser，且 goreleaser 构建过程需要网络下载 Go module 依赖。

### 方案 C：Vendor + Go 工具链捆绑（✅ 推荐）

**思路**：

1. 开发者在本地执行 `go mod vendor`，将所有 Go 依赖打包为 `vendor.tar.xz`
2. 下载 Go 1.26 官方二进制发布包（`go1.26.x.linux-amd64.tar.gz`）
3. 将以上文件作为 Source1、Source2... 在 spec 中引用
4. spec 的 `%build` 阶段使用捆绑的 Go 工具链 + vendored 依赖进行离线构建

```spec
Source0: witty-{version}.tar.gz            # 上游源码
Source1: go1.26.x.linux-amd64.tar.gz       # Go 工具链 (amd64)
Source2: go1.26.x.linux-arm64.tar.gz       # Go 工具链 (arm64)
Source3: witty-cli-vendor-{version}.tar.xz     # vendored 依赖
```

| 优点 | 缺点 |
| --- | --- |
| ✅ 完全离线构建，不访问外网 | Go 工具链 tarball 较大（~70MB 压缩后） |
| ✅ 从源码构建，可审计、可打补丁 | 需要额外脚本生成 vendor tarball |
| ✅ 与 openEuler 其他 Go 包（delve、netavark）模式一致 | 每次依赖更新需重新生成 vendor tarball |
| ✅ 复现性：固定 Go 版本 + vendor 锁定依赖 | — |
| ✅ 支持多架构（通过 `%ifarch` 条件选择） | — |

**推荐方案 C**。

### 方案 D：完全 unbundled（Fedora 经典，已废弃）

将所有 Go 依赖逐个打包为 `golang-*-devel` RPM，通过 `BuildRequires` 声明依赖链。

| 优点 | 缺点 |
| --- | --- |
| 依赖复用 | Witty 115 行 `go.sum` 需要 50+ 个独立包 |
| CVE 修复时只需更新依赖包 | 依赖地狱：版本冲突频繁 |
| | Fedora 已废弃（F43 Change Proposal 通过） |
| | Go 1.26 module 模式与 GOPATH 不兼容 |

**不推荐**。此方案已被 Fedora/Red Hat 官方放弃。

## 3. 推荐方案详细设计（方案 C）

### 3.1 整体流水线

```text
┌──────────────────────────────────────────────────────────┐
│                开发者本地 / macOS / CI                    │
│                                                          │
│  1. go mod vendor  ──→  vendor/ 目录                     │
│  2. tar -cJf vendor.tar.xz vendor/                       │
│  3. 下载 Go 1.26 官方二进制包                             │
│  4. git archive 生成源码 tarball                         │
│                                                          │
│  产物:                                                    │
│    - witty-3.0.0.tar.gz        (源码)                    │
│    - go1.26.x.linux-amd64.tar.gz  (Go 工具链 amd64)       │
│    - go1.26.x.linux-arm64.tar.gz  (Go 工具链 arm64)       │
│    - witty-cli-vendor-3.0.0.tar.xz (vendored 依赖)           │
└──────────────────────┬───────────────────────────────────┘
                       │ 上传至 openEuler 构建系统
                       ▼
┌──────────────────────────────────────────────────────────┐
│              openEuler CI 构建环境 (离线)                  │
│                                                          │
│  1. rpmbuild -ba witty.spec                              │
│     ├── %prep:  解压源码 + vendor + Go 工具链              │
│     ├── %build: 使用捆绑 Go 编译 with -mod=vendor          │
│     ├── %install: 安装到 %{buildroot}                     │
│     └── %files: 文件清单                                  │
│                                                          │
│  产物:                                                    │
│    - witty-3.0.0-1.oe2403.x86_64.rpm                     │
│    - witty-3.0.0-1.oe2403.aarch64.rpm                    │
│    - witty-3.0.0-1.oe2403.src.rpm                        │
└──────────────────────────────────────────────────────────┘
```

### 3.2 目录结构

```text
witty/
├── packaging/                      # 打包相关文件（新增）
│   ├── witty.spec                  # RPM spec 文件
│   ├── scripts/
│   │   └── prepare-vendor.sh       # 生成 vendor tarball 的脚本
│   ├── profile.d/
│   │   └── witty.sh                # Shell 集成入口（/etc/profile.d/）
│   ├── witty.bash-completion       # bash completion 文件
│   └── config.toml                 # 默认配置文件
├── .goreleaser.yaml                # 保留，用于本地/CI 快速验证
├── cmd/witty/
├── internal/
└── ...
```

### 3.3 RPM spec 设计

```spec
# witty.spec — Witty CLI for openEuler
%global go_version  1.26.4
%global import_path atomgit.com/openeuler/euler-copilot-shell

# 禁用 debuginfo（静态链接 Go 二进制不需要）
%global debug_package %{nil}

Name:           euler-copilot-shell
Version:        3.0.0
Release:        1%{?dist}
Summary:        openEuler terminal AI assistant
License:        MulanPSL2
URL:            https://atomgit.com/openeuler/euler-copilot-shell

# === Source 文件（全部本地提供） ===
Source0:        %{name}-%{version}.tar.gz
Source1:        go%{go_version}.linux-amd64.tar.gz
Source2:        go%{go_version}.linux-arm64.tar.gz
Source3:        %{name}-vendor-%{version}.tar.xz

# === 构建依赖 ===
# 注意：不需要 BuildRequires: golang —— 使用捆绑的 Go 工具链
BuildRequires:  xz

# === 运行时依赖 ===
Requires:       bash
Requires:       glibc

%description
Witty is an openEuler terminal AI assistant that integrates with
opencode MCP Server. It provides a natural language interface
directly in the Bash shell.

%prep
%setup -q -n %{name}-%{version}

# 提取 Go 工具链
%ifarch x86_64
tar -xzf %{SOURCE1} -C %{_builddir}
%define goroot %{_builddir}/go
%endif
%ifarch aarch64
tar -xzf %{SOURCE2} -C %{_builddir}
%define goroot %{_builddir}/go
%endif

# 提取 vendored 依赖
tar -xJf %{SOURCE3}

%build
export GOROOT=%{goroot}
export PATH=%{goroot}/bin:$PATH
export CGO_ENABLED=0
export GOAMD64=v1

# 确认 Go 版本正确
%{goroot}/bin/go version

# 使用 vendor 目录进行离线构建
%{goroot}/bin/go build \
    -mod=vendor \
    -ldflags="-s -w -X main.version=%{version} -X main.commit=%{commit} -X main.date=%{date}" \
    -o %{name} \
    %{import_path}/cmd/witty

%install
# 主程序
install -Dpm 0755 %{name} %{buildroot}%{_bindir}/%{name}

# 默认配置（noreplace：升级时不覆盖用户修改）
install -Dpm 0644 packaging/config.toml %{buildroot}%{_sysconfdir}/%{name}/config.toml

# bash completion
install -Dpm 0644 packaging/%{name}.bash-completion %{buildroot}%{_datadir}/bash-completion/completions/%{name}

# Shell 集成：RPM 安装后自动启用，用户通过 WITTY_SHELL_ENABLE=0 禁用
install -Dpm 0644 packaging/profile.d/%{name}.sh %{buildroot}%{_sysconfdir}/profile.d/%{name}.sh

%check
# 冒烟测试：验证二进制可执行
%{buildroot}%{_bindir}/%{name} version || exit 1
%{buildroot}%{_bindir}/%{name} --help || exit 1

%files
%license LICENSE
%doc README.md
%{_bindir}/%{name}
%dir %{_sysconfdir}/%{name}
%config(noreplace) %{_sysconfdir}/%{name}/config.toml
%{_datadir}/bash-completion/completions/%{name}
%{_sysconfdir}/profile.d/%{name}.sh

%changelog
* Mon Jun 23 2026 Witty Team <witty@openeuler.org> - 3.0.0-1
- Initial package
```

### 3.3.1 Shell 集成设计

RPM 安装后自动启用 Shell Adapter，用户无需手动修改 `.bashrc`：

```text
┌─────────────────────────────────────────────────┐
│               安装 witty RPM                      │
│                      │                           │
│  ┌───────────────────┼───────────────────────┐   │
│  │                   ▼                        │   │
│  │  /etc/profile.d/witty.sh                   │   │
│  │  ┌──────────────────────────────────────┐  │   │
│  │  │ if BASH && not disabled:             │  │   │
│  │  │   eval "$(witty init bash)"          │  │   │
│  │  └──────────────────────────────────────┘  │   │
│  │                                            │   │
│  │  /etc/profile → login shell               │   │
│  │  /etc/bashrc  → interactive non-login     │   │
│  └────────────────────────────────────────────┘   │
│                                                   │
│  用户禁用：                                        │
│    echo 'export WITTY_SHELL_ENABLE=0' >> ~/.bashrc │
│                                                   │
│  临时试用（非 RPM 安装）：                          │
│    eval "$(witty init bash)"                      │
└─────────────────────────────────────────────────┘
```

**设计原则**：

| 层级 | 文件 | 职责 |
| --- | --- | --- |
| 系统级 | `/etc/profile.d/witty.sh` | RPM 安装后默认启用，检查 `WITTY_SHELL_ENABLE` 开关 |
| 用户级 | `~/.bashrc` | 仅控制开关 `WITTY_SHELL_ENABLE=0`，不包含 `eval` 调用 |
| 临时级 | 命令行 `eval "$(witty init bash)"` | 非 RPM 安装场景的手动启用 |

与 `witty init bash` 模板的关系：

- `witty.sh` 调用 `witty init bash` 生成完整的 Shell Adapter 绑定
- 两者是**调用者与被调用者**的关系，不是重复实现
- `witty init bash` 模板保持独立，可脱离 RPM 单独使用

### 3.4 vendor tarball 生成脚本

```bash
#!/usr/bin/env bash
# packaging/scripts/prepare-vendor.sh
# 生成 vendored 依赖 tarball
#
# 用法:
#   bash packaging/scripts/prepare-vendor.sh <version>
#
# 产物:
#   witty-cli-vendor-<version>.tar.xz

set -euo pipefail

VERSION="${1:-}"
if [ -z "$VERSION" ]; then
    echo "Usage: $0 <version>" >&2
    exit 1
fi

OUTPUT="witty-cli-vendor-${VERSION}.tar.xz"

echo "==> Running go mod vendor..."
go mod vendor

echo "==> Creating vendor archive: ${OUTPUT}"
tar -cJf "${OUTPUT}" vendor/

echo "==> Cleaning up vendor/ directory..."
rm -rf vendor/

echo "==> Done: ${OUTPUT}"
ls -lh "${OUTPUT}"
```

### 3.5 GoReleaser 定位

`.goreleaser.yaml` **保留但调整职责**：

- **保留**：用于本地开发快速验证（`goreleaser release --snapshot --clean --skip=publish`）
- **保留**：注入 version/commit/date 等构建信息
- **移除**：nFPM RPM 生成（不与 openEuler spec 冲突）
- **新增**：增加 source tarball 的 archive 配置

```yaml
# .goreleaser.yaml (调整后)
builds:
  - id: witty
    main: ./cmd/witty
    goos: [linux]
    goarch: [amd64, arm64]
    env:
      - CGO_ENABLED=0
    goamd64: [v1]
    ldflags:
      - -s -w
      - -X main.version={{ .Version }}
      - -X main.commit={{ .FullCommit }}
      - -X main.date={{ .Date }}

# 不再使用 nfpms 生成 RPM，改为手写 spec
# nfpms:  ← 移除

archives:
  - id: source-tarball
    format: tar.gz
    # 源码包，供 openEuler spec 使用
    files:
      - src: "**/*.go"
      - src: "go.mod"
      - src: "go.sum"
      - src: "cmd/**"
      - src: "internal/**"
      - src: "packaging/*"
      - src: "LICENSE"
      - src: "README.md"
```

### 3.6 版本发布完整流程

```text
1. 打 tag: git tag v3.0.0
2. 生成源码 tarball:
   git archive --format=tar.gz -o witty-3.0.0.tar.gz v3.0.0
3. 生成 vendor tarball:
   bash packaging/scripts/prepare-vendor.sh 3.0.0
4. 下载 Go 工具链:
   curl -LO https://go.dev/dl/go1.26.4.linux-amd64.tar.gz
   curl -LO https://go.dev/dl/go1.26.4.linux-arm64.tar.gz
5. 上传至 openEuler 构建系统:
   - witty-3.0.0.tar.gz → Source0
   - go1.26.4.linux-amd64.tar.gz → Source1
   - go1.26.4.linux-arm64.tar.gz → Source2
   - witty-cli-vendor-3.0.0.tar.xz → Source3
6. CI 执行: rpmbuild -ba witty.spec
7. 产物:
   - witty-3.0.0-1.oe2403.x86_64.rpm
   - witty-3.0.0-1.oe2403.aarch64.rpm
```

## 4. 备选方案：Go 工具链自举

如果 Go 1.26 的官方二进制包因为网络原因无法下载，可以考虑：

### 4.1 从较低版本 Go 自举

```bash
# 在 openEuler 构建环境中：
# 1. 使用系统 go 1.21 编译 go 1.26 源码
# 2. 用编译出的 go 1.26 编译 witty
```

**缺点**：Go 自举构建时间较长（~5-10 分钟），增加 CI 耗时。

### 4.2 等待 openEuler 官方升级 Go

跟踪 `src-openeuler/golang` 仓库的版本更新。一旦 Go 1.26 进入 openEuler 主仓库，可以移除 Source1/Source2，直接使用 `BuildRequires: golang >= 1.26`。

## 5. 风险与缓解

| 风险 | 影响 | 缓解措施 |
| --- | --- | --- |
| Go 工具链 tarball 过大 | 上传/存储成本 | 使用 `.tar.gz` 压缩（~70MB），可接受 |
| vendor tarball 与上游不同步 | 构建失败 | `prepare-vendor.sh` 脚本强制从 `go.mod` + `go.sum` 生成 |
| CVE 修复需更新依赖 | 安全漏洞 | `go_vendor_archive` 工具可更新单个依赖（参考 Fedora go-vendor-tools） |
| 多架构 Go 工具链维护 | 需同时维护 amd64 和 arm64 的 Go 包 | Go 官方同时发布两架构包，版本同步 |
| openEuler 未来升级 Go 版本 | spec 中捆绑的 Go 版本过时 | 设计为可切换：当系统 Go ≥ 1.26 时用系统 Go |

## 6. 参考资料

- [Fedora Golang Packaging Guidelines (Vendored)](https://docs.fedoraproject.org/en-US/packaging-guidelines/Golang/)
- [F43 Change: Golang Packages Vendored By Default](https://fedoraproject.org/wiki/Changes/GolangPackagesVendoredByDefault)
- [Fedora Go SIG — Go Vendor Tools](https://fedora.gitlab.io/sigs/go/go-vendor-tools/)
- [openSUSE obs-service-go_modules](https://github.com/openSUSE/obs-service-go_modules)
- [src-openEuler/netavark (vendor 示例)](https://gitee.com/src-openeuler/netavark)
- [src-openEuler/delve (Go vendor 示例)](https://gitee.com/src-openeuler/delve)
- [openEuler RPM 打包文档](https://docs.openeuler.org/en/docs/25.09/server/development/application_dev/building_an_rpm_package.html)
