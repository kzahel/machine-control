#!/usr/bin/env bash

# UTM/QEMU workspace mechanisms shared by authoritative Windows and Linux
# platform adapters. The caller supplies only private, exact configuration and
# then invokes utm_workspace_main.

utm_workspace_status() {
    "$UTM_WORKSPACE_CLI" status "$1" 2>/dev/null
}

utm_workspace_id_for_name() {
    local expected_name="$1"
    "$UTM_WORKSPACE_CLI" list | awk -v expected="$expected_name" '
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

utm_workspace_wait_state() {
    local identifier="$1" expected="$2" timeout="$3"
    local deadline=$((SECONDS + timeout)) state="unknown"
    while (( SECONDS < deadline )); do
        state="$(utm_workspace_status "$identifier" || true)"
        if [[ "$state" == "$expected" ]]; then return 0; fi
        sleep 1
    done
    return 1
}

utm_workspace_limits_valid() {
    [[ "$UTM_WORKSPACE_MIN_FREE_BYTES" =~ ^[0-9]+$ &&
       "$UTM_WORKSPACE_MAX_TEMPORARY" =~ ^[0-9]+$ &&
       "$UTM_WORKSPACE_MAX_RETAINED" =~ ^[0-9]+$ &&
       "$UTM_WORKSPACE_MAX_RETAINED" -ge 1 &&
       "$UTM_WORKSPACE_FULL_COPY_FALLBACK" =~ ^(prohibited|explicit|allowed)$ ]]
}

utm_workspace_development_available() {
    [[ "$UTM_WORKSPACE_DEVELOPMENT_PROVEN" == "true" &&
       "$UTM_WORKSPACE_CURRENT_GUARDED" == "true" &&
       -n "$UTM_WORKSPACE_DEVELOPMENT_NAME" &&
       -n "$UTM_WORKSPACE_DEVELOPMENT_ID" ]] &&
        utm_workspace_status "$UTM_WORKSPACE_DEVELOPMENT_ID" >/dev/null 2>&1
}

utm_workspace_ready_base_available() {
    [[ "$UTM_WORKSPACE_READY_BASE_PROVEN" == "true" &&
       -n "$UTM_WORKSPACE_READY_BASE_NAME" &&
       -n "$UTM_WORKSPACE_READY_BASE_ID" &&
       ( "$UTM_WORKSPACE_READY_BASE_ID" != "$UTM_WORKSPACE_DEVELOPMENT_ID" ||
         "$UTM_WORKSPACE_ALLOW_SHARED_BASE" == "true" ) ]] &&
        utm_workspace_status "$UTM_WORKSPACE_READY_BASE_ID" >/dev/null 2>&1
}

utm_workspace_candidate_available() {
    utm_workspace_ready_base_available || return
    case "$UTM_WORKSPACE_FULL_COPY_FALLBACK" in
        allowed) return 0 ;;
        explicit) [[ "$UTM_WORKSPACE_ALLOW_FULL_COPY_ONCE" == "1" ]] ;;
        *) return 1 ;;
    esac
}

