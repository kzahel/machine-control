#!/usr/bin/env bash

# Shared configuration. Keep this safe to source under `set -e` and `set -u`.

LINUXVM_REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LINUXVM_CONFIG_FILE="${LINUXVM_CONFIG_FILE:-$LINUXVM_REPO_DIR/config.local}"

if [[ -f "$LINUXVM_CONFIG_FILE" ]]; then
    # shellcheck source=/dev/null
    source "$LINUXVM_CONFIG_FILE"
fi

LINUXVM_PROVIDER="${LINUXVM_PROVIDER:-utm-macos}"
LINUXVM_UTM_NAME="${LINUXVM_UTM_NAME:-Linux}"
LINUXVM_UTMCTL="${LINUXVM_UTMCTL:-/Applications/UTM.app/Contents/MacOS/utmctl}"
LINUXVM_DESKTOP_USER="${LINUXVM_DESKTOP_USER:-}"
LINUXVM_DISPLAY_WIDTH="${LINUXVM_DISPLAY_WIDTH:-1280}"
LINUXVM_DISPLAY_HEIGHT="${LINUXVM_DISPLAY_HEIGHT:-800}"
LINUXVM_BOOT_TIMEOUT="${LINUXVM_BOOT_TIMEOUT:-120}"
LINUXVM_SHUTDOWN_TIMEOUT="${LINUXVM_SHUTDOWN_TIMEOUT:-120}"
LINUXVM_EXEC_TIMEOUT="${LINUXVM_EXEC_TIMEOUT:-300}"
LINUXVM_REMOTE_ROOT="${LINUXVM_REMOTE_ROOT:-/var/tmp/linuxvm-testbed}"
LINUXVM_UI_REMOTE="${LINUXVM_UI_REMOTE:-/usr/local/libexec/linuxvm-testbed/linuxui.py}"

export LINUXVM_REPO_DIR LINUXVM_CONFIG_FILE LINUXVM_PROVIDER
export LINUXVM_UTM_NAME LINUXVM_UTMCTL LINUXVM_DESKTOP_USER
export LINUXVM_DISPLAY_WIDTH LINUXVM_DISPLAY_HEIGHT
export LINUXVM_BOOT_TIMEOUT LINUXVM_SHUTDOWN_TIMEOUT LINUXVM_EXEC_TIMEOUT
export LINUXVM_REMOTE_ROOT LINUXVM_UI_REMOTE

linuxvm_provider_path() {
    printf '%s/providers/%s/provider.sh\n' "$LINUXVM_REPO_DIR" "$LINUXVM_PROVIDER"
}

linuxvm_require_command() {
    if ! command -v "$1" >/dev/null 2>&1; then
        printf 'Required command not found: %s\n' "$1" >&2
        return 1
    fi
}
