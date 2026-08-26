# euler-copilot-shell devcontainer - openEuler 基础镜像
#
# 资源要求：内存 >= 1GB，磁盘 >= 2GB（轻量 Python TUI CLI，无需重构建）
# 首次构建需要联网拉取基础镜像、安装 uv 与 Python 依赖
#
# 基础镜像对齐仓库 RPM 发布目标（openEuler 24.03 LTS SP2，见 README 安装说明），
# 自带 Python 3.11，满足 pyproject.toml 的 requires-python >= 3.11。
# 如需固定 SP 版本，可通过构建参数覆盖，如：
#   docker build --build-arg OPENEULER_IMAGE=openeuler/openeuler:24.03-lts-sp2 .

ARG OPENEULER_IMAGE=openeuler/openeuler:24.03-lts
FROM ${OPENEULER_IMAGE:-openeuler/openeuler:24.03-lts}

ARG TZ=Asia/Shanghai
ENV TZ="${TZ}"

# 基础工具链（openEuler 用 dnf 包名；python3 在 24.03 为 3.11.x）
# 刻意不做 dnf update：基础镜像 tag 本身随 openEuler 24.03 LTS 更新而滚动，
# 跳过 update 可避免镜像源抖动导致的构建失败，并保证构建可复现。
# 纯 Python 项目（依赖均有 wheel），无需 C++ 工具链；需要源码编译时再按需安装。
RUN dnf -y --setopt=retries=10 --setopt=timeout=120 install \
    git \
    curl \
    wget \
    tar \
    unzip \
    jq \
    vim \
    tmux \
    zsh \
    sudo \
    python3 \
    python3-devel \
    python3-pip \
    gettext \
    gcc \
    make \
    && dnf clean all

# uv（Python 包管理器；openEuler 官方源无 uv 包）
# 官方安装器依赖 astral.sh / releases.astral.sh，国内网络下常超时；
# 改用 pip 安装，并支持构建参数覆盖为镜像源：
#   docker build --build-arg PIP_INDEX_URL=https://mirrors.huaweicloud.com/repository/pypi/simple .
# 运行期 Python 依赖的镜像源通过 devcontainer.json 的 UV_DEFAULT_INDEX 注入。
ARG PIP_INDEX_URL=https://pypi.org/simple
RUN python3 -m pip install --no-cache-dir --index-url "${PIP_INDEX_URL:-https://pypi.org/simple}" uv

# 创建开发用户（devcontainer remoteUser）
RUN useradd -m -s /bin/bash vscode && \
    echo 'vscode ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/vscode && \
    chmod 440 /etc/sudoers.d/vscode && \
    # 预创建 uv 缓存目录并移交属主：命名卷挂载点不存在时 Docker 会以 root 创建卷根，
    # 导致 vscode 无写权限、首次 uv sync 失败（/commandhistory 同理处理）
    mkdir -p /workspace /commandhistory /home/vscode/.cache/uv && \
    chown -R vscode:vscode /workspace /commandhistory /home/vscode/.cache/uv

WORKDIR /workspace
USER vscode

# uv 缓存挂载到命名 volume 时避免跨文件系统硬链接问题
ENV UV_LINK_MODE=copy
ENV PATH="/home/vscode/.local/bin:/usr/local/bin:$PATH"
ENV SHELL=/bin/bash
ENV EDITOR=vim
