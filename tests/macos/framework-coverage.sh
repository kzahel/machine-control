#!/usr/bin/env bash

set -euo pipefail

readonly REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
readonly TESTBED_DIR="${MACVM_TESTBED_DIR:-$REPO_DIR/../macvm-testbed}"
readonly APPKIT_ID='org.machine-control.fixture'
readonly SWIFTUI_ID='org.machine-control.swiftui-fixture'
export MACVM_FORBID_OUTER_UI=true

fail() {
    printf 'macOS framework coverage failed: %s\n' "$*" >&2
    exit 1
}

control() {
    local placement="$1" request="$2"
    case "$placement" in
        remote) "$TESTBED_DIR/bin/macvm" control "$request" ;;
        local) "$TESTBED_DIR/bin/macvm" control-local "$request" ;;
        *) fail "unknown placement: $placement" ;;
    esac
}

require_accepted() {
    local result="$1" label="$2"
    jq -e '.schema == "machine-control/v0" and .accepted == true and
           .agentRoundTrips == 1 and .hostInterference == "none"' \
        >/dev/null <<<"$result" || {
        jq . <<<"$result" >&2 || true
        fail "$label was not accepted"
    }
}

terminate_app() {
    local app="$1"
    control remote "$(jq -nc --arg target "$app" \
        '{operation:"application.terminate",target:$target}')" \
        >/dev/null 2>&1 || true
}

launch_app() {
    local placement="$1" app="$2" result
    result="$(control "$placement" "$(jq -nc --arg app "$app" \
        '{operation:"application.launch",applicationId:$app}')")"
    require_accepted "$result" "$app launch through $placement"
    jq -e '.delivery == "confirmed" and .effect == "confirmed"' \
        >/dev/null <<<"$result" || fail "$app launch effect was not confirmed"
}

snapshot_button() {
    local placement="$1" app="$2" label="$3" result
    result="$(control "$placement" "$(jq -nc --arg target "$app" \
        --arg query "$label" \
        '{operation:"snapshot",target:$target,query:$query,
          maxDepth:16,maxElements:160,projection:"compact"}')")"
    require_accepted "$result" "$app $label snapshot through $placement"
    jq -e --arg label "$label" '
        .actualRoute == "guest.user/macos.ax" and
        .fidelity == "semantic_native" and
        .data.projection == "compact" and
        ([.data.elements[] | select(.role == "AXButton" and
          .label == $label and .enabled == true and
          (.actions | index("AXPress")))] | length) == 1' \
        >/dev/null <<<"$result" \
        || fail "$app did not expose one semantic $label button"
    printf '%s\n' "$result"
}

press_snapshot_button() {
    local placement="$1" snapshot="$2" label="$3" result reference
    reference="$(jq -er --arg label "$label" \
        '[.data.elements[] | select(.role == "AXButton" and
          .label == $label)][0].reference' <<<"$snapshot")"
    result="$(control "$placement" "$(jq -nc --arg reference "$reference" \
        '{operation:"action",reference:$reference,action:"press"}')")"
    require_accepted "$result" "$label action"
    jq -e '.delivery == "confirmed" and
           (.effect == "confirmed" or .effect == "unverifiable") and
           .actualRoute == "guest.user/macos.ax"' >/dev/null <<<"$result" \
        || fail "$label action did not report honest delivery and effect"
}

wait_for_state() {
    local command="$1" expression="$2" label="$3" state
    for _ in {1..30}; do
        state="$($TESTBED_DIR/bin/macvm "$command" 2>/dev/null || true)"
        if jq -e "$expression" >/dev/null 2>&1 <<<"$state"; then
            return 0
        fi
        sleep 0.1
    done
    fail "$label was not observed in the fixture oracle"
}

cleanup() {
    terminate_app "$SWIFTUI_ID"
    terminate_app "$APPKIT_ID"
}
trap cleanup EXIT

[[ -x "$TESTBED_DIR/bin/macvm" ]] || fail "missing macvm-testbed at $TESTBED_DIR"
command -v jq >/dev/null || fail 'jq is required'
if "$TESTBED_DIR/bin/macvm" screenshot >/dev/null 2>&1; then
    fail 'outer screenshot was available during framework acceptance'
fi

host_before="$($TESTBED_DIR/bin/macvm host-state)"
java_status=unavailable
electron_status=unavailable
if "$TESTBED_DIR/bin/macvm" exec /usr/bin/java -version \
        >/dev/null 2>&1; then
    java_status=available_not_covered
