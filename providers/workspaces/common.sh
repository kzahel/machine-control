#!/usr/bin/env bash

# Shared workspace receipt, locking, storage, and JSON helpers. Host providers
# retain all hypervisor operations and exact identity checks.

MACHINE_CONTROL_WORKSPACE_ROOT="$(
    cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd
)"
MACHINE_CONTROL_WORKSPACE_RECEIPTS="${MACHINE_CONTROL_WORKSPACE_RECEIPTS:-$MACHINE_CONTROL_WORKSPACE_ROOT/providers/workspaces/receipts.py}"
MACHINE_CONTROL_WORKSPACE_PYTHON="${MACHINE_CONTROL_WORKSPACE_PYTHON:-python3}"
MACHINE_CONTROL_WORKSPACE_LOCK=""
MACHINE_CONTROL_WORKSPACE_CLAIM_INTENT=""
MACHINE_CONTROL_WORKSPACE_CLAIM_ARGUMENTS=()

# shellcheck source=../claims/common.sh
source "$MACHINE_CONTROL_WORKSPACE_ROOT/providers/claims/common.sh"

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

workspace_parse_claimed_acquire() {
    MACHINE_CONTROL_WORKSPACE_CLAIM_INTENT=""
    MACHINE_CONTROL_WORKSPACE_CLAIM_ARGUMENTS=()
    local json=false has_reason=false has_authority=false has_claimant=false
    while (( $# > 0 )); do
        case "$1" in
            --intent)
                (( $# >= 2 )) || return 2
                MACHINE_CONTROL_WORKSPACE_CLAIM_INTENT="$2"
                shift 2
                ;;
            --duration-seconds|--reason|--claimant-authority|--claimant-id|--session-id|--label|--metadata-json)
                (( $# >= 2 )) || return 2
                case "$1" in
                    --reason) has_reason=true ;;
                    --claimant-authority) has_authority=true ;;
                    --claimant-id) has_claimant=true ;;
                esac
                MACHINE_CONTROL_WORKSPACE_CLAIM_ARGUMENTS+=("$1" "$2")
                shift 2
                ;;
            --json)
                json=true
                shift
                ;;
            *) return 2 ;;
        esac
    done
    [[ -n "$MACHINE_CONTROL_WORKSPACE_CLAIM_INTENT" && "$json" == true ]] ||
        return 2
    if [[ "${MACHINE_CONTROL_CLAIM_POLICY:-required}" != optional ]]; then
        [[ "$has_reason" == true && "$has_authority" == true &&
           "$has_claimant" == true ]] || return 2
    fi
}

workspace_claim_refusal_from_result() {
    local operation="$1" value="$2" code message
    code="$(jq -r '.errorCode // "claim_operation_failed"' <<<"$value" \
        2>/dev/null || printf claim_operation_failed)"
    message="$(jq -r '.message // "The target-use claim operation failed"' \
        <<<"$value" 2>/dev/null || \
        printf 'The target-use claim operation failed')"
    workspace_refusal "$operation" "$code" "$message"
}

workspace_claim_acquire_exact() {
    local state_dir="$1" provider="$2" resource_id="$3" result
    if [[ "${MACHINE_CONTROL_CLAIM_POLICY:-required}" == optional ]]; then
        printf 'null\n'
        return
    fi
    if ! result="$(claim_store "$state_dir" acquire \
        --provider "$provider" --resource-id "$resource_id" \
        "${MACHINE_CONTROL_WORKSPACE_CLAIM_ARGUMENTS[@]}")"; then
        workspace_claim_refusal_from_result acquire "$result"
        return $?
    fi
    jq -c '.data.claim' <<<"$result"
}

workspace_claim_check_release_exact() {
    local state_dir="$1" provider="$2" resource_id="$3" result
    if [[ "${MACHINE_CONTROL_CLAIM_POLICY:-required}" == optional ]]; then
        return
    fi
    if [[ -z "${MACHINE_CONTROL_CLAIM_ID:-}" ]]; then
        workspace_refusal release claim_required \
            'Workspace release requires its live target-use claim'
        return $?
    fi
    if ! result="$(claim_store "$state_dir" check \
        --provider "$provider" --resource-id "$resource_id" \
        --claim-id "$MACHINE_CONTROL_CLAIM_ID")"; then
        workspace_claim_refusal_from_result release "$result"
        return $?
    fi
}

workspace_claim_release_exact() {
    local state_dir="$1" provider="$2" resource_id="$3" claim_id="$4"
    if [[ "${MACHINE_CONTROL_CLAIM_POLICY:-required}" == optional ]]; then
        return
    fi
    claim_store "$state_dir" release --provider "$provider" \
        --resource-id "$resource_id" --claim-id "$claim_id"
}

workspace_claim_release_selected() {
    local state_dir="$1" provider="$2" resource_id="$3" result
    if [[ "${MACHINE_CONTROL_CLAIM_POLICY:-required}" == optional ]]; then
        return
    fi
    if ! result="$(workspace_claim_release_exact "$state_dir" "$provider" \
        "$resource_id" "$MACHINE_CONTROL_CLAIM_ID")"; then
        workspace_claim_refusal_from_result release "$result"
        return $?
    fi
}

workspace_data_with_claim() {
    local data="$1" claim="$2"
    if [[ "$claim" == null ]]; then
        printf '%s\n' "$data"
    else
        jq -c --argjson claim "$claim" '. + {claim:$claim}' <<<"$data"
    fi
}
