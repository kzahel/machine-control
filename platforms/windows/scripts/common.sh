#!/usr/bin/env bash

# Shared configuration for host commands. Keep this file safe to source from
# scripts that enable either `set -e` or `set -u`.

WINVM_REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WINVM_CONFIG_FILE="${WINVM_CONFIG_FILE:-$WINVM_REPO_DIR/config.local}"

if [[ -f "$WINVM_CONFIG_FILE" ]]; then
    # shellcheck source=/dev/null
    source "$WINVM_CONFIG_FILE"
fi

WINVM_PROVIDER="${WINVM_PROVIDER:-utm-macos}"
WINVM_GUEST_DRIVER="${WINVM_GUEST_DRIVER:-windows}"
WINVM_SSH_HOST="${WINVM_SSH_HOST:-winvm}"
WINVM_SSH_PORT="${WINVM_SSH_PORT:-22}"
WINVM_UTM_NAME="${WINVM_UTM_NAME:-Windows}"
WINVM_UTMCTL="${WINVM_UTMCTL:-/Applications/UTM.app/Contents/MacOS/utmctl}"
WINVM_BOOT_TIMEOUT="${WINVM_BOOT_TIMEOUT:-120}"
WINVM_UI_PIPE_NAME="${WINVM_UI_PIPE_NAME:-winvm-ui}"
WINVM_UI_TASK_NAME="${WINVM_UI_TASK_NAME:-WinVM UI Relay}"
WINVM_UI_REMOTE_RELATIVE="${WINVM_UI_REMOTE_RELATIVE:-AppData/Local/winvm-testbed}"

export WINVM_REPO_DIR WINVM_CONFIG_FILE WINVM_PROVIDER WINVM_GUEST_DRIVER
export WINVM_SSH_HOST WINVM_SSH_PORT WINVM_UTM_NAME WINVM_UTMCTL
export WINVM_BOOT_TIMEOUT WINVM_UI_PIPE_NAME WINVM_UI_TASK_NAME
export WINVM_UI_REMOTE_RELATIVE

winvm_provider_path() {
    printf '%s/providers/%s/provider.sh\n' "$WINVM_REPO_DIR" "$WINVM_PROVIDER"
}

winvm_require_command() {
    if ! command -v "$1" >/dev/null 2>&1; then
        printf 'Required command not found: %s\n' "$1" >&2
        return 1
    fi
}

winvm_encode_powershell() {
    iconv -f UTF-8 -t UTF-16LE | base64 | tr -d '\n'
}

winvm_powershell() {
    local powershell_script="$1"
    local encoded_command
    encoded_command="$(printf '%s' "$powershell_script" | winvm_encode_powershell)"
    ssh "$WINVM_SSH_HOST" \
        "powershell.exe -NoLogo -NoProfile -NonInteractive -EncodedCommand $encoded_command"
}

winvm_tcp_check() {
    local host="$1" port="$2" timeout="${3:-2}"
    if [[ "$(uname -s)" == "Darwin" ]]; then
        nc -G "$timeout" -z "$host" "$port" >/dev/null 2>&1
    else
        nc -w "$timeout" -z "$host" "$port" >/dev/null 2>&1
    fi
}
