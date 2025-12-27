#!/bin/bash
# 颜色定义
COLOR_INFO='\033[34m'    # 蓝色信息
COLOR_SUCCESS='\033[32m' # 绿色成功
COLOR_ERROR='\033[31m'   # 红色错误
COLOR_WARNING='\033[33m' # 黄色警告
COLOR_RESET='\033[0m'    # 重置颜色

## 配置参数
# 生成随机密码函数
generate_random_password() {
  local length=${1:-24} # 默认 24 位
  local password
  password=$(tr -dc 'A-Za-z0-9' </dev/urandom | head -c "$length")
  echo "$password"
}

config_toml_file=""
PGSQL_PASSWORD=""

update_password() {
  echo -e "${COLOR_INFO}[Info] 更新配置文件中的密码...${COLOR_RESET}"

  if [[ ! -f "$config_toml_file" ]]; then
    echo -e "${COLOR_ERROR}[Error] 配置文件不存在: $config_toml_file${COLOR_RESET}"
    return 1
  fi

  # 支持单引号和双引号两种格式
  sed -i "/\[postgres\]/,/^\[/ s/password = ['\"][^'\"]*['\"]/password = '$PGSQL_PASSWORD'/" "$config_toml_file" || {
    echo -e "${COLOR_ERROR}[Error] 更新 postgres password 失败${COLOR_RESET}"
    return 1
  }

  local key1 key2 key3 key4
  key1=$(generate_random_password 20)
  key2=$(generate_random_password 20)
  key3=$(generate_random_password 20)
  key4=$(generate_random_password 20)

  sed -i "s/half_key1 = ['\"][^'\"]*['\"]/half_key1 = '$key1'/" "$config_toml_file" || {
    echo -e "${COLOR_ERROR}[Error] 更新 half_key1 失败${COLOR_RESET}"
    return 1
  }
  sed -i "s/half_key2 = ['\"][^'\"]*['\"]/half_key2 = '$key2'/" "$config_toml_file" || {
    echo -e "${COLOR_ERROR}[Error] 更新 half_key2 失败${COLOR_RESET}"
    return 1
  }
  sed -i "s/half_key3 = ['\"][^'\"]*['\"]/half_key3 = '$key3'/" "$config_toml_file" || {
    echo -e "${COLOR_ERROR}[Error] 更新 half_key3 失败${COLOR_RESET}"
    return 1
  }
  sed -i "s/jwt_key = ['\"][^'\"]*['\"]/jwt_key = '$key4'/" "$config_toml_file" || {
    echo -e "${COLOR_ERROR}[Error] 更新 jwt_key 失败${COLOR_RESET}"
    return 1
  }

  echo -e "${COLOR_SUCCESS}[Success] 配置文件密码更新完成${COLOR_RESET}"
  return 0
}

# 启用并启动服务
enable_services() {
  echo -e "${COLOR_INFO}[Info] 启动postgresql服务...${COLOR_RESET}"
  local services=("postgresql")

  for service in "${services[@]}"; do
    echo -e "${COLOR_INFO}[Info] 正在处理 $service 服务...${COLOR_RESET}"

    # 检查服务是否存在
    if ! systemctl list-unit-files | grep -q "^$service.service"; then
      echo -e "${COLOR_ERROR}[Error] 服务 $service 不存在${COLOR_RESET}"
      continue
    fi

    # 2. 检查服务是否已运行
    if systemctl is-active "$service" >/dev/null 2>&1; then
      echo -e "${COLOR_SUCCESS}[Success] 服务已在运行中${COLOR_RESET}"
      continue
    fi

    # 3. 启动服务
    echo -e "${COLOR_INFO} 正在启动 $service ...${COLOR_RESET}"
    if systemctl enable --now "$service" >/dev/null 2>&1; then
      echo -e "${COLOR_SUCCESS}[Success] $service 服务 启动成功${COLOR_RESET}"

      # 可选：验证服务是否真正启动
      sleep 1
      if ! systemctl is-active "$service" >/dev/null 2>&1; then
        echo -e "${COLOR_ERROR}[Error] 服务启动后未保持运行状态${COLOR_RESET}"
      fi
    else
      echo -e "${COLOR_ERROR}[Error] 启动失败${COLOR_RESET}"
      echo -e "${COLOR_INFO}[Info] 请手动检查：systemctl status $service${COLOR_RESET}"
    fi
  done
}

