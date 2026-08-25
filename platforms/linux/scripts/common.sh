#!/usr/bin/env bash

# Shared configuration. Keep this safe to source under `set -e` and `set -u`.

LINUXVM_REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LINUXVM_CONFIG_FILE="${LINUXVM_CONFIG_FILE:-$LINUXVM_REPO_DIR/config.local}"

# Preserve non-empty process-environment values so callers can tighten local
# configuration for one command, especially the fail-closed outer-UI guard.
linuxvm_config_names=(
    LINUXVM_PROVIDER
    LINUXVM_UTM_NAME
    LINUXVM_UTMCTL
    LINUXVM_LIBVIRT_URI
    LINUXVM_LIBVIRT_DOMAIN_NAME
    LINUXVM_LIBVIRT_VIRSH
    LINUXVM_LIBVIRT_QEMU
    LINUXVM_LIBVIRT_NETWORK
    LINUXVM_LIBVIRT_POOL
    LINUXVM_LIBVIRT_MIN_FREE_BYTES
    LINUXVM_LIBVIRT_NVRAM_DIRECTORY
    LINUXVM_LIBVIRT_NVRAM_TEMPLATE
    LINUXVM_DESKTOP_USER
    LINUXVM_DISPLAY_WIDTH
    LINUXVM_DISPLAY_HEIGHT
    LINUXVM_BOOT_TIMEOUT
    LINUXVM_SHUTDOWN_TIMEOUT
    LINUXVM_EXEC_TIMEOUT
    LINUXVM_REMOTE_ROOT
    LINUXVM_UI_REMOTE
    LINUXVM_REQUIRE_MUTATION_GUARD
    LINUXVM_TARGET_ROLE
    LINUXVM_EXPECTED_NAME
    LINUXVM_EXPECTED_UUID
    LINUXVM_FORBID_OUTER_UI
    LINUXVM_WORKSPACE_STATE_DIR
    LINUXVM_CLAIM_STATE_DIR
    LINUXVM_WORKSPACE_DEVELOPMENT_NAME
    LINUXVM_WORKSPACE_DEVELOPMENT_ID
    LINUXVM_WORKSPACE_DEVELOPMENT_PROVEN
    LINUXVM_WORKSPACE_READY_BASE_NAME
    LINUXVM_WORKSPACE_READY_BASE_ID
    LINUXVM_WORKSPACE_READY_BASE_PROVEN
    LINUXVM_WORKSPACE_ALLOW_SHARED_BASE
    LINUXVM_WORKSPACE_STORAGE_PATH
    LINUXVM_WORKSPACE_MIN_FREE_BYTES
    LINUXVM_WORKSPACE_MAX_TEMPORARY
    LINUXVM_WORKSPACE_MAX_RETAINED
    LINUXVM_WORKSPACE_FULL_COPY_FALLBACK
    LINUXVM_WORKSPACE_ALLOW_FULL_COPY_ONCE
    LINUXVM_WORKSPACE_CANDIDATE_PREFIX
)
linuxvm_environment_values=()
for linuxvm_config_name in "${linuxvm_config_names[@]}"; do
    linuxvm_environment_values+=(
        "$(printenv "$linuxvm_config_name" 2>/dev/null || true)"
    )
done

if [[ -f "$LINUXVM_CONFIG_FILE" ]]; then
    # shellcheck source=/dev/null
    source "$LINUXVM_CONFIG_FILE"
fi

for linuxvm_config_index in "${!linuxvm_config_names[@]}"; do
    linuxvm_environment_value="${linuxvm_environment_values[$linuxvm_config_index]}"
    if [[ -n "$linuxvm_environment_value" ]]; then
        printf -v "${linuxvm_config_names[$linuxvm_config_index]}" \
            '%s' "$linuxvm_environment_value"
    fi
done
unset linuxvm_config_index linuxvm_config_name linuxvm_config_names
unset linuxvm_environment_value linuxvm_environment_values

