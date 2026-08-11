#!/usr/bin/env bash

set -euo pipefail

readonly REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
readonly TESTBED_DIR="${MACVM_TESTBED_DIR:-$REPO_DIR/platforms/macos}"
readonly FIXTURE_ID='org.machine-control.fixture'

fail() {
    printf 'macOS provider comparison failed: %s\n' "$*" >&2
    exit 1
}

[[ -x "$TESTBED_DIR/bin/macvm" ]] || fail "missing macvm-testbed at $TESTBED_DIR"
command -v jq >/dev/null || fail 'jq is required'

control() {
    "$TESTBED_DIR/bin/macvm" control "$1"
}

require_accepted() {
    local result="$1" label="$2"
    jq -e '.schema == "machine-control/v0" and .accepted == true and
           .hostInterference == "none"' >/dev/null <<<"$result" || {
        printf '%s\n' "$result" | jq . >&2 || true
        fail "$label was not accepted"
    }
}

wait_for_fixture() {
    local expression="$1" label="$2" state
    for _ in {1..10}; do
        state="$($TESTBED_DIR/bin/macvm fixture-state 2>/dev/null || true)"
        if jq -e "$expression" >/dev/null 2>&1 <<<"$state"; then
            return 0
        fi
        sleep 0.1
    done
    fail "fixture oracle did not reach $label"
}

terminate_fixture() {
    control "$(jq -nc --arg target "$FIXTURE_ID" \
        '{operation:"application.terminate",target:$target}')" \
        >/dev/null 2>&1 || true
}

remove_capture() {
    local result="$1" label="$2" path
    require_accepted "$result" "$label exact-window capture"
    jq -e '.fidelity == "exact_window" and
           .coordinateSpace == "window_pixels"' >/dev/null <<<"$result" \
        || fail "$label capture metadata was incomplete"
    path="$(jq -er '.data.artifactPath' <<<"$result")" \
        || fail "$label capture returned no artifact path"
    "$TESTBED_DIR/bin/macvm" exec /bin/test -s "$path" \
        || fail "$label capture artifact was empty"
    "$TESTBED_DIR/bin/macvm" exec /bin/rm -f "$path"
}

run_fixture_cell() {
    local provider="$1" snapshot_route="$2" capture_route="$3"
    local launch snapshot reference action capture

    terminate_fixture
    launch="$(control "$(jq -nc --arg app "$FIXTURE_ID" \
        '{operation:"application.launch",applicationId:$app,
          provider:"macos-native"}')")"
    require_accepted "$launch" "$provider fixture setup"
    wait_for_fixture '.count == 0 and .enabled == false and .text == ""' \
        "$provider initial state"

    snapshot="$(control "$(jq -nc --arg target "$FIXTURE_ID" \
        --arg provider "$provider" \
        '{operation:"snapshot",target:$target,provider:$provider,
          query:"Increment",maxDepth:12,maxElements:120,
          projection:"compact"}')")"
    require_accepted "$snapshot" "$provider fixture snapshot"
    jq -e --arg route "$snapshot_route" '
        .actualRoute == $route and .data.projection == "compact" and
        (.data.elements | length) <= 3 and
        any(.data.elements[];
            .role == "AXButton" and .label == "Increment" and
            (.reference | length) > 0)' >/dev/null <<<"$snapshot" \
        || fail "$provider snapshot did not honor the common compact contract"
    reference="$(jq -er \
        '[.data.elements[] |
          select(.role == "AXButton" and .label == "Increment")][0].reference' \
        <<<"$snapshot")"

    action="$(control "$(jq -nc --arg reference "$reference" \
        '{operation:"action",reference:$reference,action:"press"}')")"
    require_accepted "$action" "$provider fixture action"
    jq -e --arg route "$snapshot_route" '.actualRoute == $route' \
        >/dev/null <<<"$action" || fail "$provider action changed provider route"
    wait_for_fixture '.count == 1' "$provider increment effect"

    capture="$(control "$(jq -nc --arg target "$FIXTURE_ID" \
        --arg provider "$provider" \
        '{operation:"capture",target:$target,provider:$provider}')")"
    jq -e --arg route "$capture_route" '.actualRoute == $route' \
        >/dev/null <<<"$capture" || fail "$provider capture changed provider route"
    remove_capture "$capture" "$provider fixture"
}

close_control_center() {
    local snapshot reference action
    snapshot="$(control \
        '{"operation":"snapshot","target":"Control Center","provider":"macos-native","query":"Control Center","maxDepth":10,"maxElements":160,"projection":"compact"}' \
        2>/dev/null || true)"
    reference="$(jq -er \
        '[.data.elements[]? |
          select(.role == "AXMenuBarItem" and .label == "Control Center")]
         [0].reference' <<<"$snapshot" 2>/dev/null || true)"
    if [[ -n "$reference" ]] && jq -e \
            'any(.data.elements[]?; .role == "AXWindow")' \
            >/dev/null 2>&1 <<<"$snapshot"; then
        action="$(control "$(jq -nc --arg reference "$reference" \
            '{operation:"action",reference:$reference,action:"press"}')" \
            2>/dev/null || true)"
        jq -e '.accepted == true' >/dev/null 2>&1 <<<"$action" || true
    fi
}

