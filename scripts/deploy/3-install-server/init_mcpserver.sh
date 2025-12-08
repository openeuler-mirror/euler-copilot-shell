#!/bin/bash
# 颜色定义
COLOR_INFO='\033[34m'    # 蓝色信息
COLOR_SUCCESS='\033[32m' # 绿色成功
COLOR_ERROR='\033[31m'   # 红色错误
COLOR_RESET='\033[0m'    # 重置颜色

init_mcp_config() {
  local mcp_config_path="../5-resource/mcp_config"
  local target_path="/var/lib/sysagent/semantics/mcp/template"

  echo -e "${COLOR_INFO}[Info] 开始初始化MCP配置文件...${COLOR_RESET}"

  # 检查源目录是否存在
  if [ ! -d "$mcp_config_path" ]; then
    echo -e "${COLOR_ERROR}[Error] 源目录不存在: $mcp_config_path${COLOR_RESET}"
    return 1
  fi

  # 创建目标目录（如果不存在）
  if [ ! -d "$target_path" ]; then
    echo -e "${COLOR_INFO}[Info] 目标目录不存在，创建: $target_path${COLOR_RESET}"
    mkdir -p "$target_path" || {
      echo -e "${COLOR_ERROR}[Error] 无法创建目标目录: $target_path${COLOR_RESET}"
      return 1
    }
  fi

  # 递归复制所有文件和子目录（保留权限和属性）
  echo -e "${COLOR_INFO}[Info] 正在复制配置文件到目标目录...${COLOR_RESET}"
  cp -R -p "$mcp_config_path"/* "$target_path/" || {
    echo -e "${COLOR_ERROR}[Error] 配置文件复制失败${COLOR_RESET}"
    return 1
  }

  echo -e "${COLOR_SUCCESS}[Success] MCP配置文件初始化完成${COLOR_RESET}"
  return 0
}
start_bak() {
  # 获取脚本所在的绝对路径
  SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
  if [ -z "$SCRIPT_DIR" ]; then
    echo -e "${COLOR_ERROR}[Error] 无法获取脚本所在目录路径${COLOR_RESET}"
    return 1
  fi

  # 切换到脚本所在目录
  echo -e "${COLOR_INFO}[Info] 切换到脚本目录: $SCRIPT_DIR${COLOR_RESET}"
  cd "$SCRIPT_DIR" || {
    echo -e "${COLOR_ERROR}[Error] 无法切换到脚本目录: $SCRIPT_DIR${COLOR_RESET}"
    return 1
  }

  # 执行MCP配置初始化
  echo -e "${COLOR_INFO}[Info] 开始执行 MCP 配置初始化...${COLOR_RESET}"
  init_mcp_config
  local init_result=$?
  if [ $init_result -ne 0 ]; then
    echo -e "${COLOR_ERROR}[Error] MCP 配置初始化失败，终止执行${COLOR_RESET}"
    return $init_result
  fi

  # 重启 sysagent 服务
  echo -e "${COLOR_INFO}[Info] 开始重启 sysagent 服务...${COLOR_RESET}"
  if ! systemctl restart sysagent; then
    echo -e "${COLOR_ERROR}[Error] sysagent 服务重启失败${COLOR_RESET}"
    return 1
  fi

  # 检查服务状态
  echo -e "${COLOR_INFO}[Info] 验证 sysagent 服务状态...${COLOR_RESET}"
  sleep 5
  if systemctl is-active --quiet sysagent; then
    echo -e "${COLOR_SUCCESS}[Success] sysagent 服务重启成功并正常运行${COLOR_RESET}"
    return 0
  else
    echo -e "${COLOR_ERROR}[Error] sysagent 服务重启后未正常运行${COLOR_RESET}"
    return 1
  fi
}
# 日志输出函数
info() {
  echo -e "${COLOR_INFO}[Info] $1${COLOR_RESET}"
}

warn() {
  echo -e "${COLOR_WARN}[Warn] $1${COLOR_RESET}"
}

error() {
  echo -e "${COLOR_ERROR}[Error] $1${COLOR_RESET}" >&2 # 错误信息输出到 stderr
}
main() {
  # 获取脚本所在的绝对路径
  SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
  if [ -z "$SCRIPT_DIR" ]; then
    error "无法获取脚本所在目录路径"
    return 1
  fi
  info "脚本所在目录: ${COLOR_BOLD}$SCRIPT_DIR${COLOR_RESET}"

  # 切换到脚本所在目录
  info "切换到脚本目录"
  cd "$SCRIPT_DIR" || {
    error "无法切换到脚本目录: $SCRIPT_DIR"
    return 1
  }

  # 定义配置文件目录和脚本路径
  local mcp_config_root="../5-resource/mcp_config"
  local agent_manager_script="../4-other-script/agent_manager.py"

  # 检查配置文件根目录是否存在
  if [ ! -d "$mcp_config_root" ]; then
    error "配置文件根目录不存在: $mcp_config_root"
    return 1
  fi

  # 检查管理脚本是否存在
  if [ ! -f "$agent_manager_script" ]; then
    error "agent_manager.py 脚本不存在: $agent_manager_script"
    return 1
  fi
  # 遍历所有子目录下的 config.json 文件
  info "开始查找配置文件: $mcp_config_root/**/config.json"
  local config_files
  config_files=$(find "$mcp_config_root" -type f -name "config.json")

  # 检查是否找到配置文件
  if [ -z "$config_files" ]; then
    warn "未在 $mcp_config_root 下找到任何 config.json 文件"
    return 0
  fi

  # 统计配置文件数量
  local file_count
  file_count=$(echo "$config_files" | wc -l | tr -d ' ')
  info "共找到 ${COLOR_BOLD}$file_count${COLOR_RESET} 个配置文件，开始处理..."

  # 遍历配置文件并执行初始化和创建操作
  local index=1
  while IFS= read -r config_file; do
    # 转换为绝对路径
    local abs_config
    abs_config=$(realpath "$config_file")
    info "\n===== 处理第 $index/$file_count 个配置文件 ====="
    info "配置文件路径: $abs_config"
    # 执行 init 操作
    info "执行初始化: python3 $agent_manager_script init $abs_config"
    if python3 "$agent_manager_script" init "$abs_config"; then
      info "初始化成功: $abs_config"
    else
      warn "继续处理下一个配置文件"
    fi

    # 执行 create 操作
    info "执行创建: python3 $agent_manager_script create $abs_config"
    if python3 "$agent_manager_script" create "$abs_config"; then
      info "创建成功: $abs_config"
    else
      warn "继续处理下一个配置文件"
    fi

    index=$((index + 1))
  done <<<"$config_files"

  info "\n===== 所有配置文件处理完成 ====="
  return 0
}

# 执行主函数
main "$@"
