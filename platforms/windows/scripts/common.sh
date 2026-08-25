#!/usr/bin/env bash

# Shared configuration for host commands. Keep this file safe to source from
# scripts that enable either `set -e` or `set -u`.

WINVM_ENVIRONMENT_OVERRIDES=()
while IFS= read -r winvm_environment_name; do
    WINVM_ENVIRONMENT_OVERRIDES+=(
        "$(declare -p "$winvm_environment_name")")
done < <(compgen -e WINVM_)

WINVM_REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WINVM_CONFIG_FILE="${WINVM_CONFIG_FILE:-$WINVM_REPO_DIR/config.local}"
WINVM_COMMON_LOADED="${WINVM_COMMON_LOADED:-0}"

if [[ "$WINVM_COMMON_LOADED" != "1" && -f "$WINVM_CONFIG_FILE" ]]; then
    # shellcheck source=/dev/null
    source "$WINVM_CONFIG_FILE"
fi
for winvm_environment_declaration in "${WINVM_ENVIRONMENT_OVERRIDES[@]}"; do
    eval "$winvm_environment_declaration"
done
unset WINVM_ENVIRONMENT_OVERRIDES winvm_environment_declaration
unset winvm_environment_name

WINVM_CONFIGURED_UTM_NAME="${WINVM_CONFIGURED_UTM_NAME:-${WINVM_UTM_NAME:-Windows}}"

WINVM_TARGET_FILE="${WINVM_TARGET_FILE:-$WINVM_REPO_DIR/.target.local}"
if [[ "$WINVM_COMMON_LOADED" != "1" && -f "$WINVM_TARGET_FILE" &&
    -z "${WINVM_EXPECTED_UTM_ID:-}" &&
    "${WINVM_TARGET_ROLE:-unclassified}" == "unclassified" ]]; then
    # shellcheck source=/dev/null
    source "$WINVM_TARGET_FILE"
fi