baseline="$(control \
    '{"operation":"applications","provider":"macos-native"}')"
require_accepted "$baseline" 'baseline application inventory'
safari_running=false
jq -e 'any(.data.applications[];
       .bundleId == "com.apple.Safari" and .running == true)' \
    >/dev/null <<<"$baseline" && safari_running=true

cleanup() {
    close_control_center
    terminate_fixture
    if [[ "$safari_running" == false ]]; then
        control \
            '{"operation":"application.terminate","target":"Safari"}' \
            >/dev/null 2>&1 || true
    fi
}
trap cleanup EXIT

status="$(control '{"operation":"status"}')"
require_accepted "$status" 'resident status'
jq -e '.data.nativeSemanticState == "ready" and
       .data.nativeCaptureState == "ready" and .data.cuaState == "ready"' \
    >/dev/null <<<"$status" \
    || fail 'native semantic, native capture, and Cua providers must be ready'

"$TESTBED_DIR/bin/macvm" deploy-fixture >/dev/null
run_fixture_cell macos-native guest.user/macos.ax guest.user/macos.quartz
run_fixture_cell cua guest.user/macos.cua guest.user/macos.cua

dock_native="$(control \
    '{"operation":"snapshot","target":"Dock","provider":"macos-native","query":"Safari","maxDepth":12,"maxElements":220,"projection":"compact"}')"
require_accepted "$dock_native" 'native Dock snapshot'
jq -e '.actualRoute == "guest.user/macos.ax" and
       any(.data.elements[];
           .role == "AXDockItem" and .label == "Safari")' \
    >/dev/null <<<"$dock_native" || fail 'native route did not expose Dock items'

dock_cua="$(control \
    '{"operation":"snapshot","target":"Dock","provider":"cua","query":"Safari","maxDepth":12,"maxElements":220,"projection":"compact"}')"
jq -e '.accepted == false and .fallbackUsed == false and
       (.errorCode | length) > 0' >/dev/null <<<"$dock_cua" \
    || fail 'Cua Dock gap was not returned as a typed no-fallback refusal'

control_center_menu="$(control \
    '{"operation":"snapshot","target":"Control Center","provider":"macos-native","query":"Control Center","maxDepth":10,"maxElements":160,"projection":"compact"}')"
require_accepted "$control_center_menu" 'native Control Center menu snapshot'
control_center_ref="$(jq -er \
    '[.data.elements[] |
      select(.role == "AXMenuBarItem" and .label == "Control Center")]
     [0].reference' <<<"$control_center_menu")" \
    || fail 'native route did not expose the Control Center menu item'
control_center_open="$(control "$(jq -nc --arg reference "$control_center_ref" \
    '{operation:"action",reference:$reference,action:"press"}')")"
require_accepted "$control_center_open" 'native Control Center open action'

control_center_state="$(control \
    '{"operation":"snapshot","target":"Control Center","provider":"macos-native","maxDepth":12,"maxElements":240,"projection":"compact"}')"
require_accepted "$control_center_state" 'native Control Center state'
jq -e '.actualRoute == "guest.user/macos.ax" and
       any(.data.elements[]; .role == "AXWindow") and
       any(.data.elements[];
           .identifier == "controlcenter-display-brightness-slider")' \
    >/dev/null <<<"$control_center_state" \
    || fail 'native route did not expose the open Control Center surface'

control_center_cua="$(control \
    '{"operation":"snapshot","target":"Control Center","provider":"cua","maxDepth":12,"maxElements":240,"projection":"compact"}')"
if jq -e '.accepted == true' >/dev/null <<<"$control_center_cua"; then
    jq -e '.actualRoute == "guest.user/macos.cua" and
           any(.data.elements[]; .role == "AXWindow")' \
        >/dev/null <<<"$control_center_cua" \
        || fail 'accepted Cua Control Center result violated the common contract'
else
    jq -e '.fallbackUsed == false and (.errorCode | length) > 0' \
        >/dev/null <<<"$control_center_cua" \
        || fail 'Cua Control Center gap was not a typed no-fallback refusal'
fi

control_center_capture="$(control \
    '{"operation":"capture","target":"Control Center","provider":"macos-native"}')"
remove_capture "$control_center_capture" 'native Control Center'
close_control_center

terminate_fixture
trap - EXIT
cleanup
printf 'macOS native/Cua provider comparison passed.\n'
