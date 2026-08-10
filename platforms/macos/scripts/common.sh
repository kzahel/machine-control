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
MACVM_CAPTURE_SYSTEM_KEYS="${MACVM_CAPTURE_SYSTEM_KEYS:-true}"
MACVM_SHARE_REPO="${MACVM_SHARE_REPO:-true}"
MACVM_GUEST_USER="${MACVM_GUEST_USER:-admin}"
MACVM_UI_REMOTE_RELATIVE="${MACVM_UI_REMOTE_RELATIVE:-Library/Application Support/macvm-testbed}"
MACVM_CONTROL_SOCKET_RELATIVE="${MACVM_CONTROL_SOCKET_RELATIVE:-Library/Application Support/macvm-testbed/control.sock}"
MACVM_REQUIRE_MUTATION_GUARD="${MACVM_REQUIRE_MUTATION_GUARD:-false}"
MACVM_TARGET_ROLE="${MACVM_TARGET_ROLE:-unspecified}"
MACVM_EXPECTED_NAME="${MACVM_EXPECTED_NAME:-}"
MACVM_FORBID_OUTER_UI="${MACVM_FORBID_OUTER_UI:-false}"
MACVM_GUEST_TRANSPORT="${MACVM_GUEST_TRANSPORT:-tart}"
MACVM_SSH_HOST="${MACVM_SSH_HOST:-}"
MACVM_SSH_USER="${MACVM_SSH_USER:-$MACVM_GUEST_USER}"
MACVM_SSH_IDENTITY_FILE="${MACVM_SSH_IDENTITY_FILE:-}"
MACVM_SSH_STRICT_HOST_KEY_CHECKING="${MACVM_SSH_STRICT_HOST_KEY_CHECKING:-accept-new}"

export MACVM_REPO_DIR MACVM_CONFIG_FILE MACVM_NAME MACVM_TART
export MACVM_BOOT_TIMEOUT MACVM_SUSPENDABLE MACVM_CAPTURE_SYSTEM_KEYS
export MACVM_SHARE_REPO
export MACVM_GUEST_USER MACVM_UI_REMOTE_RELATIVE
export MACVM_CONTROL_SOCKET_RELATIVE
export MACVM_REQUIRE_MUTATION_GUARD MACVM_TARGET_ROLE MACVM_EXPECTED_NAME
export MACVM_FORBID_OUTER_UI
export MACVM_GUEST_TRANSPORT MACVM_SSH_HOST MACVM_SSH_USER
export MACVM_SSH_IDENTITY_FILE MACVM_SSH_STRICT_HOST_KEY_CHECKING

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

macvm_assert_outer_ui_allowed() {
    if [[ "$MACVM_FORBID_OUTER_UI" == "true" ]]; then
        printf '%s\n' \
            'Refusing host-side Tart screenshot/input: outer UI is forbidden' \
            >&2
        return 1
    fi
}
