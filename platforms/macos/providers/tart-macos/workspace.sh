#!/usr/bin/env bash

set -euo pipefail

readonly PROVIDER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../../scripts/common.sh
source "$PROVIDER_DIR/../../scripts/common.sh"
# shellcheck source=../../../../providers/workspaces/common.sh
source "$MACVM_REPO_DIR/../../providers/workspaces/common.sh"

workspace_require_tools
macvm_require_host

if [[ -n "${MACHINE_CONTROL_WORKSPACE_HANDLE:-}" ]]; then
    workspace_refusal capabilities workspace_selection_conflict \
        'Workspace management cannot run through a selected workspace'
    exit $?
fi

tart_state() {
    "$MACVM_TART" get "$1" --format json 2>/dev/null | jq -r '.State // "unknown"'
}

development_available() {
    [[ "$MACVM_WORKSPACE_DEVELOPMENT_PROVEN" == "true" &&
       -n "$MACVM_WORKSPACE_DEVELOPMENT_NAME" &&
       "$MACVM_WORKSPACE_DEVELOPMENT_NAME" == "$MACVM_NAME" &&
       "$MACVM_REQUIRE_MUTATION_GUARD" == "true" &&
       "$MACVM_EXPECTED_NAME" == "$MACVM_WORKSPACE_DEVELOPMENT_NAME" &&
       "$MACVM_TARGET_ROLE" == "candidate" ]] &&
        tart_state "$MACVM_WORKSPACE_DEVELOPMENT_NAME" >/dev/null 2>&1
}

ready_base_available() {
    [[ "$MACVM_WORKSPACE_READY_BASE_PROVEN" == "true" &&
       -n "$MACVM_WORKSPACE_READY_BASE_NAME" &&
       ( "$MACVM_WORKSPACE_READY_BASE_NAME" != "$MACVM_WORKSPACE_DEVELOPMENT_NAME" ||
         "$MACVM_WORKSPACE_ALLOW_SHARED_BASE" == "true" ) ]] &&
        tart_state "$MACVM_WORKSPACE_READY_BASE_NAME" >/dev/null 2>&1
}

workspace_limits_valid() {
    [[ "$MACVM_WORKSPACE_MIN_FREE_BYTES" =~ ^[0-9]+$ &&
       "$MACVM_WORKSPACE_MAX_TEMPORARY" =~ ^[0-9]+$ &&
       "$MACVM_WORKSPACE_MAX_RETAINED" =~ ^[0-9]+$ &&
       "$MACVM_WORKSPACE_MAX_RETAINED" -ge 1 ]]
}

workspace_capabilities() {
    workspace_limits_valid || {
        printf 'Workspace policy values are invalid\n' >&2
        return 1
    }
    local persistent=unavailable derived=unavailable storage=unavailable
    local free_bytes="" persistent_reason=development-not-guarded
    local derived_reason=ready-base-not-proven
    if development_available; then
        persistent=available
        persistent_reason=""
    fi
    if ready_base_available; then
        derived=available
        derived_reason=""
    fi
    free_bytes="$(workspace_free_bytes \
        "$MACVM_WORKSPACE_STORAGE_PATH" 2>/dev/null || true)"
    if [[ "$free_bytes" =~ ^[0-9]+$ ]]; then storage=estimate; fi
    jq -n \
        --arg persistent "$persistent" --arg derived "$derived" \
        --arg persistentReason "$persistent_reason" \
        --arg derivedReason "$derived_reason" \
        --arg storage "$storage" \
        --argjson freeBytes "${free_bytes:-null}" \
        --argjson maxTemporary "$MACVM_WORKSPACE_MAX_TEMPORARY" \
        --argjson maxRetained "$MACVM_WORKSPACE_MAX_RETAINED" \
        '{schema:"machine-control-workspace-capabilities/v0",
          intents:{
            persistent:{availability:$persistent, retention:"retained",
              mechanisms:(if $persistent == "available" then [{
                kind:"existing_instance", costClass:"unknown",
                sourceMustBeStopped:false, concurrentWithSource:true}] else [] end),
              reasons:(if $persistentReason == "" then [] else [$persistentReason] end)},
            isolated:{availability:$derived, retention:"discardOnRelease",
              mechanisms:(if $derived == "available" then [{
                kind:"filesystem_cow_clone", costClass:"copy_on_write",
                sourceMustBeStopped:true, concurrentWithSource:true}] else [] end),
              reasons:(if $derivedReason == "" then [] else [$derivedReason] end)},
            candidate:{availability:$derived, retention:"retained",
              mechanisms:(if $derived == "available" then [{
                kind:"filesystem_cow_clone", costClass:"copy_on_write",
                sourceMustBeStopped:true, concurrentWithSource:true}] else [] end),
              reasons:(if $derivedReason == "" then [] else [$derivedReason] end)}},
          limits:{maxTemporaryWorkspaces:$maxTemporary,
            maxRetainedWorkspaces:$maxRetained, fullCopyFallback:"prohibited"},
          storage:{measurement:$storage, freeBytes:$freeBytes}, extensions:{}}'
}

