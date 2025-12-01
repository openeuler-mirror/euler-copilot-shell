#!/bin/bash
# 颜色定义
COLOR_INFO='\033[34m'    # 蓝色信息
COLOR_SUCCESS='\033[32m' # 绿色成功
COLOR_ERROR='\033[31m'   # 红色错误
COLOR_WARNING='\033[33m' # 黄色警告
COLOR_RESET='\033[0m'    # 重置颜色

INSTALL_MODE_FILE="/etc/euler_Intelligence_install_mode"

## 配置参数
# 生成随机密码函数
generate_random_password() {
  local length=${1:-24} # 默认 24 位
  local password
  password=$(tr -dc 'A-Za-z0-9' </dev/urandom | head -c "$length")
  echo "$password"
}

# 配置参数（自动生成随机密码）
MYSQL_ROOT_PASSWORD=$(generate_random_password)
AUTHHUB_USER_PASSWORD=$(generate_random_password)
MINIO_ROOT_PASSWORD=$(generate_random_password)
PGSQL_PASSWORD=$(generate_random_password)

SQL_FILE="/opt/aops/database/authhub.sql"
tika_jar_src="../5-resource/tika-server-standard-3.2.0.jar"
tika_service_src="../5-resource/tika.service"
tika_jar_dest="/opt/tika/tika-server-standard-3.2.0.jar"
tika_service_dest="/etc/systemd/system/tika.service"
tika_dir="/opt/tika"
config_toml_file="../5-resource/config.toml"
env_file="../5-resource/env"
mysql_temp="../5-resource/mysql_temp"

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
  # 使用sed命令更新配置文件
  sed -i "s/secret_key = .*/secret_key = '$MINIO_ROOT_PASSWORD'/" $config_toml_file
  sed -i "s/DATABASE_PASSWORD = .*/DATABASE_PASSWORD = $PGSQL_PASSWORD/" $env_file
  sed -i "s/MINIO_SECRET_KEY = .*/MINIO_SECRET_KEY = $MINIO_ROOT_PASSWORD/" $env_file
  if [ -f "$mysql_temp" ]; then
    rm -rf $mysql_temp
  fi
  touch $mysql_temp
  echo "$AUTHHUB_USER_PASSWORD" >>$mysql_temp
  return 0
}

