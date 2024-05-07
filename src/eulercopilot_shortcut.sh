run_copilot() {
    local terminal_settings=$(stty -g)
    local readline="${READLINE_LINE}"
    if [[ -z "${readline}" ]]; then
        READLINE_LINE="copilot "
        READLINE_POINT=${#READLINE_LINE}
    elif [[ ! "${readline}" =~ ^copilot ]]; then
        READLINE_LINE=""
        local username=$(whoami)
        local hostname=$(hostname -s)
        if [[ "$PWD" == "$HOME" ]]; then
            local current_base_dir='~'
        else
            local current_base_dir=$(basename "$PWD")
        fi
        if [[ $EUID -eq 0 ]]; then
            local prompt_end='#'
        else
            local prompt_end='$'
        fi
        local prompt="${PS1//\\u/$username}"
        prompt="${prompt//\\h/$hostname}"
        prompt="${prompt//\\W/$current_base_dir}"
        prompt="${prompt//\\$/$prompt_end}"
        history -s "${readline}" && echo "${prompt}${readline}"
        stty sane && (copilot "${readline}")
    fi
    stty "${terminal_settings}"
}

bind -x '"\C-o": run_copilot' 2>/dev/null
