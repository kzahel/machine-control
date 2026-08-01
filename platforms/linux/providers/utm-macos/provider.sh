#!/usr/bin/env bash

set -euo pipefail

readonly PROVIDER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../../scripts/common.sh
source "$PROVIDER_DIR/../../scripts/common.sh"

usage() {
    cat <<'EOF'
Usage: provider.sh COMMAND [ARG...]

Internal UTM-on-macOS provider. Use bin/linuxvm instead.
EOF
}

require_utmctl() {
    if [[ "$(uname -s)" != "Darwin" ]]; then
        printf 'The utm-macos provider requires macOS\n' >&2
        exit 1
    fi
    if [[ ! -x "$LINUXVM_UTMCTL" ]]; then
        printf 'UTM CLI not found at %s\n' "$LINUXVM_UTMCTL" >&2
        exit 1
    fi
}

vm_status() {
    "$LINUXVM_UTMCTL" status "$LINUXVM_UTM_NAME" 2>/dev/null
}

ensure_running() {
    local status
    status="$(vm_status || true)"
    if [[ "$status" != "started" ]]; then
        "$LINUXVM_UTMCTL" start "$LINUXVM_UTM_NAME" >/dev/null
    fi

    local deadline=$((SECONDS + LINUXVM_BOOT_TIMEOUT))
    while (( SECONDS < deadline )); do
        status="$(vm_status || true)"
        if [[ "$status" == "started" ]]; then
            return 0
        fi
        sleep 1
    done

    printf 'Timed out waiting for UTM VM %s (last status: %s)\n' \
        "$LINUXVM_UTM_NAME" "$status" >&2
    return 1
}

guest_agent_ready() {
    "$LINUXVM_UTMCTL" exec "$LINUXVM_UTM_NAME" \
        --cmd /usr/bin/id >/dev/null 2>&1
}

wait_for_guest_agent() {
    ensure_running
    local deadline=$((SECONDS + LINUXVM_BOOT_TIMEOUT))
    while (( SECONDS < deadline )); do
        if guest_agent_ready; then
            return 0
        fi
        sleep 1
    done
    printf 'QEMU guest agent is unavailable in %s; see docs/bootstrap.md\n' \
        "$LINUXVM_UTM_NAME" >&2
    return 1
}

guest_ipv4() {
    wait_for_guest_agent
    local addresses ip
    addresses="$("$LINUXVM_UTMCTL" ip-address "$LINUXVM_UTM_NAME")"
    ip="$(printf '%s\n' "$addresses" | awk \
        '/^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$/ { print; exit }')"
    if [[ -z "$ip" ]]; then
        printf 'No guest IPv4 address reported for %s\n' "$LINUXVM_UTM_NAME" >&2
        return 1
    fi
    printf '%s\n' "$ip"
}

guest_reboot() {
    wait_for_guest_agent
    local old_boot_id new_boot_id deadline
    old_boot_id="$("$LINUXVM_UTMCTL" exec "$LINUXVM_UTM_NAME" \
        --cmd /usr/bin/cat /proc/sys/kernel/random/boot_id)"
    "$LINUXVM_UTMCTL" exec "$LINUXVM_UTM_NAME" \
        --cmd /usr/bin/systemctl reboot >/dev/null 2>&1 || true

    deadline=$((SECONDS + LINUXVM_BOOT_TIMEOUT))
    while (( SECONDS < deadline )); do
        new_boot_id="$("$LINUXVM_UTMCTL" exec "$LINUXVM_UTM_NAME" \
            --cmd /usr/bin/cat /proc/sys/kernel/random/boot_id 2>/dev/null || true)"
        if [[ -n "$new_boot_id" && "$new_boot_id" != "$old_boot_id" ]]; then
            guest_ipv4
            return 0
        fi
        sleep 2
    done
    printf 'Timed out waiting for %s to complete its reboot\n' \
        "$LINUXVM_UTM_NAME" >&2
    return 1
}

