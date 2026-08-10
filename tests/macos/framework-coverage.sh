#!/usr/bin/env bash

set -euo pipefail

readonly REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
readonly TESTBED_DIR="${MACVM_TESTBED_DIR:-$REPO_DIR/../macvm-testbed}"
readonly APPKIT_ID='org.machine-control.fixture'
readonly SWIFTUI_ID='org.machine-control.swiftui-fixture'
readonly JAVA_ID='org.machine-control.java-fixture'
readonly ELECTRON_ID='org.machine-control.electron-fixture'
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

activate_app() {
    local placement="$1" app="$2" result
    result="$(control "$placement" "$(jq -nc --arg target "$app" \
        '{operation:"application.activate",target:$target}')")"
    require_accepted "$result" "$app activation through $placement"
    jq -e '.delivery == "confirmed" and .effect == "confirmed" and
           .focusConsequence == "target_application_activated"' \
        >/dev/null <<<"$result" \
        || fail "$app did not become the active guest application"
    # Cua observes the newly frontmost Chromium AX tree asynchronously.
    sleep 1
}

snapshot_button() {
    local placement="$1" app="$2" label="$3" provider="$4" route="$5" result
    for _ in {1..6}; do
        result="$(control "$placement" "$(jq -nc --arg target "$app" \
            --arg query "$label" --arg provider "$provider" \
            '{operation:"snapshot",target:$target,query:$query,provider:$provider,
              maxDepth:16,maxElements:160,projection:"compact"}')")"
        if jq -e --arg label "$label" --arg route "$route" '
            .schema == "machine-control/v0" and .accepted == true and
            .agentRoundTrips == 1 and .hostInterference == "none" and
            .actualRoute == $route and .fidelity == "semantic_native" and
            .data.projection == "compact" and
            ([.data.elements[] | select(.role == "AXButton" and
              .label == $label and .enabled == true and
              ($route == "guest.user/macos.cua" or
               (.actions | index("AXPress"))))] | length) == 1' \
                >/dev/null <<<"$result"; then
            printf '%s\n' "$result"
            return 0
        fi
        sleep 0.5
    done
    jq . <<<"$result" >&2 || true
    fail "$app did not expose one semantic $label button through $placement"
}

press_snapshot_button() {
    local placement="$1" snapshot="$2" label="$3" route="$4"
    local result reference
    reference="$(jq -er --arg label "$label" \
        '[.data.elements[] | select(.role == "AXButton" and
          .label == $label)][0].reference' <<<"$snapshot")"
    result="$(control "$placement" "$(jq -nc --arg reference "$reference" \
        '{operation:"action",reference:$reference,action:"press"}')")"
    require_accepted "$result" "$label action through $placement"
    jq -e --arg route "$route" '.delivery == "confirmed" and
           (.effect == "confirmed" or .effect == "unverifiable") and
           .actualRoute == $route' >/dev/null <<<"$result" \
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

capture_window() {
    local placement="$1" app="$2" label="$3" result artifact
    result="$(control "$placement" "$(jq -nc --arg target "$app" \
        '{operation:"capture",target:$target}')")"
    require_accepted "$result" "$label exact-window capture"
    jq -e '.fidelity == "exact_window" and
           .coordinateSpace == "window_pixels"' >/dev/null <<<"$result" \
        || fail "$label capture metadata was incomplete"
    artifact="$(jq -er '.data.artifactPath' <<<"$result")"
    "$TESTBED_DIR/bin/macvm" exec /bin/test -s "$artifact" \
        || fail "$label capture artifact was empty"
    "$TESTBED_DIR/bin/macvm" exec /bin/rm -f "$artifact"
}

cleanup() {
    terminate_app "$ELECTRON_ID"
    terminate_app "$JAVA_ID"
    terminate_app "$SWIFTUI_ID"
    terminate_app "$APPKIT_ID"
}
trap cleanup EXIT

[[ -x "$TESTBED_DIR/bin/macvm" ]] || fail "missing macvm-testbed at $TESTBED_DIR"
command -v jq >/dev/null || fail 'jq is required'
if "$TESTBED_DIR/bin/macvm" screenshot >/dev/null 2>&1; then
    fail 'outer screenshot was available during framework acceptance'
fi

runtime_status="$($TESTBED_DIR/bin/macvm framework-runtime-status)"
jq -e '.ready == true and .markerValid == true and
       .node.ready == true and .java.ready == true and
       .electron.ready == true' >/dev/null <<<"$runtime_status" \
    || fail 'the pinned framework runtimes are not ready'

host_before="$($TESTBED_DIR/bin/macvm host-state)"
"$TESTBED_DIR/bin/macvm" deploy-fixture >/dev/null
"$TESTBED_DIR/bin/macvm" deploy-swiftui-fixture >/dev/null
"$TESTBED_DIR/bin/macvm" deploy-java-fixture >/dev/null
"$TESTBED_DIR/bin/macvm" deploy-electron-fixture >/dev/null
cleanup

launch_app local "$APPKIT_ID"
appkit_remote="$(snapshot_button remote "$APPKIT_ID" Increment \
    macos-native guest.user/macos.ax)"
press_snapshot_button remote "$appkit_remote" Increment guest.user/macos.ax
wait_for_state fixture-state '.count == 1' 'AppKit increment effect'
appkit_local="$(snapshot_button local "$APPKIT_ID" Reset \
    macos-native guest.user/macos.ax)"
press_snapshot_button local "$appkit_local" Reset guest.user/macos.ax
wait_for_state fixture-state '.count == 0' 'AppKit reset effect'
capture_window local "$APPKIT_ID" AppKit