utm_workspace_capabilities() {
    utm_workspace_limits_valid || {
        printf 'Workspace policy values are invalid\n' >&2
        return 1
    }
    local persistent=unavailable isolated=unavailable candidate=unavailable
    local persistent_reason=development-not-guarded
    local isolated_reason=ready-base-not-proven candidate_reason=""
    local measurement=unavailable free_bytes=""
    if utm_workspace_development_available; then
        persistent=available
        persistent_reason=""
    fi
    if utm_workspace_ready_base_available; then
        isolated=available
        isolated_reason=""
    fi
    if utm_workspace_candidate_available; then
        candidate=available
    elif ! utm_workspace_ready_base_available; then
        candidate_reason=ready-base-not-proven
    elif [[ "$UTM_WORKSPACE_FULL_COPY_FALLBACK" == "explicit" ]]; then
        candidate_reason=full-copy-requires-explicit-authorization
    else
        candidate_reason=full-copy-prohibited
    fi
    free_bytes="$(workspace_free_bytes \
        "$UTM_WORKSPACE_STORAGE_PATH" 2>/dev/null || true)"
    if [[ "$free_bytes" =~ ^[0-9]+$ ]]; then measurement=estimate; fi
    jq -n \
        --arg persistent "$persistent" --arg isolated "$isolated" \
        --arg candidate "$candidate" \
        --arg persistentReason "$persistent_reason" \
        --arg isolatedReason "$isolated_reason" \
        --arg candidateReason "$candidate_reason" \
        --arg measurement "$measurement" \
        --argjson freeBytes "${free_bytes:-null}" \
        --argjson maxTemporary "$UTM_WORKSPACE_MAX_TEMPORARY" \
        --argjson maxRetained "$UTM_WORKSPACE_MAX_RETAINED" \
        --arg fullCopy "$UTM_WORKSPACE_FULL_COPY_FALLBACK" \
        '{schema:"machine-control-workspace-capabilities/v0",
          intents:{
            persistent:{availability:$persistent, retention:"retained",
              mechanisms:(if $persistent == "available" then [{
                kind:"existing_instance", costClass:"unknown",
                sourceMustBeStopped:false, concurrentWithSource:true}] else [] end),
              reasons:(if $persistentReason == "" then [] else [$persistentReason] end)},
            isolated:{availability:$isolated, retention:"discardOnRelease",
              mechanisms:(if $isolated == "available" then [{
                kind:"provider_disposable_overlay", costClass:"overlay",
                sourceMustBeStopped:true, concurrentWithSource:false}] else [] end),
              reasons:(if $isolatedReason == "" then [] else [$isolatedReason] end)},
            candidate:{availability:$candidate, retention:"retained",
              mechanisms:(if $candidate == "available" then [{
                kind:"full_copy", costClass:"full_copy",
                sourceMustBeStopped:true, concurrentWithSource:true}] else [] end),
              reasons:(if $candidateReason == "" then [] else [$candidateReason] end)}},
          limits:{maxTemporaryWorkspaces:$maxTemporary,
            maxRetainedWorkspaces:$maxRetained, fullCopyFallback:$fullCopy},
          storage:{measurement:$measurement, freeBytes:$freeBytes}, extensions:{}}'
}

utm_workspace_existing_receipt() {
    workspace_receipts "$UTM_WORKSPACE_STATE_DIR" find \
        --provider "$UTM_WORKSPACE_PROVIDER" --target-id "$1" --intent "$2"
}

utm_workspace_create_receipt() {
    local intent="$1" mechanism="$2" retention="$3" cleanup="$4"
    local target_name="$5" target_id="$6"
    local source_name="${7:-}" source_id="${8:-}"
    local -a arguments=(
        create --provider "$UTM_WORKSPACE_PROVIDER" --intent "$intent"
        --mechanism "$mechanism" --retention "$retention"
        --cleanup "$cleanup" --state running
        --target-name "$target_name" --target-id "$target_id"
    )
    if [[ -n "$source_name" || -n "$source_id" ]]; then
        arguments+=(--source-name "$source_name" --source-id "$source_id")
    fi
    workspace_receipts "$UTM_WORKSPACE_STATE_DIR" "${arguments[@]}"
}

utm_workspace_start() {
    local identifier="$1" mode="$2"
    local -a arguments=(start --hide "$identifier")
    if [[ "$mode" == "disposable" ]]; then arguments+=(--disposable); fi
    "$UTM_WORKSPACE_CLI" "${arguments[@]}" >/dev/null || return
    utm_workspace_wait_state "$identifier" started "$UTM_WORKSPACE_BOOT_TIMEOUT"
}