guest_exec() {
    if (( $# == 0 )); then
        printf 'Usage: linuxvm exec -- COMMAND [ARG...]\n' >&2
        return 2
    fi
    wait_for_guest_agent

    local token remote_dir remote_stdout remote_stderr remote_status
    token="$(date +%s).$$.$RANDOM"
    remote_dir="$LINUXVM_REMOTE_ROOT/run/$token"
    remote_stdout="$remote_dir/stdout"
    remote_stderr="$remote_dir/stderr"
    remote_status="$remote_dir/status"

    local quoted_command quoted_dir quoted_stdout quoted_stderr quoted_status
    printf -v quoted_command '%q ' "$@"
    printf -v quoted_dir '%q' "$remote_dir"
    printf -v quoted_stdout '%q' "$remote_stdout"
    printf -v quoted_stderr '%q' "$remote_stderr"
    printf -v quoted_status '%q' "$remote_status"

    local remote_script
    remote_script="umask 077; mkdir -p $quoted_dir; "
    remote_script+="find '$LINUXVM_REMOTE_ROOT/run' -mindepth 1 -maxdepth 1 "
    remote_script+="-type d -mmin +1440 -exec rm -rf -- {} + 2>/dev/null || true; "
    remote_script+="$quoted_command >$quoted_stdout 2>$quoted_stderr; "
    remote_script+="rc=\$?; printf '%s\\n' \"\$rc\" >$quoted_status"

    # UTM 4.7 can return from exec before a compound guest command has made
    # every side effect visible. The status file, written last, is authoritative.
    "$LINUXVM_UTMCTL" exec "$LINUXVM_UTM_NAME" \
        --cmd /usr/bin/bash -lc "$remote_script" >/dev/null 2>&1 || true

    local local_dir local_status local_stderr status deadline
    local_dir="$(mktemp -d /tmp/linuxvm-exec.XXXXXX)"
    local_status="$local_dir/status"
    local_stderr="$local_dir/stderr"
    deadline=$((SECONDS + LINUXVM_EXEC_TIMEOUT))

    while (( SECONDS < deadline )); do
        if "$LINUXVM_UTMCTL" file pull "$LINUXVM_UTM_NAME" \
            "$remote_status" >"$local_status" 2>/dev/null; then
            status="$(tr -d '\r\n' <"$local_status")"
            if [[ "$status" =~ ^[0-9]+$ ]]; then
                "$LINUXVM_UTMCTL" file pull "$LINUXVM_UTM_NAME" \
                    "$remote_stdout" 2>/dev/null || true
                if "$LINUXVM_UTMCTL" file pull "$LINUXVM_UTM_NAME" \
                    "$remote_stderr" >"$local_stderr" 2>/dev/null; then
                    cat "$local_stderr" >&2
                fi
                rm -rf "$local_dir"
                return "$status"
            fi
        fi
        sleep 1
    done

    rm -rf "$local_dir"
    printf 'Timed out after %ss waiting for guest command completion\n' \
        "$LINUXVM_EXEC_TIMEOUT" >&2
    return 124
}

guest_shell() {
    wait_for_guest_agent
    "$LINUXVM_UTMCTL" exec "$LINUXVM_UTM_NAME" --input \
        --cmd /usr/bin/bash -l
}

file_push() {
    if (( $# != 2 )); then
        printf 'Usage: linuxvm push LOCAL REMOTE\n' >&2
        return 2
    fi
    [[ -r "$1" ]] || { printf 'Unreadable local file: %s\n' "$1" >&2; return 1; }
    wait_for_guest_agent
    "$LINUXVM_UTMCTL" file push "$LINUXVM_UTM_NAME" "$2" <"$1"
}

file_pull() {
    if (( $# < 1 || $# > 2 )); then
        printf 'Usage: linuxvm pull REMOTE [LOCAL]\n' >&2
        return 2
    fi
    wait_for_guest_agent
    if (( $# == 2 )); then
        "$LINUXVM_UTMCTL" file pull "$LINUXVM_UTM_NAME" "$1" >"$2"
        printf '%s\n' "$2"
    else
        "$LINUXVM_UTMCTL" file pull "$LINUXVM_UTM_NAME" "$1"
    fi
}

input_text() {
    if (( $# != 1 )); then
        printf 'Usage: linuxvm type TEXT\n' >&2
        return 2
    fi
    /usr/bin/osascript - "$LINUXVM_UTM_NAME" "$1" <<'APPLESCRIPT'
on run argv
    tell application "UTM"
        set targetVM to first virtual machine whose name is item 1 of argv
        input keystroke targetVM text (item 2 of argv)
    end tell
end run
APPLESCRIPT
}

input_scan_codes() {
    if (( $# < 1 )); then
        printf 'Usage: linuxvm scan CODE...\n' >&2
        return 2
    fi
    local code
    for code in "$@"; do
        if [[ ! "$code" =~ ^[0-9]+$ || "$code" -gt 255 ]]; then
            printf 'Scan codes must be decimal bytes (0-255): %s\n' "$code" >&2
            return 2
        fi
    done
    /usr/bin/osascript - "$LINUXVM_UTM_NAME" "$@" <<'APPLESCRIPT'
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
    if (( $# != 1 )); then
        printf 'Usage: linuxvm key NAME\n' >&2
        return 2
    fi
    case "$1" in
        enter)       input_scan_codes 28 156 ;;
        escape)      input_scan_codes 1 129 ;;
        tab)         input_scan_codes 15 143 ;;
        ctrl-alt-t)  input_scan_codes 29 56 20 148 184 157 ;;
        super-d)     input_scan_codes 224 91 32 160 224 219 ;;
        alt-f4)      input_scan_codes 56 62 190 184 ;;
        ctrl-alt-delete) input_scan_codes 29 56 224 83 224 211 184 157 ;;
        *) printf 'Unknown key name: %s\n' "$1" >&2; return 2 ;;
    esac
}

host_control() {
    /usr/bin/swift "$PROVIDER_DIR/host-control.swift" "$@"
}

input_click() {
    if (( $# < 2 || $# > 3 )); then
        printf 'Usage: linuxvm click X Y [left|right|middle]\n' >&2
        return 2
    fi
    local button="${3:-left}"
    if [[ "$button" != "left" && "$button" != "right" && "$button" != "middle" ]]; then
        printf 'Unknown mouse button: %s\n' "$button" >&2
        return 2
    fi
    /usr/bin/osascript - "$LINUXVM_UTM_NAME" "$1" "$2" "$button" <<'APPLESCRIPT'
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

require_utmctl
command="${1:-}"
if [[ -n "$command" ]]; then shift; fi

case "$command" in
    status) vm_status ;;
    up)
        ensure_running
        if guest_agent_ready; then guest_ipv4; else printf 'started (guest agent unavailable)\n'; fi
        ;;
    ip) guest_ipv4 ;;
    exec) guest_exec "$@" ;;
    shell) guest_shell ;;
    push) file_push "$@" ;;
    pull) file_pull "$@" ;;
    screenshot) exec "$PROVIDER_DIR/screenshot" "$@" ;;
    click) input_click "$@" ;;
    drag) host_control drag "$LINUXVM_UTM_NAME" "$LINUXVM_DISPLAY_WIDTH" \
        "$LINUXVM_DISPLAY_HEIGHT" "$@" ;;
    type) input_text "$@" ;;
    key) input_key "$@" ;;
    scan) input_scan_codes "$@" ;;
    permissions) host_control permissions ;;
    window-info) host_control window-info "$LINUXVM_UTM_NAME" ;;
    suspend) "$LINUXVM_UTMCTL" suspend --save-state "$LINUXVM_UTM_NAME" ;;
    reboot) guest_reboot ;;
    shutdown) "$LINUXVM_UTMCTL" stop --request "$LINUXVM_UTM_NAME" ;;
    force-stop) "$LINUXVM_UTMCTL" stop --force "$LINUXVM_UTM_NAME" ;;
    disposable)
        [[ "$(vm_status)" == "stopped" ]] || {
            printf 'Disposable start requires a stopped VM\n' >&2; exit 1;
        }
        "$LINUXVM_UTMCTL" start "$LINUXVM_UTM_NAME" --disposable
        ;;
    clone)
        (( $# == 1 )) || { printf 'Usage: linuxvm clone NEW_NAME\n' >&2; exit 2; }
        "$LINUXVM_UTMCTL" clone "$LINUXVM_UTM_NAME" --name "$1"
        ;;
    *) usage >&2; exit 2 ;;
esac
