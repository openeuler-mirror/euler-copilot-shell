#!/bin/bash

COLOR_INFO='\033[34m'    # 蓝色信息
COLOR_SUCCESS='\033[32m' # 绿色成功
COLOR_ERROR='\033[31m'   # 红色错误
COLOR_WARNING='\033[33m' # 黄色警告
COLOR_RESET='\033[0m'    # 重置颜色
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'

INSTALL_MODE_FILE="/etc/euler_Intelligence_install_mode"

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
  echo "2) 安装 Witty Assistant"
  echo "3) 初始化配置"
  echo "4) 返回主菜单"
  echo "=============================="
  echo -n "请输入选项编号（1-4）: "
}
# 安装选项菜单（手动选择模式部署部署子菜单）
show_sub_model_menu() {
  clear
  echo "=============================="
  echo "       手动分步部署菜单         "
  echo "=============================="
  echo "1) 轻量部署 # 仅部署 oi-runtime 服务"
  echo "2) 全量部署 # 带有 Web 界面和知识库"
  echo "3) 返回主菜单"
  echo "=============================="
  echo -n "请输入选项编号（1-3）: "
}
show_restart_menu() {
  clear
  echo "=============================="
  echo "        服务重启菜单           "
  echo "=============================="
  echo "可重启的服务列表："
  echo "1) authhub"
  echo "2) oi-runtime"
  echo "3) oi-rag"
  echo "4) mysql"
  echo "5) redis"
  echo "6) postgresql"
  echo "7) 返回主菜单"
  echo "=============================="
  echo -n "请输入要重启的服务编号（1-7）: "
}

# 询问用户并保存安装模式
ask_install_options() {
  local force_mode="$1" # 接收可选参数（force或空值）
  echo "$force_mode"
  # 只有当参数不是force，且存在有效配置时才跳过询问
  if [ "$force_mode" != "force" ] && check_existing_install_mode "$INSTALL_MODE_FILE"; then
    return 0 # 非强制模式且配置有效，直接返回
  fi
  echo -e "\n${COLOR_INFO}[Info] 请选择附加组件安装选项:${COLOR_RESET}"

  # 询问是否安装web
  while true; do
    read -p "是否安装Web管理界面? (y/n，默认n): " web_choice
    web_choice=${web_choice:-n} # 默认值为y
    if [[ "$web_choice" =~ ^[YyNn]$ ]]; then
      break
    else
      echo -e "${COLOR_ERROR}[Error] 输入无效，请输入y或n${COLOR_RESET}"
    fi
  done

  # 询问是否安装rag
  while true; do
    read -p "是否安装RAG检索增强组件? (y/n，默认n): " rag_choice
    rag_choice=${rag_choice:-n} # 默认值为n
    if [[ "$rag_choice" =~ ^[YyNn]$ ]]; then
      break
    else
      echo -e "${COLOR_ERROR}[Error] 输入无效，请输入y或n${COLOR_RESET}"
    fi
  done

  # 转换为小写（统一格式）
  web_install=$(echo "$web_choice" | tr '[:upper:]' '[:lower:]')
  rag_install=$(echo "$rag_choice" | tr '[:upper:]' '[:lower:]')

  # 保存到文件（格式：key=value，便于后续读取）
  echo "web_install=$web_install" >"$INSTALL_MODE_FILE"
  echo "rag_install=$rag_install" >>"$INSTALL_MODE_FILE"

  echo -e "\n${COLOR_INFO}[Info] 安装模式已保存到: $INSTALL_MODE_FILE${COLOR_RESET}"
  return 0
}

# 轻量部署
light_deploy() {
  # 保存到文件（格式：key=value，便于后续读取）
  echo "web_install=n" >"$INSTALL_MODE_FILE"
  echo "rag_install=n" >>"$INSTALL_MODE_FILE"
  return 0
}

# 全量部署
wight_deploy() {
  # 保存到文件（格式：key=value，便于后续读取）
  echo "web_install=y" >"$INSTALL_MODE_FILE"
  echo "rag_install=y" >>"$INSTALL_MODE_FILE"
  return 0
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
    run_script_with_check "./2-install-dependency/install_openEulerIntelligence.sh" "安装 Witty Assistant"
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
    echo -e "\033[31m无效的选项，请输入1-5之间的数字\033[0m"
    return 1
    ;;
  esac
  return 0
}

# 执行子菜单选择部署模式对应脚本
run_sub_model_script() {
  case $1 in
  1)
    light_deploy
    "./0-one-click-deploy/one-click-deploy.sh"
    ;;
  2)
    wight_deploy
    "./0-one-click-deploy/one-click-deploy.sh"
    ;;
  3)
    echo "正在返回主菜单..."
    echo "按任意键继续..."
    read -r -n 1 -s
    return 2 # 特殊返回码表示返回上级菜单
    ;;
  *)
    echo -e "\033[31m无效的选项，请输入1-3之间的数字\033[0m"
    return 1
    ;;
  esac
  return 0
}

# 检查是否存在有效的安装模式配置文件
check_existing_install_mode() {
  local target_file="$1"

  # 检查文件是否存在
  if [ ! -f "$target_file" ]; then
    return 1 # 文件不存在，需要询问
  fi

  # 检查文件格式是否正确（包含必要的键）
  local web_val=$(grep "^web_install=" "$target_file" | cut -d'=' -f2)
  local rag_val=$(grep "^rag_install=" "$target_file" | cut -d'=' -f2)

  # 验证值是否合法（必须是y或n）
  if [[ -n "$web_val" && -n "$rag_val" &&
    "$web_val" =~ ^[yn]$ && "$rag_val" =~ ^[yn]$ ]]; then
    echo -e "${COLOR_INFO}[Info] 检测到有效的安装模式配置文件: $target_file${COLOR_RESET}"
    echo -e "${COLOR_INFO}[Info] 已配置: Web=${web_val^^}, RAG=${rag_val^^}${COLOR_RESET}"
    return 0 # 配置有效，无需询问
  else
    echo -e "${COLOR_WARNING}[Warning] 安装模式配置文件格式无效，将重新询问${COLOR_RESET}"
    return 1 # 配置无效，需要重新询问
  fi
}

# 手动部署子菜单循环
manual_deployment_loop() {
  while true; do
    #    show_sub_menu
    show_sub_model_menu
    read -r sub_choice
    run_sub_model_script "$sub_choice"
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
  echo -e "${GREEN}Witty Assistant 一键部署系统使用说明${COLOR_RESET}"
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
    light_deploy
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
      1) service="authhub" ;;
      2) service="oi-runtime" ;;
      3) service="oi-rag" ;;
      4) service="mysqld" ;;
      5) service="redis" ;;
      6) service="postgresql" ;;
      7) break ;;
      *)
        echo -e "${COLOR_ERROR}无效的选项，请输入1-8之间的数字${COLOR_RESET}"
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
