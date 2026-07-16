---
name: witty-dev-setup
description: 搭建 Witty 开发与测试环境。引导开发者安装 OrbStack/WSL/SSH 并配置 .agents/config.yaml。用于新成员入职或环境重建时。兼容 macOS (arm64/amd64)、Windows (x86_64)、Linux (x86_64/arm64)。
---

# Witty 开发环境搭建

## 支持的宿主机与 openEuler 组合

| 宿主机 OS | 宿主机架构 | openEuler 环境 | openEuler 架构 | 连接方式 |
| --------- | --------- | ------------- | ------------- | -------- |
| macOS | arm64 (Apple Silicon) | OrbStack VM | arm64 | `orb -m witty-openeuler` |
| macOS | arm64 (Apple Silicon) | OrbStack VM | amd64 | `orb -m witty-openeuler-amd64` |
| macOS | amd64 (Intel) | OrbStack VM | amd64 | `orb -m witty-openeuler` |
| Windows | x86_64 | WSL 发行版 | x86_64 | `wsl -d <distro>` |
| Linux | x86_64 | SSH 远程 / 本地 | x86_64 | `ssh <user>@<host>` |
| Linux | arm64 | SSH 远程 / 本地 | arm64 | `ssh <user>@<host>` |

> **Agent 自检**：执行任何 `terminal` 操作前，始终从 `.agents/config.yaml` 读取 `active` 和对应 `envs` 配置。远程命令格式见 AGENTS.md。

## 步骤 1：选择并搭建 openEuler 环境

### macOS（arm64 或 amd64）→ OrbStack

1. 确保已安装 OrbStack（<https://orbstack.dev/download>）
2. 创建 openEuler 24.03 LTS VM:

   ```bash
   # arm64（默认，Apple Silicon 原生）
   orb create openeuler:24.03 witty-openeuler

   # amd64（Apple Silicon 上通过 Rosetta 2 转译，或 Intel Mac 原生）
   orb create --arch amd64 openeuler:24.03 witty-openeuler-amd64
   ```

3. 运行一键安装脚本（自动检测 VM 内架构）:

   ```bash
   # arm64 VM
   bash dev/setup/macos-orbstack.sh witty-openeuler 24.03 arm64

   # amd64 VM
   bash dev/setup/macos-orbstack.sh witty-openeuler-amd64 24.03 amd64
   ```

   脚本自动安装: git、make、Go 1.26+、ShellCheck、shfmt。

### Windows (x86_64) → WSL

1. 安装 openEuler WSL 发行版（通过 Microsoft Store 或手动导入）
2. 进入 WSL 发行版，运行一键脚本:

   ```bash
   bash dev/setup/windows-wsl.sh
   ```

   脚本自动检测架构 (x86_64) 并安装: git、make、Go 1.26+、ShellCheck、shfmt。

### Linux（x86_64 或 arm64）→ SSH / 本地

1. 确保已有一台 openEuler 24.03 LTS 服务器（物理机或 VM）
2. SSH 登录到服务器，运行一键脚本:

   ```bash
   bash dev/setup/linux-native.sh
   ```

   脚本自动检测架构 (x86_64 或 arm64) 并安装: git、make、Go 1.26+、ShellCheck、shfmt。

> **注意**：所有 setup 脚本内的架构检测均为动态（`uname -m`），绝不硬编码。Arch 映射: `aarch64→arm64`, `x86_64→amd64`。

## 步骤 2：配置 .agents/config.yaml

```bash
cp .agents/config.template.yaml .agents/config.yaml
```

编辑 `.agents/config.yaml`，根据你的环境修改 `active` 和对应的 `envs`。

> **重要（对 Agent）**：直接读取已知路径 `.agents/config.yaml`；不要先用目录扫描工具判断存在性。gitignore 可能让搜索结果为空，但文件实际存在。

### 配置示例

**macOS OrbStack (arm64):**

```yaml
active: orbstack
envs:
  orbstack:
    type: orbstack
    vm_name: witty-openeuler
    work_dir: /Users/<username>/path/to/shell
    user: root
```

**Windows WSL:**

