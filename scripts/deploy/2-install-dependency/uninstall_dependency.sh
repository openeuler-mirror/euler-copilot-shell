#!/bin/bash
# 颜色定义
COLOR_INFO='\033[34m'    # 蓝色信息
COLOR_SUCCESS='\033[32m' # 绿色成功
COLOR_ERROR='\033[31m'   # 红色错误
COLOR_WARNING='\033[33m' # 黄色警告
COLOR_RESET='\033[0m'    # 重置颜色
declare -a uninstalled_pkgs=()
uninstall_success=true
missing_pkgs=()
# 包名格式: "package_name" 或 "package_name:alternate1:alternate2"
pkgs=(
  "postgresql"
  "libpq-devel"
  "minio"
)

# 清理函数（在中断或退出时调用）
cleanup() {
  echo -e "${COLOR_ERROR}[Error] 检测到中断，停止执行${COLOR_RESET}"
  return 1
}

# 卸载 MinIO（处理 RPM 和旧版本二进制文件）
uninstall_minio() {
  echo -e "${COLOR_INFO}[Info] 开始卸载 MinIO...${COLOR_RESET}"
  local minio_uninstalled=false

  # 1. 尝试卸载 RPM 包
  if rpm -q minio >/dev/null 2>&1; then
    echo -e "${COLOR_INFO}[Info] 检测到 MinIO RPM 包，正在卸载...${COLOR_RESET}"
    if dnf remove -y minio >/dev/null 2>&1; then
      echo -e "${COLOR_SUCCESS}[Success] MinIO RPM 包卸载成功${COLOR_RESET}"
      minio_uninstalled=true
    else
      echo -e "${COLOR_ERROR}[Error] MinIO RPM 包卸载失败${COLOR_RESET}"
      return 1
    fi
  else
    echo -e "${COLOR_INFO}[Info] 未检测到 MinIO RPM 包${COLOR_RESET}"
  fi

  # 2. 检查并清理可能存在的二进制文件（旧版本或手动安装）
  local minio_binary="/usr/local/bin/minio"
  if [ -f "$minio_binary" ]; then
    echo -e "${COLOR_INFO}[Info] 检测到 MinIO 二进制文件，正在删除...${COLOR_RESET}"
    if rm -f "$minio_binary"; then
      echo -e "${COLOR_SUCCESS}[Success] MinIO 二进制文件删除成功${COLOR_RESET}"
      minio_uninstalled=true
    else
      echo -e "${COLOR_ERROR}[Error] MinIO 二进制文件删除失败${COLOR_RESET}"
      return 1
    fi
  fi

  # 3. 清理 MinIO 配置和数据目录（在 delete_dir 中处理 /opt/minio）
  if [ -d "/etc/minio" ]; then
    echo -e "${COLOR_INFO}[Info] 清理 MinIO 配置目录...${COLOR_RESET}"
    rm -rf /etc/minio
  fi

  if [ "$minio_uninstalled" = true ]; then
    echo -e "${COLOR_SUCCESS}[Success] MinIO 卸载完成${COLOR_RESET}"
  else
    echo -e "${COLOR_INFO}[Info] MinIO 未安装，跳过卸载${COLOR_RESET}"
  fi

  return 0
}

uninstall_dependency() {
  # 捕获中断信号(Ctrl+C)和错误
  trap cleanup INT TERM ERR

  # 检查并卸载每个包
  for pkg_spec in "${pkgs[@]}"; do
    # 解析包名和备用包名（使用冒号分隔）
    IFS=':' read -ra pkg_names <<<"$pkg_spec"
    local primary_pkg="${pkg_names[0]}"

    # MinIO 使用专门的卸载函数处理
    if [ "$primary_pkg" = "minio" ]; then
      uninstall_minio || {
        uninstall_success=false
        missing_pkgs+=("$primary_pkg")
      }
      continue
    fi

    # 尝试检查并卸载主包名或备用包名
    local pkg_found=false
    for pkg in "${pkg_names[@]}"; do
      if rpm -q "$pkg" >/dev/null 2>&1; then
        pkg_found=true
        echo -e "${COLOR_INFO}[Info] 正在卸载 $pkg...${COLOR_RESET}"
        if dnf remove -y "$pkg" >/dev/null 2>&1; then
          uninstalled_pkgs+=("$pkg")
          break # 成功卸载后跳出循环
        else
          echo -e "${COLOR_ERROR}[Error] 卸载 $pkg 失败！${COLOR_RESET}"
          uninstall_success=false
          missing_pkgs+=("$pkg")
          cleanup
        fi
      fi
    done

    if [ "$pkg_found" = false ]; then
      echo -e "${COLOR_INFO}[Info] $primary_pkg 未安装，跳过...${COLOR_RESET}"
    fi
  done

  # 取消捕获
  trap - INT TERM ERR
  # 检查安装结果
  if $uninstall_success; then
    echo -e "${COLOR_INFO}[Info] 所有包卸载成功！${COLOR_RESET}"
  else
    echo -e "${COLOR_ERROR}[Error] 以下包卸载失败: ${missing_pkgs[*]}${COLOR_RESET}"
    return 1
  fi
}

