#!/usr/bin/env bash

# Shared libvirt/QEMU/KVM workspace policy. Platform wrappers configure the
# LIBVIRT_WORKSPACE_* variables and then call libvirt_workspace_main.

libvirt_workspace_core_for() {
    local name="$1" identifier="$2"
    shift 2
    MC_LIBVIRT_DOMAIN_NAME="$name" MC_LIBVIRT_EXPECTED_UUID="$identifier" \
        "$LIBVIRT_WORKSPACE_CORE" "$@"
}

libvirt_workspace_domain_for() {
    local name="$1" identifier="$2"
    shift 2
    MC_LIBVIRT_DOMAIN_NAME="$name" MC_LIBVIRT_EXPECTED_UUID="$identifier" \
        "$LIBVIRT_WORKSPACE_DOMAIN" "$@"
}

libvirt_workspace_state() {
    libvirt_workspace_core_for "$1" "$2" status 2>/dev/null
}

libvirt_workspace_development_available() {
    [[ "$LIBVIRT_WORKSPACE_CURRENT_GUARDED" == true &&
       "$LIBVIRT_WORKSPACE_DEVELOPMENT_PROVEN" == true &&
       -n "$LIBVIRT_WORKSPACE_DEVELOPMENT_NAME" &&
       -n "$LIBVIRT_WORKSPACE_DEVELOPMENT_ID" ]] &&
        libvirt_workspace_core_for \
            "$LIBVIRT_WORKSPACE_DEVELOPMENT_NAME" \
            "$LIBVIRT_WORKSPACE_DEVELOPMENT_ID" inspect >/dev/null 2>&1
}

libvirt_workspace_ready_base_available() {
    [[ "$LIBVIRT_WORKSPACE_READY_BASE_PROVEN" == true &&
       -n "$LIBVIRT_WORKSPACE_READY_BASE_NAME" &&
       -n "$LIBVIRT_WORKSPACE_READY_BASE_ID" ]] &&
        [[ "$LIBVIRT_WORKSPACE_READY_BASE_ID" != "$LIBVIRT_WORKSPACE_DEVELOPMENT_ID" ||
           "$LIBVIRT_WORKSPACE_ALLOW_SHARED_BASE" == true ]] &&
        libvirt_workspace_core_for \
            "$LIBVIRT_WORKSPACE_READY_BASE_NAME" \
            "$LIBVIRT_WORKSPACE_READY_BASE_ID" inspect >/dev/null 2>&1
}

