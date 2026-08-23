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
    claim_store "$state_dir" check --provider "$provider" \
        --resource-id "$resource_id" --claim-id "$claim_id"
}

claim_require_exact() {
    local state_dir="$1" provider="$2" resource_id="$3"
    if [[ "${MACHINE_CONTROL_CLAIM_POLICY:-required}" == optional ]]; then
        return 0
    fi
    if [[ -z "${MACHINE_CONTROL_CLAIM_ID:-}" ]]; then
        printf 'Exclusive target use requires a live claim\n' >&2
        return 1
    fi
    claim_check_exact "$state_dir" "$provider" "$resource_id" \
        "$MACHINE_CONTROL_CLAIM_ID" >/dev/null
}