utm_workspace_acquire_persistent() {
    if ! utm_workspace_development_available; then
        workspace_refusal acquire intent_unavailable \
            'The persistent development workspace is not guarded and available'
        return $?
    fi
    local identifier="$UTM_WORKSPACE_DEVELOPMENT_ID" handle data
    if [[ -n "$(utm_workspace_existing_receipt "$identifier" isolated)" ]]; then
        workspace_refusal acquire workspace_in_use \
            'The development target has an active disposable workspace receipt'
        return $?
    fi
    if [[ "$(utm_workspace_status "$identifier")" != "started" ]]; then
        utm_workspace_start "$identifier" persistent || {
            workspace_refusal acquire workspace_start_failed \
                'The persistent workspace did not start'
            return $?
        }
    fi
    handle="$(utm_workspace_existing_receipt "$identifier" persistent)"
    if [[ -z "$handle" ]]; then
        handle="$(utm_workspace_create_receipt persistent existing_instance \
            retained none "$UTM_WORKSPACE_DEVELOPMENT_NAME" "$identifier")" || return
    else
        workspace_receipts "$UTM_WORKSPACE_STATE_DIR" update \
            --handle "$handle" --state running --cleanup none
    fi
    data="$(jq -n --arg handle "$handle" \
        '{handle:$handle, requestedIntent:"persistent",
          actualMechanism:"existing_instance", retention:"retained",
          cleanup:"none", storage:{costClass:"unknown",
            measurement:"unavailable", preflight:"pass"}}')"
    workspace_result acquire none "$data"
}

utm_workspace_acquire_isolated() {
    if ! utm_workspace_ready_base_available; then
        workspace_refusal acquire intent_unavailable \
            'A controller-ready disposable base is not explicitly proven'
        return $?
    fi
    local identifier="$UTM_WORKSPACE_READY_BASE_ID" count handle data free_bytes
    if [[ "$(utm_workspace_status "$identifier")" != "stopped" ]]; then
        workspace_refusal acquire source_not_stopped \
            'Disposable execution requires the ready base to be stopped'
        return $?
    fi
    count="$(workspace_receipts "$UTM_WORKSPACE_STATE_DIR" inventory |
        jq -r '.counts.temporary')"
    if (( count >= UTM_WORKSPACE_MAX_TEMPORARY )); then
        workspace_refusal acquire workspace_limit_reached \
            'The configured temporary-workspace limit is reached'
        return $?
    fi
    if ! free_bytes="$(workspace_capacity_preflight \
        "$UTM_WORKSPACE_STORAGE_PATH" "$UTM_WORKSPACE_MIN_FREE_BYTES")"; then
        workspace_refusal acquire storage_preflight_failed \
            'The configured workspace storage reserve is unavailable'
        return $?
    fi
    handle="$(utm_workspace_create_receipt isolated \
        provider_disposable_overlay discardOnRelease release \
        "$UTM_WORKSPACE_READY_BASE_NAME" "$identifier" \
        "$UTM_WORKSPACE_READY_BASE_NAME" "$identifier")" || return
    if ! utm_workspace_start "$identifier" disposable; then
        workspace_receipts "$UTM_WORKSPACE_STATE_DIR" update \
            --handle "$handle" --state unknown --cleanup pending || true
        workspace_refusal acquire workspace_start_failed \
            'The disposable workspace was retained for diagnosis but did not start'
        return $?
    fi
    data="$(jq -n --arg handle "$handle" \
        '{handle:$handle, requestedIntent:"isolated",
          actualMechanism:"provider_disposable_overlay",
          retention:"discardOnRelease", cleanup:"providerDiscardOnStop",
          storage:{costClass:"overlay", measurement:"estimate",
            preflight:"pass"}}')"
    workspace_result acquire bounded "$data"
}

