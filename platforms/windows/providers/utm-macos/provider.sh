#!/usr/bin/env bash

set -euo pipefail

readonly PROVIDER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../../scripts/common.sh
source "$PROVIDER_DIR/../../scripts/common.sh"

usage() {
    cat <<'EOF'
Usage: provider.sh COMMAND [ARG...]

Internal UTM-on-macOS provider. Use bin/winvm instead.
EOF
}

require_utmctl() {
    if [[ "$(uname -s)" != "Darwin" ]]; then
        printf 'The utm-macos provider requires macOS\n' >&2
        exit 1
    fi
    if [[ ! -x "$WINVM_UTMCTL" ]]; then
        printf 'UTM CLI not found at %s\n' "$WINVM_UTMCTL" >&2
        exit 1
    fi
}

vm_status() {
    "$WINVM_UTMCTL" status "$WINVM_UTM_NAME" 2>/dev/null
}

ensure_running() {
    local status
    status="$(vm_status || true)"
    if [[ "$status" != "started" ]]; then
        "$WINVM_UTMCTL" start --hide "$WINVM_UTM_NAME" >/dev/null 2>&1 || true
    fi

    local deadline=$((SECONDS + WINVM_BOOT_TIMEOUT))
    while (( SECONDS < deadline )); do
        status="$(vm_status || true)"
        if [[ "$status" == "started" ]]; then
            return 0
        fi
        sleep 1
    done

    printf 'Timed out waiting for UTM VM %s to start (last status: %s)\n' \
        "$WINVM_UTM_NAME" "$status" >&2
    return 1
}

guest_ipv4() {
    ensure_running

    local deadline=$((SECONDS + WINVM_BOOT_TIMEOUT))
    local addresses ip
    while (( SECONDS < deadline )); do
        addresses="$("$WINVM_UTMCTL" ip-address "$WINVM_UTM_NAME" 2>/dev/null || true)"
        ip="$(printf '%s\n' "$addresses" | awk '/^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$/ { print; exit }')"
        if [[ -n "$ip" ]]; then
            printf '%s\n' "$ip"
            return 0
        fi
        sleep 1
    done

    printf 'Timed out waiting for %s to report an IPv4 address\n' \
        "$WINVM_UTM_NAME" >&2
    return 1
}