WINVM_PROVIDER="${WINVM_PROVIDER:-utm-macos}"
WINVM_GUEST_DRIVER="${WINVM_GUEST_DRIVER:-windows}"
WINVM_SSH_HOST="${WINVM_SSH_HOST:-winvm}"
WINVM_SSH_PORT="${WINVM_SSH_PORT:-22}"
WINVM_UTM_NAME="${WINVM_UTM_NAME:-Windows}"
WINVM_EXPECTED_UTM_ID="${WINVM_EXPECTED_UTM_ID:-}"
WINVM_TARGET_ROLE="${WINVM_TARGET_ROLE:-unclassified}"
WINVM_UTM_BUNDLE="${WINVM_UTM_BUNDLE:-$HOME/Library/Containers/com.utmapp.UTM/Data/Documents/$WINVM_UTM_NAME.utm}"
WINVM_ALLOW_SOURCE_MUTATION="${WINVM_ALLOW_SOURCE_MUTATION:-0}"
WINVM_ALLOW_PERSISTENT_SEAL_BOOT="${WINVM_ALLOW_PERSISTENT_SEAL_BOOT:-0}"
WINVM_UTMCTL="${WINVM_UTMCTL:-/Applications/UTM.app/Contents/MacOS/utmctl}"
WINVM_LIBVIRT_URI="${WINVM_LIBVIRT_URI:-qemu:///system}"
WINVM_LIBVIRT_DOMAIN_NAME="${WINVM_LIBVIRT_DOMAIN_NAME:-$WINVM_UTM_NAME}"
WINVM_LIBVIRT_VIRSH="${WINVM_LIBVIRT_VIRSH:-virsh}"
WINVM_LIBVIRT_QEMU="${WINVM_LIBVIRT_QEMU:-qemu-system-x86_64}"
WINVM_LIBVIRT_NETWORK="${WINVM_LIBVIRT_NETWORK:-default}"
WINVM_LIBVIRT_POOL="${WINVM_LIBVIRT_POOL:-default}"
WINVM_LIBVIRT_MIN_FREE_BYTES="${WINVM_LIBVIRT_MIN_FREE_BYTES:-68719476736}"
WINVM_LIBVIRT_NVRAM_DIRECTORY="${WINVM_LIBVIRT_NVRAM_DIRECTORY:-/var/lib/libvirt/qemu/nvram}"
WINVM_LIBVIRT_NVRAM_TEMPLATE="${WINVM_LIBVIRT_NVRAM_TEMPLATE:-/usr/share/OVMF/OVMF_VARS_4M.ms.fd}"
WINVM_OSASCRIPT="${WINVM_OSASCRIPT:-/usr/bin/osascript}"
WINVM_OPEN="${WINVM_OPEN:-/usr/bin/open}"
WINVM_PLUTIL="${WINVM_PLUTIL:-/usr/bin/plutil}"
WINVM_DISPLAY_WIDTH="${WINVM_DISPLAY_WIDTH:-}"
WINVM_DISPLAY_HEIGHT="${WINVM_DISPLAY_HEIGHT:-}"
WINVM_UTM_TITLEBAR_HEIGHT="${WINVM_UTM_TITLEBAR_HEIGHT:-40}"
WINVM_BOOT_TIMEOUT="${WINVM_BOOT_TIMEOUT:-600}"
WINVM_SHUTDOWN_TIMEOUT="${WINVM_SHUTDOWN_TIMEOUT:-120}"
WINVM_GUEST_SHUTDOWN_GRACE="${WINVM_GUEST_SHUTDOWN_GRACE:-30}"
WINVM_POST_UPDATE_REPORT_TIMEOUT="${WINVM_POST_UPDATE_REPORT_TIMEOUT:-45}"
WINVM_CERTIFY_CHECK_TIMEOUT="${WINVM_CERTIFY_CHECK_TIMEOUT:-1200}"
WINVM_DOCTOR_GUEST_TIMEOUT="${WINVM_DOCTOR_GUEST_TIMEOUT:-60}"
WINVM_SUSPEND_POLICY="${WINVM_SUSPEND_POLICY:-auto}"
WINVM_FORBID_OUTER_UI="${WINVM_FORBID_OUTER_UI:-false}"
WINVM_SSH_BIN="${WINVM_SSH_BIN:-ssh}"
WINVM_SCP_BIN="${WINVM_SCP_BIN:-scp}"
WINVM_NC_BIN="${WINVM_NC_BIN:-nc}"
WINVM_SSH_ALLOW_START="${WINVM_SSH_ALLOW_START:-true}"
WINVM_UI_PIPE_NAME="${WINVM_UI_PIPE_NAME:-winvm-ui}"
WINVM_UI_TASK_NAME="${WINVM_UI_TASK_NAME:-WinVM UI Relay}"
WINVM_UI_REMOTE_RELATIVE="${WINVM_UI_REMOTE_RELATIVE:-AppData/Local/winvm-testbed}"
WINVM_WORKSPACE_STATE_DIR="${WINVM_WORKSPACE_STATE_DIR:-${XDG_STATE_HOME:-$HOME/.local/state}/machine-control/windows-workspaces}"
WINVM_CLAIM_STATE_DIR="${WINVM_CLAIM_STATE_DIR:-$WINVM_WORKSPACE_STATE_DIR/claims}"
WINVM_WORKSPACE_DEVELOPMENT_NAME="${WINVM_WORKSPACE_DEVELOPMENT_NAME:-$WINVM_UTM_NAME}"
WINVM_WORKSPACE_DEVELOPMENT_ID="${WINVM_WORKSPACE_DEVELOPMENT_ID:-$WINVM_EXPECTED_UTM_ID}"
WINVM_WORKSPACE_DEVELOPMENT_PROVEN="${WINVM_WORKSPACE_DEVELOPMENT_PROVEN:-false}"
WINVM_WORKSPACE_READY_BASE_NAME="${WINVM_WORKSPACE_READY_BASE_NAME:-}"
WINVM_WORKSPACE_READY_BASE_ID="${WINVM_WORKSPACE_READY_BASE_ID:-}"
WINVM_WORKSPACE_READY_BASE_PROVEN="${WINVM_WORKSPACE_READY_BASE_PROVEN:-false}"
WINVM_WORKSPACE_ALLOW_SHARED_BASE="${WINVM_WORKSPACE_ALLOW_SHARED_BASE:-false}"
WINVM_WORKSPACE_STORAGE_PATH="${WINVM_WORKSPACE_STORAGE_PATH:-}"
WINVM_WORKSPACE_MIN_FREE_BYTES="${WINVM_WORKSPACE_MIN_FREE_BYTES:-68719476736}"
WINVM_WORKSPACE_MAX_TEMPORARY="${WINVM_WORKSPACE_MAX_TEMPORARY:-1}"
WINVM_WORKSPACE_MAX_RETAINED="${WINVM_WORKSPACE_MAX_RETAINED:-2}"
WINVM_WORKSPACE_FULL_COPY_FALLBACK="${WINVM_WORKSPACE_FULL_COPY_FALLBACK:-prohibited}"
WINVM_WORKSPACE_ALLOW_FULL_COPY_ONCE="${WINVM_WORKSPACE_ALLOW_FULL_COPY_ONCE:-0}"
WINVM_WORKSPACE_CANDIDATE_PREFIX="${WINVM_WORKSPACE_CANDIDATE_PREFIX:-machine-control-windows}"

