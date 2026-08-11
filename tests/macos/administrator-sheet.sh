#!/usr/bin/env bash

set -euo pipefail

readonly REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
readonly TESTBED_DIR="${MACVM_TESTBED_DIR:-$REPO_DIR/platforms/macos}"
readonly FIXTURE_ID='org.machine-control.admin-fixture'
readonly REQUESTER='Machine Control Admin Fixture'
readonly MODE="${1:-all}"

fail() {
    printf 'macOS administrator-sheet conformance failed: %s\n' "$*" >&2
    exit 1
}

[[ -x "$TESTBED_DIR/bin/macvm" ]] || fail "missing macvm-testbed at $TESTBED_DIR"
command -v jq >/dev/null || fail 'jq is required'
[[ -t 0 && -t 1 ]] || fail 'credential cases require an interactive terminal'
case "$MODE" in
    all|session) ;;
    *) fail 'usage: administrator-sheet.sh [all|session]' ;;
esac

control() {
    "$TESTBED_DIR/bin/macvm" control "$1"
}

require_accepted() {
    local result="$1" label="$2"
    if ! jq -e '.schema == "machine-control/v0" and .accepted == true and
                .hostInterference == "none"' >/dev/null <<<"$result"; then
        printf '%s\n' "$result" | jq . >&2 || true
        fail "$label was not accepted as an inner route"
    fi
}

require_refusal() {
    local result="$1" code="$2" label="$3"
    if ! jq -e --arg code "$code" \
            '.schema == "machine-control/v0" and .accepted == false and
             .errorCode == $code and .hostInterference == "none"' \
            >/dev/null <<<"$result"; then
        printf '%s\n' "$result" | jq . >&2 || true
        fail "$label did not fail closed with $code"
    fi
}

fixture_state() {
    "$TESTBED_DIR/bin/macvm" admin-fixture-state
}

wait_for_state() {
    local expression="$1" label="$2" state
    for _ in {1..100}; do
        state="$(fixture_state 2>/dev/null || true)"
        if jq -e "$expression" >/dev/null 2>&1 <<<"$state"; then
            printf '%s\n' "$state"
            return 0
        fi
        sleep 0.1
    done
    fail "administrator fixture did not reach $label"
}

terminate_fixture() {
    control "$(jq -nc --arg target "$FIXTURE_ID" \
        '{operation:"application.terminate",target:$target}')" \
        >/dev/null 2>&1 || true
}

launch_fixture() {
    local result state
    terminate_fixture
    "$TESTBED_DIR/bin/macvm" reset-admin-fixture
    result="$(control "$(jq -nc --arg app "$FIXTURE_ID" \
        '{operation:"application.launch",applicationId:$app}')")"
    require_accepted "$result" 'administrator fixture launch'
    state="$(wait_for_state '.status == "requested"' 'requested state')"
    jq -er '.requestId' <<<"$state"
}

begin_lease() {
    local context_id="$1" requester="${2:-$REQUESTER}" timeout="${3:-30000}"
    control "$(jq -nc --arg requester "$requester" --arg context "$context_id" \
        --argjson timeout "$timeout" \
        '{operation:"authorization.begin",expectedRequester:$requester,
          contextId:$context,timeoutMs:$timeout}')"
}

cancel_lease() {
    local lease_id="$1"
    control "$(jq -nc --arg lease "$lease_id" \
        '{operation:"authorization.cancel",leaseId:$lease}')"
}

generic_sheet_cancel() {
    local snapshot reference result
    snapshot="$(control \
        '{"operation":"snapshot","target":"com.apple.SecurityAgent","query":"Cancel","maxDepth":12,"maxElements":80}')"
    require_accepted "$snapshot" 'SecurityAgent cancel snapshot'
    reference="$(jq -er \
        '[.data.elements[] | select(.role == "AXButton" and .label == "Cancel")]
         | first.reference' <<<"$snapshot")" \
        || fail 'SecurityAgent Cancel button was not exposed'
    result="$(control "$(jq -nc --arg reference "$reference" \
        '{operation:"action",reference:$reference,action:"press"}')")"
    require_accepted "$result" 'generic SecurityAgent cancel'
}

