#!/bin/bash

COLOR_INFO='\033[34m'    # 蓝色信息
COLOR_SUCCESS='\033[32m' # 绿色成功
COLOR_ERROR='\033[31m'   # 红色错误
COLOR_WARNING='\033[33m' # 黄色警告
COLOR_RESET='\033[0m'    # 重置颜色
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'

# 顶层菜单
show_top_menu() {
  clear
  echo "=============================="
  echo "        一键部署菜单             "
  echo "=============================="
  echo "0) 自动部署"
  echo "1) 手动部署"
  echo "2) 重启服务"
  echo "3) 卸载服务"
  echo "4) 退出程序"
  echo "=============================="
  echo -n "请输入选项编号（0-4）: "
}

# 安装选项菜单（手动部署子菜单）
show_sub_menu() {
  clear
  echo "=============================="
  echo "       手动分步部署菜单         "
  echo "=============================="
  echo "1) 环境检查"
  echo "2) 安装 openEuler Intelligence"
  echo "3) 初始化配置"
  echo "4) 返回主菜单"
  echo "=============================="
  echo -n "请输入选项编号（1-4）: "
}

show_restart_menu() {
  clear
  echo "=============================="
  echo "        服务重启菜单           "
  echo "=============================="
  echo "可重启的服务列表："
  echo "1) oi-runtime"
  echo "2) oi-rag"
  echo "3) postgresql"
  echo "4) 返回主菜单"
  echo "=============================="
  echo -n "请输入要重启的服务编号（1-4）: "
}

# 带错误检查的脚本执行函数
run_script_with_check() {
  local script_path=$1
  local script_name=$2

  echo "--------------------------------------------------"
  echo "开始执行：$script_name"
  "$script_path" || {
    echo -e "\n\033[31m$script_name 执行失败！\033[0m"
    exit 1
  }
  echo -e "\n\033[32m$script_name 执行成功！\033[0m"
  echo "--------------------------------------------------"
}

# 执行子菜单对应脚本
run_sub_script() {
  case $1 in
  1)
    run_script_with_check "./1-check-env/check_env.sh" "环境检查"
    ;;
  2)
    run_script_with_check "./2-install-dependency/install_openEulerIntelligence.sh" "安装 openEuler Intelligence"
    ;;
  3)
    run_script_with_check "./3-install-server/init_config.sh" "初始化配置"
    ;;
  4)
    echo "正在返回主菜单..."
    echo "按任意键继续..."
    read -r -n 1 -s
    return 2 # 特殊返回码表示返回上级菜单
    ;;
  *)
    echo -e "\033[31m无效的选项，请输入1-4之间的数字\033[0m"
    return 1
    ;;
  esac
  return 0
}

# 手动部署子菜单循环
manual_deployment_loop() {
  while true; do
    show_sub_menu
    read -r sub_choice
    run_sub_script "$sub_choice"
    retval=$?

    if [ $retval -eq 2 ]; then # 返回主菜单
      break
    elif [ $retval -eq 0 ]; then
      echo "按任意键继续..."
      read -r -n 1 -s
    fi
  done
}

restart_service() {
  local service="$1"
  if [[ -z "$service" ]]; then
    echo -e "${COLOR_ERROR}[Error] 错误: 请输入服务名称${COLOR_RESET}"
    return 1
  fi

  # 检查服务是否存在
  if ! systemctl list-unit-files | grep -q "^$service.service"; then
    echo -e "${COLOR_ERROR}[Error] 轻量化部署模式 服务 ${service} 未安装${COLOR_RESET}"
    return 1
  fi

  # 检查服务是否活跃
  if systemctl is-active --quiet "$service"; then
    echo -e "${COLOR_INFO}[Info] ${service} 服务正在运行，准备重启...${COLOR_RESET}"
    systemctl restart "$service"
  else
    echo -e "${COLOR_INFO}[Info] ${service} 服务未运行，准备启动...${COLOR_RESET}"
    systemctl start "$service"
  fi

  sleep 2 # 给系统一点时间处理

  # 验证最终状态
  if systemctl is-active --quiet "$service"; then
    echo -e "${COLOR_SUCCESS}[Success] ${service} 服务操作成功${COLOR_RESET}"
    return 0
  else
    echo -e "${COLOR_ERROR}[Error] ${service} 服务操作失败${COLOR_RESET}"
    return 3
  fi
}