LINUXVM_PROVIDER="${LINUXVM_PROVIDER:-utm-macos}"
LINUXVM_UTM_NAME="${LINUXVM_UTM_NAME:-Linux}"
LINUXVM_UTMCTL="${LINUXVM_UTMCTL:-/Applications/UTM.app/Contents/MacOS/utmctl}"
LINUXVM_LIBVIRT_URI="${LINUXVM_LIBVIRT_URI:-qemu:///system}"
LINUXVM_LIBVIRT_DOMAIN_NAME="${LINUXVM_LIBVIRT_DOMAIN_NAME:-$LINUXVM_UTM_NAME}"
LINUXVM_LIBVIRT_VIRSH="${LINUXVM_LIBVIRT_VIRSH:-virsh}"
LINUXVM_LIBVIRT_QEMU="${LINUXVM_LIBVIRT_QEMU:-qemu-system-x86_64}"
LINUXVM_LIBVIRT_NETWORK="${LINUXVM_LIBVIRT_NETWORK:-default}"
LINUXVM_LIBVIRT_POOL="${LINUXVM_LIBVIRT_POOL:-default}"
LINUXVM_LIBVIRT_MIN_FREE_BYTES="${LINUXVM_LIBVIRT_MIN_FREE_BYTES:-34359738368}"
LINUXVM_LIBVIRT_NVRAM_DIRECTORY="${LINUXVM_LIBVIRT_NVRAM_DIRECTORY:-/var/lib/libvirt/qemu/nvram}"
LINUXVM_LIBVIRT_NVRAM_TEMPLATE="${LINUXVM_LIBVIRT_NVRAM_TEMPLATE:-/usr/share/OVMF/OVMF_VARS_4M.ms.fd}"
LINUXVM_DESKTOP_USER="${LINUXVM_DESKTOP_USER:-}"
LINUXVM_DISPLAY_WIDTH="${LINUXVM_DISPLAY_WIDTH:-1280}"
LINUXVM_DISPLAY_HEIGHT="${LINUXVM_DISPLAY_HEIGHT:-800}"
LINUXVM_BOOT_TIMEOUT="${LINUXVM_BOOT_TIMEOUT:-120}"
LINUXVM_SHUTDOWN_TIMEOUT="${LINUXVM_SHUTDOWN_TIMEOUT:-120}"
LINUXVM_EXEC_TIMEOUT="${LINUXVM_EXEC_TIMEOUT:-300}"
LINUXVM_REMOTE_ROOT="${LINUXVM_REMOTE_ROOT:-/var/tmp/linuxvm-testbed}"
LINUXVM_UI_REMOTE="${LINUXVM_UI_REMOTE:-/usr/local/libexec/linuxvm-testbed/linuxui.py}"
LINUXVM_REQUIRE_MUTATION_GUARD="${LINUXVM_REQUIRE_MUTATION_GUARD:-true}"
LINUXVM_TARGET_ROLE="${LINUXVM_TARGET_ROLE:-unspecified}"
LINUXVM_EXPECTED_NAME="${LINUXVM_EXPECTED_NAME:-}"
LINUXVM_EXPECTED_UUID="${LINUXVM_EXPECTED_UUID:-}"
LINUXVM_FORBID_OUTER_UI="${LINUXVM_FORBID_OUTER_UI:-false}"
LINUXVM_WORKSPACE_STATE_DIR="${LINUXVM_WORKSPACE_STATE_DIR:-${XDG_STATE_HOME:-$HOME/.local/state}/machine-control/linux-workspaces}"
LINUXVM_CLAIM_STATE_DIR="${LINUXVM_CLAIM_STATE_DIR:-$LINUXVM_WORKSPACE_STATE_DIR/claims}"
LINUXVM_WORKSPACE_DEVELOPMENT_NAME="${LINUXVM_WORKSPACE_DEVELOPMENT_NAME:-$LINUXVM_UTM_NAME}"
LINUXVM_WORKSPACE_DEVELOPMENT_ID="${LINUXVM_WORKSPACE_DEVELOPMENT_ID:-$LINUXVM_EXPECTED_UUID}"
LINUXVM_WORKSPACE_DEVELOPMENT_PROVEN="${LINUXVM_WORKSPACE_DEVELOPMENT_PROVEN:-false}"
LINUXVM_WORKSPACE_READY_BASE_NAME="${LINUXVM_WORKSPACE_READY_BASE_NAME:-}"
LINUXVM_WORKSPACE_READY_BASE_ID="${LINUXVM_WORKSPACE_READY_BASE_ID:-}"
LINUXVM_WORKSPACE_READY_BASE_PROVEN="${LINUXVM_WORKSPACE_READY_BASE_PROVEN:-false}"
LINUXVM_WORKSPACE_ALLOW_SHARED_BASE="${LINUXVM_WORKSPACE_ALLOW_SHARED_BASE:-false}"
LINUXVM_WORKSPACE_STORAGE_PATH="${LINUXVM_WORKSPACE_STORAGE_PATH:-}"
LINUXVM_WORKSPACE_MIN_FREE_BYTES="${LINUXVM_WORKSPACE_MIN_FREE_BYTES:-34359738368}"
LINUXVM_WORKSPACE_MAX_TEMPORARY="${LINUXVM_WORKSPACE_MAX_TEMPORARY:-1}"
LINUXVM_WORKSPACE_MAX_RETAINED="${LINUXVM_WORKSPACE_MAX_RETAINED:-2}"
LINUXVM_WORKSPACE_FULL_COPY_FALLBACK="${LINUXVM_WORKSPACE_FULL_COPY_FALLBACK:-prohibited}"
LINUXVM_WORKSPACE_ALLOW_FULL_COPY_ONCE="${LINUXVM_WORKSPACE_ALLOW_FULL_COPY_ONCE:-0}"
LINUXVM_WORKSPACE_CANDIDATE_PREFIX="${LINUXVM_WORKSPACE_CANDIDATE_PREFIX:-machine-control-linux}"