libvirt_workspace_limits_valid() {
    [[ "$LIBVIRT_WORKSPACE_MIN_FREE_BYTES" =~ ^[0-9]+$ &&
       "$LIBVIRT_WORKSPACE_MAX_TEMPORARY" =~ ^[0-9]+$ &&
       "$LIBVIRT_WORKSPACE_MAX_RETAINED" =~ ^[0-9]+$ &&
       "$LIBVIRT_WORKSPACE_MAX_RETAINED" -ge 1 &&
       "$LIBVIRT_WORKSPACE_CANDIDATE_PREFIX" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$ &&
       "$LIBVIRT_WORKSPACE_NVRAM_DIRECTORY" == /* &&
       "$LIBVIRT_WORKSPACE_NVRAM_TEMPLATE" == /* &&
       -r "$LIBVIRT_WORKSPACE_NVRAM_TEMPLATE" ]]
}

libvirt_workspace_capabilities() {
    libvirt_workspace_limits_valid || {
        printf 'Workspace policy values are invalid\n' >&2
        return 1
    }
    local persistent=unavailable derived=unavailable measurement=unavailable
    local persistent_reason=development-not-guarded
    local derived_reason=ready-base-not-proven free_bytes=""
    if libvirt_workspace_development_available; then
        persistent=available
        persistent_reason=""
    fi
    if libvirt_workspace_ready_base_available; then
        derived=available
        derived_reason=""
    fi
    free_bytes="$(workspace_free_bytes \
        "$LIBVIRT_WORKSPACE_STORAGE_PATH" 2>/dev/null || true)"
    if [[ "$free_bytes" =~ ^[0-9]+$ ]]; then measurement=exact; fi
    jq -n \
        --arg persistent "$persistent" --arg derived "$derived" \
        --arg persistentReason "$persistent_reason" \
        --arg derivedReason "$derived_reason" \
        --arg measurement "$measurement" \
        --argjson freeBytes "${free_bytes:-null}" \
        --argjson maxTemporary "$LIBVIRT_WORKSPACE_MAX_TEMPORARY" \
        --argjson maxRetained "$LIBVIRT_WORKSPACE_MAX_RETAINED" \
        '{schema:"machine-control-workspace-capabilities/v0",
          intents:{
            persistent:{availability:$persistent,retention:"retained",
              mechanisms:(if $persistent == "available" then [{
                kind:"existing_instance",costClass:"unknown",
                sourceMustBeStopped:false,concurrentWithSource:true}] else [] end),
              reasons:(if $persistentReason == "" then [] else [$persistentReason] end)},
            isolated:{availability:$derived,retention:"discardOnRelease",
              mechanisms:(if $derived == "available" then [{
                kind:"qcow_backing_overlay",costClass:"overlay",
                sourceMustBeStopped:true,concurrentWithSource:false}] else [] end),
              reasons:(if $derivedReason == "" then [] else [$derivedReason] end)},
            candidate:{availability:$derived,retention:"retained",
              mechanisms:(if $derived == "available" then [{
                kind:"qcow_backing_overlay",costClass:"overlay",
                sourceMustBeStopped:true,concurrentWithSource:false}] else [] end),
              reasons:(if $derivedReason == "" then [] else [$derivedReason] end)}},
          limits:{maxTemporaryWorkspaces:$maxTemporary,
            maxRetainedWorkspaces:$maxRetained,fullCopyFallback:"prohibited"},
          storage:{measurement:$measurement,freeBytes:$freeBytes},extensions:{}}'
}

libvirt_workspace_existing_receipt() {
    workspace_receipts "$LIBVIRT_WORKSPACE_STATE_DIR" find \
        --provider "$LIBVIRT_WORKSPACE_PROVIDER" --target-id "$1" --intent "$2"
}

libvirt_workspace_create_receipt() {
    local intent="$1" retention="$2" cleanup="$3" target_name="$4"
    local target_id="$5" source_name="${6:-}" source_id="${7:-}"
    local -a arguments=(
        create --provider "$LIBVIRT_WORKSPACE_PROVIDER" --intent "$intent"
        --mechanism "$([[ "$intent" == persistent ]] &&
            printf existing_instance || printf qcow_backing_overlay)"
        --retention "$retention" --cleanup "$cleanup" --state running
        --target-name "$target_name" --target-id "$target_id"
    )
    if [[ -n "$source_name" && -n "$source_id" ]]; then
        arguments+=(--source-name "$source_name" --source-id "$source_id")
    fi
    workspace_receipts "$LIBVIRT_WORKSPACE_STATE_DIR" "${arguments[@]}"
}

libvirt_workspace_start_selected() {
    local handle="$1" claim_id="$2"
    MACHINE_CONTROL_WORKSPACE_HANDLE="$handle" \
        MACHINE_CONTROL_CLAIM_ID="$claim_id" \
        "$LIBVIRT_WORKSPACE_PLATFORM_BIN" up >/dev/null
}

libvirt_workspace_acquire_persistent() {
    if ! libvirt_workspace_development_available; then
        workspace_refusal acquire intent_unavailable \
            'The persistent development workspace is not guarded and available'
        return $?
    fi
    local target_id="$LIBVIRT_WORKSPACE_DEVELOPMENT_ID" handle data claim claim_id
    if ! claim="$(workspace_claim_acquire_exact \
        "$LIBVIRT_WORKSPACE_CLAIM_STATE_DIR" "$LIBVIRT_WORKSPACE_PROVIDER" \
        "$target_id")"; then
        printf '%s\n' "$claim"
        return 1
    fi
    claim_id="$(jq -r '.claimId // empty' <<<"$claim")"
    handle="$(libvirt_workspace_existing_receipt "$target_id" persistent)"
    if [[ -z "$handle" ]]; then
        if ! handle="$(libvirt_workspace_create_receipt persistent retained none \
            "$LIBVIRT_WORKSPACE_DEVELOPMENT_NAME" "$target_id")"; then
            workspace_claim_release_exact "$LIBVIRT_WORKSPACE_CLAIM_STATE_DIR" \
                "$LIBVIRT_WORKSPACE_PROVIDER" "$target_id" "$claim_id" \
                >/dev/null 2>&1 || true
            return 1
        fi
    fi
    if ! libvirt_workspace_start_selected "$handle" "$claim_id"; then
        workspace_receipts "$LIBVIRT_WORKSPACE_STATE_DIR" update \
            --handle "$handle" --state unknown || true
        workspace_claim_release_exact "$LIBVIRT_WORKSPACE_CLAIM_STATE_DIR" \
            "$LIBVIRT_WORKSPACE_PROVIDER" "$target_id" "$claim_id" \
            >/dev/null 2>&1 || true
        workspace_refusal acquire workspace_start_failed \
            'The persistent workspace did not start'
        return $?
    fi
    workspace_receipts "$LIBVIRT_WORKSPACE_STATE_DIR" update \
        --handle "$handle" --state running --cleanup none
    data="$(jq -n --arg handle "$handle" \
        '{handle:$handle,requestedIntent:"persistent",
          actualMechanism:"existing_instance",retention:"retained",
          cleanup:"none",storage:{costClass:"unknown",
            measurement:"unavailable",preflight:"pass"}}')"
    data="$(workspace_data_with_claim "$data" "$claim")"
    workspace_result acquire none "$data"
}

libvirt_workspace_cleanup_derived() {
    local target_name="$1" target_id="$2" source_name="$3" source_id="$4"
    libvirt_workspace_domain_for "$target_name" "$target_id" release \
        --source-name "$source_name" --source-uuid "$source_id"
}

libvirt_workspace_acquire_derived() {
    local intent="$1" retention cleanup count maximum free_bytes token name
    local source_name="$LIBVIRT_WORKSPACE_READY_BASE_NAME"
    local source_id="$LIBVIRT_WORKSPACE_READY_BASE_ID"
    local derived target_name target_id handle data source_claim source_claim_id
    local claim claim_id
    if ! libvirt_workspace_ready_base_available; then
        workspace_refusal acquire intent_unavailable \
            'A controller-ready QCOW2 source is not explicitly proven'
        return $?
    fi
    if [[ "$(libvirt_workspace_state "$source_name" "$source_id")" != stopped ]]; then
        workspace_refusal acquire source_not_stopped \
            'QCOW2 derivation requires the ready base to be stopped'
        return $?
    fi
    if [[ "$intent" == isolated ]]; then
        retention=discardOnRelease
        cleanup=release
        maximum="$LIBVIRT_WORKSPACE_MAX_TEMPORARY"
        count="$(workspace_receipts "$LIBVIRT_WORKSPACE_STATE_DIR" inventory |
            jq -r '.counts.temporary')"
    else
        retention=retained
        cleanup=none
        maximum="$LIBVIRT_WORKSPACE_MAX_RETAINED"
        count="$(workspace_receipts "$LIBVIRT_WORKSPACE_STATE_DIR" inventory |
            jq -r '.counts.retained')"
    fi
    if (( count >= maximum )); then
        workspace_refusal acquire workspace_limit_reached \
            'The configured workspace limit is reached'
        return $?
    fi
    if ! free_bytes="$(workspace_capacity_preflight \
        "$LIBVIRT_WORKSPACE_STORAGE_PATH" "$LIBVIRT_WORKSPACE_MIN_FREE_BYTES")"; then
        workspace_refusal acquire storage_preflight_failed \
            'The configured workspace storage reserve is unavailable'
        return $?
    fi
    if ! source_claim="$(workspace_claim_acquire_exact \
        "$LIBVIRT_WORKSPACE_CLAIM_STATE_DIR" "$LIBVIRT_WORKSPACE_PROVIDER" \
        "$source_id")"; then
        printf '%s\n' "$source_claim"
        return 1
    fi
    source_claim_id="$(jq -r '.claimId // empty' <<<"$source_claim")"
    token="$("$MACHINE_CONTROL_WORKSPACE_PYTHON" -c \
        'import secrets; print(secrets.token_hex(6))')"
    target_name="$LIBVIRT_WORKSPACE_CANDIDATE_PREFIX-$intent-$token"
    if ! derived="$(libvirt_workspace_domain_for "$source_name" "$source_id" \
        derive --name "$target_name" \
        --nvram-directory "$LIBVIRT_WORKSPACE_NVRAM_DIRECTORY" \
        --nvram-template "$LIBVIRT_WORKSPACE_NVRAM_TEMPLATE")"; then
        workspace_claim_release_exact "$LIBVIRT_WORKSPACE_CLAIM_STATE_DIR" \
            "$LIBVIRT_WORKSPACE_PROVIDER" "$source_id" "$source_claim_id" \
            >/dev/null 2>&1 || true
        workspace_refusal acquire derivation_failed \
            'The provider could not derive an exact QCOW2 workspace'
        return $?
    fi
    target_id="$(jq -r '.uuid // empty' <<<"$derived")"
    target_name="$(jq -r '.name // empty' <<<"$derived")"
    if [[ -z "$target_id" || -z "$target_name" ]]; then
        workspace_claim_release_exact "$LIBVIRT_WORKSPACE_CLAIM_STATE_DIR" \
            "$LIBVIRT_WORKSPACE_PROVIDER" "$source_id" "$source_claim_id" \
            >/dev/null 2>&1 || true
        workspace_refusal acquire derivation_identity_unknown \
            'The provider did not return an exact derived identity'
        return $?
    fi
    if ! claim="$(workspace_claim_acquire_exact \
        "$LIBVIRT_WORKSPACE_CLAIM_STATE_DIR" "$LIBVIRT_WORKSPACE_PROVIDER" \
        "$target_id")"; then
        libvirt_workspace_cleanup_derived "$target_name" "$target_id" \
            "$source_name" "$source_id" >/dev/null 2>&1 || true
        workspace_claim_release_exact "$LIBVIRT_WORKSPACE_CLAIM_STATE_DIR" \
            "$LIBVIRT_WORKSPACE_PROVIDER" "$source_id" "$source_claim_id" \
            >/dev/null 2>&1 || true
        printf '%s\n' "$claim"
        return 1
    fi
    claim_id="$(jq -r '.claimId // empty' <<<"$claim")"
    workspace_claim_release_exact "$LIBVIRT_WORKSPACE_CLAIM_STATE_DIR" \
        "$LIBVIRT_WORKSPACE_PROVIDER" "$source_id" "$source_claim_id" \
        >/dev/null 2>&1 || true
    if ! handle="$(libvirt_workspace_create_receipt "$intent" "$retention" \
        "$cleanup" "$target_name" "$target_id" "$source_name" "$source_id")"; then
        libvirt_workspace_cleanup_derived "$target_name" "$target_id" \
            "$source_name" "$source_id" >/dev/null 2>&1 || true
        workspace_claim_release_exact "$LIBVIRT_WORKSPACE_CLAIM_STATE_DIR" \
            "$LIBVIRT_WORKSPACE_PROVIDER" "$target_id" "$claim_id" \
            >/dev/null 2>&1 || true
        return 1
    fi
    if ! libvirt_workspace_start_selected "$handle" "$claim_id"; then
        workspace_receipts "$LIBVIRT_WORKSPACE_STATE_DIR" update \
            --handle "$handle" --state unknown --cleanup pending || true
        workspace_claim_release_exact "$LIBVIRT_WORKSPACE_CLAIM_STATE_DIR" \
            "$LIBVIRT_WORKSPACE_PROVIDER" "$target_id" "$claim_id" \
            >/dev/null 2>&1 || true
        workspace_refusal acquire workspace_start_failed \
            'The derived workspace was retained for diagnosis but did not start'
        return $?
    fi
    data="$(jq -n --arg handle "$handle" --arg intent "$intent" \
        --arg retention "$retention" --arg cleanup "$cleanup" \
        '{handle:$handle,requestedIntent:$intent,
          actualMechanism:"qcow_backing_overlay",retention:$retention,
          cleanup:$cleanup,storage:{costClass:"overlay",measurement:"exact",
            preflight:"pass"}}')"
    data="$(workspace_data_with_claim "$data" "$claim")"
    workspace_result acquire bounded "$data"
}

libvirt_workspace_acquire_inner() {
    case "$MACHINE_CONTROL_WORKSPACE_CLAIM_INTENT" in
        persistent) libvirt_workspace_acquire_persistent ;;
        isolated|candidate)
            libvirt_workspace_acquire_derived \
                "$MACHINE_CONTROL_WORKSPACE_CLAIM_INTENT"
            ;;
        *) workspace_refusal acquire invalid_workspace_intent \
            'The requested workspace intent is invalid' ;;
    esac
}

libvirt_workspace_acquire() {
    if ! workspace_parse_claimed_acquire "$@"; then
        printf 'Usage: workspace-acquire --intent INTENT CLAIMANT... --json\n' >&2
        return 2
    fi
    libvirt_workspace_limits_valid || {
        workspace_refusal acquire workspace_policy_invalid \
            'Workspace policy values are invalid'
        return $?
    }
    workspace_with_lock "$LIBVIRT_WORKSPACE_STATE_DIR" \
        libvirt_workspace_acquire_inner
}

libvirt_workspace_release_inner() {
    local handle="$1" provider intent mechanism target_name target_id
    local source_name source_id state data disposition
    provider="$(workspace_receipt_field \
        "$LIBVIRT_WORKSPACE_STATE_DIR" "$handle" provider)" || {
        workspace_refusal release workspace_receipt_invalid \
            'The workspace receipt is absent or invalid'
        return $?
    }
    if [[ "$provider" != "$LIBVIRT_WORKSPACE_PROVIDER" ]]; then
        workspace_refusal release workspace_receipt_invalid \
            'The workspace receipt belongs to another provider'
        return $?
    fi
    intent="$(workspace_receipt_field \
        "$LIBVIRT_WORKSPACE_STATE_DIR" "$handle" intent)" || return
    mechanism="$(workspace_receipt_field \
        "$LIBVIRT_WORKSPACE_STATE_DIR" "$handle" mechanism)" || return
    target_name="$(workspace_receipt_field \
        "$LIBVIRT_WORKSPACE_STATE_DIR" "$handle" target.name)" || return
    target_id="$(workspace_receipt_field \
        "$LIBVIRT_WORKSPACE_STATE_DIR" "$handle" target.id)" || return
    workspace_claim_check_release_exact "$LIBVIRT_WORKSPACE_CLAIM_STATE_DIR" \
        "$LIBVIRT_WORKSPACE_PROVIDER" "$target_id" || return
    if [[ "$intent" != isolated ]]; then
        state="$(libvirt_workspace_state "$target_name" "$target_id" || printf unknown)"
        case "$state" in started) state=running ;; stopped) state=off ;; *) state=unknown ;; esac
        workspace_receipts "$LIBVIRT_WORKSPACE_STATE_DIR" update \
            --handle "$handle" --state "$state" --cleanup none
        data="$(jq -n --arg handle "$handle" \
            '{handle:$handle,disposition:"retained"}')"
        workspace_claim_release_selected "$LIBVIRT_WORKSPACE_CLAIM_STATE_DIR" \
            "$LIBVIRT_WORKSPACE_PROVIDER" "$target_id" || return
        workspace_result release bounded "$data"
        return
    fi
    source_name="$(workspace_receipt_field \
        "$LIBVIRT_WORKSPACE_STATE_DIR" "$handle" source.name)" || return
    source_id="$(workspace_receipt_field \
        "$LIBVIRT_WORKSPACE_STATE_DIR" "$handle" source.id)" || return
    if [[ "$mechanism" != qcow_backing_overlay ||
          "$source_id" != "$LIBVIRT_WORKSPACE_READY_BASE_ID" ||
          "$source_name" != "$LIBVIRT_WORKSPACE_READY_BASE_NAME" ||
          "$target_id" == "$source_id" ]]; then
        workspace_refusal release protected_workspace \
            'The receipt does not authorize derived workspace cleanup'
        return $?
    fi
    workspace_receipts "$LIBVIRT_WORKSPACE_STATE_DIR" update \
        --handle "$handle" --cleanup pending
    state="$(libvirt_workspace_state "$target_name" "$target_id" || printf unknown)"
    if [[ "$state" == started ]]; then
        MACHINE_CONTROL_WORKSPACE_HANDLE="$handle" \
            MACHINE_CONTROL_CLAIM_ID="$MACHINE_CONTROL_CLAIM_ID" \
            "$LIBVIRT_WORKSPACE_PLATFORM_BIN" shutdown >/dev/null || {
            workspace_refusal release workspace_stop_failed \
                'The derived workspace did not shut down cleanly'
            return $?
        }
    elif [[ "$state" != stopped ]]; then
        workspace_refusal release workspace_state_unknown \
            'The derived workspace state is unknown'
        return $?
    fi
    if ! libvirt_workspace_cleanup_derived "$target_name" "$target_id" \
        "$source_name" "$source_id"; then
        workspace_refusal release workspace_cleanup_failed \
            'The exact derived domain or volume could not be cleaned'
        return $?
    fi
    workspace_receipts "$LIBVIRT_WORKSPACE_STATE_DIR" forget --handle "$handle"
    disposition=discarded
    data="$(jq -n --arg handle "$handle" --arg disposition "$disposition" \
        '{handle:$handle,disposition:$disposition}')"
    workspace_claim_release_selected "$LIBVIRT_WORKSPACE_CLAIM_STATE_DIR" \
        "$LIBVIRT_WORKSPACE_PROVIDER" "$target_id" || return
    workspace_result release none "$data"
}

libvirt_workspace_release() {
    if [[ $# -ne 3 || "$1" != --handle || "$3" != --json ]]; then
        printf 'Usage: workspace-release --handle HANDLE --json\n' >&2
        return 2
    fi
    workspace_with_lock "$LIBVIRT_WORKSPACE_STATE_DIR" \
        libvirt_workspace_release_inner "$2"
}

libvirt_workspace_main() {
    local command="${1:-}"
    if [[ -n "$command" ]]; then shift; fi
    case "$command" in
        workspace-capabilities)
            [[ "${1:-}" == --json && $# -eq 1 ]] || return 2
            libvirt_workspace_capabilities
            ;;
        workspace-acquire) libvirt_workspace_acquire "$@" ;;
        workspace-inventory)
            [[ "${1:-}" == --json && $# -eq 1 ]] || return 2
            workspace_inventory_result "$LIBVIRT_WORKSPACE_STATE_DIR"
            ;;
        workspace-release) libvirt_workspace_release "$@" ;;
        workspace-gc)
            [[ "${1:-}" == --dry-run && "${2:-}" == --json && $# -eq 2 ]] || return 2
            workspace_gc_result "$LIBVIRT_WORKSPACE_STATE_DIR"
            ;;
        *) return 2 ;;
    esac
}
