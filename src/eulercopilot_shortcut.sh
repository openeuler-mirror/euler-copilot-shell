run_copilot() {
    local terminal_settings=$(stty -g)
    local readline="${READLINE_LINE}"
    if [[ -z "${readline}" ]]; then
        READLINE_LINE="copilot "
        READLINE_POINT=${#READLINE_LINE}
    elif [[ ! "${readline}" =~ ^copilot ]]; then
        READLINE_LINE=""
        stty sane && (copilot "${readline}")
    fi
    stty "${terminal_settings}"
}
bind -x '"\C-h": run_copilot'
