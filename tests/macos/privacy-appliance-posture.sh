#!/usr/bin/env bash

set -euo pipefail

readonly REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
readonly TESTBED_DIR="${MACVM_TESTBED_DIR:-$REPO_DIR/../macvm-testbed}"
readonly FIXTURE_ID='org.machine-control.privacy-fixture'
export MACVM_FORBID_OUTER_UI=true

fail() {
    printf 'macOS privacy posture failed: %s\n' "$*" >&2
    exit 1
}

control() { "$TESTBED_DIR/bin/macvm" control "$1"; }

require_accepted() {
    local result="$1" label="$2"
    jq -e '.schema == "machine-control/v0" and .accepted == true and
           .hostInterference == "none"' >/dev/null <<<"$result" || {
        jq . <<<"$result" >&2 || true
        fail "$label was not accepted"
    }
}

fixture_state() { "$TESTBED_DIR/bin/macvm" privacy-fixture-state; }

wait_for_state() {
    local expression="$1" label="$2" state
    for _ in {1..50}; do
        state="$(fixture_state 2>/dev/null || true)"
        if jq -e "$expression" >/dev/null 2>&1 <<<"$state"; then
            return 0
        fi
        sleep 0.1
    done
    fail "fixture oracle did not record $label"
}

launch_fixture() {
    local result
    control "$(jq -nc --arg target "$FIXTURE_ID" \
        '{operation:"application.terminate",target:$target}')" \
        >/dev/null 2>&1 || true
    result="$(control "$(jq -nc --arg app "$FIXTURE_ID" \
        '{operation:"application.launch",applicationId:$app}')")"
    require_accepted "$result" 'privacy fixture launch'
    wait_for_state '.services.accessibility.authorization != null' \
        'initial permission state'
}

press_button() {
    local label="$1" snapshot reference result
    snapshot="$(control "$(jq -nc --arg target "$FIXTURE_ID" \
        --arg query "$label" \
        '{operation:"snapshot",target:$target,query:$query,
          maxDepth:10,maxElements:140,projection:"compact"}')")"
    require_accepted "$snapshot" "$label snapshot"
    reference="$(jq -er --arg label "$label" \
        '[.data.elements[] | select(.role == "AXButton" and
          .label == $label and (.actions | index("AXPress")))][0].reference' \
        <<<"$snapshot")" || fail "button '$label' was unavailable"
    result="$(control "$(jq -nc --arg reference "$reference" \
        '{operation:"action",reference:$reference,action:"press"}')")"
    require_accepted "$result" "$label press"
}

cleanup() {
    local service
    control "$(jq -nc --arg target "$FIXTURE_ID" \
        '{operation:"application.terminate",target:$target}')" \
        >/dev/null 2>&1 || true
    for service in documents-folder downloads-folder full-disk-access; do
        "$TESTBED_DIR/bin/macvm" reset-privacy-fixture "$service" \
            >/dev/null 2>&1 || true
    done
}
trap cleanup EXIT

[[ -x "$TESTBED_DIR/bin/macvm" ]] || fail "missing macvm-testbed at $TESTBED_DIR"
command -v jq >/dev/null || fail 'jq is required'
if "$TESTBED_DIR/bin/macvm" screenshot >/dev/null 2>&1; then
    fail 'outer screenshot was available during privacy acceptance'
fi

sip_status="$($TESTBED_DIR/bin/macvm exec /usr/bin/csrutil status)"
[[ "$sip_status" == *disabled* ]] \
    || fail 'the current posture assertion expects the prepared SIP-disabled image'

"$TESTBED_DIR/bin/macvm" deploy-privacy-fixture >/dev/null
for service in documents-folder downloads-folder full-disk-access; do
    "$TESTBED_DIR/bin/macvm" reset-privacy-fixture "$service" >/dev/null
done
host_before="$($TESTBED_DIR/bin/macvm host-state)"
launch_fixture

press_button 'Documents Folder'
wait_for_state '.services["documents-folder"].effect == "read_succeeded"' \
    'unenforced Documents access'
press_button 'Downloads Folder'
wait_for_state '.services["downloads-folder"].effect == "read_succeeded"' \
    'unenforced Downloads access'
press_button 'Full Disk Access probe'
wait_for_state '.services["full-disk-access"].effect ==
                "protected_read_succeeded"' \
    'unenforced protected-data access'

host_after="$($TESTBED_DIR/bin/macvm host-state)"
[[ "$(jq -S . <<<"$host_before")" == "$(jq -S . <<<"$host_after")" ]] \
    || fail 'privacy posture changed the host cursor or frontmost application'

printf '%s\n' \
    'macOS privacy posture passed: protected-file enforcement is unavailable.'
