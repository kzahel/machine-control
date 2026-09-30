#!/usr/bin/env bash

# Shared configuration for host commands. Keep this safe to source from
# scripts that enable either `set -e` or `set -u`.

MACVM_REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MACVM_CONFIG_FILE="${MACVM_CONFIG_FILE:-$MACVM_REPO_DIR/config.local}"

# Preserve non-empty process-environment values so they take precedence over
# assignments in config.local.
macvm_config_names=(
    MACVM_NAME
    MACVM_TART
    MACVM_BOOT_TIMEOUT
    MACVM_SUSPENDABLE
    MACVM_CAPTURE_SYSTEM_KEYS
    MACVM_SHARE_REPO
    MACVM_GUEST_USER
    MACVM_ADMIN_SECRET_FILE
    MACVM_UI_REMOTE_RELATIVE
    MACVM_REQUIRE_MUTATION_GUARD
    MACVM_TARGET_ROLE
    MACVM_EXPECTED_NAME
    MACVM_FORBID_OUTER_UI
    MACVM_GUEST_TRANSPORT
    MACVM_SSH_HOST
    MACVM_SSH_USER
    MACVM_SSH_IDENTITY_FILE
    MACVM_SSH_STRICT_HOST_KEY_CHECKING
    MACVM_WORKSPACE_STATE_DIR
    MACVM_CLAIM_STATE_DIR
    MACVM_WORKSPACE_DEVELOPMENT_NAME
    MACVM_WORKSPACE_DEVELOPMENT_PROVEN
    MACVM_WORKSPACE_READY_BASE_NAME
    MACVM_WORKSPACE_READY_BASE_PROVEN
    MACVM_WORKSPACE_ALLOW_SHARED_BASE
    MACVM_WORKSPACE_STORAGE_PATH
    MACVM_WORKSPACE_MIN_FREE_BYTES
    MACVM_WORKSPACE_MAX_TEMPORARY
    MACVM_WORKSPACE_MAX_RETAINED
    MACVM_WORKSPACE_CANDIDATE_PREFIX
    MACVM_WORKSPACE_GUEST_TRANSPORT
    MACVM_CERTIFY_CHECK_TIMEOUT
)
macvm_environment_values=()
for macvm_config_name in "${macvm_config_names[@]}"; do
    macvm_environment_values+=("$(printenv "$macvm_config_name" 2>/dev/null || true)")
done

if [[ -f "$MACVM_CONFIG_FILE" ]]; then
    # shellcheck source=/dev/null
    source "$MACVM_CONFIG_FILE"
fi

for macvm_config_index in "${!macvm_config_names[@]}"; do
    macvm_environment_value="${macvm_environment_values[$macvm_config_index]}"
    if [[ -n "$macvm_environment_value" ]]; then
        printf -v "${macvm_config_names[$macvm_config_index]}" \
            '%s' "$macvm_environment_value"
    fi
done
unset macvm_config_index macvm_config_name macvm_config_names
unset macvm_environment_value macvm_environment_values