input_text() {
    if [[ $# -ne 1 ]]; then
        printf 'Usage: winvm type TEXT\n' >&2
        return 2
    fi
    /usr/bin/osascript - "$WINVM_UTM_NAME" "$1" <<'APPLESCRIPT'
on run argv
    set vmName to item 1 of argv
    set inputText to item 2 of argv
    tell application "UTM"
        set targetVM to first virtual machine whose name is vmName
        input keystroke targetVM text inputText
    end tell
end run
APPLESCRIPT
}

input_click() {
    if [[ $# -lt 2 || $# -gt 3 || ! "$1" =~ ^[0-9]+$ || ! "$2" =~ ^[0-9]+$ ]]; then
        printf 'Usage: winvm click X Y [left|right|middle]\n' >&2
        return 2
    fi
    local button="${3:-left}"
    if [[ "$button" != "left" && "$button" != "right" && "$button" != "middle" ]]; then
        printf 'Unknown mouse button: %s\n' "$button" >&2
        return 2
    fi
    /usr/bin/osascript - "$WINVM_UTM_NAME" "$1" "$2" "$button" <<'APPLESCRIPT'
on run argv
    set vmName to item 1 of argv
    set clickPosition to {(item 2 of argv) as integer, (item 3 of argv) as integer}
    set buttonName to item 4 of argv
    if buttonName is "right" then
        set buttonKind to «constant MsBtMsRt»
    else if buttonName is "middle" then
        set buttonKind to «constant MsBtMsMd»
    else
        set buttonKind to «constant MsBtMsLf»
    end if
    tell application "UTM"
        set targetVM to first virtual machine whose name is vmName
        input mouse click targetVM at clickPosition with mouse button buttonKind
    end tell
end run
APPLESCRIPT
}

input_scan_codes() {
    if [[ $# -lt 1 ]]; then
        printf 'Usage: winvm scan CODE...\n' >&2
        return 2
    fi
    local code
    for code in "$@"; do
        if [[ ! "$code" =~ ^[0-9]+$ || "$code" -gt 255 ]]; then
            printf 'Scan codes must be decimal bytes (0-255): %s\n' "$code" >&2
            return 2
        fi
    done
    /usr/bin/osascript - "$WINVM_UTM_NAME" "$@" <<'APPLESCRIPT'
on run argv
    set vmName to item 1 of argv
    set scanCodes to {}
    repeat with rawCode in items 2 thru -1 of argv
        set end of scanCodes to rawCode as integer
    end repeat
    tell application "UTM"
        set targetVM to first virtual machine whose name is vmName
        input scan code targetVM codes scanCodes
    end tell
end run
APPLESCRIPT
}

input_key() {
    if [[ $# -ne 1 ]]; then
        printf 'Usage: winvm key NAME\n' >&2
        return 2
    fi
    case "$1" in
        enter)             input_scan_codes 28 156 ;;
        escape)            input_scan_codes 1 129 ;;
        tab)               input_scan_codes 15 143 ;;
        win-r)             input_scan_codes 224 91 19 147 224 219 ;;
        win-d)             input_scan_codes 224 91 32 160 224 219 ;;
        ctrl-shift-escape) input_scan_codes 29 42 1 129 170 157 ;;
        alt-f4)            input_scan_codes 56 62 190 184 ;;
        ctrl-alt-delete)   input_scan_codes 29 56 224 83 224 211 184 157 ;;
        *)
            printf 'Unknown key name: %s\n' "$1" >&2
            return 2
            ;;
    esac
}

stage_bootstrap() {
    if [[ "$WINVM_GUEST_DRIVER" != "windows" ]]; then
        printf 'SSH bootstrap is not implemented for guest driver: %s\n' \
            "$WINVM_GUEST_DRIVER" >&2
        return 1
    fi

    local public_key="${1:-$HOME/.ssh/id_ed25519.pub}"
    local bootstrap="$WINVM_REPO_DIR/guests/windows/bootstrap-openssh.ps1"
    if [[ ! -r "$public_key" ]]; then
        printf 'Public key not found: %s\n' "$public_key" >&2
        return 1
    fi

    ensure_running
    "$WINVM_UTMCTL" file push "$WINVM_UTM_NAME" \
        'C:\Users\Public\winvm-bootstrap-openssh.ps1' < "$bootstrap"
    "$WINVM_UTMCTL" file push "$WINVM_UTM_NAME" \
        'C:\Users\Public\winvm-host.pub' < "$public_key"

    cat <<'EOF'
Bootstrap files staged. In the Windows VM, open PowerShell as Administrator
and run:

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass `
  -File C:\Users\Public\winvm-bootstrap-openssh.ps1

Then configure the SSH alias and run: bin/winvm doctor
EOF
}

require_utmctl
command="${1:-}"
if [[ -n "$command" ]]; then shift; fi

case "$command" in
    status) vm_status ;;
    up|ip) guest_ipv4 ;;
    screenshot) exec "$PROVIDER_DIR/screenshot" "$@" ;;
    type) input_text "$@" ;;
    click) input_click "$@" ;;
    key) input_key "$@" ;;
    scan) input_scan_codes "$@" ;;
    stage-bootstrap) stage_bootstrap "$@" ;;
    suspend) "$WINVM_UTMCTL" suspend --save-state "$WINVM_UTM_NAME" ;;
    shutdown) "$WINVM_UTMCTL" stop --request "$WINVM_UTM_NAME" ;;
    force-stop) "$WINVM_UTMCTL" stop --force "$WINVM_UTM_NAME" ;;
    *) usage >&2; exit 2 ;;
esac
