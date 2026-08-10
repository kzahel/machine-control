#!/usr/bin/env bash

set -euo pipefail

readonly REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
readonly TESTBED_DIR="${MACVM_TESTBED_DIR:-$REPO_DIR/../macvm-testbed}"

fail() {
    printf 'macOS real-application acceptance failed: %s\n' "$*" >&2
    exit 1
}

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

was_running() {
    local bundle="$1"
    jq -e --arg bundle "$bundle" \
        '.data.applications[] |
         select(.bundleId == $bundle and .running == true)' \
        >/dev/null <<<"$baseline"
}

wait_for_window() {
    local target="$1" title="$2" result
    for _ in {1..12}; do
        result="$(control "$(jq -nc --arg target "$target" \
            '{operation:"windows",target:$target}')")"
        if jq -e --arg title "$title" \
                '.accepted == true and any(.data.windows[];
                 .onScreen == true and (.title | contains($title)))' \
                >/dev/null <<<"$result"; then
            printf '%s\n' "$result"
            return 0
        fi
        sleep 0.2
    done
    fail "$target did not expose an on-screen '$title' window"
}

wait_not_running() {
    local bundle="$1" result
    for _ in {1..10}; do
        result="$(control '{"operation":"applications"}')"
        if jq -e --arg bundle "$bundle" \
                'all(.data.applications[];
                 .bundleId != $bundle or .running == false)' \
                >/dev/null <<<"$result"; then
            return 0
        fi
        sleep 0.2
    done
    fail "$bundle remained running after owned cleanup"
}

capture_and_remove() {
    local target="$1" result path
    result="$(control "$(jq -nc --arg target "$target" \
        '{operation:"capture",target:$target}')")"
    require_accepted "$result" "$target exact-window capture"
    jq -e '.fidelity == "exact_window" and
           .coordinateSpace == "window_pixels"' >/dev/null <<<"$result" \
        || fail "$target capture metadata was incomplete"
    path="$(jq -er '.data.artifactPath' <<<"$result")" \
        || fail "$target capture returned no artifact path"
    "$TESTBED_DIR/bin/macvm" exec /bin/test -s "$path" \
        || fail "$target capture artifact was empty"
    "$TESTBED_DIR/bin/macvm" exec /bin/rm -f "$path"
}

baseline="$(control '{"operation":"applications"}')"
require_accepted "$baseline" 'baseline application inventory'
safari_running=false
textedit_running=false
settings_running=false
was_running com.apple.Safari && safari_running=true
was_running com.apple.TextEdit && textedit_running=true
was_running com.apple.systempreferences && settings_running=true

finder_launch="$(control \
    '{"operation":"application.launch","applicationId":"com.apple.finder","arguments":"/tmp"}')"
require_accepted "$finder_launch" 'Finder folder launch'
wait_for_window Finder tmp >/dev/null
finder_snapshot="$(control \
    '{"operation":"snapshot","target":"Finder","maxDepth":10,"maxElements":300}')"
require_accepted "$finder_snapshot" 'Finder semantic snapshot'
jq -e '.data.elements | length > 5' >/dev/null <<<"$finder_snapshot" \
    || fail 'Finder semantic snapshot was unexpectedly sparse'

finder_activate="$(control \
    '{"operation":"application.activate","target":"Finder"}')"
require_accepted "$finder_activate" 'Finder foreground sentinel'
jq -e '.effect == "confirmed" and
       .focusConsequence == "target_application_activated"' \
    >/dev/null <<<"$finder_activate" || fail 'Finder was not activated'

if [[ "$settings_running" == false ]]; then
    settings_launch="$(control \
        '{"operation":"application.launch","applicationId":"com.apple.systempreferences"}')"
    require_accepted "$settings_launch" 'System Settings launch'
    wait_for_window 'System Settings' '' >/dev/null
fi
settings_snapshot="$(control \
    '{"operation":"snapshot","target":"System Settings","query":"Appearance","maxDepth":12,"maxElements":400}')"
require_accepted "$settings_snapshot" 'System Settings semantic snapshot'
appearance_ref="$(jq -er \
    '[.data.elements[] | select(.label == "Appearance")][-1].reference' \
    <<<"$settings_snapshot")" || fail 'Appearance control was not exposed'
appearance_action="$(control "$(jq -nc --arg reference "$appearance_ref" \
    '{operation:"action",reference:$reference,action:"press"}')")"
require_accepted "$appearance_action" 'background System Settings navigation'
settings_verify="$(control \
    '{"operation":"snapshot","target":"System Settings","query":"Dark","maxDepth":10,"maxElements":250}')"
require_accepted "$settings_verify" 'System Settings effect observation'
jq -e 'any(.data.elements[]; .label == "Dark")' >/dev/null \
    <<<"$settings_verify" || fail 'Appearance pane effect was not observed'
active_after_settings="$(control '{"operation":"applications"}')"
jq -e 'any(.data.applications[]; .name == "Finder" and .active == true)' \
    >/dev/null <<<"$active_after_settings" \
    || fail 'background System Settings action stole guest focus from Finder'

finder_close="$(control \
    '{"operation":"window.close","target":"Finder"}')"
require_accepted "$finder_close" 'owned Finder window cleanup'
jq -e '.effect == "confirmed"' >/dev/null <<<"$finder_close" \
    || fail 'owned Finder window remained observable'

textedit_launch="$(control \
    '{"operation":"application.launch","applicationId":"com.apple.TextEdit"}')"
require_accepted "$textedit_launch" 'TextEdit launch'
wait_for_window TextEdit Untitled >/dev/null
textedit_snapshot="$(control \
    '{"operation":"snapshot","target":"TextEdit","maxDepth":12,"maxElements":350}')"
require_accepted "$textedit_snapshot" 'TextEdit semantic snapshot'
jq -e 'any(.data.elements[]; .role == "AXTextArea") and
       any(.data.elements[]; .role == "AXMenuBar")' \
    >/dev/null <<<"$textedit_snapshot" \
    || fail 'TextEdit omitted its editor or application menu bar'
capture_and_remove TextEdit

safari_launch="$(control \
    '{"operation":"application.launch","applicationId":"com.apple.Safari","arguments":"about:blank"}')"
require_accepted "$safari_launch" 'Safari launch'
wait_for_window Safari about:blank >/dev/null
safari_snapshot="$(control \
    '{"operation":"snapshot","target":"Safari","maxDepth":12,"maxElements":500}')"
require_accepted "$safari_snapshot" 'Safari semantic snapshot'
jq -e '.data.elements | length > 10' >/dev/null <<<"$safari_snapshot" \
    || fail 'Safari semantic snapshot was unexpectedly sparse'
capture_and_remove Safari

if [[ "$safari_running" == false ]]; then
    control '{"operation":"application.terminate","target":"Safari"}' \
        >/dev/null
    wait_not_running com.apple.Safari
fi
if [[ "$textedit_running" == false ]]; then
    control '{"operation":"application.terminate","target":"TextEdit"}' \
        >/dev/null
    wait_not_running com.apple.TextEdit
fi
if [[ "$settings_running" == false ]]; then
    control \
        '{"operation":"application.terminate","target":"System Settings"}' \
        >/dev/null
    wait_not_running com.apple.systempreferences
fi

printf 'macOS real-application acceptance passed.\n'