MACVM_NAME="${MACVM_NAME:-tahoe-base}"
MACVM_TART="${MACVM_TART:-/opt/homebrew/bin/tart}"
MACVM_BOOT_TIMEOUT="${MACVM_BOOT_TIMEOUT:-120}"
MACVM_SUSPENDABLE="${MACVM_SUSPENDABLE:-true}"
MACVM_CAPTURE_SYSTEM_KEYS="${MACVM_CAPTURE_SYSTEM_KEYS:-false}"
MACVM_SHARE_REPO="${MACVM_SHARE_REPO:-true}"
MACVM_GUEST_USER="${MACVM_GUEST_USER:-admin}"
MACVM_UI_REMOTE_RELATIVE="${MACVM_UI_REMOTE_RELATIVE:-Library/Application Support/macvm-testbed}"
MACVM_REQUIRE_MUTATION_GUARD="${MACVM_REQUIRE_MUTATION_GUARD:-true}"
MACVM_TARGET_ROLE="${MACVM_TARGET_ROLE:-unspecified}"
MACVM_EXPECTED_NAME="${MACVM_EXPECTED_NAME:-}"
MACVM_FORBID_OUTER_UI="${MACVM_FORBID_OUTER_UI:-false}"
MACVM_GUEST_TRANSPORT="${MACVM_GUEST_TRANSPORT:-tart}"
MACVM_SSH_HOST="${MACVM_SSH_HOST:-}"
MACVM_SSH_USER="${MACVM_SSH_USER:-$MACVM_GUEST_USER}"
MACVM_SSH_IDENTITY_FILE="${MACVM_SSH_IDENTITY_FILE:-}"
MACVM_SSH_STRICT_HOST_KEY_CHECKING="${MACVM_SSH_STRICT_HOST_KEY_CHECKING:-accept-new}"
MACVM_WORKSPACE_STATE_DIR="${MACVM_WORKSPACE_STATE_DIR:-${XDG_STATE_HOME:-$HOME/.local/state}/machine-control/macos-workspaces}"
MACVM_CLAIM_STATE_DIR="${MACVM_CLAIM_STATE_DIR:-$MACVM_WORKSPACE_STATE_DIR/claims}"
MACVM_WORKSPACE_DEVELOPMENT_NAME="${MACVM_WORKSPACE_DEVELOPMENT_NAME:-$MACVM_NAME}"
MACVM_WORKSPACE_DEVELOPMENT_PROVEN="${MACVM_WORKSPACE_DEVELOPMENT_PROVEN:-false}"
MACVM_WORKSPACE_READY_BASE_NAME="${MACVM_WORKSPACE_READY_BASE_NAME:-}"
MACVM_WORKSPACE_READY_BASE_PROVEN="${MACVM_WORKSPACE_READY_BASE_PROVEN:-false}"
MACVM_WORKSPACE_ALLOW_SHARED_BASE="${MACVM_WORKSPACE_ALLOW_SHARED_BASE:-false}"
MACVM_WORKSPACE_STORAGE_PATH="${MACVM_WORKSPACE_STORAGE_PATH:-${TART_HOME:-$HOME/.tart}}"
MACVM_WORKSPACE_MIN_FREE_BYTES="${MACVM_WORKSPACE_MIN_FREE_BYTES:-34359738368}"
MACVM_WORKSPACE_MAX_TEMPORARY="${MACVM_WORKSPACE_MAX_TEMPORARY:-1}"
MACVM_WORKSPACE_MAX_RETAINED="${MACVM_WORKSPACE_MAX_RETAINED:-2}"
MACVM_WORKSPACE_CANDIDATE_PREFIX="${MACVM_WORKSPACE_CANDIDATE_PREFIX:-machine-control-macos}"
MACVM_WORKSPACE_GUEST_TRANSPORT="${MACVM_WORKSPACE_GUEST_TRANSPORT:-tart}"
MACVM_CERTIFY_CHECK_TIMEOUT="${MACVM_CERTIFY_CHECK_TIMEOUT:-1200}"

macvm_apply_workspace_selection() {
    local handle="${MACHINE_CONTROL_WORKSPACE_HANDLE:-}"
    [[ -n "$handle" ]] || return 0
    # shellcheck source=../../../providers/workspaces/common.sh
    source "$MACVM_REPO_DIR/../../providers/workspaces/common.sh"
    workspace_require_tools || return
    local provider target_name target_id intent
    provider="$(workspace_receipt_field \
        "$MACVM_WORKSPACE_STATE_DIR" "$handle" provider)" || return
    if [[ "$provider" != "tart-macos" ]]; then
        printf 'Workspace receipt belongs to a different provider\n' >&2
        return 1
    fi
    target_name="$(workspace_receipt_field \
        "$MACVM_WORKSPACE_STATE_DIR" "$handle" target.name)" || return
    target_id="$(workspace_receipt_field \
        "$MACVM_WORKSPACE_STATE_DIR" "$handle" target.id)" || return
    intent="$(workspace_receipt_field \
        "$MACVM_WORKSPACE_STATE_DIR" "$handle" intent)" || return
    if [[ "$target_name" != "$target_id" ]]; then
        printf 'Workspace receipt target identity is invalid\n' >&2
        return 1
    fi
    MACVM_NAME="$target_name"
    MACVM_EXPECTED_NAME="$target_name"
    MACVM_REQUIRE_MUTATION_GUARD=true
    case "$intent" in
        persistent) MACVM_TARGET_ROLE=candidate ;;
        isolated) MACVM_TARGET_ROLE=disposable ;;
        candidate) MACVM_TARGET_ROLE=candidate ;;
        *) printf 'Workspace receipt intent is invalid\n' >&2; return 1 ;;
    esac
    if [[ "$intent" != "persistent" ]]; then
        MACVM_GUEST_TRANSPORT="$MACVM_WORKSPACE_GUEST_TRANSPORT"
        # A derivative has its own network identity. Never inherit a fixed
        # endpoint from the development VM; Tart or SSH must rediscover it.
        MACVM_SSH_HOST=""
    fi
}