linuxvm_apply_workspace_selection() {
    local handle="${MACHINE_CONTROL_WORKSPACE_HANDLE:-}"
    [[ -n "$handle" ]] || return 0
    # shellcheck source=../../../providers/workspaces/common.sh
    source "$LINUXVM_REPO_DIR/../../providers/workspaces/common.sh"
    workspace_require_tools || return
    local provider target_name target_id intent
    provider="$(workspace_receipt_field \
        "$LINUXVM_WORKSPACE_STATE_DIR" "$handle" provider)" || return
    if [[ "$provider" != "$LINUXVM_PROVIDER-linux" ]]; then
        printf 'Workspace receipt belongs to a different provider\n' >&2
        return 1
    fi
    target_name="$(workspace_receipt_field \
        "$LINUXVM_WORKSPACE_STATE_DIR" "$handle" target.name)" || return
    target_id="$(workspace_receipt_field \
        "$LINUXVM_WORKSPACE_STATE_DIR" "$handle" target.id)" || return
    intent="$(workspace_receipt_field \
        "$LINUXVM_WORKSPACE_STATE_DIR" "$handle" intent)" || return
    LINUXVM_UTM_NAME="$target_name"
    LINUXVM_LIBVIRT_DOMAIN_NAME="$target_name"
    LINUXVM_EXPECTED_NAME="$target_name"
    LINUXVM_EXPECTED_UUID="$target_id"
    LINUXVM_REQUIRE_MUTATION_GUARD=true
    case "$intent" in
        persistent|candidate) LINUXVM_TARGET_ROLE=candidate ;;
        isolated) LINUXVM_TARGET_ROLE=disposable ;;
        *) printf 'Workspace receipt intent is invalid\n' >&2; return 1 ;;
    esac
}

linuxvm_apply_workspace_selection

