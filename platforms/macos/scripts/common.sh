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
    MACVM_UI_REMOTE_RELATIVE
    MACVM_CONTROL_SOCKET_RELATIVE
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
MACVM_CONTROL_SOCKET_RELATIVE="${MACVM_CONTROL_SOCKET_RELATIVE:-Library/Application Support/macvm-testbed/control.sock}"
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
export MACVM_GUEST_USER MACVM_UI_REMOTE_RELATIVE
export MACVM_CONTROL_SOCKET_RELATIVE
export MACVM_REQUIRE_MUTATION_GUARD MACVM_TARGET_ROLE MACVM_EXPECTED_NAME
export MACVM_FORBID_OUTER_UI
export MACVM_GUEST_TRANSPORT MACVM_SSH_HOST MACVM_SSH_USER
export MACVM_SSH_IDENTITY_FILE MACVM_SSH_STRICT_HOST_KEY_CHECKING
export MACVM_WORKSPACE_STATE_DIR MACVM_WORKSPACE_DEVELOPMENT_NAME
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

macvm_display_size() {
    macvm_get_json | jq -r '.Display'
}

macvm_guest_ip() {
    if [[ -n "$MACVM_SSH_HOST" ]]; then
        printf '%s\n' "$MACVM_SSH_HOST"
        return 0
    fi
    if [[ "$MACVM_GUEST_TRANSPORT" == "tart" ]]; then
        "$MACVM_TART" ip "$MACVM_NAME" --wait "$MACVM_BOOT_TIMEOUT" \
            --resolver agent
        return
    fi
    "$MACVM_TART" ip "$MACVM_NAME" --wait "$MACVM_BOOT_TIMEOUT" \
        --resolver arp 2>/dev/null \
        || "$MACVM_TART" ip "$MACVM_NAME" --wait "$MACVM_BOOT_TIMEOUT" \
            --resolver dhcp
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

macvm_remote_ui_app() {
    printf '/Users/%s/Applications/MacVM UI.app\n' "$MACVM_GUEST_USER"
}

macvm_remote_control_socket() {
    printf '/Users/%s/%s\n' "$MACVM_GUEST_USER" \
        "$MACVM_CONTROL_SOCKET_RELATIVE"
}

macvm_remote_control_cli() {
    printf '/Users/%s/bin/machine-control\n' "$MACVM_GUEST_USER"
}

macvm_remote_resident_label() {
    printf 'com.kzahel.macvm-testbed.resident\n'
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
}