existing_receipt() {
    workspace_receipts "$MACVM_WORKSPACE_STATE_DIR" find \
        --provider tart-macos --target-id "$1" --intent "$2"
}

create_receipt() {
    local intent="$1" mechanism="$2" retention="$3" cleanup="$4"
    local target="$5" source="${6:-}"
    local -a arguments=(
        create --provider tart-macos --intent "$intent"
        --mechanism "$mechanism" --retention "$retention"
        --cleanup "$cleanup" --state running
        --target-name "$target" --target-id "$target"
    )
    if [[ -n "$source" ]]; then
        arguments+=(--source-name "$source" --source-id "$source")
    fi
    workspace_receipts "$MACVM_WORKSPACE_STATE_DIR" "${arguments[@]}"
}

start_selected_workspace() {
    local handle="$1"
    MACHINE_CONTROL_WORKSPACE_HANDLE="$handle" \
        "$MACVM_REPO_DIR/bin/macvm" up >/dev/null
}

acquire_persistent() {
    if ! development_available; then
        workspace_refusal acquire intent_unavailable \
            'The persistent development workspace is not guarded and available'
        return $?
    fi
    local target="$MACVM_WORKSPACE_DEVELOPMENT_NAME" handle
    if [[ "$(tart_state "$target")" != "running" ]]; then
        MACVM_NAME="$target" MACVM_EXPECTED_NAME="$target" \
            MACVM_TARGET_ROLE=candidate MACVM_REQUIRE_MUTATION_GUARD=true \
            "$MACVM_REPO_DIR/bin/macvm" up >/dev/null || {
                workspace_refusal acquire workspace_start_failed \
                    'The persistent workspace did not start'
                return $?
            }
    fi
    handle="$(existing_receipt "$target" persistent)"
    if [[ -z "$handle" ]]; then
        handle="$(create_receipt persistent existing_instance retained none \
            "$target")" || return
    else
        workspace_receipts "$MACVM_WORKSPACE_STATE_DIR" update \
            --handle "$handle" --state running --cleanup none
    fi
    local data
    data="$(jq -n --arg handle "$handle" \
        '{handle:$handle, requestedIntent:"persistent",
          actualMechanism:"existing_instance", retention:"retained",
          cleanup:"none", storage:{costClass:"unknown",
            measurement:"unavailable", preflight:"pass"}}')"
    workspace_result acquire none "$data"
}