export LINUXVM_REPO_DIR LINUXVM_CONFIG_FILE LINUXVM_PROVIDER
export LINUXVM_UTM_NAME LINUXVM_UTMCTL LINUXVM_DESKTOP_USER
export LINUXVM_LIBVIRT_URI LINUXVM_LIBVIRT_DOMAIN_NAME
export LINUXVM_LIBVIRT_VIRSH LINUXVM_LIBVIRT_QEMU
export LINUXVM_LIBVIRT_NETWORK LINUXVM_LIBVIRT_POOL
export LINUXVM_LIBVIRT_MIN_FREE_BYTES
export LINUXVM_LIBVIRT_NVRAM_DIRECTORY LINUXVM_LIBVIRT_NVRAM_TEMPLATE
export LINUXVM_DISPLAY_WIDTH LINUXVM_DISPLAY_HEIGHT
export LINUXVM_BOOT_TIMEOUT LINUXVM_SHUTDOWN_TIMEOUT LINUXVM_EXEC_TIMEOUT
export LINUXVM_REMOTE_ROOT LINUXVM_UI_REMOTE
export LINUXVM_REQUIRE_MUTATION_GUARD LINUXVM_TARGET_ROLE
export LINUXVM_EXPECTED_NAME LINUXVM_EXPECTED_UUID LINUXVM_FORBID_OUTER_UI
export LINUXVM_WORKSPACE_STATE_DIR LINUXVM_WORKSPACE_DEVELOPMENT_NAME
export LINUXVM_CLAIM_STATE_DIR
export LINUXVM_WORKSPACE_DEVELOPMENT_ID LINUXVM_WORKSPACE_DEVELOPMENT_PROVEN
export LINUXVM_WORKSPACE_READY_BASE_NAME LINUXVM_WORKSPACE_READY_BASE_ID
export LINUXVM_WORKSPACE_READY_BASE_PROVEN LINUXVM_WORKSPACE_STORAGE_PATH
export LINUXVM_WORKSPACE_ALLOW_SHARED_BASE
export LINUXVM_WORKSPACE_MIN_FREE_BYTES LINUXVM_WORKSPACE_MAX_TEMPORARY
export LINUXVM_WORKSPACE_MAX_RETAINED LINUXVM_WORKSPACE_FULL_COPY_FALLBACK
export LINUXVM_WORKSPACE_ALLOW_FULL_COPY_ONCE LINUXVM_WORKSPACE_CANDIDATE_PREFIX
export MACHINE_CONTROL_WORKSPACE_HANDLE

linuxvm_provider_path() {
    printf '%s/providers/%s/provider.sh\n' "$LINUXVM_REPO_DIR" "$LINUXVM_PROVIDER"
}

linuxvm_require_command() {
    if ! command -v "$1" >/dev/null 2>&1; then
        printf 'Required command not found: %s\n' "$1" >&2
        return 1
    fi
}

linuxvm_selected_uuid() {
    "$LINUXVM_UTMCTL" list | /usr/bin/awk -v expected="$LINUXVM_UTM_NAME" '
        NR > 1 {
            uuid = $1
            $1 = ""
            $2 = ""
            sub(/^[[:space:]]+/, "")
            if ($0 == expected) {
                print uuid
                exit
            }
        }'
}

linuxvm_assert_mutation_target() {
    if [[ "$LINUXVM_REQUIRE_MUTATION_GUARD" != "true" ]]; then
        return 0
    fi
    if [[ -z "$LINUXVM_EXPECTED_NAME" ||
          "$LINUXVM_UTM_NAME" != "$LINUXVM_EXPECTED_NAME" ]]; then
        printf 'Refusing mutation: selected VM does not match the expected name\n' >&2
        return 1
    fi
    if [[ -z "$LINUXVM_EXPECTED_UUID" ||
          "$(linuxvm_selected_uuid)" != "$LINUXVM_EXPECTED_UUID" ]]; then
        printf 'Refusing mutation: selected VM does not match the expected UUID\n' >&2
        return 1
    fi
    case "$LINUXVM_TARGET_ROLE" in
        candidate|disposable) ;;
        *)
            printf 'Refusing mutation: target role is not candidate/disposable\n' >&2
            return 1
            ;;
    esac
}

linuxvm_assert_candidate_target() {
    linuxvm_assert_mutation_target || return
    if [[ "$LINUXVM_TARGET_ROLE" != candidate ]]; then
        printf 'Refusing operation: exact target role is not candidate\n' >&2
        return 1
    fi
}

linuxvm_assert_outer_ui_allowed() {
    if [[ "$LINUXVM_FORBID_OUTER_UI" == "true" ]]; then
        printf 'Outer UTM capture/input is prohibited for this operation\n' >&2
        return 1
    fi
}
