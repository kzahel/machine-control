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

launchd_label() {
    local safe_name
    safe_name="$(printf '%s' "$MACVM_NAME" | tr -c 'A-Za-z0-9._-' '_')"
    printf 'app.macvm-testbed.tart.%s\n' "$safe_name"
}

launchd_domain() {
    printf 'gui/%s\n' "$(/usr/bin/id -u)"
}

launchd_runtime_dir() {
    local temp_root="${TMPDIR:-/tmp}"
    printf '%s/macvm-testbed/launchd\n' "${temp_root%/}"
}

xml_escape() {
    printf '%s' "$1" | /usr/bin/sed \
        -e 's/&/\&amp;/g' \
        -e 's/</\&lt;/g' \
        -e 's/>/\&gt;/g' \
        -e 's/"/\&quot;/g' \
        -e "s/'/\\\&apos;/g"
}

write_launchd_plist() {
    local plist_path="$1" label="$2" log_path="$3"
    shift 3
    local argument
    {
        printf '%s\n' '<?xml version="1.0" encoding="UTF-8"?>'
        printf '%s\n' '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">'
        printf '%s\n' '<plist version="1.0">' '<dict>'
        printf '  <key>Label</key>\n  <string>%s</string>\n' "$(xml_escape "$label")"
        printf '%s\n' '  <key>ProgramArguments</key>' '  <array>'
        for argument in "$@"; do
            printf '    <string>%s</string>\n' "$(xml_escape "$argument")"
        done
        printf '%s\n' '  </array>'
        printf '  <key>StandardOutPath</key>\n  <string>%s</string>\n' \
            "$(xml_escape "$log_path")"
        printf '  <key>StandardErrorPath</key>\n  <string>%s</string>\n' \
            "$(xml_escape "$log_path")"
        printf '%s\n' \
            '  <key>ProcessType</key>' '  <string>Interactive</string>' \
            '  <key>LimitLoadToSessionType</key>' '  <string>Aqua</string>' \
            '  <key>RunAtLoad</key>' '<true/>' \
            '  <key>KeepAlive</key>' '<false/>' \
            '</dict>' '</plist>'
    } >"$plist_path"
    /bin/chmod 600 "$plist_path"
    /usr/bin/plutil -lint "$plist_path" >/dev/null
}

unload_launchd_runner() {
    /bin/launchctl bootout "$(launchd_domain)/$(launchd_label)" \
        >/dev/null 2>&1 || true
}

start_launchd_runner() {
    local -a arguments=("$MACVM_TART" run "$@" "$MACVM_NAME")
    local runtime_dir label plist_path log_path
    runtime_dir="$(launchd_runtime_dir)"
    label="$(launchd_label)"
    plist_path="$runtime_dir/$label.plist"
    log_path="$runtime_dir/$label.log"

    /bin/mkdir -p "$runtime_dir"
    /bin/chmod 700 "$runtime_dir"
    unload_launchd_runner
    : >"$log_path"
    write_launchd_plist "$plist_path" "$label" "$log_path" "${arguments[@]}"
    /bin/launchctl bootstrap "$(launchd_domain)" "$plist_path"
    printf '%s\n' "$log_path"
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

    local log_path
    log_path="$(start_launchd_runner "${run_args[@]}")"

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
            unload_launchd_runner
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
    stop) "$MACVM_TART" stop "$MACVM_NAME" --timeout 30; unload_launchd_runner ;;
    force-stop) "$MACVM_TART" stop "$MACVM_NAME" --timeout 0; unload_launchd_runner ;;
    *) usage >&2; exit 2 ;;
esac