fi
if "$TESTBED_DIR/bin/macvm" exec /bin/sh -c \
        'command -v node >/dev/null && command -v npm >/dev/null' \
        >/dev/null 2>&1; then
    electron_status=available_not_covered
fi
[[ "$java_status" == unavailable ]] \
    || fail 'a Java runtime is available but has no deterministic corpus fixture'
[[ "$electron_status" == unavailable ]] \
    || fail 'an Electron build runtime is available but has no corpus fixture'

"$TESTBED_DIR/bin/macvm" deploy-fixture >/dev/null
"$TESTBED_DIR/bin/macvm" deploy-swiftui-fixture >/dev/null
cleanup

launch_app local "$APPKIT_ID"
appkit_remote="$(snapshot_button remote "$APPKIT_ID" Increment)"
press_snapshot_button remote "$appkit_remote" Increment
wait_for_state fixture-state '.count == 1' 'AppKit increment effect'
appkit_local="$(snapshot_button local "$APPKIT_ID" Reset)"
press_snapshot_button local "$appkit_local" Reset
wait_for_state fixture-state '.count == 0' 'AppKit reset effect'

launch_app remote "$SWIFTUI_ID"
swiftui_remote="$(snapshot_button remote "$SWIFTUI_ID" 'Increment SwiftUI')"
press_snapshot_button remote "$swiftui_remote" 'Increment SwiftUI'
wait_for_state swiftui-fixture-state \
    '.framework == "SwiftUI" and .count == 1 and .effect == "incremented"' \
    'SwiftUI remote increment effect'
swiftui_local="$(snapshot_button local "$SWIFTUI_ID" 'Increment SwiftUI')"
press_snapshot_button local "$swiftui_local" 'Increment SwiftUI'
wait_for_state swiftui-fixture-state '.count == 2' \
    'SwiftUI local observation and second increment effect'

capture="$(control local "$(jq -nc --arg target "$SWIFTUI_ID" \
    '{operation:"capture",target:$target}')")"
require_accepted "$capture" 'SwiftUI exact-window capture'
jq -e '.fidelity == "exact_window" and
       .coordinateSpace == "window_pixels"' >/dev/null <<<"$capture" \
    || fail 'SwiftUI capture metadata was incomplete'
capture_path="$(jq -er '.data.artifactPath' <<<"$capture")"
"$TESTBED_DIR/bin/macvm" exec /bin/test -s "$capture_path" \
    || fail 'SwiftUI capture artifact was empty'
"$TESTBED_DIR/bin/macvm" exec /bin/rm -f "$capture_path"

host_after="$($TESTBED_DIR/bin/macvm host-state)"
[[ "$(jq -S . <<<"$host_before")" == "$(jq -S . <<<"$host_after")" ]] \
    || fail 'framework workflows changed the host cursor or frontmost application'

jq -n --arg java "$java_status" --arg electron "$electron_status" \
    --argjson appkitRemoteBytes "${#appkit_remote}" \
    --argjson appkitLocalBytes "${#appkit_local}" \
    --argjson swiftuiRemoteBytes "${#swiftui_remote}" \
    --argjson swiftuiLocalBytes "${#swiftui_local}" \
    --argjson appkitRemoteMs "$(jq -r '.elapsedMs' <<<"$appkit_remote")" \
    --argjson appkitLocalMs "$(jq -r '.elapsedMs' <<<"$appkit_local")" \
    --argjson swiftuiRemoteMs "$(jq -r '.elapsedMs' <<<"$swiftui_remote")" \
    --argjson swiftuiLocalMs "$(jq -r '.elapsedMs' <<<"$swiftui_local")" \
    '{appkit:{status:"passed",route:"guest.user/macos.ax",
              remote:{elapsedMs:$appkitRemoteMs,observationBytes:$appkitRemoteBytes},
              local:{elapsedMs:$appkitLocalMs,observationBytes:$appkitLocalBytes}},
      swiftui:{status:"passed",route:"guest.user/macos.ax",
               remote:{elapsedMs:$swiftuiRemoteMs,observationBytes:$swiftuiRemoteBytes},
               local:{elapsedMs:$swiftuiLocalMs,observationBytes:$swiftuiLocalBytes}},
      browserWeb:{status:"covered_by_artifact_workflows"},
      customRendered:{status:"covered_by_aqua_visual_fallback"},
      java:{status:$java},electron:{status:$electron},
      outerUI:"forbidden",hostInterference:"none"}'