winvm_apply_workspace_selection() {
    local handle="${MACHINE_CONTROL_WORKSPACE_HANDLE:-}"
    [[ -n "$handle" ]] || return 0
    # shellcheck source=../../../providers/workspaces/common.sh
    source "$WINVM_REPO_DIR/../../providers/workspaces/common.sh"
    workspace_require_tools || return
    local provider target_name target_id intent
    provider="$(workspace_receipt_field \
        "$WINVM_WORKSPACE_STATE_DIR" "$handle" provider)" || return
    if [[ "$provider" != "$WINVM_PROVIDER-windows" ]]; then
        printf 'Workspace receipt belongs to a different provider\n' >&2
        return 1
    fi
    target_name="$(workspace_receipt_field \
        "$WINVM_WORKSPACE_STATE_DIR" "$handle" target.name)" || return
    target_id="$(workspace_receipt_field \
        "$WINVM_WORKSPACE_STATE_DIR" "$handle" target.id)" || return
    intent="$(workspace_receipt_field \
        "$WINVM_WORKSPACE_STATE_DIR" "$handle" intent)" || return
    WINVM_UTM_NAME="$target_name"
    WINVM_LIBVIRT_DOMAIN_NAME="$target_name"
    WINVM_EXPECTED_UTM_ID="$target_id"
    case "$intent" in
        persistent|candidate) WINVM_TARGET_ROLE=candidate ;;
        isolated) WINVM_TARGET_ROLE=seal ;;
        *) printf 'Workspace receipt intent is invalid\n' >&2; return 1 ;;
    esac
}

winvm_apply_workspace_selection
WINVM_COMMON_LOADED=1

export WINVM_REPO_DIR WINVM_CONFIG_FILE WINVM_PROVIDER WINVM_GUEST_DRIVER
export WINVM_COMMON_LOADED
export WINVM_TARGET_FILE
export WINVM_CONFIGURED_UTM_NAME
export WINVM_SSH_HOST WINVM_SSH_PORT WINVM_UTM_NAME WINVM_UTMCTL
export WINVM_LIBVIRT_URI WINVM_LIBVIRT_DOMAIN_NAME
export WINVM_LIBVIRT_VIRSH WINVM_LIBVIRT_QEMU
export WINVM_LIBVIRT_NETWORK WINVM_LIBVIRT_POOL WINVM_LIBVIRT_MIN_FREE_BYTES
export WINVM_LIBVIRT_NVRAM_DIRECTORY WINVM_LIBVIRT_NVRAM_TEMPLATE
export WINVM_UTM_BUNDLE WINVM_OPEN WINVM_PLUTIL
export WINVM_EXPECTED_UTM_ID WINVM_TARGET_ROLE
export WINVM_ALLOW_SOURCE_MUTATION WINVM_ALLOW_PERSISTENT_SEAL_BOOT
export WINVM_OSASCRIPT WINVM_DISPLAY_WIDTH WINVM_DISPLAY_HEIGHT
export WINVM_UTM_TITLEBAR_HEIGHT
export WINVM_BOOT_TIMEOUT WINVM_SHUTDOWN_TIMEOUT
export WINVM_GUEST_SHUTDOWN_GRACE WINVM_SUSPEND_POLICY WINVM_SSH_BIN
export WINVM_SCP_BIN WINVM_NC_BIN WINVM_SSH_ALLOW_START
export WINVM_POST_UPDATE_REPORT_TIMEOUT
export WINVM_CERTIFY_CHECK_TIMEOUT
export WINVM_DOCTOR_GUEST_TIMEOUT
export WINVM_FORBID_OUTER_UI
export WINVM_UI_PIPE_NAME WINVM_UI_TASK_NAME
export WINVM_UI_REMOTE_RELATIVE
export WINVM_WORKSPACE_STATE_DIR WINVM_WORKSPACE_DEVELOPMENT_NAME
export WINVM_CLAIM_STATE_DIR
export WINVM_WORKSPACE_DEVELOPMENT_ID WINVM_WORKSPACE_DEVELOPMENT_PROVEN
export WINVM_WORKSPACE_READY_BASE_NAME WINVM_WORKSPACE_READY_BASE_ID
export WINVM_WORKSPACE_READY_BASE_PROVEN WINVM_WORKSPACE_STORAGE_PATH
export WINVM_WORKSPACE_ALLOW_SHARED_BASE
export WINVM_WORKSPACE_MIN_FREE_BYTES WINVM_WORKSPACE_MAX_TEMPORARY
export WINVM_WORKSPACE_MAX_RETAINED WINVM_WORKSPACE_FULL_COPY_FALLBACK
export WINVM_WORKSPACE_ALLOW_FULL_COPY_ONCE WINVM_WORKSPACE_CANDIDATE_PREFIX
export MACHINE_CONTROL_WORKSPACE_HANDLE

