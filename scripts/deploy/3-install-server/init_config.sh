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

# 配置参数（自动生成随机密码）
MINIO_ROOT_PASSWORD=$(generate_random_password)
PGSQL_PASSWORD=$(generate_random_password)

config_toml_file="../5-resource/config.toml"

# 配置MinIO（RPM安装后的配置）
install_minio() {
  echo -e "${COLOR_INFO}[Info] 开始配置MinIO...${COLOR_RESET}"

  # 1. 配置MinIO环境变量
  echo -e "${COLOR_INFO}[Info] 配置MinIO环境变量...${COLOR_RESET}"
  cat >/etc/default/minio <<EOF
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=$MINIO_ROOT_PASSWORD
MINIO_VOLUMES=/var/lib/minio
EOF

  # 2. 创建用户和数据目录（RPM可能已创建，这里确保存在）
  echo -e "${COLOR_INFO}[Info] 创建MinIO用户和数据目录...${COLOR_RESET}"
  if ! id minio-user &>/dev/null; then
    groupadd minio-user
    useradd -g minio-user --shell=/sbin/nologin -r minio-user || {
      echo -e "${COLOR_ERROR}[Error] 创建minio-user失败${COLOR_RESET}"
      return 1
    }
  fi

  mkdir -p /var/lib/minio
  chown -R minio-user:minio-user /var/lib/minio || {
    echo -e "${COLOR_ERROR}[Error] 无法设置/var/lib/minio权限${COLOR_RESET}"
    return 1
  }

  # 3. 启动MinIO服务
  echo -e "${COLOR_INFO}[Info] 启动MinIO服务...${COLOR_RESET}"
  systemctl daemon-reload
  systemctl enable --now minio || {
    echo -e "${COLOR_ERROR}[Error] MinIO服务启动失败${COLOR_RESET}"
    return 1
  }

  # 4. 检查服务状态
  echo -e "${COLOR_INFO}[Info] 验证MinIO服务状态...${COLOR_RESET}"
  if systemctl is-active --quiet minio; then
    echo -e "${COLOR_SUCCESS}[Success] MinIO配置完成${COLOR_RESET}"
    return 0
  else
    echo -e "${COLOR_ERROR}[Error] MinIO服务未正常运行，请查看日志: journalctl -u minio -f${COLOR_RESET}"
    return 1
  fi
}

