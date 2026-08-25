#!/usr/bin/env bash

# Shared target-use claim helper. The authoritative adapter supplies an exact
# private provider identity and state directory; public callers see only the
# minimized claim contract.

MACHINE_CONTROL_CLAIMS_ROOT="$(
    cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd
)"
MACHINE_CONTROL_CLAIMS="${MACHINE_CONTROL_CLAIMS:-$MACHINE_CONTROL_CLAIMS_ROOT/providers/claims/claims.py}"
MACHINE_CONTROL_CLAIMS_PYTHON="${MACHINE_CONTROL_CLAIMS_PYTHON:-python3}"

claim_require_tools() {
    command -v "$MACHINE_CONTROL_CLAIMS_PYTHON" >/dev/null 2>&1 || {
        printf 'Target-use claim Python is unavailable\n' >&2
        return 1
    }
    [[ -f "$MACHINE_CONTROL_CLAIMS" ]] || {
        printf 'Target-use claim helper is unavailable\n' >&2
        return 1
    }
}

claim_store() {
    local state_dir="$1"
    shift
    "$MACHINE_CONTROL_CLAIMS_PYTHON" "$MACHINE_CONTROL_CLAIMS" \
        --state-dir "$state_dir" \
        --minimum-duration "${MACHINE_CONTROL_CLAIM_MINIMUM_DURATION:-60}" \
        --default-duration "${MACHINE_CONTROL_CLAIM_DEFAULT_DURATION:-1800}" \
        --maximum-duration "${MACHINE_CONTROL_CLAIM_MAXIMUM_DURATION:-14400}" \
        --maximum-lifetime "${MACHINE_CONTROL_CLAIM_MAXIMUM_LIFETIME:-14400}" \
        "$@"
}

claim_check_exact() {
    local state_dir="$1" provider="$2" resource_id="$3" claim_id="$4"
    shift 4
    claim_store "$state_dir" check --provider "$provider" \
        --resource-id "$resource_id" --claim-id "$claim_id" "$@"
}

claim_require_exact() {
    local state_dir="$1" provider="$2" resource_id="$3"
    if [[ "${MACHINE_CONTROL_CLAIM_POLICY:-required}" == optional ]]; then
        return 0
    fi
    if [[ -z "$resource_id" ]]; then
        printf 'Exact target identity is unavailable; repair private inventory and rerun doctor\n' >&2
        return 1
    fi
    if [[ -z "${MACHINE_CONTROL_CLAIM_ID:-}" ]]; then
        printf 'Exclusive target use requires a live claim\n' >&2
        return 1
    fi
    claim_check_exact "$state_dir" "$provider" "$resource_id" \
        "$MACHINE_CONTROL_CLAIM_ID" >/dev/null
}

claim_require_disruptive_exact() {
    local state_dir="$1" provider="$2" resource_id="$3" result
    if [[ "${MACHINE_CONTROL_CLAIM_POLICY:-required}" == optional ]]; then
        return 0
    fi
    if [[ -z "$resource_id" ]]; then
        printf 'Exact target identity is unavailable; repair private inventory and rerun doctor\n' >&2
        return 1
    fi
    if [[ -z "${MACHINE_CONTROL_CLAIM_ID:-}" ]]; then
        printf 'Exclusive target use requires a live claim\n' >&2
        return 1
    fi
    if ! result="$(claim_check_exact "$state_dir" "$provider" \
        "$resource_id" "$MACHINE_CONTROL_CLAIM_ID" \
        --required-use-class disruptive)"; then
        printf '%s\n' "$result" >&2
        return 1
    fi
}

claim_adapter_main() {
    local state_dir="$1" provider="$2" resource_id="$3" command="$4"
    shift 4
    local json=false argument
    local -a forwarded=()
    for argument in "$@"; do
        if [[ "$argument" == "--json" ]]; then
            json=true
        else
            forwarded+=("$argument")
        fi
    done
    if [[ "$json" != true ]]; then
        printf 'Claim adapter commands require --json\n' >&2
        return 2
    fi
    claim_require_tools || return
    if [[ "$command" != claim-capabilities && -z "$resource_id" ]]; then
        local operation="${command#claim-}"
        printf '{"schema":"machine-control-claim/v0","operation":"%s","accepted":false,"uncertainty":"none","errorCode":"claim_identity_unavailable","message":"Exact target identity is unavailable; repair private inventory and rerun doctor","data":{}}\n' \
            "$operation"
        return 1
    fi
    case "$command" in
        claim-capabilities)
            (( ${#forwarded[@]} == 0 )) || return 2
            claim_store "$state_dir" capabilities
            ;;
        claim-status)
            (( ${#forwarded[@]} == 0 )) || return 2
            claim_store "$state_dir" status --provider "$provider" \
                --resource-id "$resource_id"
            ;;
        claim-acquire)
            claim_store "$state_dir" acquire --provider "$provider" \
                --resource-id "$resource_id" "${forwarded[@]}"
            ;;
        claim-check)
            claim_store "$state_dir" check --provider "$provider" \
                --resource-id "$resource_id" "${forwarded[@]}"
            ;;
        claim-renew)
            claim_store "$state_dir" renew --provider "$provider" \
                --resource-id "$resource_id" "${forwarded[@]}"
            ;;
        claim-release)
            claim_store "$state_dir" release --provider "$provider" \
                --resource-id "$resource_id" "${forwarded[@]}"
            ;;
        *)
            printf 'Unknown target-use claim command\n' >&2
            return 2
            ;;
    esac
}