cleanup() {
    local status
    status="$($TESTBED_DIR/bin/macvm status 2>/dev/null || true)"
    if [[ "$status" != 'running' ]]; then
        "$TESTBED_DIR/bin/macvm" up >/dev/null 2>&1 || return
    fi
    terminate_fixture
    "$TESTBED_DIR/bin/macvm" remove-admin-fixture >/dev/null 2>&1 || true
}
trap cleanup EXIT

"$TESTBED_DIR/bin/macvm" deploy-admin-fixture >/dev/null

# A semantically similar but incorrectly named sheet must not receive a lease.
request_id="$(launch_fixture)"
result="$(begin_lease "$request_id" 'Different Requester')"
require_refusal "$result" 'authorization_sheet_unavailable' 'wrong requester'
result="$(control '{"operation":"snapshot","target":"com.apple.SecurityAgent","query":"Enter your password","maxDepth":10,"maxElements":60}')"
require_accepted "$result" 'post-refusal sheet observation'
result="$(begin_lease "$request_id")"
require_accepted "$result" 'fresh lease after wrong requester'
lease_id="$(jq -er '.data.leaseId' <<<"$result")"
result="$(cancel_lease "$lease_id")"
require_accepted "$result" 'cancel after wrong requester'
wait_for_state '.status == "cancelled" and .authorized == false' \
    'cancelled state' >/dev/null

# Cancellation is independently observed and the single-use lease cannot recur.
request_id="$(launch_fixture)"
result="$(begin_lease "$request_id")"
require_accepted "$result" 'cancellation lease'
lease_id="$(jq -er '.data.leaseId' <<<"$result")"
result="$(cancel_lease "$lease_id")"
require_accepted "$result" 'lease cancellation'
jq -e '.delivery == "confirmed" and .effect == "confirmed" and
       .data.sheetDismissed == true' >/dev/null <<<"$result" \
    || fail 'cancellation did not distinguish delivery and effect'
wait_for_state '.status == "cancelled" and .errorCode == -128' \
    'cancelled fixture oracle' >/dev/null
result="$(cancel_lease "$lease_id")"
require_refusal "$result" 'authorization_lease_used' 'reused cancellation lease'

# Expired leases fail closed; a fresh lease can still safely cancel the sheet.
request_id="$(launch_fixture)"
result="$(begin_lease "$request_id" "$REQUESTER" 250)"
require_accepted "$result" 'short authorization lease'
lease_id="$(jq -er '.data.leaseId' <<<"$result")"
sleep 0.4
result="$(cancel_lease "$lease_id")"
require_refusal "$result" 'authorization_lease_expired' 'expired lease'
result="$(begin_lease "$request_id")"
require_accepted "$result" 'replacement lease after expiry'
result="$(cancel_lease "$(jq -er '.data.leaseId' <<<"$result")")"
require_accepted "$result" 'cancel after lease expiry'

# A changed or dismissed sheet invalidates the lease rather than redirecting it.
request_id="$(launch_fixture)"
result="$(begin_lease "$request_id")"
require_accepted "$result" 'changed-sheet lease'
lease_id="$(jq -er '.data.leaseId' <<<"$result")"
generic_sheet_cancel
wait_for_state '.status == "cancelled"' 'externally cancelled state' >/dev/null
result="$(cancel_lease "$lease_id")"
require_refusal "$result" 'authorization_sheet_changed' 'changed sheet'

# A resident generation change makes every old lease a stale reference.
request_id="$(launch_fixture)"
result="$(begin_lease "$request_id")"
require_accepted "$result" 'pre-restart lease'
lease_id="$(jq -er '.data.leaseId' <<<"$result")"
old_generation="$(jq -er '.generation' <<<"$result")"
"$TESTBED_DIR/bin/macvm" ui resident-restart >/dev/null
result="$(cancel_lease "$lease_id")"
require_refusal "$result" 'stale_reference' 'pre-restart lease'
new_status="$(control '{"operation":"status"}')"
require_accepted "$new_status" 'post-restart status'
[[ "$(jq -r '.generation' <<<"$new_status")" != "$old_generation" ]] \
    || fail 'resident restart did not change generation'
