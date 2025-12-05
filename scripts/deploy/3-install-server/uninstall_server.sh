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
  "euler-copilot-framework"
  "minio"
)

# 清理函数（在中断或退出时调用）
cleanup() {
  echo -e "${COLOR_ERROR}[Error] 检测到中断，停止执行${COLOR_RESET}"
  return 1
}

uninstall_server() {
  # 捕获中断信号(Ctrl+C)和错误
  trap cleanup INT TERM ERR
  # 检查并卸载每个包
  for pkg in "${pkgs[@]}"; do
    if rpm -q "$pkg" >/dev/null 2>&1; then
      echo -e "${COLOR_INFO}[Info] 正在卸载 $pkg...${COLOR_RESET}"

      if [ "$pkg" = "euler-copilot-framework" ]; then
        systemctl stop sysagent 2>/dev/null || true
        systemctl stop oi-runtime 2>/dev/null || true # 兼容旧版本
      elif [ "$pkg" = "minio" ]; then
        systemctl stop minio >/dev/null 2>&1
      else
        systemctl stop "$pkg"
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
  rm -rf /var/log/openEulerIntelligence
  rm -rf /etc/sysagent
  rm -rf /etc/euler-copilot-framework # 兼容旧版本
  rm -rf /etc/systemd/system/sysagent.service
  rm -rf /etc/systemd/system/multi-user.target.wants/sysagent.service
  rm -rf /etc/systemd/system/oi-runtime.service                         # 兼容旧版本
  rm -rf /etc/systemd/system/multi-user.target.wants/oi-runtime.service # 兼容旧版本

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
