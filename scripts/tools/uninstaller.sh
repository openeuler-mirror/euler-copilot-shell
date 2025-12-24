#!/usr/bin/env bash

# Uninstaller for Witty Assistant
# Run as root or with sudo on openEuler

# Check openEuler environment
if [ ! -f /etc/openEuler-release ]; then
    echo "Error: This script must be run on openEuler environment." >&2
    exit 1
fi

# Parse arguments
FULL_UNINSTALL=false
if [[ "$1" == "--full" ]]; then
    FULL_UNINSTALL=true
fi

set -e

uninstall_full() {
    echo "Performing full uninstall including all dependencies and services..."

    # Stop additional services
    for svc in mysqld redis postgresql; do
        unit="${svc}.service"
        if systemctl list-unit-files --type=service | awk '{print $1}' | grep -Fxq "$unit"; then
            if systemctl is-active --quiet "$unit"; then
                echo "Stopping $unit ..."
                systemctl stop "$unit" || true
            fi
            systemctl disable "$unit" || true
        fi
    done

    # Uninstall additional dependency packages
    dnf remove -y nginx redis mysql java-17-openjdk postgresql libpq-devel || true

    # Remove additional directories
    rm -rf /opt/pgvector /opt/scws* /opt/zhparser
    rm -rf /usr/lib/euler-copilot-rag /var/log/openEulerIntelligence /etc/euler-copilot-rag
    rm -rf /etc/systemd/system/sysagent.service /etc/systemd/system/multi-user.target.wants/sysagent.service
    rm -rf /etc/systemd/system/oi-runtime.service /etc/systemd/system/multi-user.target.wants/oi-runtime.service # 兼容旧版本

    # Clean additional database data
    rm -rf /var/lib/mysql /var/log/mysql /var/lib/pgsql

    echo "Full uninstall complete."
}

echo "Stopping services..."
# For each expected service, first check if the unit file exists, then stop if running and disable it.
for svc in sysagent oi-runtime oi-rag tika; do
    unit="${svc}.service"
    # Check if the service unit exists on the system
    if systemctl list-unit-files --type=service | awk '{print $1}' | grep -Fxq "$unit"; then
        # If the service is active/running, stop it; otherwise just report
        if systemctl is-active --quiet "$unit"; then
            echo "Stopping $unit ..."
            systemctl stop "$unit" || true
        else
            echo "$unit is not running."
        fi
        # Attempt to disable the unit (may already be disabled)
        echo "Disabling $unit ..."
        systemctl disable "$unit" || true
    else
        echo "$unit not found; skipping."
    fi
done

echo "Removing packages..."
dnf remove -y openeuler-intelligence-* || true
dnf remove -y euler-copilot-framework euler-copilot-rag || true
dnf remove -y euler-copilot-web euler-copilot-witchaind-web || true

echo "Checking ports and restarting nginx if necessary..."
for port in 8080 9888 8000 11120; do
    if ss -tlnp | grep -q ":$port "; then
        echo "Port $port is in use."
        if systemctl is-active --quiet nginx; then
            echo "Restarting nginx..."
            systemctl restart nginx || true
        else
            echo "Nginx is not running, skipping restart."
        fi
        break
    fi
done

echo "Cleaning deployment files..."
# Remove framework data
rm -rf /opt/copilot
rm -rf /usr/lib/sysagent
rm -rf /etc/sysagent
rm -rf /usr/lib/euler-copilot-framework # 兼容旧版本
rm -rf /etc/euler-copilot-framework     # 兼容旧版本
# Remove Tika
rm -rf /opt/tika
rm -f /etc/systemd/system/tika.service
# Remove installation files
rm -f /etc/euler_Intelligence_install*
rm -f /usr/lib/witty-assistant/scripts/resources/config.*
rm -f /usr/lib/witty-assistant/scripts/resources/env.*
# Remove PostgreSQL data
rm -rf /var/lib/pgsql/data
rm -f /var/lib/pgsql/*.log

echo "Clearing user configs & cache logs..."
for home in /root /home/*; do
    cache_dir="$home/.cache/witty/logs"
    if [ -d "$cache_dir" ]; then
        echo "Removing $cache_dir"
        rm -rf "$cache_dir"
    fi
    config_dir="$home/.config/witty"
    if [ -d "$config_dir" ]; then
        echo "Removing $config_dir"
        rm -rf "$config_dir"
    fi
done

echo "Removing configuration template..."
rm -f /etc/witty-assistant/config-template.json

echo "Uninstalling built-in MCP servers ..."
# Check for running systrace-mcpserver services and stop/disable them if present.
services=$(systemctl list-units --type=service --state=running | awk '{print $1}' | grep -E '^systrace-mcpserver' || true)
if [ -n "$services" ]; then
    for service in $services; do
        echo "Stopping $service ..."
        systemctl stop "$service" || true
        echo "Disabling $service ..."
        systemctl disable "$service" || true
    done
else
    echo "No running systrace-mcpserver services found."
fi

dnf remove -y sysTrace-* || true
dnf remove -y mcp-servers-perf mcp-servers-remote-shell || true

if $FULL_UNINSTALL; then
    uninstall_full
fi

systemctl daemon-reload || true
echo "Uninstallation complete."