launch_app remote "$SWIFTUI_ID"
swiftui_remote="$(snapshot_button remote "$SWIFTUI_ID" 'Increment SwiftUI' \
    macos-native guest.user/macos.ax)"
press_snapshot_button remote "$swiftui_remote" 'Increment SwiftUI' \
    guest.user/macos.ax
wait_for_state swiftui-fixture-state \
    '.framework == "SwiftUI" and .count == 1 and .effect == "incremented"' \
    'SwiftUI remote increment effect'
swiftui_local="$(snapshot_button local "$SWIFTUI_ID" 'Increment SwiftUI' \
    macos-native guest.user/macos.ax)"
press_snapshot_button local "$swiftui_local" 'Increment SwiftUI' \
    guest.user/macos.ax
wait_for_state swiftui-fixture-state '.count == 2' \
    'SwiftUI local observation and second increment effect'
capture_window remote "$SWIFTUI_ID" SwiftUI

launch_app local "$JAVA_ID"
java_remote="$(snapshot_button remote "$JAVA_ID" 'Increment Java' \
    macos-native guest.user/macos.ax)"
press_snapshot_button remote "$java_remote" 'Increment Java' \
    guest.user/macos.ax
wait_for_state java-fixture-state \
    '.framework == "Java Swing" and .count == 1 and .effect == "incremented"' \
    'Java remote increment effect'
java_local="$(snapshot_button local "$JAVA_ID" 'Reset Java' \
    macos-native guest.user/macos.ax)"
press_snapshot_button local "$java_local" 'Reset Java' \
    guest.user/macos.ax
wait_for_state java-fixture-state '.count == 0 and .effect == "reset"' \
    'Java local reset effect'
capture_window local "$JAVA_ID" 'Java Swing'

launch_app remote "$ELECTRON_ID"
activate_app remote "$ELECTRON_ID"
electron_remote="$(snapshot_button remote "$ELECTRON_ID" 'Increment Electron' \
    cua guest.user/macos.cua)"
press_snapshot_button remote "$electron_remote" 'Increment Electron' \
    guest.user/macos.cua
wait_for_state electron-fixture-state \
    '.framework == "Electron" and .count == 1 and .effect == "incremented"' \
    'Electron remote increment effect'
activate_app local "$ELECTRON_ID"
electron_local="$(snapshot_button local "$ELECTRON_ID" 'Reset Electron' \
    cua guest.user/macos.cua)"
press_snapshot_button local "$electron_local" 'Reset Electron' \
    guest.user/macos.cua
wait_for_state electron-fixture-state '.count == 0 and .effect == "reset"' \
    'Electron local reset effect'
capture_window remote "$ELECTRON_ID" Electron

host_after="$($TESTBED_DIR/bin/macvm host-state)"
[[ "$(jq -S . <<<"$host_before")" == "$(jq -S . <<<"$host_after")" ]] \
    || fail 'framework workflows changed the host cursor or frontmost application'

jq -n --argjson runtimes "$runtime_status" \
    --argjson appkitRemoteBytes "${#appkit_remote}" \
    --argjson appkitLocalBytes "${#appkit_local}" \
    --argjson swiftuiRemoteBytes "${#swiftui_remote}" \
    --argjson swiftuiLocalBytes "${#swiftui_local}" \
    --argjson javaRemoteBytes "${#java_remote}" \
    --argjson javaLocalBytes "${#java_local}" \
    --argjson electronRemoteBytes "${#electron_remote}" \
    --argjson electronLocalBytes "${#electron_local}" \
    --argjson appkitRemoteMs "$(jq -r '.elapsedMs' <<<"$appkit_remote")" \
    --argjson appkitLocalMs "$(jq -r '.elapsedMs' <<<"$appkit_local")" \
    --argjson swiftuiRemoteMs "$(jq -r '.elapsedMs' <<<"$swiftui_remote")" \
    --argjson swiftuiLocalMs "$(jq -r '.elapsedMs' <<<"$swiftui_local")" \
    --argjson javaRemoteMs "$(jq -r '.elapsedMs' <<<"$java_remote")" \
    --argjson javaLocalMs "$(jq -r '.elapsedMs' <<<"$java_local")" \
    --argjson electronRemoteMs "$(jq -r '.elapsedMs' <<<"$electron_remote")" \
    --argjson electronLocalMs "$(jq -r '.elapsedMs' <<<"$electron_local")" \
    '{runtimes:$runtimes,
      appkit:{status:"passed",route:"guest.user/macos.ax",
              remote:{elapsedMs:$appkitRemoteMs,observationBytes:$appkitRemoteBytes},
              local:{elapsedMs:$appkitLocalMs,observationBytes:$appkitLocalBytes}},
      swiftui:{status:"passed",route:"guest.user/macos.ax",
               remote:{elapsedMs:$swiftuiRemoteMs,observationBytes:$swiftuiRemoteBytes},
               local:{elapsedMs:$swiftuiLocalMs,observationBytes:$swiftuiLocalBytes}},
      javaSwing:{status:"passed",route:"guest.user/macos.ax",
                 remote:{elapsedMs:$javaRemoteMs,observationBytes:$javaRemoteBytes},
                 local:{elapsedMs:$javaLocalMs,observationBytes:$javaLocalBytes}},
      electron:{status:"passed",route:"guest.user/macos.cua",
                remote:{elapsedMs:$electronRemoteMs,observationBytes:$electronRemoteBytes},
                local:{elapsedMs:$electronLocalMs,observationBytes:$electronLocalBytes}},
      browserWeb:{status:"covered_by_artifact_workflows"},
      customRendered:{status:"covered_by_aqua_visual_fallback"},
      exactWindowCapture:["AppKit","SwiftUI","Java Swing","Electron"],
      outerUI:"forbidden",hostInterference:"none"}'
