#!/bin/bash

# 颜色定义
COLOR_INFO='\033[34m'    # 蓝色信息
COLOR_SUCCESS='\033[32m' # 绿色成功
COLOR_ERROR='\033[31m'   # 红色错误
COLOR_RESET='\033[0m'    # 重置颜色

# 存储安装模式的文件路径
INSTALL_MODE_FILE="/etc/euler_Intelligence_install_mode"

# 询问用户并保存安装模式
ask_install_options() {
  # 存储安装模式的文件路径
  INSTALL_MODE_FILE="/etc/euler_Intelligence_install_mode"
  echo -e "\n${COLOR_INFO}[Info] 请选择附加组件安装选项:${COLOR_RESET}"

  # 询问是否安装web
  while true; do
    read -p "是否安装Web管理界面? (y/n，默认y): " web_choice
    web_choice=${web_choice:-y} # 默认值为y
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
# 读取安装模式的方法
read_install_mode() {
  # 检查文件是否存在
  if [ ! -f "$INSTALL_MODE_FILE" ]; then
    echo -e "${COLOR_ERROR}[Error] 安装模式文件不存在: $INSTALL_MODE_FILE${COLOR_RESET}"
    return 1
  fi

  # 从文件读取配置（格式：key=value）
  local web_install=$(grep "web_install=" "$INSTALL_MODE_FILE" | cut -d'=' -f2)
  local rag_install=$(grep "rag_install=" "$INSTALL_MODE_FILE" | cut -d'=' -f2)

  # 验证读取结果
  if [ -z "$web_install" ] || [ -z "$rag_install" ]; then
    echo -e "${COLOR_ERROR}[Error] 安装模式文件格式错误${COLOR_RESET}"
    return 1
  fi

  # 输出读取结果（也可根据需要返回变量）
  echo -e "${COLOR_INFO}[Info] 读取安装模式:"
  echo -e "  安装Web界面: ${web_install}"
  echo -e "  安装RAG组件: ${rag_install}${COLOR_RESET}"

  # 将结果存入全局变量（供其他函数使用）
  WEB_INSTALL=$web_install
  RAG_INSTALL=$rag_install
  return 0
}
# 示例：根据安装模式执行对应操作（可根据实际需求扩展）
install_components() {
  # 读取安装模式
  read_install_mode || return 1

  # 安装Web界面（如果用户选择）
  if [ "$WEB_INSTALL" = "y" ]; then
    echo -e "\n${COLOR_INFO}[Info] 开始安装Web管理界面...${COLOR_RESET}"
    # 此处添加Web安装命令，示例：
    # yum install -y web-component
  else
    echo -e "\n${COLOR_INFO}[Info] 跳过Web管理界面安装${COLOR_RESET}"
  fi

  # 安装RAG组件（如果用户选择）
  if [ "$RAG_INSTALL" = "y" ]; then
    echo -e "\n${COLOR_INFO}[Info] 开始安装RAG检索增强组件...${COLOR_RESET}"
    # 此处添加RAG安装命令，示例：
    # yum install -y rag-component
  else
    echo -e "\n${COLOR_INFO}[Info] 跳过RAG检索增强组件安装${COLOR_RESET}"
  fi
}

# 假设的初始化本地仓库函数（示例）
init_local_repo() {
  echo -e "${COLOR_INFO}[Info] 初始化本地仓库...${COLOR_RESET}"
  # 实际逻辑...
  return 0
}

# 假设的安装框架函数（示例）
install_framework() {
  echo -e "${COLOR_INFO}[Info] 安装核心框架...${COLOR_RESET}"
  # 实际逻辑...
  return 0
}

# 主执行函数
main() {
  echo -e "${COLOR_INFO}[Info] === 开始服务安装 ===${COLOR_RESET}"

  # 获取脚本所在的绝对路径
  declare SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
  # 切换到脚本所在目录
  cd "$SCRIPT_DIR" || return 1
  echo -e "${COLOR_INFO}[Info] 脚本执行目录: $SCRIPT_DIR${COLOR_RESET}"

  # 停止dnf缓存定时器
  systemctl stop dnf-makecache.timer || echo -e "${COLOR_WARNING}[Warning] 停止dnf-makecache.timer失败，继续执行...${COLOR_RESET}"

  # 执行安装验证
  init_local_repo || return 1

  # 询问用户安装选项并保存
  ask_install_options || return 1

  # 安装核心框架
  install_framework || return 1

  # 根据用户选择安装附加组件
  install_components || return 1

  echo -e "\n${COLOR_SUCCESS}[Success] 安装 Witty Assistant 完成！${COLOR_RESET}"
  return 0
}

# 执行主函数
main "$@"
