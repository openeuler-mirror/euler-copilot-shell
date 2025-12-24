#!/bin/bash
# 颜色定义
COLOR_INFO='\033[34m'    # 蓝色信息
COLOR_SUCCESS='\033[32m' # 绿色成功
COLOR_ERROR='\033[31m'   # 红色错误
COLOR_WARNING='\033[33m' # 黄色警告
COLOR_RESET='\033[0m'    # 重置颜色
# 全局模式标记
OFFLINE_MODE=false

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

# 全局变量：默认端口列表
PORTS=(8002)

# 读取安装模式并设置端口列表的函数
init_ports() {
  echo -e "${COLOR_INFO} 端口列表: ${PORTS[*]}${COLOR_RESET}"
}

function check_user {
  if [[ $(id -u) -ne 0 ]]; then
    echo -e "${COLOR_ERROR}[Error] 请以root权限运行该脚本！${COLOR_RESET}"
    return 1
  fi
  return 0
}

function check_version {
  local current_version_id="$1"
  local sp="$2"
  local supported_versions=("${@:3}")
  echo -e "${COLOR_INFO}[Info] 当前操作系统版本为：$current_version_id LTS-$sp${COLOR_RESET}"
  for version_id in "${supported_versions[@]}"; do
    if [[ "$current_version_id" == "$version_id" ]]; then
      case "$current_version_id" in
      "22.03")
        if [[ "$sp" == "SP4" ]]; then
          echo -e "${COLOR_SUCCESS}[Success] 操作系统满足兼容性要求${COLOR_RESET}"
          return 0
        fi
        ;;
      "24.03")
        if [[ "$sp" == "SP2" || "$sp" == "SP3" ]]; then
          echo -e "${COLOR_SUCCESS}[Success] 操作系统满足兼容性要求${COLOR_RESET}"
          return 0
        fi
        ;;
      "25.03" | "25.09")
        if [[ -z "$sp" ]]; then
          echo -e "${COLOR_SUCCESS}[Success] 操作系统满足兼容性要求${COLOR_RESET}"
          return 0
        fi
        ;;
      esac
    fi
  done

  echo -e "${COLOR_ERROR}[Error] 操作系统不满足兼容性要求，脚本将退出${COLOR_RESET}"
  return 1
}

function check_os_version {
  local id
  local version
  local sp
  id=$(grep '^ID=' /etc/os-release | cut -d= -f2 | tr -d '"')
  version=$(grep -E "^VERSION_ID=" /etc/os-release | cut -d '"' -f 2)
  sp=$(grep -E "^VERSION=" /etc/os-release | grep -oP 'SP\d+')

  echo -e "${COLOR_INFO}[Info] 当前发行版为：$id${COLOR_RESET}"

  case $id in
  "openEuler")
    local supported_versions=("22.03" "24.03" "25.03" "25.09")
    check_version "$version" "$sp" "${supported_versions[@]}"
    ;;
  "hce")
    echo -e "${COLOR_INFO}[Info] 检测到 HCE 发行版，跳过版本检查${COLOR_RESET}"
    return 0
    ;;
  *)
    echo -e "${COLOR_ERROR}[Error] 发行版不受支持，脚本将退出${COLOR_RESET}"
    return 1
    ;;
  esac
  return $?
}