winvm_provider_path() {
    printf '%s/providers/%s/provider.sh\n' "$WINVM_REPO_DIR" "$WINVM_PROVIDER"
}

winvm_require_command() {
    if ! command -v "$1" >/dev/null 2>&1; then
        printf 'Required command not found: %s\n' "$1" >&2
        return 1
    fi
}

winvm_encode_powershell() {
    iconv -f UTF-8 -t UTF-16LE | base64 | tr -d '\n'
}

winvm_powershell() {
    local powershell_script="$1"
    local encoded_command
    encoded_command="$(printf '%s' "$powershell_script" | winvm_encode_powershell)"
    winvm_ssh \
        "& ([ScriptBlock]::Create([Text.Encoding]::Unicode.GetString([Convert]::FromBase64String('$encoded_command'))))"
}

winvm_ssh() {
    "$(winvm_provider_path)" ssh-exec "$@"
}

winvm_ssh_host_key_alias() {
    printf '%s\n' "${WINVM_SSH_HOST##*@}"
}

winvm_doctor_appliance_ready() {
    jq -e '
        .schema == "machine-control-doctor/v0" and
        (
            .ready == true or
            (
                .ready == false and
                .states.administration == "ready" and
                .states.desktop == "locked" and
                .states.resident == "ready" and
                .states.semantic == "ready" and
                .states.capture == "ready" and
                .states.input == "ready" and
                .states.outer == "prohibited"
            )
        )
    '
}

winvm_run_bounded() {
    local timeout="$1"
    shift
    if [[ ! "$timeout" =~ ^[1-9][0-9]*$ ]]; then
        printf 'Timeout must be a positive integer: %s\n' "$timeout" >&2
        return 2
    fi

    "$@" &
    local pid=$! deadline=$((SECONDS + timeout))
    while kill -0 "$pid" >/dev/null 2>&1; do
        if (( SECONDS >= deadline )); then
            kill -TERM "$pid" >/dev/null 2>&1 || true
            wait "$pid" >/dev/null 2>&1 || true
            return 124
        fi
        sleep 0.1
    done
    wait "$pid"
}

winvm_powershell_bounded() {
    local timeout="$1" powershell_script="$2"
    local encoded_command
    encoded_command="$(printf '%s' "$powershell_script" | winvm_encode_powershell)"
    winvm_run_bounded "$timeout" \
        "$(winvm_provider_path)" ssh-exec \
        "& ([ScriptBlock]::Create([Text.Encoding]::Unicode.GetString([Convert]::FromBase64String('$encoded_command'))))"
}

winvm_tcp_check() {
    local host="$1" port="$2" timeout="${3:-2}"
    if [[ "$(uname -s)" == "Darwin" ]]; then
        "$WINVM_NC_BIN" -G "$timeout" -z "$host" "$port" >/dev/null 2>&1
    else
        "$WINVM_NC_BIN" -w "$timeout" -z "$host" "$port" >/dev/null 2>&1
    fi
}
