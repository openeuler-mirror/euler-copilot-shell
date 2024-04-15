run_copilot() {
    local readline="${READLINE_LINE}"
    if [[ -z "${readline}" ]]; then
        READLINE_LINE="copilot "
        READLINE_POINT=${#READLINE_LINE}
    elif [[ ! "${readline}" =~ ^copilot ]]; then
        READLINE_LINE="copilot '${readline}'"
        READLINE_POINT=${#READLINE_LINE}
    fi
}
bind -x '"\C-h": run_copilot'