acquire_derived() {
    local intent="$1" retention cleanup count maximum source state
    local free_bytes destination handle data
    if ! ready_base_available; then
        workspace_refusal acquire intent_unavailable \
            'A controller-ready derivation base is not explicitly proven'
        return $?
    fi
    source="$MACVM_WORKSPACE_READY_BASE_NAME"
    state="$(tart_state "$source")"
    if [[ "$state" != "stopped" ]]; then
        workspace_refusal acquire source_not_stopped \
            'Workspace derivation requires the ready base to be stopped'
        return $?
    fi
    if [[ "$intent" == "isolated" ]]; then
        retention=discardOnRelease
        cleanup=release
        maximum="$MACVM_WORKSPACE_MAX_TEMPORARY"
        count="$(workspace_receipts "$MACVM_WORKSPACE_STATE_DIR" inventory |
            jq -r '.counts.temporary')"
    else
        retention=retained
        cleanup=none
        maximum="$MACVM_WORKSPACE_MAX_RETAINED"
        count="$(workspace_receipts "$MACVM_WORKSPACE_STATE_DIR" inventory |
            jq -r '.counts.retained')"
    fi
    if (( count >= maximum )); then
        workspace_refusal acquire workspace_limit_reached \
            'The configured workspace count limit is reached'
        return $?
    fi
    if ! free_bytes="$(workspace_capacity_preflight \
        "$MACVM_WORKSPACE_STORAGE_PATH" \
        "$MACVM_WORKSPACE_MIN_FREE_BYTES")"; then
        workspace_refusal acquire storage_preflight_failed \
            'The configured workspace storage reserve is unavailable'
        return $?
    fi
    if [[ ! "$MACVM_WORKSPACE_CANDIDATE_PREFIX" =~ ^[A-Za-z0-9._-]+$ ]]; then
        workspace_refusal acquire workspace_policy_invalid \
            'The configured workspace candidate prefix is invalid'
        return $?
    fi
    destination="$MACVM_WORKSPACE_CANDIDATE_PREFIX-$intent-$(
        "$MACHINE_CONTROL_WORKSPACE_PYTHON" -c \
            'import secrets; print(secrets.token_hex(6))'
    )"
    if tart_state "$destination" >/dev/null 2>&1; then
        workspace_refusal acquire destination_exists \
            'The generated workspace destination already exists'
        return $?
    fi
    TART_NO_AUTO_PRUNE= "$MACVM_TART" clone "$source" "$destination" \
        >/dev/null || {
            workspace_refusal acquire derivation_failed \
                'The provider could not derive a workspace'
            return $?
        }
    handle="$(create_receipt "$intent" filesystem_cow_clone "$retention" \
        "$cleanup" "$destination" "$source")" || return
    if ! start_selected_workspace "$handle"; then
        if [[ "$intent" == "isolated" ]]; then
            workspace_receipts "$MACVM_WORKSPACE_STATE_DIR" update \
                --handle "$handle" --cleanup pending --state unknown || true
        fi
        workspace_refusal acquire workspace_start_failed \
            'The derived workspace was retained but did not start'
        return $?
    fi
    data="$(jq -n --arg handle "$handle" --arg intent "$intent" \
        --arg retention "$retention" \
        '{handle:$handle, requestedIntent:$intent,
          actualMechanism:"filesystem_cow_clone", retention:$retention,
          cleanup:(if $intent == "isolated" then "explicitRelease" else "none" end),
          storage:{costClass:"copy_on_write", measurement:"estimate",
            preflight:"pass"}}')"
    workspace_result acquire bounded "$data"
}

workspace_acquire_inner() {
    case "$1" in
        persistent) acquire_persistent ;;
        isolated|candidate) acquire_derived "$1" ;;
        *) workspace_refusal acquire invalid_workspace_intent \
            'The requested workspace intent is invalid' ;;
    esac
}

