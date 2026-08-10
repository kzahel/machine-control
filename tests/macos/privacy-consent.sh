#!/usr/bin/env bash

set -euo pipefail

readonly REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
readonly TESTBED_DIR="${MACVM_TESTBED_DIR:-$REPO_DIR/../macvm-testbed}"
readonly FIXTURE_ID='org.machine-control.privacy-fixture'
readonly PROMPT_ID='com.apple.UserNotificationCenter'
export MACVM_FORBID_OUTER_UI=true

fail() {
    printf 'macOS privacy consent failed: %s\n' "$*" >&2
    exit 1
}

control() {
    local placement="$1" request="$2"
    case "$placement" in
        remote) "$TESTBED_DIR/bin/macvm" control "$request" ;;
        local) "$TESTBED_DIR/bin/macvm" control-local "$request" ;;
        *) fail "unknown placement $placement" ;;
    esac
}

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
    for _ in {1..30}; do
        state="$(fixture_state 2>/dev/null || true)"
        if jq -e "$expression" >/dev/null 2>&1 <<<"$state"; then
            printf '%s\n' "$state"
            return 0
        fi
        sleep 0.1
    done
    fail "fixture oracle did not record $label"
}

press_named() {
    local placement="$1" target="$2" label="$3" snapshot reference result
    snapshot="$(control "$placement" "$(jq -nc --arg target "$target" \
        --arg query "$label" \
        '{operation:"snapshot",target:$target,query:$query,
          maxDepth:8,maxElements:100,projection:"compact"}')")"
    require_accepted "$snapshot" "$label snapshot"
    reference="$(jq -er --arg label "$label" \
        '[.data.elements[] | select(.role == "AXButton" and .label == $label and
          (.actions | index("AXPress")))][0].reference' <<<"$snapshot")" \
        || fail "button '$label' was not uniquely available on $target"
    result="$(control "$placement" "$(jq -nc --arg reference "$reference" \
        '{operation:"action",reference:$reference,action:"press"}')")"
    require_accepted "$result" "$label press"
}

wait_for_prompt() {
    local service_text="$1" snapshot
    for _ in {1..30}; do
        snapshot="$(control remote "$(jq -nc --arg target "$PROMPT_ID" \
            '{operation:"snapshot",target:$target,maxDepth:3,maxElements:20,
              projection:"compact"}')" 2>/dev/null || true)"
        if jq -e --arg fixture 'Machine Control Privacy Fixture' \
                --arg service "$service_text" \
                '.accepted == true and
                 ([.data.elements[] | (.label // ""), (.value // "")] | join(" ") |
                  contains($fixture) and contains($service)) and
                 ([.data.elements[] | select(.label == "Allow")] | length == 1) and
                 ([.data.elements[] | select(.label == "Don’t Allow")] | length == 1)' \
                >/dev/null 2>&1 <<<"$snapshot"; then
            return 0
        fi
        sleep 0.1
    done
    fail "$service_text consent prompt was not observed"
}

reset_and_launch() {
    local service="$1" result
    "$TESTBED_DIR/bin/macvm" reset-privacy-fixture "$service" >/dev/null
    result="$(control remote "$(jq -nc --arg app "$FIXTURE_ID" \
        '{operation:"application.launch",applicationId:$app}')")"
    require_accepted "$result" "$service fixture launch"
    wait_for_state '.services.camera.authorization != null' 'initial privacy state' \
        >/dev/null
}

run_decision() {
    local service="$1" trigger="$2" prompt_text="$3" decision="$4"
    local expression="$5"
    reset_and_launch "$service"
    press_named remote "$FIXTURE_ID" "$trigger"
    wait_for_prompt "$prompt_text"
    press_named local "$PROMPT_ID" "$decision"
    wait_for_state "$expression" "$service $decision effect" >/dev/null
}

cleanup() {
    local service
    control remote "$(jq -nc --arg target "$FIXTURE_ID" \
        '{operation:"application.terminate",target:$target}')" \
        >/dev/null 2>&1 || true
    for service in camera microphone automation; do
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

"$TESTBED_DIR/bin/macvm" deploy-privacy-fixture >/dev/null
host_before="$($TESTBED_DIR/bin/macvm host-state)"

run_decision camera Camera Camera 'Don’t Allow' \
    '.services.camera.authorization == "denied" and
     .services.camera.hardwareAvailable == false'
run_decision camera Camera Camera Allow \
    '.services.camera.authorization == "authorized" and
     .services.camera.hardwareAvailable == false'

run_decision microphone Microphone Microphone 'Don’t Allow' \
    '.services.microphone.authorization == "denied" and
     .services.microphone.hardwareAvailable == false'
run_decision microphone Microphone Microphone Allow \
    '.services.microphone.authorization == "authorized" and
     .services.microphone.hardwareAvailable == false'

run_decision automation 'Automation (System Events)' 'System Events' \
    'Don’t Allow' \
    '.services.automation.effect == "no_reply" and
     .services.automation.errorCode == -1743'
run_decision automation 'Automation (System Events)' 'System Events' Allow \
    '.services.automation.effect == "system_events_replied" and
     .services.automation.errorCode == null'

host_after="$($TESTBED_DIR/bin/macvm host-state)"
[[ "$(jq -S . <<<"$host_before")" == "$(jq -S . <<<"$host_after")" ]] \
    || fail 'privacy workflows changed the host cursor or frontmost application'

printf 'macOS standard privacy consent passed (deny and allow).\n'