utm_workspace_acquire_candidate() {
    if ! utm_workspace_candidate_available; then
        workspace_refusal acquire intent_unavailable \
            'Full-copy candidate derivation is not authorized by policy'
        return $?
    fi
    local source_id="$UTM_WORKSPACE_READY_BASE_ID" count free_bytes
    local destination target_id handle data
    if [[ "$(utm_workspace_status "$source_id")" != "stopped" ]]; then
        workspace_refusal acquire source_not_stopped \
            'Candidate derivation requires the ready base to be stopped'
        return $?
    fi
    count="$(workspace_receipts "$UTM_WORKSPACE_STATE_DIR" inventory |
        jq -r '.counts.retained')"
    if (( count >= UTM_WORKSPACE_MAX_RETAINED )); then
        workspace_refusal acquire workspace_limit_reached \
            'The configured retained-workspace limit is reached'
        return $?
    fi
    if ! free_bytes="$(workspace_capacity_preflight \
        "$UTM_WORKSPACE_STORAGE_PATH" "$UTM_WORKSPACE_MIN_FREE_BYTES")"; then
        workspace_refusal acquire storage_preflight_failed \
            'The configured workspace storage reserve is unavailable'
        return $?
    fi
    if [[ ! "$UTM_WORKSPACE_CANDIDATE_PREFIX" =~ ^[A-Za-z0-9._-]+$ ]]; then
        workspace_refusal acquire workspace_policy_invalid \
            'The configured workspace candidate prefix is invalid'
        return $?
    fi
    destination="$UTM_WORKSPACE_CANDIDATE_PREFIX-candidate-$(
        "$MACHINE_CONTROL_WORKSPACE_PYTHON" -c \
            'import secrets; print(secrets.token_hex(6))'
    )"
    if [[ -n "$(utm_workspace_id_for_name "$destination")" ]]; then
        workspace_refusal acquire destination_exists \
            'The generated workspace destination already exists'
        return $?
    fi
    "$UTM_WORKSPACE_CLI" clone --hide "$source_id" --name "$destination" \
        >/dev/null || {
            workspace_refusal acquire derivation_failed \
                'The provider could not derive a candidate workspace'
            return $?
        }
    target_id="$(utm_workspace_id_for_name "$destination")"
    if [[ -z "$target_id" || "$(utm_workspace_status "$target_id")" != "stopped" ]]; then
        workspace_refusal acquire derivation_identity_unknown \
            'The provider did not return an exact stopped candidate identity'
        return $?
    fi
    handle="$(utm_workspace_create_receipt candidate full_copy retained none \
        "$destination" "$target_id" "$UTM_WORKSPACE_READY_BASE_NAME" \
        "$source_id")" || return
    if ! utm_workspace_start "$target_id" persistent; then
        workspace_receipts "$UTM_WORKSPACE_STATE_DIR" update \
            --handle "$handle" --state unknown || true
        workspace_refusal acquire workspace_start_failed \
            'The retained candidate did not start'
        return $?
    fi
    data="$(jq -n --arg handle "$handle" \
        '{handle:$handle, requestedIntent:"candidate",
          actualMechanism:"full_copy", retention:"retained", cleanup:"none",
          storage:{costClass:"full_copy", measurement:"estimate",
            preflight:"pass"}}')"
    workspace_result acquire bounded "$data"
}

utm_workspace_acquire_inner() {
    case "$1" in
        persistent) utm_workspace_acquire_persistent ;;
        isolated) utm_workspace_acquire_isolated ;;
        candidate) utm_workspace_acquire_candidate ;;
        *) workspace_refusal acquire invalid_workspace_intent \
            'The requested workspace intent is invalid' ;;
    esac
}

utm_workspace_acquire() {
    if [[ $# -ne 3 || "$1" != "--intent" || "$3" != "--json" ]]; then
        printf 'Usage: workspace-acquire --intent INTENT --json\n' >&2
        return 2
    fi
    utm_workspace_limits_valid || {
        workspace_refusal acquire workspace_policy_invalid \
            'Workspace policy values are invalid'
        return $?
    }
    workspace_with_lock "$UTM_WORKSPACE_STATE_DIR" \
        utm_workspace_acquire_inner "$2"
}

utm_workspace_public_state() {
    case "$(utm_workspace_status "$1" 2>/dev/null || true)" in
        started) printf 'running\n' ;;
        stopped) printf 'off\n' ;;
        *) printf 'unknown\n' ;;
    esac
}

