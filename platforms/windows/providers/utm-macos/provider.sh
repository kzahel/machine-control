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

utm_configuration_devices() {
    "$WINVM_OSASCRIPT" - "$WINVM_UTM_NAME" <<'APPLESCRIPT'
on run argv
    set vmName to item 1 of argv
    tell application "UTM"
        set targetVM to first virtual machine whose name is vmName
        set vmConfig to configuration of targetVM
        set outputLines to {}
        repeat with displayConfig in displays of vmConfig
            set end of outputLines to "display\t" & (hardware of displayConfig as text)
        end repeat
        repeat with driveConfig in drives of vmConfig
            set end of outputLines to "drive\t" & (interface of driveConfig as text)
        end repeat
    end tell
    set AppleScript's text item delimiters to linefeed
    return outputLines as text
end run
APPLESCRIPT
}

detect_suspend_capability() {
    SUSPEND_AVAILABILITY="unknown"
    SUSPEND_SOURCE="policy"
    SUSPEND_REASONS=()

    case "$WINVM_SUSPEND_POLICY" in
        enabled)
            SUSPEND_AVAILABILITY="available"
            SUSPEND_SOURCE="configured"
            return
            ;;
        disabled)
            SUSPEND_AVAILABILITY="unavailable"
            SUSPEND_SOURCE="configured"
            SUSPEND_REASONS+=("configured-disabled")
            return
            ;;
        auto) ;;
        *)
            printf 'Invalid WINVM_SUSPEND_POLICY: %s (expected auto, enabled, or disabled)\n' \
                "$WINVM_SUSPEND_POLICY" >&2
            return 2
            ;;
    esac

    SUSPEND_SOURCE="utm-configuration"
    local devices kind hardware normalized
    if ! devices="$(utm_configuration_devices 2>/dev/null)"; then
        SUSPEND_REASONS+=("utm-configuration-unavailable")
        return
    fi

    local found_gpu=0 found_nvme=0
    while IFS=$'\t' read -r kind hardware; do
        normalized="$(printf '%s' "$hardware" | tr '[:upper:]' '[:lower:]')"
        if [[ "$kind" == "display" && "$normalized" == *-gl* && "$found_gpu" -eq 0 ]]; then
            SUSPEND_REASONS+=("utm-qemu-gpu-display")
            found_gpu=1
        elif [[ "$kind" == "drive" && "$normalized" == "nvme" && "$found_nvme" -eq 0 ]]; then
            SUSPEND_REASONS+=("utm-qemu-nvme-disk")
            found_nvme=1
        fi
    done <<< "$devices"

    if (( ${#SUSPEND_REASONS[@]} > 0 )); then
        SUSPEND_AVAILABILITY="unavailable"
    else
        # UTM documents common blockers but does not expose a definitive
        # per-VM capability. Absence of a known blocker is not proof.
        SUSPEND_REASONS+=("utm-support-not-declared")
    fi
}

default_down_action() {
    if [[ "$SUSPEND_AVAILABILITY" == "available" ]]; then
        printf 'suspend\n'
    else
        printf 'guest-shutdown\n'
    fi
}

provider_capabilities() {
    local output_format="human"
    case "${1:-}" in
        "") ;;
        --json) output_format="json" ;;
        *)
            printf 'Usage: winvm capabilities [--json]\n' >&2
            return 2
            ;;
    esac

    detect_suspend_capability || return
    local action state reasons_json='[]'
    action="$(default_down_action)"
    state="$(vm_status || printf 'unknown\n')"

    if [[ "$output_format" == "json" ]]; then
        winvm_require_command jq || return
        if (( ${#SUSPEND_REASONS[@]} > 0 )); then
            reasons_json="$(printf '%s\n' "${SUSPEND_REASONS[@]}" | jq -R . | jq -s .)"
        fi
        jq -n \
            --arg state "$state" \
            --arg availability "$SUSPEND_AVAILABILITY" \
            --arg source "$SUSPEND_SOURCE" \
            --argjson reasons "$reasons_json" \
            --arg action "$action" \
            '{schema_version: 1, state: $state, lifecycle: {suspend: {availability: $availability, source: $source, reasons: $reasons}, default_down_action: $action, seal: {availability: "available", kind: "full_clone", requires: ["source_stopped", "destination_unregistered"]}, disposable_start: {availability: "available", persistence: "discard_on_stop"}, delete: {availability: "available", requires: ["configured_target_stopped", "exact_name_confirmation"]}}}'
        return
    fi

    printf 'suspend: %s\n' "$SUSPEND_AVAILABILITY"
    local reason
    for reason in "${SUSPEND_REASONS[@]}"; do
        printf 'suspend-reason: %s\n' "$reason"
    done
    printf 'default-down-action: %s\n' "$action"
    printf 'seal: available (stopped full clone)\n'
    printf 'disposable-start: available (discard on stop)\n'
    printf 'delete: available (stopped exact-name confirmation)\n'
}

vm_is_registered() {
    "$WINVM_UTMCTL" status "$1" >/dev/null 2>&1
}

vm_seal() {
    if [[ $# -ne 1 || -z "$1" ]]; then
        printf 'Usage: winvm seal DESTINATION_NAME\n' >&2
        return 2
    fi
    local destination="$1" status
    if [[ "$destination" == "$WINVM_UTM_NAME" ]]; then
        printf 'Seal destination must differ from the configured source VM.\n' >&2
        return 2
    fi
    status="$(vm_status || true)"
    if [[ "$status" != "stopped" ]]; then
        printf 'Seal requires a stopped source VM (current state: %s).\n' \
            "${status:-unknown}" >&2
        return 1
    fi
    if vm_is_registered "$destination"; then
        printf 'Seal destination is already registered.\n' >&2
        return 1
    fi
    "$WINVM_UTMCTL" clone --hide "$WINVM_UTM_NAME" --name "$destination" \
        >/dev/null
    status="$("$WINVM_UTMCTL" status "$destination" 2>/dev/null || true)"
    if [[ "$status" != "stopped" ]]; then
        printf 'UTM did not produce a stopped seal (state: %s).\n' \
            "${status:-unknown}" >&2
        return 1
    fi
    printf 'sealed\n'
}

vm_disposable_up() {
    local status
    status="$(vm_status || true)"
    if [[ "$status" != "stopped" ]]; then
        printf 'Disposable start requires a stopped VM (current state: %s).\n' \
            "${status:-unknown}" >&2
        return 1
    fi
    "$WINVM_UTMCTL" start --hide "$WINVM_UTM_NAME" --disposable >/dev/null
    if ! wait_for_vm_state started "$WINVM_BOOT_TIMEOUT"; then
        printf 'Timed out waiting for disposable VM start (last state: %s).\n' \
            "${LAST_VM_STATUS:-unknown}" >&2
        return 1
    fi
    guest_ipv4
}

vm_delete() {
    if [[ $# -ne 2 || "$1" != "--confirm" || -z "$2" ]]; then
        printf 'Usage: winvm delete --confirm CONFIGURED_VM_NAME\n' >&2
        return 2
    fi
    local confirmation="$2" status
    if [[ "$confirmation" != "$WINVM_UTM_NAME" ]]; then
        printf 'Delete confirmation does not match the configured VM.\n' >&2
        return 2
    fi
    status="$(vm_status || true)"
    if [[ "$status" != "stopped" ]]; then
        printf 'Delete requires the configured VM to be stopped (state: %s).\n' \
            "${status:-unknown}" >&2
        return 1
    fi
    "$WINVM_UTMCTL" delete "$WINVM_UTM_NAME" >/dev/null
    if vm_is_registered "$WINVM_UTM_NAME"; then
        printf 'UTM still reports the deleted VM as registered.\n' >&2
        return 1
    fi
    printf 'deleted\n'
}

print_suspend_unavailable() {
    local joined=""
    if (( ${#SUSPEND_REASONS[@]} > 0 )); then
        joined="$(IFS=,; printf '%s' "${SUSPEND_REASONS[*]}")"
    fi
    printf 'Suspend is %s for this VM%s; use: winvm down\n' \
        "$SUSPEND_AVAILABILITY" "${joined:+ ($joined)}" >&2
}

vm_suspend() {
    detect_suspend_capability || return
    if [[ "$SUSPEND_AVAILABILITY" != "available" ]]; then
        print_suspend_unavailable
        return 1
    fi
    "$WINVM_UTMCTL" suspend --save-state "$WINVM_UTM_NAME"
}

wait_for_vm_state() {
    local expected="$1" timeout="$2"
    local deadline=$((SECONDS + timeout)) status="unknown"
    while (( SECONDS < deadline )); do
        status="$(vm_status || true)"
        if [[ "$status" == "$expected" ]]; then
            return 0
        fi
        sleep 1
    done
    LAST_VM_STATUS="$status"
    return 1
}

vm_shutdown() {
    local status
    status="$(vm_status || true)"
    if [[ "$status" == "stopped" ]]; then
        printf 'stopped\n'
        return
    fi
    if [[ "$status" != "started" ]]; then
        ensure_running
    fi

    # Prefer a shutdown initiated by Windows. An SSH disconnect is expected as
    # the guest exits, so provider state is the authoritative result.
    "$WINVM_SSH_BIN" \
        -o BatchMode=yes \
        -o ConnectTimeout=10 \
        "$WINVM_SSH_HOST" \
        'shutdown.exe /s /t 0' >/dev/null 2>&1 || true

    if wait_for_vm_state stopped "$WINVM_GUEST_SHUTDOWN_GRACE"; then
        printf 'stopped\n'
        return
    fi

    # Requesting power-down is the non-destructive provider fallback. Never
    # promote a routine shutdown to force-stop.
    "$WINVM_UTMCTL" stop --request "$WINVM_UTM_NAME" >/dev/null
    if wait_for_vm_state stopped "$WINVM_SHUTDOWN_TIMEOUT"; then
        printf 'stopped\n'
        return
    fi

    printf 'Timed out waiting for UTM VM %s to shut down (last status: %s)\n' \
        "$WINVM_UTM_NAME" "${LAST_VM_STATUS:-unknown}" >&2
    return 1
}

vm_down() {
    if [[ "$(vm_status || true)" == "stopped" ]]; then
        printf 'stopped\n'
        return
    fi
    detect_suspend_capability || return
    if [[ "$SUSPEND_AVAILABILITY" == "available" ]]; then
        vm_suspend
    else
        vm_shutdown
    fi
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
    capabilities) provider_capabilities "$@" ;;
    up|ip) guest_ipv4 ;;
    screenshot) exec "$PROVIDER_DIR/screenshot" "$@" ;;
    type) input_text "$@" ;;
    click) input_click "$@" ;;
    key) input_key "$@" ;;
    scan) input_scan_codes "$@" ;;
    stage-bootstrap) stage_bootstrap "$@" ;;
    seal) vm_seal "$@" ;;
    disposable-up) vm_disposable_up "$@" ;;
    delete) vm_delete "$@" ;;
    down) vm_down ;;
    suspend) vm_suspend ;;
    shutdown) vm_shutdown ;;
    force-stop) "$WINVM_UTMCTL" stop --force "$WINVM_UTM_NAME" ;;
    *) usage >&2; exit 2 ;;
esac
