#!/usr/bin/env bash
# Grant the shared Machine Control.app Accessibility and Screen Recording in
# a Tart guest by driving the guest's own System Settings through the
# retiring testbed resident, which already holds Accessibility. This uses
# normal visible consent UI and the one-shot credential channel for any
# administrator sheet; it never edits the TCC database or uses outer input.

set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

macvm_require_host
macvm_assert_mutation_target

readonly SETTINGS_ID='com.apple.systempreferences'
readonly REQUESTER='Privacy & Security'
readonly TOGGLE='Machine Control_Toggle'
legacy_binary="$(macvm_remote_legacy_ui_app)/Contents/MacOS/macui"
legacy_socket="$(macvm_remote_legacy_control_socket)"
readonly legacy_binary legacy_socket

fail() {
    printf 'Resident consent failed: %s\n' "$*" >&2
    exit 1
}

legacy() { macvm_exec "$legacy_binary" request "$legacy_socket" "$1"; }

accepted() { /usr/bin/jq -e '.accepted == true' >/dev/null <<<"$1"; }

legacy_ready="$(legacy '{"operation":"status"}' 2>/dev/null |
    /usr/bin/jq -r '.data.nativeSemanticState // empty' || true)"
[[ "$legacy_ready" == ready ]] ||
    fail 'the testbed resident with Accessibility is not available; use docs/bootstrap.md'

# Register the new identity from its own process so its rows appear.
macvm_resident_request '{"operation":"permissions.request"}' >/dev/null || true
sleep 1

open_pane() {
    local pane="$1" snapshot reference=''
    legacy "$(/usr/bin/jq -nc --arg target "$SETTINGS_ID" \
        '{operation:"application.terminate",target:$target}')" >/dev/null 2>&1 || true
    macvm_exec /usr/bin/open \
        'x-apple.systempreferences:com.apple.settings.PrivacySecurity.extension'
    for _ in {1..40}; do
        snapshot="$(legacy "$(/usr/bin/jq -nc --arg target "$SETTINGS_ID" --arg query "$pane" \
            '{operation:"snapshot",target:$target,query:$query,
              maxDepth:20,maxElements:500,projection:"compact"}')" 2>/dev/null || true)"
        reference="$(/usr/bin/jq -r --arg pane "$pane" \
            '[.data.elements[]? | select(.role == "AXButton" and
              (.identifier | endswith("_Navigator")) and
              (.label | contains($pane)))][0].reference // empty' <<<"$snapshot")"
        [[ -n "$reference" ]] && break
        sleep 0.2
    done
    [[ -n "$reference" ]] || fail "Privacy pane '$pane' was unavailable"
    accepted "$(legacy "$(/usr/bin/jq -nc --arg reference "$reference" \
        '{operation:"action",reference:$reference,action:"press"}')")" ||
        fail "could not open '$pane'"
}

toggle() {
    local snapshot
    snapshot="$(legacy "$(/usr/bin/jq -nc --arg target "$SETTINGS_ID" --arg query "$TOGGLE" \
        '{operation:"snapshot",target:$target,query:$query,
          maxDepth:20,maxElements:500,projection:"compact"}')" 2>/dev/null || true)"
    /usr/bin/jq -c --arg id "$TOGGLE" \
        '[.data.elements[]? | select(.identifier == $id and .role == "AXCheckBox")][0] // empty' \
        <<<"$snapshot"
}

authorize_if_needed() {
    local context="$1" result lease
    result="$(legacy "$(/usr/bin/jq -nc --arg requester "$REQUESTER" --arg context "$context" \
        '{operation:"authorization.begin",expectedRequester:$requester,
          contextId:$context,timeoutMs:20000}')")" || true
    if /usr/bin/jq -e '.errorCode == "authorization_sheet_unavailable"' >/dev/null <<<"$result"; then
        return 0
    fi
    accepted "$result" || fail "$context authorization lease was refused"
    lease="$(/usr/bin/jq -er '.data.leaseId' <<<"$result")"
    result="$("$SCRIPT_DIR/submit-authorization.sh" --stored --legacy-resident "$lease")"
    /usr/bin/jq -e '.accepted == true and .data.sheetDismissed == true' >/dev/null <<<"$result" ||
        fail "$context authorization sheet was not dismissed"
}

grant_pane() {
    local pane="$1" context="$2" element value=''
    open_pane "$pane"
    for _ in {1..30}; do
        element="$(toggle)"
        [[ -n "$element" ]] && break
        sleep 0.2
    done
    [[ -n "$element" ]] || fail "Machine Control is not listed in '$pane'"
    if [[ "$(/usr/bin/jq -r '.value' <<<"$element")" == 1 ]]; then
        printf '%s already allowed\n' "$pane"
        return 0
    fi
    accepted "$(legacy "$(/usr/bin/jq -nc --arg reference "$(/usr/bin/jq -r .reference <<<"$element")" \
        '{operation:"action",reference:$reference,action:"press"}')")" ||
        fail "could not press the '$pane' switch"
    authorize_if_needed "$context"
    for _ in {1..40}; do
        value="$(toggle | /usr/bin/jq -r '.value // empty')"
        [[ "$value" == 1 ]] && break
        sleep 0.2
    done
    [[ "$value" == 1 ]] || fail "'$pane' switch did not turn on"
    printf 'Allowed Machine Control in %s\n' "$pane"
}

grant_pane Accessibility resident-accessibility
grant_pane 'Screen & System Audio Recording' resident-screen-recording
legacy "$(/usr/bin/jq -nc --arg target "$SETTINGS_ID" \
    '{operation:"application.terminate",target:$target}')" >/dev/null 2>&1 || true
