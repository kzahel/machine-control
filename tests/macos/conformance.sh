#!/usr/bin/env bash

set -euo pipefail

readonly REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
readonly TESTBED_DIR="${MACVM_TESTBED_DIR:-$REPO_DIR/../macvm-testbed}"
readonly FIXTURE_ID='org.machine-control.fixture'
readonly MODE="${1:-all}"

fail() {
    printf 'macOS conformance failed: %s\n' "$*" >&2
    exit 1
}

[[ -x "$TESTBED_DIR/bin/macvm" ]] || fail "missing macvm-testbed at $TESTBED_DIR"
command -v jq >/dev/null || fail 'jq is required'
case "$MODE" in
    all) placements=(remote local) ;;
    remote|local) placements=("$MODE") ;;
    *) fail 'usage: conformance.sh [all|remote|local]' ;;
esac

control() {
    local placement="$1" request="$2"
    case "$placement" in
        remote) "$TESTBED_DIR/bin/macvm" control "$request" ;;
        local) "$TESTBED_DIR/bin/macvm" control-local "$request" ;;
    esac
}

require_accepted() {
    local result="$1" label="$2"
    if ! jq -e '.schema == "machine-control/v0" and .accepted == true' \
            >/dev/null <<<"$result"; then
        printf '%s\n' "$result" | jq . >&2 || true
        fail "$label was not accepted"
    fi
    if [[ "$(jq -r '.hostInterference' <<<"$result")" != 'none' ]]; then
        fail "$label reported host interference"
    fi
}

fixture_state() {
    "$TESTBED_DIR/bin/macvm" fixture-state
}

wait_for_fixture() {
    local expression="$1" label="$2" state
    for _ in {1..8}; do
        state="$(fixture_state 2>/dev/null || true)"
        if jq -e "$expression" >/dev/null 2>&1 <<<"$state"; then
            printf '%s\n' "$state"
            return 0
        fi
        sleep 0.1
    done
    fail "fixture oracle did not reach $label"
}

snapshot_reference() {
    local placement="$1" query="$2" role="$3" result
    result="$(control "$placement" "$(jq -nc \
        --arg target "$FIXTURE_ID" --arg query "$query" \
        '{operation:"snapshot",target:$target,query:$query,
          maxDepth:12,maxElements:120,projection:"compact"}')")"
    require_accepted "$result" "fixture snapshot for $query"
    jq -er --arg label "$query" --arg role "$role" \
        '[.data.elements[] | select(.role == $role and
          ($label == "" or .label == $label))]
         | first.reference' <<<"$result" \
        || fail "snapshot did not expose $role '$query'"
}

terminate_fixture() {
    local placement="$1"
    control "$placement" "$(jq -nc --arg target "$FIXTURE_ID" \
        '{operation:"application.terminate",target:$target}')" \
        >/dev/null 2>&1 || true
}