# 检查单个软件包是否可用
# 参数: 包名 [备用包名1] [备用包名2] ...
check_package() {
  local primary_pkg=$1
  shift
  local alternate_pkgs=("$@")

  # 先检查主包名
  if dnf list "$primary_pkg" &>/dev/null; then
    echo -e "${COLOR_INFO}[Info] $(printf '%-30s' "$primary_pkg") \t(可用)${COLOR_RESET}"
    return 0
  fi

  # 如果主包名不可用，尝试备用包名
  for alt_pkg in "${alternate_pkgs[@]}"; do
    if dnf list "$alt_pkg" &>/dev/null; then
      echo -e "${COLOR_INFO}[Info] $(printf '%-30s' "$primary_pkg") \t(可用，使用 $alt_pkg)${COLOR_RESET}"
      return 0
    fi
  done

  # 所有包名都不可用
  if [ ${#alternate_pkgs[@]} -gt 0 ]; then
    echo -e "${COLOR_ERROR}[Error] $(printf '%-30s' "$primary_pkg") \t(不可用，已尝试: ${alternate_pkgs[*]})${COLOR_RESET}"
  else
    echo -e "${COLOR_ERROR}[Error] $(printf '%-30s' "$primary_pkg") \t(不可用)${COLOR_RESET}"
  fi
  return 1
}

all_available=true
# 检查所有软件包
# 包名格式: "package_name" 或 "package_name:alternate1:alternate2"
check_packages() {
  local packages=("$@")

  local timeout_seconds=30
  local start_time
  start_time=$(date +%s)

  echo -e "${COLOR_INFO}--------------------------------${COLOR_RESET}"

  for pkg_spec in "${packages[@]}"; do
    # 检查是否超时
    local current_time
    current_time=$(date +%s)
    local elapsed=$((current_time - start_time))

    if [ $elapsed -ge $timeout_seconds ]; then
      echo -e "${COLOR_ERROR}[Error] 检查操作已超时(${timeout_seconds}s)${COLOR_RESET}"
      echo -e "${COLOR_INFO}--------------------------------${COLOR_RESET}"
      return 2
    fi

    # 分割包名和备用名（使用冒号分隔）
    IFS=':' read -ra pkg_names <<<"$pkg_spec"
    if ! check_package "${pkg_names[@]}"; then
      all_available=false
    fi
    sleep 0.1 # 避免请求过快
  done
}
check_framework_pkg() {
  local pkgs=(
    "euler-copilot-framework"
    "make"
    "gcc"
    "gcc-c++"
    "clang"
    "llvm"
    "tar"
    "postgresql"
    "postgresql-server"
    "postgresql-server-devel"
    "libpq-devel"
  )
  if ! check_packages "${pkgs[@]}"; then
    return 1
  fi
}

function check_dns {
  echo -e "${COLOR_INFO}[Info] 检查DNS设置${COLOR_RESET}"
  if grep -q "^nameserver" /etc/resolv.conf; then
    echo -e "${COLOR_SUCCESS}[Success] DNS已配置${COLOR_RESET}"
    return 0
  fi

  if $OFFLINE_MODE; then
    echo -e "${COLOR_WARNING}[Warning] 离线模式：请手动配置内部DNS服务器${COLOR_RESET}"
    return 0
  else
    echo -e "${COLOR_WARNING}[Warning] DNS未配置，建议手动设置DNS服务器（如8.8.8.8）${COLOR_RESET}"
    echo -e "${COLOR_INFO}[Info] 可通过以下命令设置：echo 'nameserver 8.8.8.8' >> /etc/resolv.conf${COLOR_RESET}"
    return 0
  fi
}

function check_ram {
  local RAM_THRESHOLD=1024
  local current_mem
  current_mem=$(free -m | awk '/Mem/{print $2}')

  echo -e "${COLOR_INFO}[Info] 当前内存：$current_mem MB${COLOR_RESET}"
  if ((current_mem < RAM_THRESHOLD)); then
    echo -e "${COLOR_ERROR}[Error] 内存不足 ${RAM_THRESHOLD} MB${COLOR_RESET}"
    return 1
  fi
  echo -e "${COLOR_SUCCESS}[Success] 内存满足要求${COLOR_RESET}"
  return 0
}

check_disk_space() {
  local DIR="$1"
  local THRESHOLD="$2"

  local USAGE
  USAGE=$(df --output=pcent "$DIR" | tail -n 1 | sed 's/%//g' | tr -d ' ')

  if [ "$USAGE" -ge "$THRESHOLD" ]; then
    echo -e "${COLOR_WARNING}[Warning] $DIR 的磁盘使用率已达到 ${USAGE}%，超过阈值 ${THRESHOLD}%${COLOR_RESET}"
    return 1
  else
    echo -e "${COLOR_INFO}[Info] $DIR 的磁盘使用率为 ${USAGE}%，低于阈值 ${THRESHOLD}%${COLOR_RESET}"
    return 0
  fi
}

# 检查端口是否被占用
check_ports() {
  local occupied=()
  echo -e "${COLOR_INFO}正在检查端口占用情况...${COLOR_RESET}"
  init_ports

  for port in "${PORTS[@]}"; do
    if ss -tuln | grep -q ":${port} "; then
      occupied+=("$port")
      echo -e "${COLOR_WARNING}[Warning] 端口 $port 已被占用${COLOR_RESET}"
    else
      echo -e "${COLOR_INFO}[Info] 端口 $port 可用${COLOR_RESET}"
    fi
  done

  if [ ${#occupied[@]} -gt 0 ]; then
    echo -e "${COLOR_ERROR}[Error]错误: 以下端口已被占用: ${occupied[*]}${COLOR_RESET}"
    echo -e "${COLOR_ERROR}[Error]请先释放这些端口再运行脚本${COLOR_RESET}"
    return 1
  fi
  echo -e "${COLOR_SUCCESS}[Success]检查端口占用情况成功，端口未占用${COLOR_RESET}"
  return 0
}

# 配置防火墙
setup_firewall() {

  echo -e "${COLOR_INFO}[Info]配置防火墙...${COLOR_RESET}"

  if ! systemctl is-active --quiet firewalld; then
    echo -e "${COLOR_SUCCESS}[Success]防火墙未运行${COLOR_RESET}"
    return 0
  fi
  echo -e "${COLOR_INFO}[Info]防火墙已运行，开放端口${COLOR_RESET}"
  for port in "${PORTS[@]}"; do
    echo -e "${COLOR_INFO}[Info]开放端口 $port/tcp...${COLOR_RESET}"
    firewall-cmd --permanent --add-port="${port}"/tcp || {
      echo -e "${COLOR_ERROR}[Error]开放端口 $port 失败！${COLOR_RESET}"
      return 1
    }
  done

  echo -e "${COLOR_INFO}[Info]重新加载防火墙规则...${COLOR_RESET}"
  firewall-cmd --reload || {
    echo -e "${COLOR_ERROR}[Error]防火墙规则重载失败！${COLOR_RESET}"
    return 1
  }
  echo -e "${COLOR_SUCCESS}[Success]重新加载防火墙规则成功${COLOR_RESET}"
  return 0
}

# 检查软件包是否可用
install_components() {
  echo -e "${COLOR_INFO}[Info] 检查软件包是否可用${COLOR_RESET}"

  check_framework_pkg
  echo -e "--------------------------------"

  if $all_available; then
    echo -e "${COLOR_SUCCESS}[Success] 所有软件包都可用${COLOR_RESET}"
    return 0
  else
    echo -e "${COLOR_ERROR}[Error] 部分软件包不可用${COLOR_RESET}"
    echo -e "${COLOR_INFO}[Info] 提示：可以尝试以下命令更新仓库缓存：${COLOR_RESET}"
    echo -e "${COLOR_INFO}[Info] sudo dnf clean all && sudo dnf makecache${COLOR_RESET}"
    return 1
  fi
}

function main {
  check_user || return 1
  check_os_version || return 1

  # 检查软件包可用性
  install_components || return 1

  check_dns || return 1
  check_ram || return 1
  check_disk_space "/" 70

  if [ $? -eq 1 ]; then
    echo -e "${COLOR_WARNING}[Warning] 需要清理磁盘空间！${COLOR_RESET}"
  else
    echo -e "${COLOR_SUCCESS}[Success] 磁盘空间正常${COLOR_RESET}"
  fi

  check_ports || return 1
  setup_firewall || return 1

  # 最终部署提示
  echo -e "\n${COLOR_SUCCESS}#####################################"
  echo -e "#         环境检查完成             #"
  echo -e "#####################################${COLOR_RESET}"
  return 0
}

main
