#!/bin/bash

# 配置参数
CONFIG_DIR="/etc/aops/conf.d"
CONFIG_FILE="${CONFIG_DIR}/authhub.yml"
mysql_temp="../resources/mysql_temp"

# 检查并创建目录
ensure_config_dir() {
  if [ ! -d "$CONFIG_DIR" ]; then
    echo -e"${COLOR_ERROR}[Error] 创建配置目录: $CONFIG_DIR${COLOR_RESET}"
    mkdir -p "$CONFIG_DIR" || {
      echo -e "${COLOR_ERROR}[Error] 目录创建失败${COLOR_RESET}"
      exit 1
    }
    chmod 755 "$CONFIG_DIR"
  fi
}
modify_authhub_yml() {
  local YAML_FILE="/etc/aops/conf.d/authhub.yml"

  # 检查参数是否为空
  if [ -z "$password" ]; then
    echo -e "${COLOR_ERROR}[Error] Error: Password argument is required.${COLOR_RESET}"
    return 1
  fi

  # 检查文件是否存在
  if [ ! -f "$YAML_FILE" ]; then
    echo -e "${COLOR_ERROR}[Error] Error: File $YAML_FILE does not exist.${COLOR_RESET}"
    return 1
  fi

  # 备份原始文件
  cp "$YAML_FILE" "$YAML_FILE.bak" || {
    echo -e "${COLOR_ERROR}[Error] Error: Failed to create backup.${COLOR_RESET}"
    return 1
  }

  # 使用sed命令修改username并添加password
  sed -i '/^mysql:/,/^[^ ]/ {
        s/username: root/username: authhub/
        /^    database: oauth2/a\    password: '"$password"'
    }' "$YAML_FILE" || {
    echo -e "${COLOR_ERROR}[Error] Error: Failed to modify YAML file.${COLOR_RESET}"
    return 1
  }

  return 0
}

# 验证配置
validate_config() {
  echo -e "${COLOR_INFO}[Info] 验证配置文件内容:${COLOR_RESET}"
  echo "========================================"
  grep -A5 "mysql:" "$CONFIG_FILE" | sed 's/^/  /'
  echo "========================================"

  if ! grep -q "username: authhub" "$CONFIG_FILE"; then
    echo -e "${COLOR_ERROR}[Error] 错误: MySQL用户名配置失败${COLOR_RESET}"
    return 1
  fi

  if ! grep -q "database: oauth2" "$CONFIG_FILE"; then
    echo -e "${COLOR_ERROR}[Error] 错误: 数据库名配置失败${COLOR_RESET}"
    return 1
  fi

  return 0
}

# 安装服务
install_service() {
  echo -e "${COLOR_INFO}[Info] authhub 服务启动...${COLOR_RESET}"
  systemctl enable --now authhub &&
    systemctl status authhub --no-pager
}

# 检查并确保authhub服务状态
ensure_authhub_status() {
  # 检查服务是否存在
  if ! systemctl list-unit-files | grep -q 'authhub.service'; then
    return 1
  fi

  # 检查服务是否正在运行
  local status=$(systemctl is-active authhub 2>/dev/null)
  if [ "$status" = "active" ]; then
    echo -e "${COLOR_INFO}[Info] authhub服务已在运行中，如需重新安装请先卸载${COLOR_RESET}"
    systemctl status authhub --no-pager
    return 0
  fi
}

# 主函数
main() {
  [ "$(id -u)" -ne 0 ] && {
    echo "请使用root权限执行"
    exit 1
  }
  declare password=$(head -n 1 "$mysql_temp" | tr -d '[:space:]')
  if ! ensure_authhub_status; then
    return 0
  fi
  ensure_config_dir || return 1
  modify_authhub_yml || return 1
  if validate_config; then
    install_service
    echo -e "${COLOR_SUCCESS}[Success] authhub 服务初始化完成${COLOR_RESET}"
  else
    echo -e "${COLOR_ERROR}[Error] authhub 服务初始化失败${COLOR_RESET}"
    exit 1
  fi
}

main "$@"