run_fixture_workflow() {
    local placement="$1" result reference state before_key_count capture_path

    terminate_fixture "$placement"
    result="$(control "$placement" "$(jq -nc --arg app "$FIXTURE_ID" \
        '{requestId:("fixture-launch-" + $app),operation:"application.launch",
          applicationId:$app}')")"
    require_accepted "$result" "$placement fixture launch"
    jq -e '.effect == "confirmed" and .data.launch_state.window_ready == true' \
        >/dev/null <<<"$result" || fail "$placement fixture window was not ready"
    state="$(wait_for_fixture '.count == 0 and .enabled == false and .text == ""' \
        'initial state')"
    before_key_count="$(jq -r '.keyEventCount' <<<"$state")"

    result="$(control "$placement" "$(jq -nc --arg target "$FIXTURE_ID" \
        '{operation:"input.key",target:$target,key:"cmd-a"}')")"
    require_accepted "$result" "$placement guest-local hotkey"
    jq -e '.actualRoute == "guest.user/macos.cua" and
           .delivery == "confirmed" and .focusConsequence != null' \
        >/dev/null <<<"$result" || fail "$placement hotkey route was incomplete"
    state="$(fixture_state)"
    if ! jq -e ".keyEventCount > $before_key_count" >/dev/null <<<"$state"; then
        result="$(control "$placement" "$(jq -nc --arg target "$FIXTURE_ID" \
            '{operation:"input.key",target:$target,key:"cmd-a",
              deliveryMode:"foreground"}')")"
        require_accepted "$result" "$placement foreground hotkey fallback"
        wait_for_fixture ".keyEventCount > $before_key_count" \
            'a received foreground key event' >/dev/null
    fi

    result="$(control "$placement" "$(jq -nc --arg target "$FIXTURE_ID" \
        --arg text "raw-$placement" \
        '{operation:"input.text",target:$target,text:$text}')")"
    require_accepted "$result" "$placement guest-local text"
    wait_for_fixture ".text == \"raw-$placement\"" 'raw text input' >/dev/null

    reference="$(snapshot_reference "$placement" Enabled AXCheckBox)"
    result="$(control "$placement" "$(jq -nc --arg reference "$reference" \
        '{operation:"action",reference:$reference,action:"press"}')")"
    require_accepted "$result" "$placement checkbox action"
    wait_for_fixture '.enabled == true' 'enabled checkbox effect' >/dev/null

    reference="$(snapshot_reference "$placement" Increment AXButton)"
    result="$(control "$placement" "$(jq -nc --arg reference "$reference" \
        '{operation:"action",reference:$reference,action:"press"}')")"
    require_accepted "$result" "$placement increment action"
    wait_for_fixture '.count == 1' 'increment file effect' >/dev/null

    reference="$(snapshot_reference "$placement" '' AXTextField)"
    result="$(control "$placement" "$(jq -nc --arg reference "$reference" \
        --arg text "semantic-$placement" \
        '{operation:"action",reference:$reference,action:"set_value",text:$text}')")"
    require_accepted "$result" "$placement semantic text action"
    wait_for_fixture ".text == \"semantic-$placement\"" \
        'semantic text effect' >/dev/null

    result="$(control "$placement" "$(jq -nc --arg target "$FIXTURE_ID" \
        '{operation:"capture",target:$target}')")"
    require_accepted "$result" "$placement exact-window capture"
    jq -e '.fidelity == "exact_window" and
           .coordinateSpace == "window_pixels"' >/dev/null <<<"$result" \
        || fail "$placement capture did not report exact-window fidelity"
    capture_path="$(jq -er '.data.screenshot_file_path' <<<"$result")" \
        || fail "$placement capture returned no file artifact"
    "$TESTBED_DIR/bin/macvm" exec /bin/test -s "$capture_path" \
        || fail "$placement capture artifact was empty"

    terminate_fixture "$placement"
}

"$TESTBED_DIR/bin/macvm" deploy-fixture >/dev/null

remote_status="$(control remote \
    '{"requestId":"remote-status","operation":"status"}')"
local_status="$(control local \
    '{"requestId":"local-status","operation":"status"}')"
require_accepted "$remote_status" 'remote resident status'
require_accepted "$local_status" 'local resident status'
[[ "$(jq -r '.generation' <<<"$remote_status")" == \
   "$(jq -r '.generation' <<<"$local_status")" ]] \
    || fail 'local and remote placements reached different residents'

capabilities="$(control remote '{"operation":"capabilities"}')"
require_accepted "$capabilities" 'resident capabilities'
jq -e '[.data.providers[] | select(.state == "ready")] | length > 0' \
    >/dev/null <<<"$capabilities" || fail 'no resident provider is ready'

for placement in "${placements[@]}"; do
    run_fixture_workflow "$placement"
done

terminate_fixture remote
launch="$(control remote "$(jq -nc --arg app "$FIXTURE_ID" \
    '{operation:"application.launch",applicationId:$app}')")"
require_accepted "$launch" 'stale-reference fixture launch'
old_snapshot="$(control remote "$(jq -nc --arg target "$FIXTURE_ID" \
    '{operation:"snapshot",target:$target,query:"Increment",
      maxDepth:10,maxElements:80}')")"
require_accepted "$old_snapshot" 'stale-reference snapshot'
old_reference="$(jq -er \
    '[.data.elements[] | select(.label == "Increment")][0].reference' \
    <<<"$old_snapshot")"
old_generation="$(jq -r '.generation' <<<"$old_snapshot")"
"$TESTBED_DIR/bin/macvm" ui resident-restart >/dev/null
new_status="$(control remote '{"operation":"status"}')"
require_accepted "$new_status" 'post-restart status'
[[ "$(jq -r '.generation' <<<"$new_status")" != "$old_generation" ]] \
    || fail 'resident restart did not change generation'
stale="$(control remote "$(jq -nc --arg reference "$old_reference" \
    '{operation:"action",reference:$reference,action:"press"}')")"
jq -e '.accepted == false and .errorCode == "stale_reference" and
       .staleReferenceEvents == 1' >/dev/null <<<"$stale" \
    || fail 'old reference did not fail closed after restart'
terminate_fixture remote

printf 'macOS resident conformance passed (%s).\n' "$MODE"
