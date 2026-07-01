#!/bin/sh

# Copyright (c) 2026 openEuler
# Witty OpenCode is licensed under Mulan PSL v2.
# You can use this software according to the terms and conditions of the Mulan PSL v2.
# You may obtain a copy of Mulan PSL v2 at:
#          http://license.coscl.org.cn/MulanPSL2
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND,
# EITHER EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT,
# MERCHANTABILITY OR FIT FOR A PARTICULAR PURPOSE.
# See the Mulan PSL v2 for more details.

set -u

HOOK_NAME="${1:-unknown}"
PREFIX="witty-opencode rpm hook [${HOOK_NAME}]"

GENERATOR="${WITTY_OPENCODE_MANAGED_CONFIG_GENERATOR:-/usr/libexec/witty-opencode/rebuild-managed-config.mjs}"
CONFIG_DROPINS="${WITTY_OPENCODE_CONFIG_DROPINS:-${WITTY_OPENCODE_AGENT_DROPINS:-/usr/share/witty/opencode/config.d}}"
SKILLS_ROOT="${WITTY_OPENCODE_SKILLS_ROOT:-/usr/share/witty/opencode/skills}"
OPENCODE_OUTPUT="${WITTY_OPENCODE_CONFIG_OUTPUT:-/etc/opencode/opencode.json}"
TUI_OUTPUT="${WITTY_OPENCODE_TUI_OUTPUT:-/etc/opencode/tui.json}"
LOGO_PLUGIN="${WITTY_OPENCODE_LOGO_PLUGIN:-/usr/share/witty/opencode/plugins/logo/witty-logo.tsx}"
STRICT="${WITTY_OPENCODE_RPM_HOOK_STRICT:-0}"

log() {
    printf '%s: %s\n' "$PREFIX" "$*" >&2
}

finish() {
    status="$1"
    shift
    log "$*"
    if [ "$STRICT" = "1" ]; then
        exit "$status"
    fi
    log "continuing transaction (set WITTY_OPENCODE_RPM_HOOK_STRICT=1 to fail hard)"
    exit 0
}

if [ ! -f "$GENERATOR" ]; then
    finish 0 "generator not found at $GENERATOR; skipping rebuild"
fi

if [ ! -x "$GENERATOR" ]; then
    log "generator is not executable; invoking through node if available"
    if command -v node >/dev/null 2>&1; then
        node "$GENERATOR" \
            --config-dropins "$CONFIG_DROPINS" \
            --skills-root "$SKILLS_ROOT" \
            --opencode-output "$OPENCODE_OUTPUT" \
            --tui-output "$TUI_OUTPUT" \
            --logo-plugin "$LOGO_PLUGIN"
    else
        finish 1 "generator is not executable and node is not available"
    fi
else
    "$GENERATOR" \
        --config-dropins "$CONFIG_DROPINS" \
        --skills-root "$SKILLS_ROOT" \
        --opencode-output "$OPENCODE_OUTPUT" \
        --tui-output "$TUI_OUTPUT" \
        --logo-plugin "$LOGO_PLUGIN"
fi

status="$?"
if [ "$status" -ne 0 ]; then
    finish "$status" "managed config rebuild failed"
fi

log "managed config rebuild completed"
exit 0