delete_dir() {
  # 基础目录和子目录定义
  local BASE_PWD="/opt"
  local dirs=(
    "minio"
    "pgvector"
    "scws*"
    "zhparser"
  )

  # 状态跟踪
  local delete_success=true
  local deleted_dirs=()
  local failed_dirs=()
  local skipped_dirs=()

  # 日志文件
  local LOG_FILE
  LOG_FILE="/var/log/deletion_$(date +%Y%m%d).log"
  echo "[$(date +'%Y-%m-%d %H:%M:%S')] 开始目录清理操作" >>"$LOG_FILE"

  # 检查root权限
  if [[ $EUID -ne 0 ]]; then
    echo -e "${COLOR_ERROR}[Error] 需要root权限执行此操作${COLOR_RESET}" | tee -a "$LOG_FILE"
    return 1
  fi

  # 显示将要删除的目录
  echo -e "${COLOR_WARNING}[Warning] 即将删除以下目录：${COLOR_RESET}" | tee -a "$LOG_FILE"
  for dir in "${dirs[@]}"; do
    echo "  $BASE_PWD/$dir" | tee -a "$LOG_FILE"
  done
  echo "  /var/lib/sysagent" | tee -a "$LOG_FILE"

  # 捕获中断信号
  trap 'echo -e "${COLOR_ERROR}[Error] 操作被中断！${COLOR_RESET}" | tee -a "$LOG_FILE"; exit 1' INT TERM

  # 执行删除 /opt 下的目录
  for dir in "${dirs[@]}"; do
    local target="$BASE_PWD/$dir"

    # 检查目录是否存在
    if ls -d "$target" &>/dev/null; then
      echo -e "${COLOR_INFO}[Info] 正在删除: $target${COLOR_RESET}" | tee -a "$LOG_FILE"

      # 实际删除操作
      if rm -rf "$target"; then
        deleted_dirs+=("$target")
        echo -e "${COLOR_INFO}[Info] 成功删除: $target${COLOR_RESET}" | tee -a "$LOG_FILE"
      else
        failed_dirs+=("$target")
        delete_success=false
        echo -e "${COLOR_ERROR}[Error] 删除失败: $target${COLOR_RESET}" | tee -a "$LOG_FILE"
      fi
    else
      skipped_dirs+=("$target")
      echo -e "${COLOR_INFO}[Info] 目录不存在，跳过: $target${COLOR_RESET}" | tee -a "$LOG_FILE"
    fi
  done

  # 删除 euler_copilot 数据目录
  if [ -d "/var/lib/sysagent" ]; then
    echo -e "${COLOR_INFO}[Info] 正在删除: /var/lib/sysagent${COLOR_RESET}" | tee -a "$LOG_FILE"
    if rm -rf "/var/lib/sysagent"; then
      deleted_dirs+=("/var/lib/sysagent")
      echo -e "${COLOR_INFO}[Info] 成功删除: /var/lib/sysagent${COLOR_RESET}" | tee -a "$LOG_FILE"
    else
      failed_dirs+=("/var/lib/sysagent")
      delete_success=false
      echo -e "${COLOR_ERROR}[Error] 删除失败: /var/lib/sysagent${COLOR_RESET}" | tee -a "$LOG_FILE"
    fi
  fi

  # 取消信号捕获
  trap - INT TERM

  if $delete_success; then
    echo -e "${COLOR_INFO}[Info] 目录清理完成！${COLOR_RESET}" | tee -a "$LOG_FILE"
  else
    echo -e "${COLOR_ERROR}[Error] 目录清理未完全成功！${COLOR_RESET}" | tee -a "$LOG_FILE"
    echo -e "${COLOR_ERROR}[Error] 失败的目录: ${failed_dirs[*]}${COLOR_RESET}" | tee -a "$LOG_FILE"
    return 1
  fi
}
delete_data() {
  echo -e "${COLOR_INFO}[Info] 清理数据库遗留数据！${COLOR_RESET}"
  rm -rf /var/lib/pgsql
  echo -e "${SUCCESS}[Success] 清理数据库遗留数据 完成！${COLOR_RESET}"
}

# 主执行函数
main() {
  echo -e "${COLOR_INFO}[Info] === 开始卸载依赖===${COLOR_RESET}"

  # 执行安装验证
  if uninstall_dependency; then
    delete_dir
    delete_data
    echo -e "${COLOR_SUCCESS}[Success] 卸载依赖完成！${COLOR_RESET}"
    return 0
  else
    echo -e "${COLOR_ERROR}[Error] 卸载依赖失败！${COLOR_RESET}"
    return 1
  fi
}

main
