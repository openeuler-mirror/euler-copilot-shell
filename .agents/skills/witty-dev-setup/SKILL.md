---
name: witty-dev-setup
description: 搭建 Witty 开发与测试环境。引导开发者安装 OrbStack/WSL/SSH 并配置 .agents/config.yaml。用于新成员入职或环境重建时。
---

# Witty 开发环境搭建

## 步骤 1：选择并搭建 openEuler 环境

根据你的操作系统选择一种方式：

### macOS → OrbStack

1. 确保已安装 OrbStack（<https://orbstack.dev/download>），若未安装请先手动安装
2. 创建 openEuler 24.03 LTS VM:

   ```bash
   orb create openeuler:24.03 witty-openeuler
   ```

3. 在 VM 中安装基础开发依赖:

   交互式进入 VM：

   ```bash
   orb -m witty-openeuler -u root
   ```

   或非交互执行单条命令（对 Agent 更重要）：

   ```bash
   orb -m witty-openeuler -u root sh -lc 'yum install -y golang git make'
   ```

4. ShellCheck 和 shfmt 不在 openEuler 默认仓库中，需手动安装。推荐直接运行一键脚本（自动检测架构）:

   `bash dev/setup/macos-orbstack.sh`

### Windows → WSL

在 WSL openEuler 发行版中:

```bash
yum install -y golang git make shellcheck shfmt
```

或运行: `bash dev/setup/windows-wsl.sh`

### 自定义 → 远程 SSH

确保远程 openEuler 服务器已安装 golang、git、make、shellcheck、shfmt。
记录 SSH 连接信息（主机、端口、用户、私钥路径）。

## 步骤 2：配置 .agents/config.yaml

```bash
cp .agents/config.template.yaml .agents/config.yaml
```

编辑 `.agents/config.yaml`，根据你的环境修改 `active` 和对应的 `envs` 配置。
此文件已被 `.gitignore` 排除，不会提交到仓库。

> **重要（对 Agent）**：检查该文件时，直接读取已知路径 `shell/.agents/config.yaml`；不要先用 `find_path`、目录扫描或其它发现型工具判断存在性。gitignore 可能让搜索结果为空，但文件实际存在。

支持的连接类型:

- `orbstack` — macOS OrbStack VM
- `wsl` — Windows WSL 发行版
- `ssh` — 远程 SSH 服务器（支持跳板机配置）

## 步骤 3：验证环境

Agent 将自动读取 `.agents/config.yaml` 并在远程环境中执行验证。
若直接读取 `shell/.agents/config.yaml` 失败，再回退参考 `shell/.agents/config.template.yaml`。

> **重要（对 Agent）**：OrbStack / WSL 的非交互命令必须显式经 shell 执行，例如 `orb -m witty-openeuler -u root sh -lc 'cd /path/to/repo && go test ./...'`；不要把整段 `cd ... && go test ...` 直接作为 `orb` / `wsl` 的命令参数，否则很容易出现 `No such file or directory`。

验证示例：

```bash
go version
go build ./cmd/witty
go test ./...
```

## 检查清单

- [ ] openEuler 环境可访问（VM/SSH/WSL）
- [ ] Go 1.26+ 已安装
- [ ] shellcheck 已安装并可执行
- [ ] `.agents/config.yaml` 已配置且 active 指向正确的环境
- [ ] `go build ./cmd/witty` 通过
- [ ] `go test ./...` 通过
