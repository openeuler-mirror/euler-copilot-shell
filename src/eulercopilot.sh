# Copyright (c) Huawei Technologies Co., Ltd. 2024-2024. All rights reserved.

read_query_mode() {
    if [ ! -f ~/.config/eulercopilot/config.json ]; then
        return
    fi

    local query_mode
    query_mode=$(jq '.query_mode' ~/.config/eulercopilot/config.json)
    
    if [ "$query_mode" = "\"chat\"" ]; then
        echo "智能问答"
    elif [ "$query_mode" = "\"flow\"" ]; then
        echo "智能插件"
    elif [ "$query_mode" = "\"diagnose\"" ]; then
        echo "智能诊断"
    elif [ "$query_mode" = "\"tuning\"" ]; then
        echo "智能调优"
    else
        echo "未知模式"
    fi
}

get_prompt() {
    local username
    local hostname
    local current_base_dir
    local prompt_end
    local prompt

    username=$(whoami)
    hostname=$(hostname -s)
    if [[ "$PWD" == "$HOME" ]]; then
        current_base_dir='~'
    else
        current_base_dir=$(basename "$PWD")
    fi
    if [[ $EUID -eq 0 ]]; then
        prompt_end='#'
    else
        prompt_end='$'
    fi
    prompt="${PS1//\\u/$username}"
    prompt="${prompt//\\h/$hostname}"
    prompt="${prompt//\\W/$current_base_dir}"
    prompt="${prompt//\\$/$prompt_end}"
    echo "${prompt}"
}

set_prompt() {
    local query_mode
    query_mode="$(read_query_mode)"

    if [ -z "$query_mode" ]; then
        return
    fi

    if [[ "$PS1" != *"\[\033[1;33m"* ]]; then
        PS1="╭─ \[\033[1;33m\]${query_mode}\[\033[0m\] ─╮\n╰${PS1}"
    fi
}

revert_prompt() {
    PS1="${PS1#*╰}"
}

run_copilot() {
    local terminal_settings
    local readline="${READLINE_LINE}"
    if [[ -z "${readline}" ]]; then
        READLINE_LINE="copilot "
        READLINE_POINT=${#READLINE_LINE}
    elif [[ ! "${readline}" =~ ^copilot ]]; then
        terminal_settings=$(stty -g)
        READLINE_LINE=""
        local _ps1
        local prompt
        _ps1=$(get_prompt)
        prompt=${_ps1#*\\n}
        history -s "${readline}" && echo "${prompt}${readline}"
        stty sane && (copilot "${readline}")
        stty "${terminal_settings}"
        if [[ $_ps1 =~ \\n ]]; then
            prompt="${_ps1%%\\n*}"
            prompt="${prompt//\\[/}"
            prompt="${prompt//\\]/}"
            echo -e "${prompt}"
        fi
    elif [[ "${readline}" == "copilot " ]]; then
        READLINE_LINE=""
        if [[ "$PS1" == *"\[\033[1;33m"* ]]; then
            revert_prompt
            printf "\033[1;31m已关闭 openEuler Copilot System 提示符\033[0m\n"
        else
            set_prompt
            printf "\033[1;32m已开启 openEuler Copilot System 提示符\033[0m\n"
        fi
    fi
}

bind -x '"\C-o": run_copilot' 2>/dev/null
alias set_copilot_prompt='set_prompt'
alias revert_copilot_prompt='revert_prompt'
