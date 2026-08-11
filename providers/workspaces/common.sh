#!/usr/bin/env bash

# Shared workspace receipt, locking, storage, and JSON helpers. Host providers
# retain all hypervisor operations and exact identity checks.

MACHINE_CONTROL_WORKSPACE_ROOT="$(
    cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd
)"
MACHINE_CONTROL_WORKSPACE_RECEIPTS="${MACHINE_CONTROL_WORKSPACE_RECEIPTS:-$MACHINE_CONTROL_WORKSPACE_ROOT/providers/workspaces/receipts.py}"
MACHINE_CONTROL_WORKSPACE_PYTHON="${MACHINE_CONTROL_WORKSPACE_PYTHON:-python3}"
MACHINE_CONTROL_WORKSPACE_LOCK=""

workspace_require_tools() {
    command -v "$MACHINE_CONTROL_WORKSPACE_PYTHON" >/dev/null 2>&1 || {
        printf 'Workspace receipt Python is unavailable\n' >&2
        return 1
    }
    command -v jq >/dev/null 2>&1 || {
        printf 'Workspace JSON support is unavailable\n' >&2
        return 1
    }
    [[ -f "$MACHINE_CONTROL_WORKSPACE_RECEIPTS" ]] || {
        printf 'Workspace receipt helper is unavailable\n' >&2
        return 1
    }
}

workspace_receipts() {
    local state_dir="$1"
    shift
    "$MACHINE_CONTROL_WORKSPACE_PYTHON" \
        "$MACHINE_CONTROL_WORKSPACE_RECEIPTS" \
        --state-dir "$state_dir" "$@"
}

workspace_lock_acquire() {
    local state_dir="$1" lock_dir stale_dir owner_pid=""
    workspace_receipts "$state_dir" inventory >/dev/null || return
    lock_dir="$state_dir/.operation.lock"
    if ! mkdir "$lock_dir" 2>/dev/null; then
        if [[ -f "$lock_dir/pid" ]]; then
            owner_pid="$(tr -d '\r\n' <"$lock_dir/pid")"
        fi
        if [[ "$owner_pid" =~ ^[0-9]+$ ]] && kill -0 "$owner_pid" 2>/dev/null; then
            printf 'Another workspace operation is active\n' >&2
            return 1
        fi
        stale_dir="$state_dir/.operation.lock.stale.$$"
        if ! mv "$lock_dir" "$stale_dir" 2>/dev/null; then
            printf 'Workspace operation lock could not be recovered\n' >&2
            return 1
        fi
        rm -f -- "$stale_dir/pid"
        if ! rmdir "$stale_dir"; then
            printf 'Workspace operation lock contained unexpected state\n' >&2
            return 1
        fi
        mkdir "$lock_dir" || return
    fi
    chmod 700 "$lock_dir"
    printf '%s\n' "$$" >"$lock_dir/pid"
    chmod 600 "$lock_dir/pid"
    MACHINE_CONTROL_WORKSPACE_LOCK="$lock_dir"
}

workspace_lock_release() {
    if [[ -z "$MACHINE_CONTROL_WORKSPACE_LOCK" ]]; then
        return 0
    fi
    rm -f -- "$MACHINE_CONTROL_WORKSPACE_LOCK/pid"
    rmdir "$MACHINE_CONTROL_WORKSPACE_LOCK" 2>/dev/null || true
    MACHINE_CONTROL_WORKSPACE_LOCK=""
}

workspace_with_lock() {
    local state_dir="$1" function_name="$2" status
    shift 2
    workspace_lock_acquire "$state_dir" || return
    set +e
    "$function_name" "$@"
    status=$?
    set -e
    workspace_lock_release
    return "$status"
}

workspace_free_bytes() {
    local storage_path="$1"
    [[ -n "$storage_path" && -d "$storage_path" ]] || return 1
    df -Pk "$storage_path" | awk 'NR == 2 { printf "%.0f\n", $4 * 1024 }'
}

workspace_capacity_preflight() {
    local storage_path="$1" minimum_free_bytes="$2" free_bytes
    [[ "$minimum_free_bytes" =~ ^[0-9]+$ ]] || return 2
    free_bytes="$(workspace_free_bytes "$storage_path" 2>/dev/null || true)"
    [[ "$free_bytes" =~ ^[0-9]+$ ]] || return 2
    (( free_bytes >= minimum_free_bytes )) || return 1
    printf '%s\n' "$free_bytes"
}

workspace_refusal() {
    local operation="$1" code="$2" message="$3"
    jq -n --arg operation "$operation" --arg code "$code" \
        --arg message "$message" \
        '{schema:"machine-control-workspace/v0", operation:$operation,
          accepted:false, uncertainty:"none", errorCode:$code,
          message:$message, data:{}}'
    return 1
}

workspace_result() {
    local operation="$1" uncertainty="$2" data="$3"
    jq -n --arg operation "$operation" --arg uncertainty "$uncertainty" \
        --argjson data "$data" \
        '{schema:"machine-control-workspace/v0", operation:$operation,
          accepted:true, uncertainty:$uncertainty, data:$data}'
}

workspace_inventory_result() {
    local state_dir="$1" data
    data="$(workspace_receipts "$state_dir" inventory)" || return
    workspace_result inventory bounded "$data"
}

workspace_gc_result() {
    local state_dir="$1" data
    data="$(workspace_receipts "$state_dir" gc)" || return
    workspace_result gc bounded "$data"
}

workspace_receipt_field() {
    local state_dir="$1" handle="$2" field="$3"
    workspace_receipts "$state_dir" field --handle "$handle" --field "$field"
}