# PostgreSQL 配置函数
configure_postgresql() {
  echo -e "${COLOR_INFO}[Info] 开始配置 PostgreSQL...${COLOR_RESET}"
  local pg_service="postgresql"
  local pg_data_dir="/var/lib/pgsql/data"
  local db_already_initialized=false

  # 1. 检查数据库是否已初始化
  if [ -d "$pg_data_dir" ] && [ -f "$pg_data_dir/PG_VERSION" ]; then
    echo -e "${COLOR_INFO}[Info] 检测到已存在的 PostgreSQL 数据目录${COLOR_RESET}"
    db_already_initialized=true
  fi

  # 2. 检查并处理 PostgreSQL 服务状态
  echo -e "${COLOR_INFO}[Info] 检查 PostgreSQL 服务状态...${COLOR_RESET}"
  if systemctl is-active --quiet "$pg_service"; then
    if [ "$db_already_initialized" = true ]; then
      echo -e "${COLOR_INFO}[Info] PostgreSQL 服务正在运行，将复用现有数据库${COLOR_RESET}"
    else
      echo -e "${COLOR_WARNING}[Warning] PostgreSQL 服务正在运行，正在停止服务...${COLOR_RESET}"
      systemctl stop "$pg_service" || {
        echo -e "${COLOR_ERROR}[Error] 无法停止 PostgreSQL 服务${COLOR_RESET}"
        return 1
      }
    fi
  fi

  # 3. 初始化数据库（仅在未初始化时执行）
  if [ "$db_already_initialized" = false ]; then
    echo -e "${COLOR_INFO}[Info] 初始化 PostgreSQL 数据库...${COLOR_RESET}"
    /usr/bin/postgresql-setup --initdb || {
      echo -e "${COLOR_ERROR}[Error] 数据库初始化失败"
      echo -e "请检查日志文件: /var/lib/pgsql/initdb_postgresql.log${COLOR_RESET}"
      return 1
    }
  else
    echo -e "${COLOR_INFO}[Info] 跳过数据库初始化（已存在）${COLOR_RESET}"
  fi

  # 4. 启动服务
  echo -e "${COLOR_INFO}[Info] 启动 PostgreSQL 服务...${COLOR_RESET}"
  systemctl enable --now postgresql || {
    echo -e "${COLOR_ERROR}[Error] 服务启动失败${COLOR_RESET}"
    return 1
  }

  # 5. 确保 postgres 用户可以本地连接（使用 peer 认证）
  local pg_hba_conf="/var/lib/pgsql/data/pg_hba.conf"
  if [ ! -f "$pg_hba_conf" ]; then
    pg_hba_conf="/var/lib/postgresql/data/pg_hba.conf"
  fi

  if [ -f "$pg_hba_conf" ]; then
    # 临时确保本地连接使用 peer 认证（重新部署时可能已被改为 md5）
    if grep -qE "^local\s+all\s+all\s+md5" "$pg_hba_conf"; then
      echo -e "${COLOR_INFO}[Info] 临时恢复本地 peer 认证以配置数据库...${COLOR_RESET}"
      sed -i -E 's/^(local\s+all\s+all\s+)md5/\1peer/' "$pg_hba_conf"
      systemctl reload postgresql
      sleep 2
    fi
  fi

  # 6. 创建或更新 euler_copilot 用户和数据库
  echo -e "${COLOR_INFO}[Info] 配置 euler_copilot 用户和数据库...${COLOR_RESET}"

  # 定义 psql 执行函数
  # 脚本以 root 运行，使用 su 切换到 postgres 用户
  run_psql() {
    su - postgres -c "psql $*"
  }

  # 检查用户是否存在
  if run_psql "-tAc \"SELECT 1 FROM pg_roles WHERE rolname='euler_copilot'\"" | grep -q 1; then
    echo -e "${COLOR_INFO}[Info] 用户已存在，更新密码...${COLOR_RESET}"
    run_psql "-c \"ALTER USER euler_copilot WITH PASSWORD '$PGSQL_PASSWORD';\"" || {
      echo -e "${COLOR_ERROR}[Error] 更新用户密码失败${COLOR_RESET}"
      return 1
    }
  else
    echo -e "${COLOR_INFO}[Info] 创建用户...${COLOR_RESET}"
    run_psql "-c \"CREATE USER euler_copilot WITH PASSWORD '$PGSQL_PASSWORD';\"" || {
      echo -e "${COLOR_ERROR}[Error] 创建用户失败${COLOR_RESET}"
      return 1
    }
  fi

  # 检查数据库是否存在
  if run_psql "-tAc \"SELECT 1 FROM pg_database WHERE datname='euler_copilot'\"" | grep -q 1; then
    echo -e "${COLOR_INFO}[Info] 数据库已存在，跳过创建${COLOR_RESET}"
  else
    echo -e "${COLOR_INFO}[Info] 创建数据库...${COLOR_RESET}"
    run_psql "-c \"CREATE DATABASE euler_copilot OWNER euler_copilot;\"" || {
      echo -e "${COLOR_ERROR}[Error] 创建数据库失败${COLOR_RESET}"
      return 1
    }
  fi

  run_psql "-c \"GRANT ALL PRIVILEGES ON DATABASE euler_copilot TO euler_copilot;\"" || {
    echo -e "${COLOR_ERROR}[Error] 授权失败${COLOR_RESET}"
    return 1
  }

  # 7. 在 euler_copilot 数据库中启用扩展
  echo -e "${COLOR_INFO}[Info] 启用 PostgreSQL 扩展...${COLOR_RESET}"
  run_psql "-d euler_copilot -c \"CREATE EXTENSION IF NOT EXISTS zhparser;\"" || {
    echo -e "${COLOR_ERROR}[Error] 无法启用 zhparser 扩展${COLOR_RESET}"
    return 1
  }

  run_psql "-d euler_copilot -c \"CREATE EXTENSION IF NOT EXISTS vector;\"" || {
    echo -e "${COLOR_ERROR}[Error] 无法启用 vector 扩展${COLOR_RESET}"
    return 1
  }

  # CREATE TEXT SEARCH CONFIGURATION 不支持 IF NOT EXISTS，需要先检查再创建
  run_psql "-d euler_copilot" <<'EOSQL' || {
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_ts_config WHERE cfgname = 'zhparser') THEN
        CREATE TEXT SEARCH CONFIGURATION zhparser (PARSER = zhparser);
        ALTER TEXT SEARCH CONFIGURATION zhparser ADD MAPPING FOR n,v,a,i,e,l WITH simple;
    END IF;
END
$$;
EOSQL
    echo -e "${COLOR_ERROR}[Error] 无法创建全文搜索配置${COLOR_RESET}"
    return 1
  }

  # 8. 配置认证方式（将 peer/ident 改为 md5）
  echo -e "${COLOR_INFO}[Info] 配置认证方式...${COLOR_RESET}"

  # pg_hba_conf 已在步骤 5 中设置
  if [ -z "$pg_hba_conf" ] || [ ! -f "$pg_hba_conf" ]; then
    # 重新查找
    if [ -f "/var/lib/pgsql/data/pg_hba.conf" ]; then
      pg_hba_conf="/var/lib/pgsql/data/pg_hba.conf"
    elif [ -f "/var/lib/postgresql/data/pg_hba.conf" ]; then
      pg_hba_conf="/var/lib/postgresql/data/pg_hba.conf"
    fi
  fi

  if [ -z "$pg_hba_conf" ] || [ ! -f "$pg_hba_conf" ]; then
    echo -e "${COLOR_ERROR}[Error] 找不到 pg_hba.conf 文件${COLOR_RESET}"
    return 1
  fi

  # 备份原始文件
  cp "$pg_hba_conf" "${pg_hba_conf}.bak"

  # 修改认证方式
  sed -i -E 's/(local\s+all\s+all\s+)peer/\1md5/' "$pg_hba_conf"
  sed -i -E 's/(host\s+all\s+all\s+127\.0\.0\.1\/32\s+)ident/\1md5/' "$pg_hba_conf"
  sed -i -E 's/(host\s+all\s+all\s+::1\/128\s+)ident/\1md5/' "$pg_hba_conf"

  # 9. 重启服务
  echo -e "${COLOR_INFO}[Info] 重启 PostgreSQL 服务...${COLOR_RESET}"
  systemctl daemon-reload
  systemctl restart postgresql || {
    echo -e "${COLOR_ERROR}[Error] 服务重启失败${COLOR_RESET}"
    return 1
  }
  echo -e "${COLOR_SUCCESS}[Success] PostgreSQL 配置完成${COLOR_RESET}"
  return 0
}

