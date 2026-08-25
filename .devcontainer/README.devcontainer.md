# euler-copilot-shell devcontainer 使用说明

## 判定结论

🟢 推荐：Python 3.11+ Textual TUI CLI，pytest 测试齐全、依赖由 uv 管理、发布形态为 openEuler RPM。采用**单容器**模式，基础镜像 `openeuler/openeuler:24.03-lts`（对齐仓库 RPM 目标 openEuler 24.03 LTS SP2，自带 Python 3.11）。

## 启动方式

1. VS Code 安装 Dev Containers 扩展，打开本仓库后执行 **Reopen in Container**；
2. 或使用 CLI：

   ```sh
   devcontainer up --workspace-folder .
   devcontainer exec --workspace-folder . bash
   ```

首次启动会自动构建镜像并执行 `post_install.sh`：创建 `.venv`、安装依赖
（`uv sync --extra dev`）、安装 pytest 并运行测试子集。`.venv` 与生成的 `uv.lock`
均已被 `.gitignore` 忽略，不会污染仓库。

> 国内/内网网络建议：uv 官方安装器与 PyPI 官方源在国内常超时。构建时可用参数切换
> pip 镜像源，运行期用 `UV_DEFAULT_INDEX` 切换依赖源：
>
> ```sh
> # 构建时（devcontainer.json 的 build.args 已预留 PIP_INDEX_URL）
> docker build --build-arg PIP_INDEX_URL=https://mirrors.huaweicloud.com/repository/pypi/simple \
>   -t euler-copilot-shell-dev .
> # 运行期（宿主机环境变量，devcontainer.json remoteEnv 自动透传）
> export UV_DEFAULT_INDEX=https://mirrors.huaweicloud.com/repository/pypi/simple
> ```

> 注意：devcontainer CLI 的 `${localEnv:VAR:默认值}` 不支持含 `:` 的默认值（URL 会被
> 截断，例如 `https://pypi.org/simple` 会变成 `https`，镜像 tag 也会丢失）。因此
> `PIP_INDEX_URL` / `OPENEULER_IMAGE` 的默认值写在 Dockerfile 里（`ARG ...=...` +
> `${VAR:-默认值}` 兜底），devcontainer.json 仅做宿主机环境变量透传；未设置时回落到
> Dockerfile 默认值。

## 环境内容

- openEuler 24.03 LTS（dnf 包管理，与 RPM 发布形态对齐）
- Python 3.11 + uv（依赖锁定/虚拟环境）
- 扩展：Python、Pylance、Ruff（格式化/静态检查）
- 系统工具：git、curl、jq、vim、tmux、zsh、gettext（i18n 编译）等
  （ripgrep/fd-find 不在 openEuler 24.03 默认源，未预装）
- 非 root 用户 `vscode`，可 `sudo` NOPASSWD

## 范围边界

### 开发容器内可以做的事

- 代码编辑、`uv run witty --help` / `--version` 等 CLI 冒烟验证
- TUI 运行（需容器内终端，Textual 在 VS Code 集成终端中可用）
- pytest 兼容测试子集（见下）；`uv run ruff check src` 等静态检查
- i18n 编译：`bash scripts/tools/i18n-manager.sh compile`

### 刻意不做（请勿在容器内运行）

- `witty --init` / `--agent` / `--llm-config`：目标机部署/系统级操作，需要 openEuler
  宿主机、sudo、dnf 网络与系统服务，与开发容器职责错位
- `witty --login`：浏览器登录需要宿主机图形环境与浏览器，容器内默认不支持
- RPM 打包（`scripts/build/build_rpm.sh`）：依赖 rpmbuild 宿主环境，另见 OBS/EBS
- 部署脚本测试（`tests/app/deployment/*`）：脚本式异步测试，会做系统/资源目录检查，
  属于真实部署验证，不属于开发门禁

## 测试命令

pytest 兼容子集（`postCreateCommand` 自动执行，也可手动）：

```sh
cd /workspace
PYTHONPATH=src uv run pytest -q \
  tests/log \
  tests/tool/test_browser_availability.py \
  tests/tool/test_token_validation.py
```

脚本式异步测试（手动，按需）：

```sh
PYTHONPATH=src uv run python tests/tool/test_token_integration.py
PYTHONPATH=src uv run python tests/app/deployment/test_rpm_availability.py
```

> 注：项目的 dev 可选依赖只声明了 ruff，未包含 pytest；`post_install.sh` 会额外将
pytest 装入 `.venv`。若希望固化，建议后续把 `pytest` 加入
`[project.optional-dependencies].dev`。

> 已知问题（仓库既有，非 devcontainer 引入）：`tests/tool/test_login.py` 中 2 个
> `get_auth_url` 用例调用旧签名（源码已改为单参数并返回元组），当前必然失败
> （仓库 `.pytest_cache/v/cache/lastfailed` 已记录）。默认门禁已排除该文件；
> 修复用例后可用 `PYTHONPATH=src uv run pytest tests/tool/test_login.py` 验证并重新纳入。

## 凭据注入

`devcontainer.json` 的 `remoteEnv` 通过 `${localEnv:KEY:}` 从宿主机环境变量透传占位，
**不写死任何真实密钥**。示例（`.devcontainer/.env.example`）：

```sh
export OPENAI_API_KEY=xxx
export OPENAI_API_BASE=https://api.example.com/v1
export OI_SKIP_SSL_VERIFY=0
```

导出后重新 Reopen in Container 生效。应用内的 API Key 也可通过 TUI 设置界面保存到
用户配置目录（`~/.config/eulerintelli`）。

## 资源要求

- 内存 >= 1GB，磁盘 >= 2GB（轻量 Python CLI，无重构建）
- 首次构建需联网（拉取 openEuler 镜像、安装 uv、解析 Python 依赖）

## 已知限制

- 无中间件编排（MongoDB/PostgreSQL/MinIO 属于部署安装器在目标机管理的服务，CLI 开发不需要）
- 无 privileged / GPU / 内核特性直通；部署助手功能需要在真实 openEuler 主机上验证
- 仓库未提交 `uv.lock`；首次 `uv sync` 会生成（已被 gitignore），如需可复现构建建议
  提交锁文件
- 基础镜像 tag 可通过构建参数覆盖（如 `24.03-lts-sp2`）以精确对齐发布目标
- `tests/tool/test_login.py` 为过时测试（见上文“已知问题”）