result="$(begin_lease "$request_id")"
require_accepted "$result" 'post-restart lease'
result="$(cancel_lease "$(jq -er '.data.leaseId' <<<"$result")")"
require_accepted "$result" 'post-restart cancellation'
missing_lease="$(jq -r '.generation' <<<"$new_status"):auth:missing"
result="$(cancel_lease "$missing_lease")"
require_refusal "$result" 'authorization_lease_missing' 'missing lease'

# One controlled incorrect attempt proves no-effect reporting and no retry.
request_id="$(launch_fixture)"
result="$(begin_lease "$request_id")"
require_accepted "$result" 'incorrect-credential lease'
lease_id="$(jq -er '.data.leaseId' <<<"$result")"
printf '\nEnter one deliberately incorrect guest credential.\n' >&2
result="$($TESTBED_DIR/bin/macvm authorization-submit "$lease_id")"
require_accepted "$result" 'incorrect credential submission'
jq -e '.delivery == "confirmed" and .effect == "no_effect" and
       .data.sheetDismissed == false and
       .retrySafety == "observe_before_retry"' >/dev/null <<<"$result" \
    || fail 'incorrect credential outcome was not bounded and observable'
wait_for_state '.status == "requested" and .authorized == false and
                .commandCompleted == false' \
    'unchanged oracle after incorrect credential' >/dev/null
result="$(cancel_lease "$lease_id")"
require_refusal "$result" 'authorization_lease_used' \
    'incorrect credential lease reuse'
result="$(begin_lease "$request_id")"
require_accepted "$result" 'cleanup lease after incorrect credential'
result="$(cancel_lease "$(jq -er '.data.leaseId' <<<"$result")")"
require_accepted "$result" 'cleanup after incorrect credential'

# A fresh correct submission must dismiss the sheet and complete the oracle.
request_id="$(launch_fixture)"
result="$(begin_lease "$request_id")"
require_accepted "$result" 'correct-credential lease'
lease_id="$(jq -er '.data.leaseId' <<<"$result")"
printf '\nEnter the guest administrator credential for the success case.\n' >&2
result="$($TESTBED_DIR/bin/macvm authorization-submit "$lease_id")"
require_accepted "$result" 'correct credential submission'
jq -e '.delivery == "confirmed" and .effect == "confirmed" and
       .data.sheetDismissed == true' >/dev/null <<<"$result" \
    || fail 'correct credential did not confirm sheet dismissal'
state="$(wait_for_state '.status == "completed" and .authorized == true and
                         .commandCompleted == true' \
    'independently completed authorization')"
[[ "$(jq -r '.requestId' <<<"$state")" == "$request_id" ]] \
    || fail 'completed authorization belonged to another fixture request'

if [[ "$MODE" == 'all' ]]; then
    "$TESTBED_DIR/bin/macvm" shutdown >/dev/null
    "$TESTBED_DIR/bin/macvm" up >/dev/null
    result="$(control '{"operation":"status"}')"
    require_accepted "$result" 'post-reboot resident status'
    jq -e '.data.semanticState == "ready" and
           .data.captureState == "ready"' \
        >/dev/null <<<"$result" || fail 'resident was not ready after reboot'
    "$TESTBED_DIR/bin/macvm" deploy-admin-fixture >/dev/null
    request_id="$(launch_fixture)"
    result="$(begin_lease "$request_id")"
    require_accepted "$result" 'post-reboot authorization lease'
    result="$(cancel_lease "$(jq -er '.data.leaseId' <<<"$result")")"
    require_accepted "$result" 'post-reboot authorization cancellation'
    wait_for_state '.status == "cancelled"' 'post-reboot cancellation' \
        >/dev/null
fi

terminate_fixture
"$TESTBED_DIR/bin/macvm" remove-admin-fixture
trap - EXIT
if "$TESTBED_DIR/bin/macvm" admin-fixture-state >/dev/null 2>&1; then
    fail 'administrator fixture oracle survived cleanup'
fi

printf 'macOS administrator-sheet conformance passed (%s).\n' "$MODE"