macvm_apply_workspace_selection

export MACVM_REPO_DIR MACVM_CONFIG_FILE MACVM_NAME MACVM_TART
export MACVM_BOOT_TIMEOUT MACVM_SUSPENDABLE MACVM_CAPTURE_SYSTEM_KEYS
export MACVM_SHARE_REPO
export MACVM_GUEST_USER MACVM_ADMIN_SECRET_FILE MACVM_UI_REMOTE_RELATIVE
export MACVM_REQUIRE_MUTATION_GUARD MACVM_TARGET_ROLE MACVM_EXPECTED_NAME
export MACVM_FORBID_OUTER_UI
export MACVM_GUEST_TRANSPORT MACVM_SSH_HOST MACVM_SSH_USER
export MACVM_SSH_IDENTITY_FILE MACVM_SSH_STRICT_HOST_KEY_CHECKING
export MACVM_WORKSPACE_STATE_DIR MACVM_WORKSPACE_DEVELOPMENT_NAME
export MACVM_CLAIM_STATE_DIR
export MACVM_WORKSPACE_DEVELOPMENT_PROVEN
export MACVM_WORKSPACE_READY_BASE_NAME MACVM_WORKSPACE_READY_BASE_PROVEN
export MACVM_WORKSPACE_ALLOW_SHARED_BASE
export MACVM_WORKSPACE_STORAGE_PATH MACVM_WORKSPACE_MIN_FREE_BYTES
export MACVM_WORKSPACE_MAX_TEMPORARY MACVM_WORKSPACE_MAX_RETAINED
export MACVM_WORKSPACE_CANDIDATE_PREFIX MACVM_WORKSPACE_GUEST_TRANSPORT
export MACVM_CERTIFY_CHECK_TIMEOUT
export MACHINE_CONTROL_WORKSPACE_HANDLE

macvm_require_command() {
    if ! command -v "$1" >/dev/null 2>&1; then
        printf 'Required command not found: %s\n' "$1" >&2
        return 1
    fi
}

macvm_require_host() {
    if [[ "$(uname -s)" != "Darwin" ]]; then
        printf 'MacVM Testbed requires a macOS host\n' >&2
        return 1
    fi
    if [[ ! -x "$MACVM_TART" ]]; then
        printf 'Tart not found at %s\n' "$MACVM_TART" >&2
        return 1
    fi
}

macvm_get_json() {
    "$MACVM_TART" get "$MACVM_NAME" --format json
}

macvm_state() {
    macvm_get_json 2>/dev/null | jq -r '.State // "unknown"'
}

macvm_saved_state_path() {
    printf '%s/vms/%s/state.vzvmsave\n' "${TART_HOME:-$HOME/.tart}" "$MACVM_NAME"
}

# Virtualization.framework protects a saved VM state with the host user's
# keychain, so a restore fails with "permission denied" unless the controller
# user's console session is unlocked. Print that host session state:
# unlocked, locked, not_on_console, no_session, or unknown.
macvm_host_session_state() {
    local sessions
    if ! sessions="$("${MACVM_IOREG:-/usr/sbin/ioreg}" -n Root -d1 -a 2>/dev/null |
            /usr/bin/plutil -extract IOConsoleUsers json -o - - 2>/dev/null)"; then
        printf 'unknown\n'
        return 0
    fi
    jq -r --argjson uid "$(/usr/bin/id -u)" '
        [.[] | select(.kCGSSessionUserIDKey == $uid)] as $mine
        | [$mine[] | select(.kCGSSessionOnConsoleKey == true)] as $console
        | if ($mine | length) == 0 then "no_session"
          elif ($console | length) == 0 then "not_on_console"
          elif $console[0].CGSSessionScreenIsLocked == true then "locked"
          else "unlocked" end' <<<"$sessions" 2>/dev/null || printf 'unknown\n'
}

# Print whether someone may be using this host: attended, unattended, or
# unspecified. The common client passes the controller configuration's
# hostAttendance; direct use reads the same per-user file.
macvm_host_attendance() {
    local value="${MACHINE_CONTROL_HOST_ATTENDANCE:-}"
    local config="${XDG_CONFIG_HOME:-$HOME/.config}/machine-control/config.json"
    if [[ -z "$value" && -f "$config" ]]; then
        value="$(jq -r '.hostAttendance // empty' "$config" 2>/dev/null)" ||
            value=invalid
    fi
    case "${value:-unspecified}" in
        attended|unattended|unspecified) printf '%s\n' "${value:-unspecified}" ;;
        *) printf 'invalid\n' ;;
    esac
}