utm_workspace_release_inner() {
    local handle="$1" provider intent mechanism target_id source_id state data
    local disposition
    provider="$(workspace_receipt_field \
        "$UTM_WORKSPACE_STATE_DIR" "$handle" provider)" || {
            workspace_refusal release workspace_receipt_invalid \
                'The workspace receipt is absent or invalid'
            return $?
        }
    if [[ "$provider" != "$UTM_WORKSPACE_PROVIDER" ]]; then
        workspace_refusal release workspace_receipt_invalid \
            'The workspace receipt belongs to another provider'
        return $?
    fi
    intent="$(workspace_receipt_field \
        "$UTM_WORKSPACE_STATE_DIR" "$handle" intent)" || return
    mechanism="$(workspace_receipt_field \
        "$UTM_WORKSPACE_STATE_DIR" "$handle" mechanism)" || return
    target_id="$(workspace_receipt_field \
        "$UTM_WORKSPACE_STATE_DIR" "$handle" target.id)" || return
    if [[ "$intent" != "isolated" ]]; then
        state="$(utm_workspace_public_state "$target_id")"
        workspace_receipts "$UTM_WORKSPACE_STATE_DIR" update \
            --handle "$handle" --state "$state" --cleanup none
        data="$(jq -n --arg handle "$handle" \
            '{handle:$handle, disposition:"retained"}')"
        workspace_result release bounded "$data"
        return
    fi
    source_id="$(workspace_receipt_field \
        "$UTM_WORKSPACE_STATE_DIR" "$handle" source.id)" || return
    if [[ "$mechanism" != "provider_disposable_overlay" ||
          "$target_id" != "$UTM_WORKSPACE_READY_BASE_ID" ||
          "$source_id" != "$UTM_WORKSPACE_READY_BASE_ID" ||
          ( "$target_id" == "$UTM_WORKSPACE_DEVELOPMENT_ID" &&
            "$UTM_WORKSPACE_ALLOW_SHARED_BASE" != "true" ) ]]; then
        workspace_refusal release protected_workspace \
            'The receipt does not authorize disposable-base release'
        return $?
    fi
    state="$(utm_workspace_status "$target_id" 2>/dev/null || true)"
    if [[ -z "$state" ]]; then
        workspace_receipts "$UTM_WORKSPACE_STATE_DIR" forget --handle "$handle"
        disposition=alreadyAbsent
    else
        workspace_receipts "$UTM_WORKSPACE_STATE_DIR" update \
            --handle "$handle" --cleanup pending
        if [[ "$state" == "started" ]]; then
            "$UTM_WORKSPACE_CLI" stop --hide "$target_id" --request >/dev/null || {
                workspace_refusal release workspace_stop_failed \
                    'The disposable workspace did not accept a shutdown request'
                return $?
            }
            if ! utm_workspace_wait_state "$target_id" stopped \
                "$UTM_WORKSPACE_SHUTDOWN_TIMEOUT"; then
                workspace_refusal release workspace_stop_failed \
                    'The disposable workspace did not stop; force was not used'
                return $?
            fi
        elif [[ "$state" != "stopped" ]]; then
            workspace_refusal release workspace_state_unknown \
                'The disposable workspace state is unknown'
            return $?
        fi
        workspace_receipts "$UTM_WORKSPACE_STATE_DIR" forget --handle "$handle"
        disposition=discarded
    fi
    data="$(jq -n --arg handle "$handle" --arg disposition "$disposition" \
        '{handle:$handle, disposition:$disposition}')"
    workspace_result release none "$data"
}

utm_workspace_release() {
    if [[ $# -ne 3 || "$1" != "--handle" || "$3" != "--json" ]]; then
        printf 'Usage: workspace-release --handle HANDLE --json\n' >&2
        return 2
    fi
    workspace_with_lock "$UTM_WORKSPACE_STATE_DIR" \
        utm_workspace_release_inner "$2"
}

utm_workspace_main() {
    local command="${1:-}"
    if [[ -n "$command" ]]; then shift; fi
    case "$command" in
        workspace-capabilities)
            [[ "${1:-}" == "--json" && $# -eq 1 ]] || return 2
            utm_workspace_capabilities
            ;;
        workspace-acquire) utm_workspace_acquire "$@" ;;
        workspace-inventory)
            [[ "${1:-}" == "--json" && $# -eq 1 ]] || return 2
            workspace_inventory_result "$UTM_WORKSPACE_STATE_DIR"
            ;;
        workspace-release) utm_workspace_release "$@" ;;
        workspace-gc)
            [[ "${1:-}" == "--dry-run" && "${2:-}" == "--json" && $# -eq 2 ]] || return 2
            workspace_gc_result "$UTM_WORKSPACE_STATE_DIR"
            ;;
        *) printf 'Unknown workspace command\n' >&2; return 2 ;;
    esac
}
