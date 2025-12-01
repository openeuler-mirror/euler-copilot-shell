#!/bin/bash
# 颜色定义
COLOR_INFO='\033[34m'    # 蓝色信息
COLOR_SUCCESS='\033[32m' # 绿色成功
COLOR_ERROR='\033[31m'   # 红色错误
COLOR_WARNING='\033[33m' # 黄色警告
COLOR_RESET='\033[0m'    # 重置颜色
INSTALL_MODE_FILE="/etc/euler_Intelligence_install_mode"
# 全局变量
declare -a installed_pkgs=()
install_success=true
missing_pkgs=()
LOCAL_REPO_DIR="/var/cache/rpms"
LOCAL_REPO_FILE="/etc/yum.repos.d/local.repo"

# 检查系统版本并返回兼容的 el 版本
get_el_version() {
  # 首先检查是否为 openEuler 系统
  if [ -f "/etc/openEuler-release" ]; then
    local openeuler_version
    openeuler_version=$(grep -Eo 'openEuler release [0-9]+\.[0-9]+' /etc/openEuler-release | awk '{print $3}' | tail -n 1)

    if [ -n "$openeuler_version" ]; then
      # 将版本号转换为可比较的数字格式（如 22.03 -> 2203）
      local major minor
      major=$(echo "$openeuler_version" | cut -d'.' -f1)
      minor=$(echo "$openeuler_version" | cut -d'.' -f2)

      if [[ "$major" =~ ^[0-9]+$ && "$minor" =~ ^[0-9]+$ ]]; then
        local version_num=$((10#$major * 100 + 10#$minor))

        # openEuler 22.03 及之前使用 el8，24.03 及之后使用 el9
        if [ $version_num -le 2203 ]; then
          echo "8"
          return 0
        else
          echo "9"
          return 0
        fi
      fi
    fi
  fi

  # 如果不是标准的 openEuler 或无法获取版本，则检查内核版本
  echo -e "${COLOR_WARNING}[Warning] 非标准 openEuler 系统，基于内核版本判断 el 版本${COLOR_RESET}" >&2
  local kernel_version
  kernel_version=$(uname -r | cut -d'.' -f1,2)

  # 将版本号转换为可比较的数字格式
  local major minor
  major=$(echo "$kernel_version" | cut -d'.' -f1)
  minor=$(echo "$kernel_version" | cut -d'.' -f2)

  if [[ "$major" =~ ^[0-9]+$ && "$minor" =~ ^[0-9]+$ ]]; then
    local version_num=$((10#$major * 100 + 10#$minor))

    # 内核版本 < 5.14 使用 el8，>= 5.14 使用 el9
    if [ $version_num -lt 514 ]; then
      echo "8"
      return 0
    else
      echo "9"
      return 0
    fi
  fi

  echo -e "${COLOR_ERROR}[Error] 无法确定兼容的 el 版本，请检查系统信息${COLOR_RESET}" >&2
  return 1
}

# 初始化本地仓库
init_local_repo() {
  [ "$(id -u)" -ne 0 ] && {
    echo "需要root权限"
    return 1
  }

  # 检查仓库目录和repo文件是否存在
  if [ ! -d "$LOCAL_REPO_DIR" ] 2>/dev/null; then
    return 0
  fi

  # 配置本地仓库
  cat >"$LOCAL_REPO_FILE" <<EOF
[local-rpms]
name=Local RPM Repository
baseurl=file://$LOCAL_REPO_DIR
enabled=1
gpgcheck=0
priority=1  # 本地仓库优先
metadata_expire=never
EOF

  # 重建元数据（如果已有rpm文件）
  if ls "$LOCAL_REPO_DIR"/*.rpm &>/dev/null; then
    if ! command -v createrepo &>/dev/null; then
      dnf install -y createrepo
    fi
    createrepo --update "$LOCAL_REPO_DIR"
  fi

  dnf clean all
  dnf makecache

}
# 获取 wget 日志文件名
get_wget_log_filename() {
  local file_path=$1
  # 创建日志目录（如果不存在）
  mkdir -p "$HOME/.cache/openEuler Intelligence/logs"
  # 获取开始下载的时间戳
  local timestamp
  timestamp=$(date +%Y%m%d_%H%M%S)
  # 获取下载文件名
  local filename
  filename=$(basename "$file_path")
  # 构造日志文件路径
  local logfile="$HOME/.cache/openEuler Intelligence/logs/${timestamp}_${filename}.log"
  echo "$logfile"
}
# 获取最新的 MinIO RPM 下载地址
get_latest_minio_rpm_url() {
  local arch=$1
  local base_url

  case "$arch" in
  x86_64 | i386 | i686)
    base_url="https://dl.min.io/server/minio/release/linux-amd64/archive/"
    ;;
  aarch64 | arm64)
    base_url="https://dl.min.io/server/minio/release/linux-arm64/archive/"
    ;;
  *)
    echo -e "${COLOR_ERROR}[Error] 不支持的架构: $arch${COLOR_RESET}" >&2
    return 1
    ;;
  esac

  # 获取目录列表并解析最新的 RPM 文件
  # 使用兼容 macOS 和 Linux 的 grep 选项
  local rpm_file
  rpm_file=$(curl -sL "$base_url" | grep -o 'minio-[0-9][^"]*\.rpm' | sort -V | tail -1)

  if [ -z "$rpm_file" ]; then
    echo -e "${COLOR_ERROR}[Error] 无法获取最新的 MinIO RPM 文件名${COLOR_RESET}" >&2
    return 1
  fi

  # 只输出 URL 到 stdout（作为函数返回值）
  echo "${base_url}${rpm_file}"
  return 0
}

# 安装MinIO
install_minio() {
  echo -e "${COLOR_INFO}[Info] 开始安装MinIO...${COLOR_RESET}"
  local minio_dir="/opt/minio"
  local arch
  arch=$(uname -m)

  if ! mkdir -p "$minio_dir"; then
    echo -e "${COLOR_ERROR}[Error] 创建目录失败: $minio_dir${COLOR_RESET}"
    return 1
  fi

  # 根据架构选择不同的安装方式
  case "$arch" in
  x86_64 | i386 | i686 | aarch64 | arm64)
    # 首先检查缓存目录中是否已存在 MinIO RPM 文件（任何版本）
    local existing_rpm
    existing_rpm=$(find "$minio_dir" -name "minio-*.rpm" -type f 2>/dev/null | head -1)

    if [ -n "$existing_rpm" ]; then
      # 找到已存在的 RPM 文件，直接使用
      echo -e "${COLOR_INFO}[Info] 发现已存在的 MinIO RPM 文件: $(basename "$existing_rpm")${COLOR_RESET}"
      echo -e "${COLOR_INFO}[Info] 使用缓存的 RPM 文件，跳过下载${COLOR_RESET}"
      local minio_file="$existing_rpm"
    else
      # 没有找到已存在的 RPM，获取最新版本并下载
      echo -e "${COLOR_INFO}[Info] 未找到缓存的 MinIO RPM，准备下载最新版本...${COLOR_RESET}"
      echo -e "${COLOR_INFO}[Info] 获取最新的 MinIO RPM 下载地址（$arch）...${COLOR_RESET}"

      local minio_url
      minio_url=$(get_latest_minio_rpm_url "$arch")
      if [ $? -ne 0 ] || [ -z "$minio_url" ]; then
        echo -e "${COLOR_ERROR}[Error] 获取 MinIO 下载地址失败${COLOR_RESET}"
        return 1
      fi

      local rpm_filename
      rpm_filename=$(basename "$minio_url")
      local minio_file="$minio_dir/$rpm_filename"

      echo -e "${COLOR_INFO}[Info] 最新版本: $rpm_filename${COLOR_RESET}"
      echo -e "${COLOR_INFO}[Info] 正在下载MinIO软件包...${COLOR_RESET}"

      local logfile
      logfile=$(get_wget_log_filename "$minio_file")
      if ! wget "$minio_url" --no-check-certificate -O "$minio_file" -o "$logfile"; then
        echo -e "${COLOR_ERROR}[Error] MinIO下载失败${COLOR_RESET}"
        return 1
      fi
    fi

    # 安装 RPM 文件
    dnf install -y "$minio_file" || {
      echo -e "${COLOR_ERROR}[Error] MinIO安装失败${COLOR_RESET}"
      return 1
    }
    echo -e "${COLOR_SUCCESS}[Success] MinIO安装成功${COLOR_RESET}"
    return 0
    ;;
  *)
    echo -e "${COLOR_ERROR}[Error] 不支持的架构: $arch${COLOR_RESET}"
    echo -e "${COLOR_ERROR}[Error] 仅支持 x86_64、aarch64 架构${COLOR_RESET}"
    return 1
    ;;
  esac
}
# 智能安装函数
# 参数: 包名 或 "包名:备用包名1:备用包名2"
smart_install() {
  local pkg_spec=$1
  local retry=3
  local LOCAL_REPO_DIR="/var/cache/rpms"
  local use_local=false

  # 解析包名和备用包名
  IFS=':' read -ra pkg_names <<<"$pkg_spec"
  local primary_pkg="${pkg_names[0]}"

  # 检查本地仓库目录是否存在
  if [ -d "$LOCAL_REPO_DIR" ]; then
    use_local=true
  fi

  echo -e "${COLOR_INFO}[Info] 正在安装 $primary_pkg ...${COLOR_RESET}"

  # 尝试安装主包名和备用包名
  for pkg in "${pkg_names[@]}"; do
    local current_retry=$retry

    while [ $current_retry -gt 0 ]; do
      # 本地安装模式（仅在本地仓库可用时尝试）
      if [[ "$use_local" == true ]]; then
        # 检查本地是否存在包（支持模糊匹配）
        local local_pkg
        local_pkg=$(find "$LOCAL_REPO_DIR" -name "${pkg}-*.rpm" | head -1)

        if [[ -n "$local_pkg" ]]; then
          if dnf --disablerepo='*' --enablerepo=local-rpms install -y "$pkg"; then
            installed_pkgs+=("$primary_pkg")
            return 0
          fi
        fi
      fi

      # 在线安装模式（本地仓库不可用或本地安装失败）
      if dnf install -y "$pkg"; then
        installed_pkgs+=("$primary_pkg")
        return 0
      fi

      ((current_retry--))
      sleep 1
    done
  done

  # 所有包名都尝试失败
  echo "${COLOR_ERROR}[Error] 错误: $primary_pkg 安装失败！${COLOR_RESET}"
  missing_pkgs+=("$primary_pkg")
  install_success=false

  return 1
}
#&>/dev/null
install_and_verify() {
  # 接收传入的包列表参数
  local pkgs=("$@")
  # 检查并安装每个包
  for pkg in "${pkgs[@]}"; do
    smart_install "$pkg"
    sleep 1
  done
  # 检查安装结果
  if $install_success; then
    echo -e "${COLOR_SUCCESS}[Success] dnf 包安装完成！${COLOR_RESET}"
  else
    echo -e "${COLOR_ERROR}[Error] 以下包安装失败: ${missing_pkgs[*]}${COLOR_RESET}"
    return 1
  fi
}
# 安装pgvector服务
install_pgvector() {
  local pgvector_dir="/opt/pgvector"
  local zhparser_url="https://bgithub.xyz/pgvector/pgvector.git"
  local pgvector_installed_marker="/usr/share/pgsql/extension/vector.control" # pgvector安装后的标志文件
  echo -e "${COLOR_INFO}[Info] 开始安装pgvector...${COLOR_RESET}"
  if [ -f "$pgvector_installed_marker" ]; then
    echo -e "${COLOR_INFO}[Info] pgvector已安装，跳过安装过程${COLOR_RESET}"
    return 0
  fi
  # 1. 临时禁用SSL验证
  echo -e "${COLOR_INFO} 临时禁用Git SSL验证...${COLOR_RESET}"
  git config --global http.sslVerify false

  # 2. 克隆仓库
  echo -e "${COLOR_INFO} 正在克隆zhparser仓库...${COLOR_RESET}"
  if [ -d "$pgvector_dir" ]; then
    echo -e "${COLOR_INFO} 目标目录已存在，尝试更新代码...${COLOR_RESET}"
    cd "$pgvector_dir" || {
      echo -e "${COLOR_ERROR}[Error] 无法进入目录: $pgvector_dir${COLOR_RESET}"
      return 1
    }
    git pull origin master || {
      echo -e "${COLOR_ERROR}[Error] 代码更新失败${COLOR_RESET}"
      return 1
    }
  else
    git clone --branch v0.8.0 "$zhparser_url" "$pgvector_dir" || {
      echo -e "${COLOR_ERROR}[Error] 克隆仓库失败${COLOR_RESET}"
      return 1
    }
    cd "$pgvector_dir" || {
      echo -e "${COLOR_ERROR}[Error] 无法进入目录: $pgvector_dir${COLOR_RESET}"
      return 1
    }
  fi

  # 3. 恢复SSL验证
  echo -e "${COLOR_INFO} 恢复Git SSL验证...${COLOR_RESET}"
  git config --global http.sslVerify true

  # 4. 进入解压目录编译安装
  echo -e "${COLOR_INFO} 正在编译安装pgvector...${COLOR_RESET}"
  cd "$pgvector_dir" || {
    echo -e "${COLOR_ERROR}[Error] 无法进入目录: $pgvector_dir${COLOR_RESET}"
    return 1
  }

  if ! make >/dev/null; then
    echo -e "${COLOR_ERROR}[Error] make编译失败${COLOR_RESET}"
    return 1
  fi
  if ! make install >/dev/null; then
    echo -e "${COLOR_ERROR}[Error] make install安装失败${COLOR_RESET}"
    return 1
  fi
  echo -e "${COLOR_SUCCESS}[Success] pgvector安装成功${COLOR_RESET}"
  return 0
}
# 安装scws服务
install_scws() {
  local scws_url="http://www.xunsearch.com/scws/down/scws-1.2.3.tar.bz2"
  local scws_tar="/opt/scws-1.2.3.tar.bz2"
  local scws_dir="/opt/scws"
  local scws_installed_marker="/usr/local/lib/libscws.la" # SCWS安装后的标志性文件

  echo -e "${COLOR_INFO}[Info] 开始安装SCWS分词库...${COLOR_RESET}"
  # 1. 检查是否已安装
  if [ -f "$scws_installed_marker" ]; then
    echo -e "${COLOR_INFO}[Info] SCWS已安装，跳过安装过程${COLOR_RESET}"
    return 0
  fi
  # 2. 检查并下载SCWS安装包
  if [ -f "$scws_tar" ]; then
    echo -e "${COLOR_INFO}[Info] SCWS安装包已存在，跳过下载${COLOR_RESET}"
  else
    echo -e "${COLOR_INFO} 正在下载SCWS...${COLOR_RESET}"
    local logfile
    logfile=$(get_wget_log_filename "$scws_tar")
    if ! wget "$scws_url" --no-check-certificate -O "$scws_tar" -o "$logfile"; then
      echo -e "${COLOR_ERROR}[Error] SCWS下载失败${COLOR_RESET}"
      return 1
    fi
  fi

  # 3. 创建目标目录
  if ! mkdir -p "$scws_dir"; then
    echo -e "${COLOR_ERROR}[Error] 创建目录失败: $scws_dir${COLOR_RESET}"
    return 1
  fi

  # 4. 解压安装包
  echo -e "${COLOR_INFO} 正在解压SCWS...${COLOR_RESET}"
  if ! tar -xjf "$scws_tar" -C "$scws_dir" --strip-components=1; then
    echo -e "${COLOR_ERROR}[Error] 解压SCWS失败${COLOR_RESET}"
    return 1
  fi

  # 5. 编译安装
  echo -e "${COLOR_INFO} 正在编译安装SCWS...${COLOR_RESET}"
  cd "$scws_dir" || {
    echo -e "${COLOR_ERROR}[Error] 无法进入目录: $scws_dir${COLOR_RESET}"
    return 1
  }

  if ! ./configure >/dev/null; then
    echo -e "${COLOR_ERROR}[Error] configure配置失败${COLOR_RESET}"
    return 1
  fi

  if ! make >/dev/null; then
    echo -e "${COLOR_ERROR}[Error] make编译失败${COLOR_RESET}"
    return 1
  fi

  if ! make install >/dev/null; then
    echo -e "${COLOR_ERROR}[Error] make install安装失败${COLOR_RESET}"
    return 1
  fi

  echo -e "${COLOR_SUCCESS}[Success] SCWS安装成功${COLOR_RESET}"
  return 0
}
# 安装zhparser服务
install_zhparser() {
  # 目标目录
  local zhparser_dir="/opt/zhparser"
  local zhparser_url="https://bgithub.xyz/amutu/zhparser.git"
  local zhparser_installed_marker="/usr/share/pgsql/extension/zhparser.control" # zhparser安装后的标志文件
  echo -e "${COLOR_INFO}[Info] 开始安装zhparser...${COLOR_RESET}"
  # 检查是否已安装
  if [ -f "$zhparser_installed_marker" ]; then
    echo -e "${COLOR_INFO}[INFO] zhparser已安装，跳过安装过程${COLOR_RESET}"
    return 0
  fi
  # 1. 临时禁用SSL验证
  echo -e "${COLOR_INFO} 临时禁用Git SSL验证...${COLOR_RESET}"
  git config --global http.sslVerify false

  # 2. 克隆仓库
  echo -e "${COLOR_INFO} 正在克隆zhparser仓库...${COLOR_RESET}"
  if [ -d "$zhparser_dir" ]; then
    echo -e "${COLOR_INFO}[Info] 目标目录已存在，尝试更新代码...${COLOR_RESET}"
    cd "$zhparser_dir" || {
      echo -e "${COLOR_ERROR}[Error] 无法进入目录: $zhparser_dir${COLOR_RESET}"
      return 1
    }
    git pull origin master || {
      echo -e "${COLOR_ERROR}[Error] 代码更新失败${COLOR_RESET}"
      return 1
    }
  else
    git clone "$zhparser_url" "$zhparser_dir" || {
      echo -e "${COLOR_ERROR}[Error] 克隆仓库失败${COLOR_RESET}"
      return 1
    }
    cd "$zhparser_dir" || {
      echo -e "${COLOR_ERROR}[Error] 无法进入目录: $zhparser_dir${COLOR_RESET}"
      return 1
    }
  fi

  # 3. 恢复SSL验证
  echo -e "${COLOR_INFO} 恢复Git SSL验证...${COLOR_RESET}"
  git config --global http.sslVerify true

  # 4. 编译安装
  echo -e "${COLOR_INFO} 正在编译安装zhparser...${COLOR_RESET}"
  if ! make; then
    echo -e "${COLOR_ERROR}[Error] 编译失败${COLOR_RESET}"
    return 1
  fi

  if ! make install; then
    echo -e "${COLOR_ERROR}[Error] 安装失败${COLOR_RESET}"
    return 1
  fi

  echo -e "${COLOR_SUCCESS}[Success] zhparser安装成功${COLOR_RESET}"
  return 0
}

check_pip_rag() {
  local need_install=0
  local install_list=()

  # 定义需要检查的包和版本
  declare -A REQUIRED_PACKAGES=(
    ["sqlalchemy"]="2.0.23"
    ["paddlepaddle"]="3.0.0"
    ["paddleocr"]="2.9.1"
    ["tiktoken"]=""
  )

  echo -e "${COLOR_INFO}[Info] 检查Python依赖包...${COLOR_RESET}"

  # 检查每个包是否需要安装
  for pkg in "${!REQUIRED_PACKAGES[@]}"; do
    local required_ver
    local installed_ver
    required_ver="${REQUIRED_PACKAGES[$pkg]}"
    installed_ver=$(pip show "$pkg" 2>/dev/null | grep '^Version:' | awk '{print $2}')

    if [[ -z "$installed_ver" ]]; then
      echo -e "${COLOR_WARNING}[Warning] 未安装包: $pkg${COLOR_RESET}"
      need_install=1
      if [[ -n "$required_ver" ]]; then
        install_list+=("${pkg}==${required_ver}")
      else
        install_list+=("$pkg")
      fi
    elif [[ -n "$required_ver" && "$installed_ver" != "$required_ver" ]]; then
      echo -e "${COLOR_WARNING}[Warning] 包版本不匹配: $pkg (已安装: $installed_ver, 需要: $required_ver)${COLOR_RESET}"
      need_install=1
      install_list+=("${pkg}==${required_ver}")
    else
      echo -e "${COLOR_SUCCESS}[OK] 已安装: $pkg${COLOR_RESET}"
    fi
  done

  # 如果需要安装，则执行安装命令
  if [[ "$need_install" -eq 1 ]]; then
    echo -e "${COLOR_INFO}[Info] 开始安装Python依赖...${COLOR_RESET}"
    pip install --retries 10 --timeout 120 "${install_list[@]}" -i https://repo.huaweicloud.com/repository/pypi/simple || {
      echo -e "${COLOR_ERROR}[Error] Python依赖安装失败！${COLOR_RESET}"
      return 1
    }
    echo -e "${COLOR_SUCCESS}[Success] Python依赖安装完成！${COLOR_RESET}"
  else
    echo -e "${COLOR_SUCCESS}[Success] Python依赖已满足要求，跳过安装${COLOR_RESET}"
  fi

  return 0
}

check_pip_framework() {
  local need_install=0
  local install_list=()

  # 获取 Python 版本
  local python_version
  python_version=$(python3 --version 2>&1 | grep -oP '\d+\.\d+' | head -1)

  # 根据 Python 版本选择包列表
  declare -A REQUIRED_PACKAGES
  if [[ "$python_version" =~ ^3\.(11|[2-9][0-9])$ ]]; then
    # Python 3.11 或更新版本，检查并安装 DNF 源中缺失的 pip 依赖
    REQUIRED_PACKAGES=(
      ["pydantic"]=""
    )
  elif [[ "$python_version" =~ ^3\.(9|10)$ ]]; then
    # Python 3.9 或 3.10，RPM 包安装过程已处理 pip 依赖
    # 对于 Python 3.9，单独安装 MCP 的 wheel 包
    local wheel_path="../5-resource/pip/mcp-1.6.0-py3-none-any.whl"
    if [ -f "$wheel_path" ]; then
      echo -e "${COLOR_INFO}[Info] 为 Python 3.9 安装 wheel 包: $wheel_path${COLOR_RESET}"
      install_list+=("$wheel_path")
      need_install=1
    else
      echo -e "${COLOR_WARNING}[Warning] Wheel 文件不存在: $wheel_path${COLOR_RESET}"
    fi
  else
    echo -e "${COLOR_WARNING}[Warning] 不支持的 Python 版本: $python_version${COLOR_RESET}"
    return 1
  fi

  echo -e "${COLOR_INFO}[Info] 检查Python依赖包...${COLOR_RESET}"

  # 检查每个包是否需要安装
  for pkg in "${!REQUIRED_PACKAGES[@]}"; do
    local required_ver
    local installed_ver
    required_ver="${REQUIRED_PACKAGES[$pkg]}"
    installed_ver=$(pip show "$pkg" 2>/dev/null | grep '^Version:' | awk '{print $2}')

    if [[ -z "$installed_ver" ]]; then
      echo -e "${COLOR_WARNING}[Warning] 未安装包: $pkg${COLOR_RESET}"
      need_install=1
      if [[ -n "$required_ver" ]]; then
        install_list+=("${pkg}==${required_ver}")
      else
        install_list+=("$pkg")
      fi
    elif [[ -n "$required_ver" && "$installed_ver" != "$required_ver" ]]; then
      echo -e "${COLOR_WARNING}[Warning] 包版本不匹配: $pkg (已安装: $installed_ver, 需要: $required_ver)${COLOR_RESET}"
      need_install=1
      install_list+=("${pkg}==${required_ver}")
    else
      echo -e "${COLOR_SUCCESS}[OK] 已安装: $pkg${COLOR_RESET}"
    fi
  done

  # 如果需要安装，则执行安装命令
  if [[ "$need_install" -eq 1 ]]; then
    echo -e "${COLOR_INFO}[Info] 开始安装Python依赖...${COLOR_RESET}"
    pip install --retries 10 --timeout 120 "${install_list[@]}" -i https://repo.huaweicloud.com/repository/pypi/simple || {
      echo -e "${COLOR_ERROR}[Error] Python依赖安装失败！${COLOR_RESET}"
      return 1
    }
    echo -e "${COLOR_SUCCESS}[Success] Python依赖安装完成！${COLOR_RESET}"
  else
    echo -e "${COLOR_SUCCESS}[Success] Python依赖已满足要求，跳过安装${COLOR_RESET}"
  fi

  return 0
}

install_framework() {
  echo -e "\n${COLOR_INFO}[Info] 开始安装框架服务...${COLOR_RESET}"
  local pkgs=(
    "euler-copilot-framework"
    "git"
    "make"
    "gcc"
    "gcc-c++"
    "tar"
    "python3-pip"
    "postgresql"
    "postgresql-server"
    "postgresql-server-devel"
    "libpq-devel"
  )
  if ! install_and_verify "${pkgs[@]}"; then
    echo -e "${COLOR_ERROR}[Error] dnf安装验证未通过！${COLOR_RESET}"
    return 1
  fi
  # 安装 PostgreSQL 扩展
  cd "$SCRIPT_DIR" || return 1
  install_scws || return 1
  cd "$SCRIPT_DIR" || return 1
  install_pgvector || return 1
  cd "$SCRIPT_DIR" || return 1
  install_zhparser || return 1
  # 安装 MinIO 对象存储
  cd "$SCRIPT_DIR" || return 1
  install_minio || return 1
  cd "$SCRIPT_DIR" || return 1
  check_pip_framework || return 1
}

install_rag() {
  local pkgs=(
    "euler-copilot-rag"
    "clang"
    "llvm"
    "java-17-openjdk"
  )
  if ! install_and_verify "${pkgs[@]}"; then
    echo -e "${COLOR_ERROR}[Error] dnf安装验证未通过！${COLOR_RESET}"
    return 1
  fi
  cd "$SCRIPT_DIR" || return 1
  check_pip_rag || return 1
}

# 读取安装模式的方法
read_install_mode() {
  if [ ! -f "$INSTALL_MODE_FILE" ]; then
    echo "rag_install=n" >"$INSTALL_MODE_FILE"
  fi

  # 从文件读取配置（格式：key=value）
  local rag_install
  rag_install=$(grep "rag_install=" "$INSTALL_MODE_FILE" | cut -d'=' -f2)

  # 验证读取结果
  if [ -z "$rag_install" ]; then
    echo -e "${COLOR_ERROR}[Error] 安装模式文件格式错误${COLOR_RESET}"
    return 1
  fi

  # 输出读取结果（也可根据需要返回变量）
  echo -e "${COLOR_INFO}[Info] 读取安装模式:"
  echo -e "  安装RAG组件: ${rag_install}${COLOR_RESET}"

  # 将结果存入全局变量（供其他函数使用）
  RAG_INSTALL=$rag_install
  return 0
}

# 根据安装模式执行对应操作
install_components() {
  # 读取安装模式
  read_install_mode || return 1

  # 安装RAG组件（如果用户选择）
  if [ "$RAG_INSTALL" = "y" ]; then
    echo -e "\n${COLOR_INFO}[Info] 开始安装RAG检索增强组件...${COLOR_RESET}"
    install_rag || return 1
  fi
}

# 主执行函数
main() {
  echo -e "${COLOR_INFO}[Info] === 开始服务安装===${COLOR_RESET}"
  # 获取脚本所在的绝对路径
  local SCRIPT_DIR
  SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
  # 切换到脚本所在目录
  cd "$SCRIPT_DIR" || return 1
  #查看当前脚本执行的模式

  systemctl stop dnf-makecache.timer
  # 执行安装验证
  init_local_repo
  #分支执行TODO
  install_framework || return 1
  install_components || return 1
  echo -e "${COLOR_SUCCESS}[Success] 安装 openEuler Intelligence 完成！${COLOR_RESET}"
  return 0
}

main