# Print one reason per line why a new suspend should not be taken. A suspend
# taken while the host is locked, on an unattended host, or on a controller
# configured not to suspend, may be impossible to resume.
macvm_suspend_blockers() {
    if [[ "$MACVM_SUSPENDABLE" != "true" ]]; then
        printf 'disabled_by_configuration\n'
    fi
    case "$(macvm_host_attendance)" in
        unattended) printf 'host_unattended\n' ;;
        invalid) printf 'host_attendance_invalid\n' ;;
    esac
    local host
    host="$(macvm_host_session_state)"
    if [[ "$host" != "unlocked" ]]; then
        printf 'host_session_%s\n' "$host"
    fi
}

macvm_display_size() {
    macvm_get_json | jq -r '.Display'
}

macvm_guest_ip() {
    case "$MACVM_GUEST_TRANSPORT" in
        tart)
            "$MACVM_TART" ip "$MACVM_NAME" --wait "$MACVM_BOOT_TIMEOUT" \
                --resolver agent
            ;;
        ssh)
            if [[ -n "$MACVM_SSH_HOST" ]]; then
                printf '%s\n' "$MACVM_SSH_HOST"
                return 0
            fi
            "$MACVM_TART" ip "$MACVM_NAME" --wait "$MACVM_BOOT_TIMEOUT" \
                --resolver arp 2>/dev/null \
                || "$MACVM_TART" ip "$MACVM_NAME" \
                    --wait "$MACVM_BOOT_TIMEOUT" --resolver dhcp
            ;;
        *)
            printf 'Unsupported guest transport: %s\n' \
                "$MACVM_GUEST_TRANSPORT" >&2
            return 2
            ;;
    esac
}

macvm_quote_remote_argument() {
    local value="${1//\'/\'\\\'\'}"
    printf "'%s'" "$value"
}

macvm_ssh_exec() {
    local -a options=(
        -o BatchMode=yes
        -o ConnectTimeout=10
        -o "StrictHostKeyChecking=$MACVM_SSH_STRICT_HOST_KEY_CHECKING"
    )
    if [[ -n "$MACVM_SSH_IDENTITY_FILE" ]]; then
        options+=(-i "$MACVM_SSH_IDENTITY_FILE")
    fi
    local remote_command='' argument
    for argument in "$@"; do
        if [[ -n "$remote_command" ]]; then
            remote_command+=' '
        fi
        remote_command+="$(macvm_quote_remote_argument "$argument")"
    done
    if [[ -z "$remote_command" ]]; then
        printf 'Guest command is required\n' >&2
        return 2
    fi
    command ssh "${options[@]}" \
        "$MACVM_SSH_USER@$(macvm_guest_ip)" "$remote_command"
}

macvm_exec() {
    local forward_stdin=false
    if [[ "${1:-}" == "-i" ]]; then
        forward_stdin=true
        shift
    fi
    case "$MACVM_GUEST_TRANSPORT" in
        tart)
            if [[ "$forward_stdin" == "true" ]]; then
                "$MACVM_TART" exec -i "$MACVM_NAME" "$@"
            else
                "$MACVM_TART" exec "$MACVM_NAME" "$@"
            fi
            ;;
        ssh)
            macvm_ssh_exec "$@"
            ;;
        *)
            printf 'Unsupported guest transport: %s\n' \
                "$MACVM_GUEST_TRANSPORT" >&2
            return 2
            ;;
    esac
}

macvm_guest_xcrun() {
    local guest_major guest_sdk
    guest_major="$(macvm_exec /usr/bin/sw_vers -productVersion)"
    guest_major="${guest_major%%.*}"
    guest_sdk="/Library/Developer/CommandLineTools/SDKs/MacOSX${guest_major}.sdk"
    if [[ "$guest_major" =~ ^[0-9]+$ ]] &&
            macvm_exec /bin/test -d "$guest_sdk"; then
        macvm_exec /usr/bin/env "SDKROOT=$guest_sdk" /usr/bin/xcrun "$@"
    else
        macvm_exec /usr/bin/xcrun "$@"
    fi
}

macvm_shell() {
    case "$MACVM_GUEST_TRANSPORT" in
        tart) "$MACVM_TART" exec -it "$MACVM_NAME" /bin/zsh -l ;;
        ssh)
            local -a options=(-t -o BatchMode=yes)
            if [[ -n "$MACVM_SSH_IDENTITY_FILE" ]]; then
                options+=(-i "$MACVM_SSH_IDENTITY_FILE")
            fi
            command ssh "${options[@]}" \
                "$MACVM_SSH_USER@$(macvm_guest_ip)" /bin/zsh -l
            ;;
        *)
            printf 'Unsupported guest transport: %s\n' \
                "$MACVM_GUEST_TRANSPORT" >&2
            return 2
            ;;
    esac
}

