# shellcheck shell=bash
# /etc/profile.d/witty.sh — Witty shell integration
# Sourced by /etc/profile (login shell) and /etc/bashrc (interactive non-login).
# To disable: add 'export WITTY_SHELL_ENABLE=0' to ~/.bashrc
if [ -n "${BASH_VERSION:-}" ] && [ -z "${__WITTY_SHELL_INIT_LOADED:-}" ]; then
  eval "$(witty init bash 2>/dev/null)" || true
fi
