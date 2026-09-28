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

launchd_runner_running() {
    /bin/launchctl print "$(launchd_domain)/$(launchd_label)" 2>/dev/null |
        /usr/bin/grep -Eq '^[[:space:]]*state = running'
}

# True once launchd has run the job and it is no longer running.
launchd_runner_exited() {
    local description
    description="$(/bin/launchctl print "$(launchd_domain)/$(launchd_label)" \
        2>/dev/null)" || return 1
    /usr/bin/grep -Eq '^[[:space:]]*runs = [1-9]' <<<"$description" &&
        ! /usr/bin/grep -Eq '^[[:space:]]*state = running' <<<"$description"
}

report_runner_exit() {
    local log_path="$1"
    printf 'Tart exited before VM %s started; see %s\n' \
        "$MACVM_NAME" "$log_path" >&2
    /usr/bin/tail -n 3 "$log_path" >&2 || true
    if /usr/bin/grep -q 'failed to restore' "$log_path" 2>/dev/null; then
        printf '%s\n' \
            "Restoring the saved suspend state failed. Virtualization.framework" \
            "protects saved state with the host keychain, so a restore needs the" \
            "host user's console session unlocked (host session is now:" \
            "$(macvm_host_session_state)). Resume from an unlocked host, or run" \
            "'macvm discard-suspended-state' to cold boot from disk instead." >&2
    fi
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
    macvm_assert_mutation_target
    if [[ "$state" == "suspended" && "$MACVM_SUSPENDABLE" != "true" ]]; then
        printf '%s\n' \
            "VM $MACVM_NAME holds a suspend state saved from a suspendable run," \
            "which cannot be restored while MACVM_SUSPENDABLE=false. Set it to" \
            "true on an unlocked host to resume, or run" \
            "'macvm discard-suspended-state' to cold boot from disk." >&2
        return 3
    fi

    local -a run_args=()
    if [[ "$MACVM_SUSPENDABLE" == "true" ]]; then
        run_args+=(--suspendable)
    fi
    if [[ "$MACVM_CAPTURE_SYSTEM_KEYS" == "true" &&
          "$MACVM_FORBID_OUTER_UI" != "true" ]]; then
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
        if launchd_runner_exited; then
            report_runner_exit "$log_path"
            return 1
        fi
        sleep 1
    done

    printf 'Timed out waiting for Tart VM %s to start; see %s\n' \
        "$MACVM_NAME" "$log_path" >&2
    return 1
}

suspend_vm() {
    macvm_assert_mutation_target
    local blockers
    blockers="$(macvm_suspend_blockers)"
    if [[ -n "$blockers" ]]; then
        printf 'Refusing to suspend %s: %s\n' "$MACVM_NAME" \
            "$(/usr/bin/paste -sd, - <<<"$blockers")" >&2
        printf '%s\n' \
            "A saved state can be restored only while the host session is" \
            "unlocked. Use shutdown to park the VM instead." >&2
        return 3
    fi
    "$MACVM_TART" suspend "$MACVM_NAME"
    # `tart suspend` returns while the runner is still writing the snapshot.
    # Wait until Tart reports the saved state so a following `up` cannot
    # replace the runner mid-write.
    local deadline=$((SECONDS + MACVM_BOOT_TIMEOUT))
    while (( SECONDS < deadline )); do
        if [[ "$(macvm_state || true)" == "suspended" ]] &&
                ! launchd_runner_running; then
            return 0
        fi
        sleep 1
    done
    printf 'Tart did not finish suspending %s within %s seconds\n' \
        "$MACVM_NAME" "$MACVM_BOOT_TIMEOUT" >&2
    return 1
}

discard_suspended_state() {
    macvm_assert_mutation_target
    local state saved_state
    state="$(macvm_state || true)"
    if [[ "$state" != "suspended" ]] || launchd_runner_running; then
        printf 'VM %s is not suspended (state: %s)\n' "$MACVM_NAME" "$state" >&2
        return 3
    fi
    saved_state="$(macvm_saved_state_path)"
    if [[ ! -f "$saved_state" ]]; then
        printf 'No saved suspend state found for %s\n' "$MACVM_NAME" >&2
        return 1
    fi
    # The guest loses its suspended memory, as after a power loss; its disk
    # is kept and the next `up` cold boots.
    /bin/rm -f "$saved_state"
    unload_launchd_runner
    macvm_state
}

guest_ip() {
    ensure_running
    macvm_guest_ip
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
    macvm_assert_outer_input_allowed
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
    macvm_assert_outer_input_allowed
    if [[ $# -ne 1 ]]; then
        printf 'Usage: macvm type TEXT\n' >&2
        return 2
    fi
    host_control type "$MACVM_NAME" "$1"
}

input_secret() {
    macvm_assert_outer_input_allowed
    macvm_assert_candidate_target
    [[ $# -eq 0 ]] || {
        printf 'Usage: macvm type-secret\n' >&2
        return 2
    }
    local secret_file="${MACVM_ADMIN_SECRET_FILE:-}"
    if [[ -z "$secret_file" || ! -f "$secret_file" || -L "$secret_file" ||
          "$(/usr/bin/stat -f %Lp "$secret_file" 2>/dev/null)" != 600 ||
          "$(/usr/bin/stat -f %u "$secret_file" 2>/dev/null)" != "$(/usr/bin/id -u)" ||
          "$(/usr/bin/stat -f %z "$secret_file" 2>/dev/null)" == 0 ]]; then
        printf 'A nonempty owner-only guest credential file is required\n' >&2
        return 1
    fi
    host_control type-secret "$MACVM_NAME" < "$secret_file"
}

input_drag() {
    macvm_assert_outer_input_allowed
    if [[ $# -ne 4 ]]; then
        printf 'Usage: macvm drag X1 Y1 X2 Y2\n' >&2
        return 2
    fi
    local width height
    read -r width height < <(display_parts)
    host_control drag "$MACVM_NAME" "$width" "$height" "$@"
}

input_key() {
    macvm_assert_outer_input_allowed
    if [[ $# -ne 1 ]]; then
        printf 'Usage: macvm key CHORD\n' >&2
        return 2
    fi
    host_control key "$MACVM_NAME" "$1"
}

guest_shutdown() {
    macvm_assert_mutation_target
    ensure_running
    # A successful halt closes the guest-agent transport before `tart exec`
    # can receive a normal exit status. Treat that disconnect as expected and
    # use the observed VM state below as the authoritative result.
    macvm_exec /usr/bin/sudo /sbin/shutdown -h now \
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
    host-state) host_control state ;;
    host-permissions) host_control permissions ;;
    up) ensure_running; macvm_state ;;
    ip) guest_ip ;;
    screenshot) exec "$PROVIDER_DIR/screenshot" "$@" ;;
    click) input_click "$@" ;;
    drag) input_drag "$@" ;;
    type) input_type "$@" ;;
    type-secret) input_secret "$@" ;;
    key) input_key "$@" ;;
    suspend) suspend_vm ;;
    discard-suspended-state) discard_suspended_state ;;
    shutdown) guest_shutdown ;;
    stop)
        macvm_assert_mutation_target
        "$MACVM_TART" stop "$MACVM_NAME" --timeout 30
        unload_launchd_runner
        ;;
    force-stop)
        macvm_assert_mutation_target
        "$MACVM_TART" stop "$MACVM_NAME" --timeout 0
        unload_launchd_runner
        ;;
    *) usage >&2; exit 2 ;;
esac
