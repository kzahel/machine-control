#!/usr/bin/env bash

set -euo pipefail

readonly PROVIDER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../../scripts/common.sh
source "$PROVIDER_DIR/../../scripts/common.sh"

usage() {
    cat <<'EOF'
Usage: provider.sh COMMAND [ARG...]

Internal Tart-on-macOS provider. Use bin/macvm instead.
EOF
}

ensure_running() {
    local state
    state="$(macvm_state || true)"
    if [[ "$state" == "running" ]]; then
        return 0
    fi
    if [[ "$state" == "unknown" || -z "$state" ]]; then
        printf 'Tart VM not found: %s\n' "$MACVM_NAME" >&2
        return 1
    fi

    local -a run_args=()
    if [[ "$MACVM_SUSPENDABLE" == "true" ]]; then
        run_args+=(--suspendable)
    fi
    if [[ "$MACVM_CAPTURE_SYSTEM_KEYS" == "true" ]]; then
        run_args+=(--capture-system-keys)
    fi
    if [[ "$MACVM_SHARE_REPO" == "true" ]]; then
        run_args+=(--dir="macvm-testbed:$MACVM_REPO_DIR:ro")
    fi

    local log_path="/tmp/macvm-${MACVM_NAME//[^A-Za-z0-9_.-]/_}.log"
    nohup "$MACVM_TART" run "${run_args[@]}" "$MACVM_NAME" \
        >"$log_path" 2>&1 &

    local deadline=$((SECONDS + MACVM_BOOT_TIMEOUT))
    while (( SECONDS < deadline )); do
        state="$(macvm_state || true)"
        if [[ "$state" == "running" ]]; then
            return 0
        fi
        sleep 1
    done

    printf 'Timed out waiting for Tart VM %s to start; see %s\n' \
        "$MACVM_NAME" "$log_path" >&2
    return 1
}

guest_ip() {
    ensure_running
    "$MACVM_TART" ip "$MACVM_NAME" --wait "$MACVM_BOOT_TIMEOUT" --resolver agent
}

display_parts() {
    local display
    display="$(macvm_display_size)"
    if [[ ! "$display" =~ ^([0-9]+)x([0-9]+)$ ]]; then
        printf 'Unexpected Tart display size: %s\n' "$display" >&2
        return 1
    fi
    printf '%s %s\n' "${BASH_REMATCH[1]}" "${BASH_REMATCH[2]}"
}

host_control() {
    /usr/bin/swift "$PROVIDER_DIR/host-control.swift" "$@"
}

input_click() {
    if [[ $# -lt 2 || $# -gt 3 ]]; then
        printf 'Usage: macvm click X Y [left|right|middle]\n' >&2
        return 2
    fi
    local button="${3:-left}"
    local width height
    read -r width height < <(display_parts)
    host_control click "$MACVM_NAME" "$width" "$height" "$1" "$2" "$button"
}

input_type() {
    if [[ $# -ne 1 ]]; then
        printf 'Usage: macvm type TEXT\n' >&2
        return 2
    fi
    host_control type "$MACVM_NAME" "$1"
}

input_drag() {
    if [[ $# -ne 4 ]]; then
        printf 'Usage: macvm drag X1 Y1 X2 Y2\n' >&2
        return 2
    fi
    local width height
    read -r width height < <(display_parts)
    host_control drag "$MACVM_NAME" "$width" "$height" "$@"
}

input_key() {
    if [[ $# -ne 1 ]]; then
        printf 'Usage: macvm key CHORD\n' >&2
        return 2
    fi
    host_control key "$MACVM_NAME" "$1"
}

guest_shutdown() {
    ensure_running
    # A successful halt closes the guest-agent transport before `tart exec`
    # can receive a normal exit status. Treat that disconnect as expected and
    # use the observed VM state below as the authoritative result.
    "$MACVM_TART" exec "$MACVM_NAME" /usr/bin/sudo /sbin/shutdown -h now \
        >/dev/null 2>&1 || true
    local deadline=$((SECONDS + MACVM_BOOT_TIMEOUT))
    while (( SECONDS < deadline )); do
        if [[ "$(macvm_state || true)" != "running" ]]; then
            return 0
        fi
        sleep 1
    done
    printf 'Guest did not shut down within %s seconds\n' "$MACVM_BOOT_TIMEOUT" >&2
    return 1
}

macvm_require_host
macvm_require_command jq

command="${1:-}"
if [[ -n "$command" ]]; then shift; fi

case "$command" in
    status) macvm_state ;;
    get) macvm_get_json ;;
    up) ensure_running; guest_ip ;;
    ip) guest_ip ;;
    screenshot) exec "$PROVIDER_DIR/screenshot" "$@" ;;
    click) input_click "$@" ;;
    drag) input_drag "$@" ;;
    type) input_type "$@" ;;
    key) input_key "$@" ;;
    suspend) "$MACVM_TART" suspend "$MACVM_NAME" ;;
    shutdown) guest_shutdown ;;
    stop) "$MACVM_TART" stop "$MACVM_NAME" --timeout 30 ;;
    force-stop) "$MACVM_TART" stop "$MACVM_NAME" --timeout 0 ;;
    *) usage >&2; exit 2 ;;
esac