# 更新配置文件中的密码
update_password() {
  # 更新 config.toml 中的 minio 和 postgres 密码
  sed -i "s/secret_key = '.*'/secret_key = '$MINIO_ROOT_PASSWORD'/" $config_toml_file
  sed -i "/\[postgres\]/,/^\[/ s/password = '.*'/password = '$PGSQL_PASSWORD'/" $config_toml_file
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
  # 1. 检查并处理 PostgreSQL 服务状态
  echo -e "${COLOR_INFO}[Info] 检查 PostgreSQL 服务状态...${COLOR_RESET}"
  if systemctl is-active --quiet "$pg_service"; then
    echo -e "${COLOR_WARNING}[Warning] PostgreSQL 服务正在运行，正在停止服务...${COLOR_RESET}"
    systemctl stop "$pg_service" || {
      echo -e "${COLOR_ERROR}[Error] 无法停止 PostgreSQL 服务${COLOR_RESET}"
      return 1
    }
  fi

  # 2. 初始化数据库
  echo -e "${COLOR_INFO}[Info] 初始化 PostgreSQL 数据库...${COLOR_RESET}"
  /usr/bin/postgresql-setup --initdb || {
    echo -e "${COLOR_ERROR}[Error] 数据库初始化失败"
    echo -e "请检查日志文件: /var/lib/pgsql/initdb_postgresql.log${COLOR_RESET}"
    return 1
  }

  # 3. 启动服务
  echo -e "${COLOR_INFO}[Info] 启动 PostgreSQL 服务...${COLOR_RESET}"
  systemctl enable --now postgresql || {
    echo -e "${COLOR_ERROR}[Error] 服务启动失败${COLOR_RESET}"
    return 1
  }

  # 4. 创建 euler_copilot 用户和数据库
  echo -e "${COLOR_INFO}[Info] 创建 euler_copilot 用户和数据库...${COLOR_RESET}"
  sudo -u postgres psql -c "CREATE USER euler_copilot WITH PASSWORD '$PGSQL_PASSWORD';" || {
    echo -e "${COLOR_ERROR}[Error] 创建用户失败${COLOR_RESET}"
    return 1
  }
  sudo -u postgres psql -c "CREATE DATABASE euler_copilot OWNER euler_copilot;" || {
    echo -e "${COLOR_ERROR}[Error] 创建数据库失败${COLOR_RESET}"
    return 1
  }
  sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE euler_copilot TO euler_copilot;" || {
    echo -e "${COLOR_ERROR}[Error] 授权失败${COLOR_RESET}"
    return 1
  }

  # 5. 启用扩展（在 euler_copilot 数据库中）
  echo -e "${COLOR_INFO}[Info] 启用 PostgreSQL 扩展...${COLOR_RESET}"
  sudo -u postgres psql -d euler_copilot -c "CREATE EXTENSION IF NOT EXISTS zhparser;" || {
    echo -e "${COLOR_ERROR}[Error] 无法启用 zhparser 扩展${COLOR_RESET}"
    return 1
  }

  sudo -u postgres psql -d euler_copilot -c "CREATE EXTENSION IF NOT EXISTS vector;" || {
    echo -e "${COLOR_ERROR}[Error] 无法启用 vector 扩展${COLOR_RESET}"
    return 1
  }

  sudo -u postgres psql -d euler_copilot -c "CREATE TEXT SEARCH CONFIGURATION IF NOT EXISTS zhparser (PARSER = zhparser);" || {
    echo -e "${COLOR_ERROR}[Error] 无法创建全文搜索配置${COLOR_RESET}"
    return 1
  }

  sudo -u postgres psql -d euler_copilot -c "ALTER TEXT SEARCH CONFIGURATION zhparser ADD MAPPING FOR n,v,a,i,e,l WITH simple;" || {
    echo -e "${COLOR_ERROR}[Error] 无法添加映射${COLOR_RESET}"
    return 1
  }

  # 6. 查找并修改pg_hba.conf
  echo -e "${COLOR_INFO}[Info] 配置认证方式...${COLOR_RESET}"
  local pg_hba_conf
  pg_hba_conf=$(find / -name pg_hba.conf 2>/dev/null | head -n 1)

  if [ -z "$pg_hba_conf" ]; then
    echo -e "${COLOR_ERROR}[Error] 找不到 pg_hba.conf 文件${COLOR_RESET}"
    return 1
  fi

  # 备份原始文件
  cp "$pg_hba_conf" "${pg_hba_conf}.bak"

  # 修改认证方式
  sed -i -E 's/(local\s+all\s+all\s+)peer/\1md5/' "$pg_hba_conf"
  sed -i -E 's/(host\s+all\s+all\s+127\.0\.0\.1\/32\s+)ident/\1md5/' "$pg_hba_conf"
  sed -i -E 's/(host\s+all\s+all\s+::1\/128\s+)ident/\1md5/' "$pg_hba_conf"
  # 7. 重启服务
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
  echo -e "${COLOR_INFO}[Info] 开始初始化配置 euler-copilot-framework...${COLOR_RESET}"

  # 2. 检查并创建必要目录
  echo -e "${COLOR_INFO}[Info] 创建数据目录...${COLOR_RESET}"
  mkdir -p /var/lib/euler_copilot || {
    echo -e "${COLOR_ERROR}[Error] 无法创建数据目录 /var/lib/euler_copilot${COLOR_RESET}"
    return 1
  }

  # 3. 获取本机IP
  local ip_address
  config_toml_path="../5-resource/config.toml"
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
  local framework_file="../5-resource/config.toml"
  local framework_target="/etc/euler-copilot-framework/config.toml"
  local framework_service_file="../5-resource/oi-runtime.service"
  local framework_service_target="/etc/systemd/system/oi-runtime.service"

  # 检查源文件是否存在
  for file in "$framework_file" "$framework_service_file"; do
    if [[ ! -f "$file" ]]; then
      echo -e "${COLOR_ERROR}[Error] 找不到配置文件: $file${COLOR_RESET}"
      return 1
    fi
  done

  # 备份原文件
  echo -e "${COLOR_INFO}[Info] 备份配置文件...${COLOR_RESET}"
  cp -v "$framework_file" "${framework_file}.bak" || {
    echo -e "${COLOR_ERROR}[Error] 无法备份配置文件${COLOR_RESET}"
    return 1
  }
  echo -e "${COLOR_INFO}[Info] 更新配置文件参数...${COLOR_RESET}"
  port=8002
  sed -i "/\[login\.settings\]/,/^\[/ s|host = '.*'|host = 'http://${ip_address}:8000'|" "$framework_file"
  sed -i "s|login_api = '.*'|login_api = 'http://${ip_address}:8080/api/auth/login'|" $framework_file
  sed -i "s/domain = '.*'/domain = '$ip_address'/" $framework_file

  #更新 security key
  key1=$(generate_random_password 20)
  key2=$(generate_random_password 20)
  key3=$(generate_random_password 20)
  key4=$(generate_random_password 20)
  sed -i "s/half_key1 = '.*'/half_key1 = '$key1'/" $framework_file
  sed -i "s/half_key2 = '.*'/half_key2 = '$key2'/" $framework_file
  sed -i "s/half_key3 = '.*'/half_key3 = '$key3'/" $framework_file
  sed -i "s/jwt_key = '.*'/jwt_key = '$key4'/" $framework_file
  # 6. 部署配置文件
  echo -e "${COLOR_INFO}[Info] 部署配置文件...${COLOR_RESET}"
  mkdir -p "$(dirname "$framework_target")"
  if ! cp -v "$framework_file" "$framework_target"; then
    echo -e "${COLOR_ERROR}[Error] 无法复制配置文件到 $framework_target${COLOR_RESET}"
    return 1
  fi

  if ! cp -v "$framework_service_file" "$framework_service_target"; then
    echo -e "${COLOR_ERROR}[Error] 无法复制服务文件到 $framework_service_target${COLOR_RESET}"
    return 1
  fi

  # 7. 设置文件权限
  echo -e "${COLOR_INFO}[Info] 设置文件权限...${COLOR_RESET}"
  chmod 640 "$framework_target" || {
    echo -e "${COLOR_WARNING}[Warning] 无法设置配置文件权限${COLOR_RESET}"
  }
  chmod 644 "$framework_service_target" || {
    echo -e "${COLOR_WARNING}[Warning] 无法设置服务文件权限${COLOR_RESET}"
  }

  # 8. 启动服务
  echo -e "${COLOR_INFO}[Info] 启动 oi-runtime 服务...${COLOR_RESET}"
  systemctl daemon-reload || {
    echo -e "${COLOR_ERROR}[Error] systemd 配置重载失败${COLOR_RESET}"
    return 1
  }

  if ! systemctl enable --now oi-runtime; then
    echo -e "${COLOR_ERROR}[Error] 无法启动 oi-runtime 服务${COLOR_RESET}"
    systemctl status oi-runtime --no-pager
    return 1
  fi

  # 9. 验证服务状态
  echo -e "${COLOR_INFO}[Info] 检查服务状态...${COLOR_RESET}"
  if ! systemctl is-active --quiet oi-runtime; then
    echo -e "${COLOR_ERROR}[Error] oi-runtime 服务未运行${COLOR_RESET}"
    journalctl -u oi-runtime --no-pager -n 20
    return 1
  fi

  # 10. 清理备份文件
  rm -f "${framework_file}.bak"

  echo -e "${COLOR_SUCCESS}[Success] euler-copilot-framework 安装完成${COLOR_RESET}"
  echo -e "${COLOR_INFO}[Info] 服务访问地址: http://${ip_address}:$port${COLOR_RESET}"
  return 0
}

main() {
  # 获取脚本所在的绝对路径
  SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
  # 切换到脚本所在目录
  cd "$SCRIPT_DIR" || return 1
  update_password
  configure_postgresql || return 1
  install_minio || return 1
  install_framework || return 1
}

main "$@"