# 帮助信息函数
show_help() {
  echo -e "${GREEN}openEuler Intelligence 一键部署系统使用说明${COLOR_RESET}"
  echo "=============================================================================="
  echo -e "${BLUE}使用方式:${COLOR_RESET}"
  echo "  $0 [选项]"
  echo ""
  echo -e "${BLUE}选项:${COLOR_RESET}"
  echo "  无参数        进入交互式菜单"
  echo "  --h          显示本帮助信息"
  echo "  --help       同 --h"
  echo "  --a          进入 Agent 初始化模式，详见部署文档"
  echo ""
  echo -e "${BLUE}服务部署手册查看位置:${COLOR_RESET}"
  echo "  1. 在线文档: https://gitee.com/openeuler/euler-copilot-shell/blob/dev/scripts/deploy/安装部署手册.md"
  echo ""
  echo -e "${BLUE}常见问题:${COLOR_RESET}"
  echo "  - 服务启动失败排查: journalctl -xe -u [服务名称] --all"
  echo "  - 部署日志查看: /var/log/openEulerIntelligence/Install-xxx.log"
  echo ""
  echo -e "${YELLOW}如需详细配置指导，请参考上述文档或联系系统管理员${COLOR_RESET}"
  echo "=============================================================================="
  exit 0
}

agent_manager() {
  # 获取主脚本绝对路径并切换到所在目录
  MAIN_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
  if [ "${MAIN_DIR}" = "/usr/bin" ]; then
    cd /usr/lib/openeuler-intelligence/scripts || exit 1
  else
    cd "$MAIN_DIR" || exit 1
  fi

  # 将所有接收的参数传递给 Python 脚本
  python3 4-other-script/agent_manager.py "$@"
  return 0
}

# 检查帮助参数
if [[ "$1" == "--h" || "$1" == "--help" ]]; then
  show_help
fi

# 检查是否进入 Agent 初始化模式
if [[ "$1" == "--a" ]]; then
  agent_manager "${@:2}"
  exit 0
fi

# 获取主脚本绝对路径并切换到所在目录
MAIN_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
if [ "${MAIN_DIR}" = "/usr/bin" ]; then
  cd /usr/lib/openeuler-intelligence/scripts || exit 1
else
  cd "$MAIN_DIR" || exit 1
fi

# 主程序循环改进
while true; do
  show_top_menu
  read -r main_choice
  case $main_choice in
  0)
    "./0-one-click-deploy/one-click-deploy.sh"
    echo "按任意键继续..."
    read -r -n 1 -s
    ;;
  1)
    manual_deployment_loop
    ;;
  2)
    while true; do
      show_restart_menu
      read -r restart_choice
      case $restart_choice in
      1) service="oi-runtime" ;;
      2) service="oi-rag" ;;
      3) service="postgresql" ;;
      4) break ;;
      *)
        echo -e "${COLOR_ERROR}无效的选项，请输入1-4之间的数字${COLOR_RESET}"
        continue
        ;;
      esac

      if [[ -n "$service" ]]; then
        restart_service "$service"
        echo "按任意键继续..."
        read -r -n 1 -s
      fi
    done
    ;;

  3)
    run_script_with_check "./3-install-server/uninstall_server.sh" "卸载所有服务"
    run_script_with_check "./2-install-dependency/uninstall_dependency.sh" "卸载数据库和文件服务"
    echo "按任意键继续..."
    read -r -n 1 -s
    ;;
  4)
    echo "退出部署系统"
    exit 0
    ;;
  *)
    echo -e "${COLOR_ERROR}无效的选项，请输入0-4之间的数字${COLOR_RESET}"
    sleep 1
    ;;
  esac
done
return 0
