#!/usr/bin/env bash

set -euo pipefail

readonly REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
readonly TESTBED_DIR="${MACVM_TESTBED_DIR:-$REPO_DIR/../macvm-testbed}"
readonly FIXTURE_ID='org.machine-control.privacy-fixture'
readonly SETTINGS_ID='com.apple.systempreferences'
readonly REQUESTER='Privacy & Security'
export MACVM_FORBID_OUTER_UI=true

fail() {
    printf 'macOS privacy settings failed: %s\n' "$*" >&2
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
    local target="$1" label="$2" snapshot reference result
    snapshot="$(control "$(jq -nc --arg target "$target" --arg query "$label" \
        '{operation:"snapshot",target:$target,query:$query,
          maxDepth:20,maxElements:500,projection:"compact"}')")"
    require_accepted "$snapshot" "$label snapshot"
    reference="$(jq -er --arg label "$label" \
        '[.data.elements[] | select(.role == "AXButton" and .label == $label and
          (.actions | index("AXPress")))][0].reference' <<<"$snapshot")" \
        || fail "button '$label' was not available"
    result="$(control "$(jq -nc --arg reference "$reference" \
        '{operation:"action",reference:$reference,action:"press"}')")"
    require_accepted "$result" "$label press"
}

open_privacy_pane() {
    local pane="$1" snapshot reference result
    control "$(jq -nc --arg target "$SETTINGS_ID" \
        '{operation:"application.terminate",target:$target}')" \
        >/dev/null 2>&1 || true
    "$TESTBED_DIR/bin/macvm" exec /usr/bin/open \
        'x-apple.systempreferences:com.apple.settings.PrivacySecurity.extension'
    for _ in {1..30}; do
        snapshot="$(control "$(jq -nc --arg target "$SETTINGS_ID" \
            --arg query "$pane" \
            '{operation:"snapshot",target:$target,query:$query,
              maxDepth:20,maxElements:500,projection:"compact"}')" \
            2>/dev/null || true)"
        reference="$(jq -r --arg pane "$pane" \
            '[.data.elements[]? | select(.role == "AXButton" and
              (.identifier | endswith("_Navigator")) and
              (.label | contains($pane)))][0].reference // empty' \
            <<<"$snapshot")"
        if [[ -n "$reference" ]]; then break; fi
        sleep 0.1
    done
    [[ -n "${reference:-}" ]] || fail "Privacy pane '$pane' was unavailable"
    result="$(control "$(jq -nc --arg reference "$reference" \
        '{operation:"action",reference:$reference,action:"press"}')")"
    require_accepted "$result" "$pane navigation"
}

toggle_snapshot() {
    control "$(jq -nc --arg target "$SETTINGS_ID" \
        '{operation:"snapshot",target:$target,
          query:"Machine Control Privacy Fixture_Toggle",
          maxDepth:20,maxElements:500,projection:"compact"}')"
}

toggle_value() {
    local snapshot
    snapshot="$(toggle_snapshot)"
    require_accepted "$snapshot" 'privacy fixture toggle snapshot'
    jq -er '[.data.elements[] | select(
        .identifier == "Machine Control Privacy Fixture_Toggle" and
        .role == "AXCheckBox")][0].value' <<<"$snapshot"
}

press_toggle() {
    local snapshot reference result
    snapshot="$(toggle_snapshot)"
    require_accepted "$snapshot" 'privacy fixture toggle snapshot'
    reference="$(jq -er '[.data.elements[] | select(
        .identifier == "Machine Control Privacy Fixture_Toggle" and
        .role == "AXCheckBox")][0].reference' <<<"$snapshot")" \
        || fail 'privacy fixture was not registered in the selected pane'
    result="$(control "$(jq -nc --arg reference "$reference" \
        '{operation:"action",reference:$reference,action:"press"}')")"
    require_accepted "$result" 'privacy fixture toggle press'
}

toggle_exists() {
    toggle_value >/dev/null 2>&1
}