macvm_remote_ui_dir() {
    printf '/Users/%s/%s\n' "$MACVM_GUEST_USER" "$MACVM_UI_REMOTE_RELATIVE"
}

macvm_remote_ui_binary() {
    printf '%s/Contents/MacOS/macui\n' "$(macvm_remote_ui_app)"
}

# Guests run the same Machine Control.app, LaunchAgent, and socket as a
# physical host; only the root-owned deployment policy differs.
macvm_remote_ui_app() {
    printf '/Users/%s/Applications/Machine Control.app\n' "$MACVM_GUEST_USER"
}

macvm_remote_control_socket() {
    printf '/Users/%s/Library/Application Support/MachineControl/control.sock\n' \
        "$MACVM_GUEST_USER"
}

# The pre-shared testbed resident, retired by deploy-ui after the shared
# application holds its own consent.
macvm_remote_legacy_ui_app() {
    printf '/Users/%s/Applications/MacVM UI.app\n' "$MACVM_GUEST_USER"
}

macvm_remote_legacy_control_socket() {
    printf '/Users/%s/Library/Application Support/macvm-testbed/control.sock\n' \
        "$MACVM_GUEST_USER"
}

macvm_remote_legacy_resident_label() {
    printf 'com.kzahel.macvm-testbed.resident\n'
}

macvm_remote_control_cli() {
    printf '/Users/%s/bin/machine-control\n' "$MACVM_GUEST_USER"
}

macvm_remote_resident_label() {
    printf 'org.machine-control.resident\n'
}

macvm_remote_resident_plist() {
    printf '/Users/%s/Library/LaunchAgents/%s.plist\n' \
        "$MACVM_GUEST_USER" "$(macvm_remote_resident_label)"
}

macvm_remote_post_update_script() {
    printf '/Users/%s/Library/Application Support/macvm-testbed/post-update.sh\n' \
        "$MACVM_GUEST_USER"
}

macvm_resident_request() {
    macvm_exec "$(macvm_remote_ui_binary)" request \
        "$(macvm_remote_control_socket)" "$1"
}

macvm_assert_mutation_target() {
    if [[ "$MACVM_REQUIRE_MUTATION_GUARD" != "true" ]]; then
        return 0
    fi
    if [[ -z "$MACVM_EXPECTED_NAME" || "$MACVM_NAME" != "$MACVM_EXPECTED_NAME" ]]; then
        printf 'Refusing mutation: selected VM does not match the expected name\n' >&2
        return 1
    fi
    case "$MACVM_TARGET_ROLE" in
        candidate|disposable) ;;
        *)
            printf 'Refusing mutation: target role is %s, not candidate/disposable\n' \
                "$MACVM_TARGET_ROLE" >&2
            return 1
            ;;
    esac
}

macvm_assert_candidate_target() {
    macvm_assert_mutation_target
    if [[ "$MACVM_TARGET_ROLE" != candidate ]]; then
        printf 'Refusing mutation: target role is not candidate\n' >&2
        return 1
    fi
    if [[ -n "${MACHINE_CONTROL_WORKSPACE_HANDLE:-}" ]]; then
        printf 'Refusing candidate mutation through a workspace selector\n' >&2
        return 1
    fi
}

macvm_assert_outer_ui_allowed() {
    if [[ "$MACVM_FORBID_OUTER_UI" == "true" ]]; then
        printf '%s\n' \
            'Refusing host-side Tart screenshot/input: outer UI is forbidden' \
            >&2
        return 1
    fi
    case "$(macvm_host_attendance)" in
        attended)
            printf '%s\n' \
                'Refusing host-side Tart screenshot/input: the host is declared attended' \
                >&2
            return 1
            ;;
        invalid)
            printf '%s\n' \
                'Refusing host-side Tart screenshot/input: host attendance is invalid' \
                >&2
            return 1
            ;;
    esac
}

# Host input is posted to the global HID event stream. While the host session
# is locked it would reach the host lock screen instead of the VM.
macvm_assert_outer_input_allowed() {
    macvm_assert_outer_ui_allowed || return
    local host
    host="$(macvm_host_session_state)"
    if [[ "$host" != "unlocked" ]]; then
        printf 'Refusing host-side Tart input: the host session is %s\n' \
            "$host" >&2
        return 1
    fi
}