```yaml
active: wsl
envs:
  wsl:
    type: wsl
    distro: openEuler
    work_dir: /home/<username>/shell
    user: root
```

**Linux SSH:**

```yaml
active: ssh
envs:
  ssh:
    type: ssh
    host: 192.168.1.100
    port: 22
    user: root
    identity_file: ~/.ssh/id_rsa
    work_dir: /root/shell
```

## 步骤 3：验证环境

> **🔴 构建铁律**：构建必须走 `bash scripts/build.sh`，产物在 `build/<GOOS>-<GOARCH>/`。**严禁** `go build ./cmd/witty`（会在当前目录产生二进制）。详见 `.agents/skills/witty-build/SKILL.md`。
>
> **重要（对 Agent）**：远程命令必须显式经 shell 执行，例如 `orb -m witty-openeuler -u root sh -lc 'cd <work_dir> && ...'`；不要把整段 `cd ... && ...` 当成 `orb` 的直接命令名。

### 宿主机验证

```bash
go version
bash scripts/build.sh
go test -count=1 ./...
build/<host-goos>-<host-goarch>/witty version
```

### openEuler 远程验证

```bash
# 以 OrbStack 为例（其他连接方式同理，替换命令前缀和 work_dir）
orb -m <vm> -u <user> sh -lc 'export PATH=/usr/local/go/bin:$PATH && cd <work_dir> && go ver
sion && bash scripts/build.sh && go test -count=1 ./... && build/linux-<arch>/witty version'
```

## 步骤 4：环境重建

当 VM/WSL/远程环境过大或异常时，销毁并重建。

### macOS OrbStack

```bash
# 4a. 销毁
orb delete -f witty-openeuler

# 4b. 创建（架构根据需求选择）
orb create openeuler:24.03 witty-openeuler

# 4c. 安装依赖
bash dev/setup/macos-orbstack.sh witty-openeuler 24.03 arm64

# 4d. 验证
orb -m witty-openeuler -u root sh -lc 'export PATH=/usr/local/go/bin:$PATH && cd <work_dir> && bash scripts/build.sh && go test -count=1 ./... && build/linux-<arch>/witty version'
```

### Windows WSL

```bash
# 4a. 注销发行版
wsl --unregister <distro>

# 4b. 重新安装 openEuler WSL 发行版（通过 Microsoft Store 或手动导入）

# 4c. 进入 WSL 发行版，运行一键脚本
bash dev/setup/windows-wsl.sh

# 4d. 验证（从 WSL 内执行）
export PATH=/usr/local/go/bin:$PATH && cd <work_dir> && bash scripts/build.sh && go test -count=1 ./... && build/linux-amd64/witty version
```

### Linux SSH（远程服务器）

```bash
# 4a. 登录服务器，清理旧环境
ssh <user>@<host> "rm -rf <work_dir> /usr/local/go /usr/local/bin/shellcheck /usr/local/bin/shfmt"

# 4b. 重新部署项目代码（git clone / rsync 等）

# 4c. 在服务器上运行一键脚本
ssh <user>@<host> "cd <work_dir> && bash dev/setup/linux-native.sh"

# 4d. 验证
ssh <user>@<host> "export PATH=/usr/local/go/bin:\$PATH && cd <work_dir> && bash scripts/build.sh && go test -count=1 ./... && build/linux-\$(uname -m | sed 's/x86_64/amd64/;s/aarch64/arm64/')/witty version"
```

## 检查清单

- [ ] openEuler 环境可访问（VM/SSH/WSL）
- [ ] Go 1.26+ 已安装（`/usr/local/go/bin/go version`）
- [ ] shellcheck 已安装并可执行
- [ ] shfmt 已安装并可执行
- [ ] `.agents/config.yaml` 已配置且 `active` 指向正确环境
- [ ] `bash scripts/build.sh` 通过（宿主机 + openEuler 各一次）
- [ ] `go test -count=1 ./...` 通过（宿主机 + openEuler 各一次）
- [ ] 试运行通过（`build/<goos>-<goarch>/witty version`）
- [ ] 项目根目录下无 `witty` 或 `wittyd` 二进制（构建产物仅在 `build/` 中）