add_fixture_to_current_pane() {
    local context="$1" snapshot reference result x y
    press_button "$SETTINGS_ID" Add
    authorize_if_needed "$context-add"
    for _ in {1..30}; do
        snapshot="$(control "$(jq -nc --arg target "$SETTINGS_ID" \
            '{operation:"snapshot",target:$target,
              query:"Machine Control Privacy Fixture",
              maxDepth:24,maxElements:900,projection:"compact"}')" \
            2>/dev/null || true)"
        reference="$(jq -r '[.data.elements[]? | select(
            .role == "AXTextField" and
            .value == "Machine Control Privacy Fixture" and
            (.bounds.width // 0) > 0)][0].reference // empty' \
            <<<"$snapshot")"
        if [[ -n "$reference" ]]; then break; fi
        sleep 0.1
    done
    [[ -n "${reference:-}" ]] || fail "$context fixture was absent from the open panel"
    x="$(jq -er --arg reference "$reference" \
        '.data.elements[] | select(.reference == $reference) |
         (.bounds.x + (.bounds.width / 2) | floor)' <<<"$snapshot")"
    y="$(jq -er --arg reference "$reference" \
        '.data.elements[] | select(.reference == $reference) |
         (.bounds.y + (.bounds.height / 2) | floor)' <<<"$snapshot")"
    result="$(control "$(jq -nc --arg target "$SETTINGS_ID" \
        --argjson x "$x" --argjson y "$y" \
        '{operation:"input.click",target:$target,provider:"macos-native",
          coordinateSpace:"global_display_points",x:$x,y:$y}')")"
    require_accepted "$result" "$context open panel fixture selection"
    for _ in {1..30}; do
        snapshot="$(control "$(jq -nc --arg target "$SETTINGS_ID" \
            '{operation:"snapshot",target:$target,query:"Open",
              maxDepth:24,maxElements:700,projection:"compact"}')" \
            2>/dev/null || true)"
        reference="$(jq -r '[.data.elements[]? | select(
            .role == "AXButton" and .label == "Open" and .enabled == true)][0]
            .reference // empty' <<<"$snapshot")"
        if [[ -n "$reference" ]]; then break; fi
        sleep 0.1
    done
    [[ -n "${reference:-}" ]] || fail "$context selected app was not openable"
    result="$(control "$(jq -nc --arg reference "$reference" \
        '{operation:"action",reference:$reference,action:"press"}')")"
    require_accepted "$result" "$context open panel Open"
    wait_for_toggle 1
}

wait_for_toggle() {
    local expected="$1" value
    for _ in {1..30}; do
        value="$(toggle_value 2>/dev/null || true)"
        [[ "$value" == "$expected" ]] && return 0
        sleep 0.1
    done
    fail "privacy fixture toggle did not reach $expected"
}

authorize_if_needed() {
    local context="$1" result lease
    result="$(control "$(jq -nc --arg requester "$REQUESTER" \
        --arg context "$context" \
        '{operation:"authorization.begin",expectedRequester:$requester,
          contextId:$context,timeoutMs:120000}')")"
    if jq -e '.accepted == false and
              .errorCode == "authorization_sheet_unavailable"' \
            >/dev/null <<<"$result"; then
        return 0
    fi
    require_accepted "$result" "$context authorization lease"
    lease="$(jq -er '.data.leaseId' <<<"$result")"
    printf '\nEnter the guest administrator credential for %s.\n' "$context" >&2
    result="$($TESTBED_DIR/bin/macvm authorization-submit "$lease")"
    require_accepted "$result" "$context authorization submission"
    jq -e '.delivery == "confirmed" and .effect == "confirmed" and
           .data.sheetDismissed == true' >/dev/null <<<"$result" \
        || { jq . <<<"$result" >&2; fail "$context authorization sheet was not dismissed"; }
}