# 启用并启动服务
enable_services() {
  echo -e "${COLOR_INFO}[Info] 启动redis、mysql服务...${COLOR_RESET}"
  local services=("redis" "mysqld")

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

import_sql_file() {
  local DB_NAME="oauth2" # 替换为你的数据库名
  local DB_USER="root"   # 数据库用户名

  # 检查SQL文件是否存在
  if [ ! -f "$SQL_FILE" ]; then
    echo -e "${COLOR_WARNING}[Warning] 警告：未找到 $SQL_FILE 文件，跳过数据库导入${COLOR_RESET}"
    return 1
  fi

  echo -e "${COLOR_INFO} 正在准备导入数据库($SQL_FILE)...${COLOR_RESET}"

  # 检查数据库是否已存在
  if mysql -u "$DB_USER" -e "USE $DB_NAME" 2>/dev/null; then
    echo -e "${COLOR_INFO} 检测到已存在数据库 $DB_NAME，将执行重建...${COLOR_RESET}"

    # 删除现有数据库
    if ! mysql -u "$DB_USER" -e "DROP DATABASE $DB_NAME" 2>/dev/null; then
      echo -e "${COLOR_ERROR}[Error] 错误: 无法删除现有数据库 $DB_NAME${COLOR_RESET}"
      return 1
    fi
    echo -e "${COLOR_SUCCESS} 成功删除旧数据库${COLOR_RESET}"
  fi

  # 导入SQL文件
  echo -e "${COLOR_INFO}正在导入SQL文件...${COLOR_RESET}"
  if mysql -u "$DB_USER" <"$SQL_FILE"; then
    echo -e "${COLOR_SUCCESS} 数据库导入成功${COLOR_RESET}"

    # 验证导入结果
    if mysql -u "$DB_USER" -e "USE $DB_NAME; SHOW TABLES" 2>/dev/null | grep -q .; then
      echo -e "${COLOR_SUCCESS} 数据库验证通过${COLOR_RESET}"
      return 0
    else
      echo -e "${COLOR_WARNING}[Warning] 警告：数据库导入后未检测到数据表${COLOR_RESET}"
      return 1
    fi
  else
    echo -e "${COLOR_ERROR}[Error] 数据库导入失败${COLOR_RESET}"
    echo -e "${COLOR_INFO}[Info] 可能原因："
    echo -e "[Info] 1. SQL文件格式错误"
    echo -e "[Info] 2. 数据库权限不足"
    echo -e "[Info] 3. SQL文件包含错误语句${COLOR_RESET}"
    return 1
  fi
}

# 配置MySQL
configure_mysql() {
  echo -e "${COLOR_INFO}[Info] 初始化MySQL数据库... ${COLOR_RESET}"

  # 安全初始化MySQL（如果未初始化）
  if ! mysql -u root -e "SELECT 1" >/dev/null 2>&1; then
    echo -e "${COLOR_INFO}正在初始化MySQL安全配置...${COLOR_RESET}"
    mysql_secure_installation <<EOF
y
${MYSQL_ROOT_PASSWORD}
${MYSQL_ROOT_PASSWORD}
y
y
y
y
EOF
  fi

  # 创建 authhub 用户
  echo -e "${COLOR_INFO}正在创建 authhub 用户... ${COLOR_RESET}"
  if mysql -u root -e "CREATE USER IF NOT EXISTS 'authhub'@'localhost' IDENTIFIED BY '${AUTHHUB_USER_PASSWORD}'" >/dev/null 2>&1; then
    echo -e "${COLOR_SUCCESS} 创建 authhub 用户成功${COLOR_RESET}"
  else
    echo -e "${COLOR_ERROR}[Error] 失败${COLOR_RESET}"
    echo -e "${COLOR_ERROR}[Error] 错误: 无法创建MySQL用户${COLOR_RESET}"
    return 1
  fi

  import_sql_file || return 1

  # 设置权限
  echo -e "${COLOR_INFO} 正在设置数据库权限... ${COLOR_RESET}"
  if mysql -u root -e "GRANT ALL PRIVILEGES ON oauth2.* TO 'authhub'@'localhost' WITH GRANT OPTION" >/dev/null 2>&1; then
    echo -e "${COLOR_SUCCESS} 设置数据库权限成功${COLOR_RESET}"
    return 0
  else
    echo -e "${COLOR_ERROR}[Error] 失败${COLOR_RESET}"
    echo -e "${COLOR_ERROR}[Error] 错误: 权限设置失败，请检查oauth2数据库是否存在${COLOR_RESET}"
    return 1
  fi
}

# 配置 nginx
configure_nginx() {
  local nginx_conf="/etc/nginx/conf.d/authhub.nginx.conf"
  local backup_conf="/etc/nginx/conf.d/authhub.nginx.conf.bak"
  local temp_conf="/tmp/authhub.nginx.conf.tmp"

  echo -e "${COLOR_INFO}[Info] 初始化Nginx...${COLOR_RESET}"

  # 1. 检查原配置文件是否存在
  if [ ! -f "$nginx_conf" ]; then
    echo -e "${COLOR_ERROR}[Error] Nginx配置文件不存在: $nginx_conf${COLOR_RESET}"
    return 1
  fi

  # 2. 创建备份
  if ! cp -f "$nginx_conf" "$backup_conf"; then
    echo -e "${COLOR_ERROR}[Error] 创建配置文件备份失败${COLOR_RESET}"
    return 1
  fi
  echo -e "${COLOR_INFO} 已创建配置文件备份: $backup_conf${COLOR_RESET}"

  # 3. 执行替换操作
  if ! sed 's|proxy_pass http://oauth2server;|proxy_pass http://127.0.0.1:11120;|g' "$nginx_conf" >"$temp_conf"; then
    echo -e "${COLOR_ERROR}[Error] 配置文件替换失败${COLOR_RESET}"
    return 1
  fi

  # 4. 应用新配置
  if ! mv -f "$temp_conf" "$nginx_conf"; then
    echo -e "${COLOR_ERROR}[Error] 应用新配置文件失败${COLOR_RESET}"
    return 1
  fi
  # 5. 验证新配置文件语法
  if ! nginx -t &>/dev/null; then
    echo -e "${COLOR_ERROR}[Error] 新配置文件语法检查失败${COLOR_RESET}"
    echo -e "${COLOR_INFO}[Info] 正在恢复原始配置...${COLOR_RESET}"
    cp -f "$backup_conf" "$nginx_conf"
    return 1
  fi

  if ! systemctl enable --now nginx; then
    echo -e "${COLOR_ERROR}[Error] Nginx启动失败${COLOR_RESET}"
  fi
  # 6. 重载Nginx配置
  if ! systemctl reload nginx; then
    echo -e "${COLOR_ERROR}[Error] Nginx配置重载失败${COLOR_RESET}"
    echo -e "${COLOR_INFO}[Info] 正在恢复原始配置...${COLOR_RESET}"
    cp -f "$backup_conf" "$nginx_conf"
    systemctl reload nginx
    return 1
  fi

  echo -e "${COLOR_SUCCESS}[Success] Nginx初始化成功！${COLOR_RESET}"
  return 0
}

# 安装并配置Tika服务
install_tika() {
  echo -e "${COLOR_INFO}[Info] 开始安装Tika服务...${COLOR_RESET}"

  # 1. 检查源文件是否存在
  if [ ! -f "$tika_jar_src" ]; then
    echo -e "${COLOR_ERROR}[Error] Tika JAR文件不存在: $tika_jar_src${COLOR_RESET}"
    return 1
  fi

  if [ ! -f "$tika_service_src" ]; then
    echo -e "${COLOR_ERROR}[Error] Tika服务文件不存在: $tika_service_src${COLOR_RESET}"
    return 1
  fi

  # 2. 复制JAR文件并设置权限
  if [ ! -d "$tika_dir" ]; then
    echo -e "${COLOR_INFO}[Info] 创建目录: $tika_dir${COLOR_RESET}"
    if ! mkdir -p "$tika_dir"; then
      echo -e "${COLOR_ERROR}[Error] 无法创建目录: $tika_dir${COLOR_RESET}"
      return 1
    fi
  fi
  if ! cp -v "$tika_jar_src" "$tika_jar_dest"; then
    echo -e "${COLOR_ERROR}[Error] 复制Tika JAR文件失败${COLOR_RESET}"
    return 1
  fi

  if ! chmod 755 "$tika_jar_dest"; then
    echo -e "${COLOR_WARNING}[Warning] 设置Tika JAR文件权限失败${COLOR_RESET}"
  fi

  # 3. 复制服务文件并设置权限
  if ! cp -v "$tika_service_src" "$tika_service_dest"; then
    echo -e "${COLOR_ERROR}[Error] 复制Tika服务文件失败${COLOR_RESET}"
    return 1
  fi

  if ! chmod 644 "$tika_service_dest"; then
    echo -e "${COLOR_WARNING}[Warning] 设置Tika服务文件权限失败${COLOR_RESET}"
  fi

  # 4. 重载systemd
  if ! systemctl daemon-reload; then
    echo -e "${COLOR_ERROR}[Error] systemd重载失败${COLOR_RESET}"
    return 1
  fi

  # 5. 启用并启动服务
  if ! systemctl enable --now tika; then
    echo -e "${COLOR_ERROR}[Error] Tika服务启动失败${COLOR_RESET}"

    # 检查服务状态获取更多信息
    local service_status
    service_status=$(systemctl status tika --no-pager 2>&1)
    echo -e "${COLOR_INFO}[Debug] 服务状态信息:\n$service_status${COLOR_RESET}"

    journalctl -u tika --no-pager -n 20 | grep -i error
    return 1
  fi

  # 6. 验证服务运行状态
  sleep 2 # 等待服务启动
  if ! systemctl is-active --quiet tika; then
    echo -e "${COLOR_ERROR}[Error] Tika服务未正常运行${COLOR_RESET}"
    return 1
  fi

  echo -e "${COLOR_SUCCESS}[Success] Tika服务安装配置完成！${COLOR_RESET}"

  # 显示安装信息
  #    echo -e "${COLOR_INFO}[Info] Tika JAR位置: $tika_jar_dest${COLOR_RESET}"
  #    echo -e "${COLOR_INFO}[Info] 服务文件位置: $tika_service_dest${COLOR_RESET}"
  #    echo -e "${COLOR_INFO}[Info] 使用命令: systemctl status tika 查看服务状态${COLOR_RESET}"
  return 0
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

  # 4. 设置 postgres 用户密码
  echo -e "${COLOR_INFO}[Info] 设置 PostgreSQL 密码...${COLOR_RESET}"
  sudo -u postgres psql -c "ALTER USER postgres PASSWORD '$PGSQL_PASSWORD';" || {
    echo -e "${COLOR_ERROR}[Error] 密码设置失败${COLOR_RESET}"
    return 1
  }

  # 5. 启用扩展
  echo -e "${COLOR_INFO}[Info] 启用 PostgreSQL 扩展...${COLOR_RESET}"
  sudo -u postgres psql -c "CREATE EXTENSION  zhparser;" || {
    echo -e "${COLOR_ERROR}[Error] 无法启用 zhparser 扩展${COLOR_RESET}"
    return 1
  }

  sudo -u postgres psql -c "CREATE EXTENSION  vector;" || {
    echo -e "${COLOR_ERROR}[Error] 无法启用 vector 扩展${COLOR_RESET}"
    return 1
  }

  sudo -u postgres psql -c "CREATE TEXT SEARCH CONFIGURATION  zhparser (PARSER = zhparser);" || {
    echo -e "${COLOR_ERROR}[Error] 无法创建全文搜索配置${COLOR_RESET}"
    return 1
  }

  sudo -u postgres psql -c "ALTER TEXT SEARCH CONFIGURATION zhparser ADD MAPPING FOR n,v,a,i,e,l WITH simple;" || {
    echo -e "${COLOR_ERROR}[Error] 无法添加映射${COLOR_RESET}"
    return 1
  }

  # 5. 查找并修改pg_hba.conf
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
  # 6. 重启服务
  echo -e "${COLOR_INFO}[Info] 重启 PostgreSQL 服务...${COLOR_RESET}"
  systemctl daemon-reload
  systemctl restart postgresql || {
    echo -e "${COLOR_ERROR}[Error] 服务重启失败${COLOR_RESET}"
    return 1
  }
  echo -e "${COLOR_SUCCESS}[Success] PostgreSQL 配置完成${COLOR_RESET}"
  return 0
}

install_rag() {
  echo -e "${COLOR_INFO}[Info] 开始初始化配置 euler-copilot-rag...${COLOR_RESET}"

  # 配置文件处理
  local env_file="../5-resource/env"
  local env_target="/etc/euler-copilot-rag/data_chain/env"
  local service_file="../5-resource/oi-rag.service"
  local service_target="/etc/systemd/system/oi-rag.service"

  # 复制配置文件（验证文件存在性）
  if [[ -f "$env_file" ]]; then
    cp -v "$env_file" "$env_target" || {
      echo -e "${COLOR_ERROR}[Error] 复制 env 文件失败！${COLOR_RESET}"
      return 1
    }
  else
    echo -e "${COLOR_WARNING}[Warning] 未找到 env 文件：$env_file${COLOR_RESET}"
  fi

  if [[ -f "$service_file" ]]; then
    cp -v "$service_file" "$service_target" || {
      echo -e "${COLOR_ERROR}[Error] 复制 service 文件失败！${COLOR_RESET}"
      return 1
    }
  else
    echo -e "${COLOR_WARNING}[Warning] 未找到 service 文件：$service_file${COLOR_RESET}"
  fi

  # 安装图形库依赖（OpenGL）
  if ! dnf install -y mesa-libGL >/dev/null; then
    echo -e "${COLOR_WARNING}[Warning] mesa-libGL 安装失败，可能影响图形功能${COLOR_RESET}"
  fi

  # 启动服务
  echo -e "${COLOR_INFO}[Info] 设置并启动 oi-rag 服务...${COLOR_RESET}"
  systemctl daemon-reload
  systemctl enable --now oi-rag || {
    echo -e "${COLOR_ERROR}[Error] oi-rag 服务启动失败！${COLOR_RESET}"
    systemctl status oi-rag --no-pager
    return 1
  }

  # 验证服务状态
  echo -e "${COLOR_INFO}[Info] 验证 oi-rag 服务状态...${COLOR_RESET}"
  if systemctl is-active --quiet oi-rag; then
    echo -e "${COLOR_SUCCESS}[Success] oi-rag 服务运行正常${COLOR_RESET}"
    systemctl status oi-rag --no-pager | grep -E "Active:|Loaded:"
  else
    echo -e "${COLOR_ERROR}[Error] oi-rag 服务未运行！${COLOR_RESET}"
    journalctl -u oi-rag --no-pager -n 20
    return 1
  fi

  echo -e "${COLOR_SUCCESS}[Success] euler-copilot-rag 安装完成${COLOR_RESET}"
  return 0
}

# 网络检测函数
check_network_reachable() {
  local test_url="https://openaipublic.blob.core.windows.net"
  local timeout=3

  echo -e "${COLOR_INFO}[Info] 检测网络连通性 (测试地址: $test_url)...${COLOR_RESET}"

  # 使用curl检测
  if curl --silent --connect-timeout $timeout --head $test_url >/dev/null; then
    echo -e "${COLOR_SUCCESS}[Success] 网络连接正常${COLOR_RESET}"
    return 0
  fi

  # 使用ping二次验证
  if ping -c 1 -W $timeout openaipublic.blob.core.windows.net >/dev/null 2>&1; then
    echo -e "${COLOR_SUCCESS}[Success] 网络连接正常 (ping检测)${COLOR_RESET}"
    return 0
  fi

  echo -e "${COLOR_WARNING}[Warning] 网络不可达${COLOR_RESET}"
  return 1
}

setup_tiktoken_cache() {
  # 预置的本地资源路径
  local local_tiktoken_file="../5-resource/9b5ad71b2ce5302211f9c61530b329a4922fc6a4"
  local cache_dir="/root/.cache/tiktoken"
  local target_file="$cache_dir/9b5ad71b2ce5302211f9c61530b329a4922fc6a4"

  # 1. 检查本地资源文件是否存在
  if [[ ! -f "$local_tiktoken_file" ]]; then
    echo -e "${COLOR_ERROR}[Error] 本地tiktoken资源文件不存在: $local_tiktoken_file${COLOR_RESET}"
    return 1
  fi

  # 2. 创建缓存目录
  echo -e "${COLOR_INFO}[Info] 创建tiktoken缓存目录...${COLOR_RESET}"
  if ! mkdir -p "$cache_dir"; then
    echo -e "${COLOR_ERROR}[Error] 无法创建缓存目录: $cache_dir${COLOR_RESET}"
    return 1
  fi

  # 3. 复制文件到缓存目录
  dos2unix "$local_tiktoken_file"
  if ! cp -r "$local_tiktoken_file" "$target_file"; then
    echo -e "${COLOR_ERROR}[Error] tiktoken.tar 解压失败${COLOR_RESET}"
    return 1
  fi

  # 4. 设置权限（确保可读）
  chmod 644 "$target_file" || {
    echo -e "${COLOR_WARNING}[Warning] 无法设置文件权限${COLOR_RESET}"
  }

  # 6. 设置环境变量（影响当前进程）
  # 特殊处理改 token 代码
  FILE="/usr/lib/euler-copilot-framework/apps/llm/token.py"
  token_py_file="../5-resource/token.py"
  cp $token_py_file $FILE
  echo -e "${COLOR_SUCCESS}[Success] tiktoken缓存已配置: $target_file${COLOR_RESET}"
}

get_client_info_auto() {
  # 声明全局变量
  declare -g client_id=""
  declare -g client_secret=""

  # 直接调用Python脚本并传递域名参数
  python3 "../4-other-script/get_client_id_and_secret.py" "$1" >client_info.tmp 2>&1

  # 检查Python脚本执行结果
  if [ $? -ne 0 ]; then
    echo -e "${COLOR_ERROR}[Error] Python脚本执行失败${COLOR_RESET}"
    cat client_info.tmp
    rm -f client_info.tmp
    return 1
  fi

  # 提取凭证信息
  client_id=$(grep "client_id: " client_info.tmp | awk '{print $2}')
  client_secret=$(grep "client_secret: " client_info.tmp | awk '{print $2}')
  rm -f client_info.tmp

  # 验证结果
  if [ -z "$client_id" ] || [ -z "$client_secret" ]; then
    echo -e "${COLOR_ERROR}[Error] 无法获取有效的客户端凭证${COLOR_RESET}" >&2
    return 1
  fi
}

install_framework() {
  # 1. 安装前检查
  echo -e "${COLOR_INFO}[Info] 开始初始化配置 euler-copilot-framework...${COLOR_RESET}"

  # 2. 检查并创建必要目录
  echo -e "${COLOR_INFO}[Info] 创建数据目录...${COLOR_RESET}"
  mkdir -p /opt/copilot || {
    echo -e "${COLOR_ERROR}[Error] 无法创建数据目录 /opt/copilot${COLOR_RESET}"
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
  port=8080
  # 安装 Web 界面（如果用户选择）配置 app_id
  if [ "$WEB_INSTALL" = "y" ]; then
    echo -e "${COLOR_INFO}[Info] 获取客户端凭证...${COLOR_RESET}"
    if ! get_client_info_auto "$ip_address"; then
      echo -e "${COLOR_ERROR}[Error] 获取客户端凭证失败${COLOR_RESET}"
      return 1
    fi
    sed -i "s@app_id = \".*\"@app_id = \"$client_id\"@" $framework_file
    sed -i "s@app_secret = \".*\"@app_secret = \"$client_secret\"@" $framework_file
    # 验证替换结果
    if ! grep -q "app_id = \"$client_id\"" "$framework_file" || ! grep -q "app_secret = \"$client_secret\"" "$framework_file"; then
      echo -e "${COLOR_ERROR}[Error] 配置文件验证失败${COLOR_RESET}"
      mv -v "${framework_file}.bak" "$framework_file"
      return 1
    fi
  else
    port=8002
    sed -i "/\[login\.settings\]/,/^\[/ s|host = '.*'|host = 'http://${ip_address}:8000'|" "$framework_file"
    sed -i "s|login_api = '.*'|login_api = 'http://${ip_address}:8080/api/auth/login'|" $framework_file
    sed -i "s/domain = '.*'/domain = '$ip_address'/" $framework_file
    # 添加 no_auth 参数
    # 检查文件中是否已存在 [no_auth] 块
    if grep -q '^\[no_auth\]$' "$framework_file"; then
      echo -e "${COLOR_INFO}[Info] 文件中已存在 [no_auth] 配置块，更新内容...${COLOR_RESET}"

      # 使用 sed 替换现有 [no_auth] 块下的内容（保留块，更新键值）
      # 先删除现有块内的内容，再添加新内容
      sed -i '/^\[no_auth\]$/,/^\[.*\]$/ {
            /^\[no_auth\]$/!{ /^\[.*\]$/!d; }
        }' "$framework_file"

      # 在 [no_auth] 块后添加配置
      sed -i '/^\[no_auth\]$/a\enable = true' "$framework_file"
    else
      echo -e "${COLOR_INFO}[Info] 向文件添加 [no_auth] 配置块...${COLOR_RESET}"
      # 追加新的配置块到文件末尾
      cat <<EOF >>"$framework_file"

[no_auth]
enable = true

EOF
    fi
  fi

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

  # 特殊处理，如果 openaipublic.blob.core.windows.net 网络不可达
  # 创建缓存目录（通常是 ~/.cache/tiktoken）
  check_network_reachable || {
    setup_tiktoken_cache || echo -e "${COLOR_WARNING}[Warning] 无网络 cl100k_base.tiktoken  文件下载失败,请检查网络${COLOR_RESET}"
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

uninstall_pkg() {
  dnf remove -y euler-copilot-rag
  dnf remove -y euler-copilot-framework
}

# 读取安装模式的方法
read_install_mode() {
  # 检查文件是否存在
  if [ ! -f "$INSTALL_MODE_FILE" ]; then
    echo -e "${COLOR_ERROR}[Error] 安装模式文件不存在: $INSTALL_MODE_FILE${COLOR_RESET}"
    return 1
  fi

  # 从文件读取配置（格式：key=value）
  local web_install
  local rag_install
  web_install=$(grep "web_install=" "$INSTALL_MODE_FILE" | cut -d'=' -f2)
  rag_install=$(grep "rag_install=" "$INSTALL_MODE_FILE" | cut -d'=' -f2)

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

init_rag() {
  cd "$SCRIPT_DIR" || return 1
  install_tika || return 1
  cd "$SCRIPT_DIR" || return 1
  install_minio || return 1
  cd "$SCRIPT_DIR" || return 1
  install_rag || return 1
}

init_web() {
  cd "$SCRIPT_DIR" || return 1
  enable_services || return 1
  configure_mysql || return 1
  configure_nginx || return 1
  cd "$SCRIPT_DIR" || return 1
  ./install_authhub_config.sh || return 1
}

# 示例：根据安装模式执行对应操作（可根据实际需求扩展）
install_components() {
  # 读取安装模式
  read_install_mode || return 1

  # 安装Web界面（如果用户选择）
  if [ "$WEB_INSTALL" = "y" ]; then
    echo -e "\n${COLOR_INFO}[Info] 开始初始化Web管理界面...${COLOR_RESET}"
    # 此处添加Web初始化命令，示例：
    init_web || return 1
  fi

  # 初始化RAG组件（如果用户选择）
  if [ "$RAG_INSTALL" = "y" ]; then
    echo -e "\n${COLOR_INFO}[Info] 开始初始化RAG检索增强组件...${COLOR_RESET}"
    # 此处添加RAG初始化命令，示例：
    init_rag || return 1
  fi
}

main() {
  # 获取脚本所在的绝对路径
  SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
  # 切换到脚本所在目录
  cd "$SCRIPT_DIR" || return 1
  update_password
  configure_postgresql || return 1
  install_components || return 1
  install_framework || return 1
}

main "$@"