workspace_acquire() {
    if [[ $# -ne 3 || "$1" != "--intent" || "$3" != "--json" ]]; then
        printf 'Usage: workspace-acquire --intent INTENT --json\n' >&2
        return 2
    fi
    workspace_limits_valid || {
        workspace_refusal acquire workspace_policy_invalid \
            'Workspace policy values are invalid'
        return $?
    }
    workspace_with_lock "$MACVM_WORKSPACE_STATE_DIR" \
        workspace_acquire_inner "$2"
}

release_inner() {
    local handle="$1" provider intent target target_id source state disposition
    provider="$(workspace_receipt_field \
        "$MACVM_WORKSPACE_STATE_DIR" "$handle" provider)" || {
            workspace_refusal release workspace_receipt_invalid \
                'The workspace receipt is absent or invalid'
            return $?
        }
    if [[ "$provider" != "tart-macos" ]]; then
        workspace_refusal release workspace_receipt_invalid \
            'The workspace receipt belongs to another provider'
        return $?
    fi
    intent="$(workspace_receipt_field \
        "$MACVM_WORKSPACE_STATE_DIR" "$handle" intent)" || return
    target="$(workspace_receipt_field \
        "$MACVM_WORKSPACE_STATE_DIR" "$handle" target.name)" || return
    target_id="$(workspace_receipt_field \
        "$MACVM_WORKSPACE_STATE_DIR" "$handle" target.id)" || return
    if [[ "$target" != "$target_id" ]]; then
        workspace_refusal release workspace_identity_mismatch \
            'The workspace provider identity does not match its receipt'
        return $?
    fi
    if [[ "$intent" != "isolated" ]]; then
        state="$(tart_state "$target" 2>/dev/null || printf unknown)"
        [[ "$state" == "running" || "$state" == "stopped" ]] || state=unknown
        [[ "$state" == "stopped" ]] && state=off
        workspace_receipts "$MACVM_WORKSPACE_STATE_DIR" update \
            --handle "$handle" --state "$state" --cleanup none
        data="$(jq -n --arg handle "$handle" \
            '{handle:$handle, disposition:"retained"}')"
        workspace_result release bounded "$data"
        return
    fi
    source="$(workspace_receipt_field \
        "$MACVM_WORKSPACE_STATE_DIR" "$handle" source.id)" || return
    if [[ "$source" != "$MACVM_WORKSPACE_READY_BASE_NAME" ||
          "$target" == "$source" ||
          "$target" == "$MACVM_WORKSPACE_DEVELOPMENT_NAME" ]]; then
        workspace_refusal release protected_workspace \
            'The workspace receipt does not authorize derived-target cleanup'
        return $?
    fi
    if ! state="$(tart_state "$target" 2>/dev/null)"; then
        workspace_receipts "$MACVM_WORKSPACE_STATE_DIR" forget --handle "$handle"
        disposition=alreadyAbsent
    else
        workspace_receipts "$MACVM_WORKSPACE_STATE_DIR" update \
            --handle "$handle" --cleanup pending
        if [[ "$state" == "running" ]]; then
            MACHINE_CONTROL_WORKSPACE_HANDLE="$handle" \
                "$MACVM_REPO_DIR/bin/macvm" stop >/dev/null || {
                    workspace_refusal release workspace_stop_failed \
                        'The temporary workspace did not stop'
                    return $?
                }
        fi
        if [[ "$(tart_state "$target" 2>/dev/null || printf unknown)" == "running" ]]; then
            workspace_refusal release workspace_stop_failed \
                'The temporary workspace is still running'
            return $?
        fi
        "$MACVM_TART" delete "$target" >/dev/null || {
            workspace_refusal release workspace_delete_failed \
                'The temporary workspace could not be deleted'
            return $?
        }
        if tart_state "$target" >/dev/null 2>&1; then
            workspace_refusal release workspace_delete_failed \
                'The temporary workspace still exists after deletion'
            return $?
        fi
        workspace_receipts "$MACVM_WORKSPACE_STATE_DIR" forget --handle "$handle"
        disposition=discarded
    fi
    data="$(jq -n --arg handle "$handle" --arg disposition "$disposition" \
        '{handle:$handle, disposition:$disposition}')"
    workspace_result release none "$data"
}

workspace_release() {
    if [[ $# -ne 3 || "$1" != "--handle" || "$3" != "--json" ]]; then
        printf 'Usage: workspace-release --handle HANDLE --json\n' >&2
        return 2
    fi
    workspace_with_lock "$MACVM_WORKSPACE_STATE_DIR" release_inner "$2"
}

command="${1:-}"
if [[ -n "$command" ]]; then shift; fi
case "$command" in
    workspace-capabilities)
        [[ "${1:-}" == "--json" && $# -eq 1 ]] || exit 2
        workspace_capabilities
        ;;
    workspace-acquire) workspace_acquire "$@" ;;
    workspace-inventory)
        [[ "${1:-}" == "--json" && $# -eq 1 ]] || exit 2
        workspace_inventory_result "$MACVM_WORKSPACE_STATE_DIR"
        ;;
    workspace-release) workspace_release "$@" ;;
    workspace-gc)
        [[ "${1:-}" == "--dry-run" && "${2:-}" == "--json" && $# -eq 2 ]] || exit 2
        workspace_gc_result "$MACVM_WORKSPACE_STATE_DIR"
        ;;
    *) printf 'Unknown workspace command\n' >&2; exit 2 ;;
esac
