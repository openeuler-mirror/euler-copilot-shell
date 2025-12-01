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
pkgs=(
  "euler-copilot-web"
  "euler-copilot-witchaind-web"
  "authHub"
  "authhub-web"
  "euler-copilot-rag"
  "euler-copilot-framework"
  "minio"
)

# 清理函数（在中断或退出时调用）
cleanup() {
  echo -e "${COLOR_ERROR}[Error] 检测到中断，停止执行${COLOR_RESET}"
  return 1
}

uninstall_tika() {
  local tika_jar_dest="/opt/tika/tika-server-standard-3.2.0.jar"
  local tika_service_dest="/etc/systemd/system/tika.service"
  echo -e "${COLOR_INFO}[Info] 正在卸载 Tika...${COLOR_RESET}"
  # 1. 检查源文件是否存在
  if [ ! -f "$tika_jar_dest" ]; then
    #        echo -e "${COLOR_WARNING}[Warning] Tika JAR文件不存在: $tika_jar_dest${COLOR_RESET}"
    return 1
  fi

  if [ ! -f "$tika_service_dest" ]; then
    echo -e "${COLOR_WARNING}[Warning] Tika服务文件不存在: $tika_service_dest${COLOR_RESET}"
    return 1
  fi
  systemctl stop tika
  rm -rf $tika_jar_dest
  rm -rf $tika_service_dest
  # 2. 重载systemd
  if ! systemctl daemon-reload; then
    echo -e "${COLOR_ERROR}[Error] systemd重载失败${COLOR_RESET}"
    return 1
  fi
}
is_x86_architecture() {
  local arch
  arch=$(uname -m)
  if [[ $arch == i386 || $arch == i686 || $arch == x86_64 ]]; then
    return 0 # 是 x86 架构，返回 0（成功）
  else
    return 1 # 非 x86 架构，返回 1（失败）
  fi
}
uninstall_server() {
  uninstall_tika

  # 捕获中断信号(Ctrl+C)和错误
  trap cleanup INT TERM ERR
  # 检查并卸载每个包
  for pkg in "${pkgs[@]}"; do
    if rpm -q "$pkg" >/dev/null 2>&1; then
      echo -e "${COLOR_INFO}[Info] 正在卸载 $pkg...${COLOR_RESET}"

      if [ "$pkg" = "authHub" ]; then
        systemctl stop authhub
      elif [[ "$pkg" = "euler-copilot-web" || "$pkg" = "euler-copilot-witchaind-web" || "$pkg" = "euler-copilot-rag" ]]; then
        : # 什么都不做
      elif [ "$pkg" = "minio" ]; then
        if is_x86_architecture; then
          dnf remove -y "$pkg" >/dev/null 2>&1
        else
          systemctl stop minio >/dev/null 2>&1
          rm -rf /etc/systemd/system/minio.service
          rm -rf /etc/default/minio
          rm -rf /var/lib/minio
          rm -rf /etc/systemd/system/minio.service
          rm -rf /usr/local/bin/minio
          systemctl daemon-reload || {
            echo -e "${COLOR_WARNING}[Warning] 卸载 $pkg 重载systemd失败${COLOR_RESET}"
          }

        fi
      elif [ "$pkg" = "euler-copilot-framework" ]; then
        systemctl stop oi-runtime
      else
        systemctl stop $pkg
      fi
      if dnf remove -y "$pkg" >/dev/null 2>&1; then
        uninstalled_pkgs+=("$pkg")

        systemctl daemon-reload || {
          echo -e "${COLOR_WARNING}[Warning] 卸载 $pkg 重载systemd失败${COLOR_RESET}"
        }
      else
        echo -e "${COLOR_ERROR}[Error] 卸载 $pkg 失败！${COLOR_RESET}"
        uninstall_success=false
        missing_pkgs+=("$pkg")
        cleanup
      fi
    else
      echo -e "${COLOR_INFO}[Info] $pkg 未安装，跳过...${COLOR_RESET}"
    fi

  done
  # 删除残留文件和目录
  rm -rf /usr/lib/euler-copilot-rag
  rm -rf /var/log/openEulerIntelligence
  rm -rf /etc/euler-copilot-framework
  rm -rf /etc/euler-copilot-rag
  rm -rf /etc/euler_Intelligence_install_mode
  rm -rf /etc/nginx/conf.d/authhub.nginx.conf.bak
  rm -rf /etc/systemd/system/oi-runtime.service
  rm -rf /etc/systemd/system/multi-user.target.wants/oi-runtime.service

  # 清理系统配置
  systemctl daemon-reload
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

# 主执行函数
main() {
  echo -e "${COLOR_INFO}[Info] === 开始卸载服务===${COLOR_RESET}"
  # 执行安装验证
  if uninstall_server; then
    echo -e "${COLOR_SUCCESS}[Success] 卸载服务完成！${COLOR_RESET}"
    return 0
  else
    echo -e "${COLOR_ERROR}[Error] 卸载服务失败！${COLOR_RESET}"
    return 1
  fi
}

main
