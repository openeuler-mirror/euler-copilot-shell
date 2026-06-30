# Witty — openEuler 终端 AI 助手

Go CLI，对接 opencode HTTP Server。单二进制 + Bash Shell Adapter + SSE 流式传输。
目标平台：openEuler (Linux amd64/arm64)，CGO_ENABLED=0。

## 关键命令

- 构建: `bash scripts/build.sh`（产物路径由脚本输出）
- 测试: `go test -count=1 ./...`
- 格式化: `go fmt ./...`
- RPM 构建: `rpmbuild -ba packaging/euler-copilot-shell.spec`（在 VM 上）
- 生成发布产物: `bash packaging/scripts/prepare-release.sh <version>`

## openEuler 远程执行

读取 `.agents/config.yaml` 获取连接方式，通过 orb/wsl/ssh 在 VM 中执行命令：

```bash
# OrbStack
orb run -m <vm> -u <user> sh -lc 'cd <work_dir> && <command>'

# WSL
wsl -d <distro> -u <user> -- sh -lc 'cd <work_dir> && <command>'

# SSH
ssh <user>@<host> "cd <work_dir> && <command>"
```

> 不要把整段 `cd ... && ...` 当成远程命令名直接传给 orb/wsl。

## 🚫 严禁（无例外）

- 将构建产物写到 `build/` 以外的任何路径（`/tmp/`、`/var/tmp/`、项目根目录等均禁止）
- 以任何方式绕过 `bash scripts/build.sh` 直接调用 `go build -o <path>`
- 在非 Linux 的宿主机上产出 Linux 二进制
- 使用 `CGO_ENABLED=1`
- 在 Bash 模板中使用 `{{ }}` 分隔符（只能用 `[[ ]]`）
- 提交 secrets、token、`.agents/config.yaml`

## ⚠️ Agent 每次终端操作前自检

执行任何 `terminal` 调用前核验：

1. **产物路径** — 会创建二进制吗？是的话走 `bash scripts/build.sh` → `build/`
2. **执行环境** — 该在 VM 上跑吗？（构建 Linux 二进制、vendor tarball、rpmbuild → VM）
3. **Skill 加载** — 匹配强制加载规则吗？已加载对应 SKILL.md 吗？
4. **禁止模式** — 含 `go build -o /tmp/...`、Linux 交叉编译等禁止模式吗？

## 🔴 强制 Skill 加载

下列 skill 不可懒加载，执行对应操作前必须完整读取 SKILL.md：

| 操作 | 必须先加载 |
| ---- | --------- |
| `go build` / `go test` / `bash scripts/build.sh` | `.agents/skills/witty-build/SKILL.md` |
| `prepare-release.sh` / `prepare-vendor.sh` / `rpmbuild` | `.agents/skills/witty-release/SKILL.md` |

## Agent 启动时必须执行

1. 读取 `.agents/rules/` 下所有 `.md` 文件
2. 扫描 `.agents/skills/` 下各 `SKILL.md` 的 name / description
3. 直接读取 `.agents/config.yaml`（若失败再回退 template）