install_framework() {
  # 1. 安装前检查
  echo -e "${COLOR_INFO}[Info] 开始初始化配置 sysagent...${COLOR_RESET}"

  # 2. 检查并创建必要目录
  echo -e "${COLOR_INFO}[Info] 创建数据目录...${COLOR_RESET}"
  mkdir -p /var/lib/sysagent || {
    echo -e "${COLOR_ERROR}[Error] 无法创建数据目录 /var/lib/sysagent${COLOR_RESET}"
    return 1
  }

  # 3. 获取本机IP
  local ip_address
  config_toml_path="../resources/config.toml"
  # 提取 domain 的值，支持多种 TOML 字符串格式（双引号、单引号、无引号）
  if [ ! -f "$config_toml_path" ]; then
    echo -e "${COLOR_ERROR}[Error] 配置文件不存在: $config_toml_path${COLOR_RESET}"
    return 1
  fi
  # 使用 grep 和 sed 提取 domain 值，支持多种引号格式
  local domain_line
  domain_line=$(grep -E "^[[:space:]]*domain[[:space:]]*=[[:space:]]*" "$config_toml_path")
  if [ -z "$domain_line" ]; then
    echo -e "${COLOR_ERROR}[Error] 配置文件中未找到 domain 配置项${COLOR_RESET}"
    return 1
  fi
  ip_address=$(echo "$domain_line" | sed 's/.*=[[:space:]]*//' | sed 's/^["'"'"']//' | sed 's/["'"'"']$//')
  if [ -z "$ip_address" ]; then
    echo -e "${COLOR_ERROR}[Error] 无法从配置文件中提取有效的 domain 值，部署失败${COLOR_RESET}"
    return 1
  fi
  echo -e "${COLOR_INFO} [Info] 提取的 IP 地址: '$ip_address'${COLOR_RESET}"

  # 4. 获取客户端信息
  # 针对代理服务器做特殊处理
  unset http_proxy https_proxy

  # 5. 配置文件处理
  local framework_file="../resources/config.toml"
  local framework_target="/etc/sysagent/config.toml"

  # 检查源文件是否存在
  if [[ ! -f "$framework_file" ]]; then
    echo -e "${COLOR_ERROR}[Error] 找不到配置文件: $framework_file${COLOR_RESET}"
    return 1
  fi

  # 备份原文件
  echo -e "${COLOR_INFO}[Info] 备份配置文件...${COLOR_RESET}"
  cp -v "$framework_file" "${framework_file}.bak" || {
    echo -e "${COLOR_ERROR}[Error] 无法备份配置文件${COLOR_RESET}"
    return 1
  }
  echo -e "${COLOR_INFO}[Info] 更新配置文件参数...${COLOR_RESET}"
  port=8002
  sed -i "s/domain = '.*'/domain = '$ip_address'/" "$framework_file"

  # 部署配置文件
  echo -e "${COLOR_INFO}[Info] 部署配置文件...${COLOR_RESET}"
  mkdir -p "$(dirname "$framework_target")"
  if ! cp -v "$framework_file" "$framework_target"; then
    echo -e "${COLOR_ERROR}[Error] 无法复制配置文件到 $framework_target${COLOR_RESET}"
    return 1
  fi

  # 7. 设置文件权限
  echo -e "${COLOR_INFO}[Info] 设置文件权限...${COLOR_RESET}"
  chmod 640 "$framework_target" || {
    echo -e "${COLOR_WARNING}[Warning] 无法设置配置文件权限${COLOR_RESET}"
  }

  # 8. 启动服务
  echo -e "${COLOR_INFO}[Info] 启动 sysagent 服务...${COLOR_RESET}"
  systemctl daemon-reload || {
    echo -e "${COLOR_ERROR}[Error] systemd 配置重载失败${COLOR_RESET}"
    return 1
  }

  if ! systemctl enable --now sysagent; then
    echo -e "${COLOR_ERROR}[Error] 无法启动 sysagent 服务${COLOR_RESET}"
    systemctl status sysagent --no-pager
    return 1
  fi

  # 9. 验证服务状态
  echo -e "${COLOR_INFO}[Info] 检查服务状态...${COLOR_RESET}"
  if ! systemctl is-active --quiet sysagent; then
    echo -e "${COLOR_ERROR}[Error] sysagent 服务未运行${COLOR_RESET}"
    journalctl -u sysagent --no-pager -n 20
    return 1
  fi

  # 10. 清理备份文件
  rm -f "${framework_file}.bak"

  echo -e "${COLOR_SUCCESS}[Success] sysagent 安装完成${COLOR_RESET}"
  echo -e "${COLOR_INFO}[Info] 服务访问地址: http://${ip_address}:$port${COLOR_RESET}"
  return 0
}

main() {
  SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
  cd "$SCRIPT_DIR" || return 1

  config_toml_file="$SCRIPT_DIR/../resources/config.toml"
  PGSQL_PASSWORD=$(generate_random_password)

  update_password || return 1

  configure_postgresql || return 1
  install_framework || return 1
}

main "$@"