run_settings_class() {
    local service="$1" trigger="$2" pane="$3" state_key="$4"
    "$TESTBED_DIR/bin/macvm" reset-privacy-fixture "$service" >/dev/null
    launch_fixture
    press_button "$FIXTURE_ID" "$trigger"
    open_privacy_pane "$pane"
    if toggle_exists; then
        [[ "$(toggle_value)" == '0' ]] || fail "$service did not begin denied"
        press_toggle
        authorize_if_needed "privacy-$service"
        wait_for_toggle 1
    else
        add_fixture_to_current_pane "privacy-$service"
    fi
    launch_fixture
    wait_for_state ".services[\"$state_key\"].authorization == \"authorized\"" \
        "$service authorized effect"
    press_button "$FIXTURE_ID" "$trigger"
    case "$service" in
        input-monitoring)
            wait_for_state '.services["input-monitoring"].tapAvailable == true' \
                'authorized Input Monitoring event tap'
            ;;
        screen-recording)
            wait_for_state '.services["screen-recording"].captureAvailable == true' \
                'authorized Screen Recording capture'
            ;;
    esac
    open_privacy_pane "$pane"
    [[ "$(toggle_value)" == '1' ]] || fail "$service grant did not persist"
    press_toggle
    authorize_if_needed "privacy-$service-revoke"
    wait_for_toggle 0
    launch_fixture
    wait_for_state ".services[\"$state_key\"].authorization != \"authorized\"" \
        "$service revoked effect"
    "$TESTBED_DIR/bin/macvm" reset-privacy-fixture "$service" >/dev/null
}

cleanup() {
    local snapshot reference
    snapshot="$(control "$(jq -nc --arg target "$SETTINGS_ID" \
        '{operation:"snapshot",target:$target,query:"Cancel",
          maxDepth:24,maxElements:700,projection:"compact"}')" \
        2>/dev/null || true)"
    reference="$(jq -r '[.data.elements[]? | select(
        .role == "AXButton" and .identifier == "CancelButton" and
        .enabled == true)][0].reference // empty' <<<"$snapshot")"
    if [[ -n "$reference" ]]; then
        control "$(jq -nc --arg reference "$reference" \
            '{operation:"action",reference:$reference,action:"press"}')" \
            >/dev/null 2>&1 || true
    fi
    control "$(jq -nc --arg target "$FIXTURE_ID" \
        '{operation:"application.terminate",target:$target}')" \
        >/dev/null 2>&1 || true
    control "$(jq -nc --arg target "$SETTINGS_ID" \
        '{operation:"application.terminate",target:$target}')" \
        >/dev/null 2>&1 || true
}
trap cleanup EXIT

[[ -x "$TESTBED_DIR/bin/macvm" ]] || fail "missing macvm-testbed at $TESTBED_DIR"
command -v jq >/dev/null || fail 'jq is required'
[[ -t 0 && -t 1 ]] || fail 'settings grants require an interactive terminal'
if "$TESTBED_DIR/bin/macvm" screenshot >/dev/null 2>&1; then
    fail 'outer screenshot was available during privacy settings acceptance'
fi

"$TESTBED_DIR/bin/macvm" deploy-privacy-fixture >/dev/null
host_before="$($TESTBED_DIR/bin/macvm host-state)"
for settings_class in ${MACOS_PRIVACY_SETTINGS_CLASSES:-accessibility input-monitoring screen-recording}; do
    case "$settings_class" in
        accessibility)
            run_settings_class accessibility Accessibility Accessibility \
                accessibility
            ;;
        input-monitoring)
            run_settings_class input-monitoring 'Input Monitoring' \
                'Input Monitoring' input-monitoring
            ;;
        screen-recording)
            run_settings_class screen-recording 'Screen Recording' \
                'Screen & System Audio Recording' screen-recording
            ;;
        *) fail "unknown privacy settings class: $settings_class" ;;
    esac
done
host_after="$($TESTBED_DIR/bin/macvm host-state)"
[[ "$(jq -S . <<<"$host_before")" == "$(jq -S . <<<"$host_after")" ]] \
    || fail 'privacy settings changed the host cursor or frontmost application'

printf 'macOS settings-managed privacy passed (grant and revoke).\n'
