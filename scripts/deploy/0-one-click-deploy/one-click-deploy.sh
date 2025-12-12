#!/bin/bash
# 颜色定义
RESET='\033[0m'
BOLD='\033[1m'
RED='\033[38;5;196m'
GREEN='\033[38;5;46m'
YELLOW='\033[38;5;226m'
BLUE='\033[38;5;45m'
MAGENTA='\033[38;5;201m'
CYAN='\033[38;5;51m'
WHITE='\033[38;5;255m'
BG_BLUE='\033[48;5;45m'
DIM='\033[2m'

# 打印步骤标题
print_step_title() {
  echo -e "\n${BG_BLUE}${WHITE}${BOLD} 步骤 $1  ${RESET} ${MAGENTA}${BOLD}$2${RESET}"
  echo -e "${DIM}${BLUE}$(printf '━%.0s' "$(seq 1 "$(tput cols)")")${RESET}"
}

# 主界面显示
show_header() {
  clear
  echo -e "\n${BOLD}${MAGENTA}$(printf '✧%.0s' "$(seq 1 "$(tput cols)")")${RESET}"
  echo -e "${BOLD}${WHITE}                  Witty Assistant 一键部署系统                  ${RESET}"
  echo -e "${BOLD}${MAGENTA}$(printf '✧%.0s' "$(seq 1 "$(tput cols)")")${RESET}"
}
# 结束标志
show_end() {
  clear
  echo -e "\n${BOLD}${MAGENTA}$(printf '✧%.0s' "$(seq 1 "$(tput cols)")")${RESET}"
  echo -e "${BOLD}${WHITE}                  Witty Assistant 部署完成                     ${RESET}"
  echo -e "${BOLD}${MAGENTA}$(printf '✧%.0s' "$(seq 1 "$(tput cols)")")${RESET}"
}
# 带颜色输出的进度条函数
colorful_progress() {
  local current=$1
  local total=$2
  local progress=$((current * 100 / total))
  local completed=$((PROGRESS_WIDTH * current / total))
  local remaining=$((PROGRESS_WIDTH - completed))

  printf "\r%s⟦%s" "${BOLD}${BLUE}" "${RESET}"
  printf "%s%${completed}s%s" "${BG_BLUE}${WHITE}" "" "${RESET}" | tr ' ' '▌'
  printf "%s%${remaining}s%s" "${DIM}${BLUE}" "" "${RESET}" | tr ' ' '·'
  printf "%s⟧%s %s%3d%%%s %s[%d/%d]%s" \
    "${BOLD}${BLUE}" "${RESET}" "${GREEN}" "$progress" "${RESET}" "${CYAN}" "$current" "$total" "${RESET}"
}
# 自定义日志处理器（仅显示 Success 并高亮）
filter_logs() {
  while IFS= read -r line; do
    # 所有日志写入文件（确保完整记录）
    echo "$line" >>"$log_file"

    # 根据日志级别进行过滤和高亮
    case "$line" in
    *"[Success]"*)
      echo -e "${GREEN}[SUCCESS] ${line//*\[Success\]/}${RESET}"
      ;;
    *"[Info]"*)
      echo -e "${BLUE}[INFO] ${line//*\[Info\]/}${RESET}"
      ;;
    *"[Warning]"*)
      echo -e "${YELLOW}[WARNING] ${line//*\[Warning\]/}${RESET}"
      ;;
    *"[Error]"*)
      echo -e "${RED}[ERROR] ${line//*\[Error\]/}${RESET}"
      ;;
    esac
  done
}
run_script_with_check() {
  local script_path=$1
  local script_name=$2
  local step_number=$3
  shift 4
  local extra_args=("$@") # 使用数组来存储额外参数
  # 前置检查：脚本是否存在
  if [ ! -f "$script_path" ]; then
    echo -e "\n${BOLD}${RED}✗ 致命错误: ${RESET}${YELLOW}${script_name}${RESET}${RED} 不存在 (路径: ${CYAN}${script_path}${RED})${RESET}" >&2
    return 1 # 使用 return 而不是 exit，以便调用者可以处理错误
  fi

  print_step_title "$step_number" "$script_name"

  # 获取绝对路径和执行目录
  local script_abs_path
  script_abs_path=$(realpath "$script_path")
  local script_dir
  script_dir=$(dirname "$script_abs_path")
  local script_base
  script_base=$(basename "$script_abs_path")

  echo -e "${DIM}${BLUE}🠖 脚本绝对路径：${YELLOW}${script_abs_path}${RESET}"
  echo -e "${DIM}${BLUE}🠖 执行工作目录：${YELLOW}${script_dir}${RESET}"
  echo -e "${DIM}${BLUE}🠖 额外参数：${YELLOW}${extra_args[*]}${RESET}"
  echo -e "${DIM}${BLUE}🠖 开始执行时间：${YELLOW}$(date +'%Y-%m-%d %H:%M:%S')${RESET}"

  local exit_code_file
  exit_code_file=$(mktemp)

  # 执行脚本并捕获退出码
  (
    cd "$script_dir" || exit 1
    bash "./$script_base" "${extra_args[@]}" 2>&1 | filter_logs
    echo "${PIPESTATUS[0]}" >"$exit_code_file" # 关键点：获取原命令的退出码
  )
  # 读取保存的退出码
  exit_code=$(cat "$exit_code_file")
  rm -f "$exit_code_file"

  # 处理执行结果
  if [ "$exit_code" -eq 0 ]; then
    echo -e "\n${BOLD}${GREEN}✓ ${script_name} 执行成功！${RESET}"
    echo -e "${DIM}${CYAN}详细日志请查看：${YELLOW}${log_file}${RESET}"
  else
    echo -e "\n${BOLD}${RED}✗ ${script_name} 执行失败！${RESET}" >&2
    echo -e "${DIM}${RED}$(printf '%.0s─' "$(seq 1 "$(tput cols)")")${RESET}" >&2
    echo -e "${BOLD}${RED}错误摘要：${RESET}" >&2
    # 只显示最后20行错误日志
    tail -n 20 "$log_file" | sed -e "s/^/${RED}  ✗ ${RESET}/" >&2
    echo -e "${DIM}${RED}$(printf '%.0s─' "$(seq 1 "$(tput cols)")")${RESET}" >&2
    echo -e "${BOLD}${YELLOW}完整错误日志请查看：${YELLOW}${log_file}${RESET}" >&2
    return 1
  fi

  return "$exit_code" # 返回实际的退出码
}
# 初始化部署流程
start_deployment() {
  local total_steps=3
  local current_step=1
  export GLOBAL_IS_AUTO="TRUE"

  # 使用索引数组维护执行顺序
  local step_order=(
    "../1-check-env/check_env.sh"
    "../2-install-dependency/install_openEulerIntelligence.sh"
    "../3-install-server/init_config.sh"
  )

  # 使用关联数组存储脚本名称
  declare -A step_names=(
    ["../1-check-env/check_env.sh"]="环境检查"
    ["../2-install-dependency/install_openEulerIntelligence.sh"]="安装后端服务"
    ["../3-install-server/init_config.sh"]="初始化配置"
  )
  MAIN_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
  cd "${MAIN_DIR}" || return 1
  # 创建带时间戳的日志文件
  declare log_dir=/var/log/openEulerIntelligence
  mkdir -p "$log_dir"
  declare timestamp
  timestamp=$(date +"%Y%m%d_%H%M%S")
  declare log_file="$log_dir/installLog-${timestamp}.log"
  echo -e "${DIM}${BLUE}🠖 部署日志文件：${YELLOW}${log_file}${RESET}"
  for script_path in "${step_order[@]}"; do
    local script_name="${step_names[$script_path]}"

    if ! run_script_with_check "$script_path" "$script_name" $current_step; then
      echo "Error: Script execution failed"
      return 1
    fi

    colorful_progress $current_step $total_steps
    ((current_step++))
  done
}
function main {
  # 记录开始时间（Unix 时间戳，单位秒）
  START_TIME=$(date +%s)
  show_header
  if start_deployment; then
    show_end
  fi
  # 记录结束时间
  END_TIME=$(date +%s)
  # 计算总耗时（秒）
  TOTAL_SECONDS=$((END_TIME - START_TIME))
  # 转换为时分秒格式
  HOURS=$((TOTAL_SECONDS / 3600))
  MINUTES=$(((TOTAL_SECONDS % 3600) / 60))
  SECONDS=$((TOTAL_SECONDS % 60))
  # 格式化输出（确保两位数显示）
  printf "\n执行总耗时: %02d:%02d:%02d\n" $HOURS $MINUTES $SECONDS
  return 0
}

main
