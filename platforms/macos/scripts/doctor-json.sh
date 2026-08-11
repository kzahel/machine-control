#!/usr/bin/env bash

set -uo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"
readonly MACVM="$MACVM_REPO_DIR/bin/macvm"

checks='[]'

add_check() {
    local id="$1" status="$2" summary="$3"
    checks="$(jq -cn --argjson current "$checks" --arg id "$id" \
        --arg status "$status" --arg summary "$summary" \
        '$current + [{id:$id,status:$status,summary:$summary}]')"
}

power=unknown
administration=unavailable
desktop=no_session
resident=unavailable
semantic=unavailable
capture=unavailable
input=unavailable
outer=unknown
resident_json=null

state="$(macvm_state 2>/dev/null || true)"
case "$state" in
    running)
        power=running
        add_check power pass 'Target is running'
        ;;
    stopped|off)
        power=off
        add_check power fail 'Target is powered off'
        ;;
    suspended|paused)
        power=suspended
        add_check power fail 'Target is suspended'
        ;;
    *)
        add_check power fail 'Target power state is unknown'
        ;;
esac

if [[ "$power" == running ]] &&
        macvm_exec /usr/bin/true >/dev/null 2>&1; then
    administration=ready
    add_check administration pass 'Guest administration is ready'
else
    add_check administration fail 'Guest administration is unavailable'
fi

console_user=""
if [[ "$administration" == ready ]]; then
    console_user="$(macvm_exec /usr/bin/stat -f %Su /dev/console \
        2>/dev/null || true)"
fi
if [[ -n "$console_user" && "$console_user" != root &&
      "$console_user" != loginwindow ]]; then
    desktop=unlocked
    add_check desktop pass 'Logged-in Aqua session is ready'
else
    add_check desktop fail 'Logged-in Aqua session is unavailable'
fi

control_status=""
if [[ "$desktop" == unlocked ]] &&
        control_status="$($MACVM control \
            '{"operation":"status"}' 2>/dev/null)" &&
        jq -e '.schema == "machine-control/v0" and .accepted == true' \
            <<<"$control_status" >/dev/null 2>&1; then
    resident=ready
    semantic="$(jq -r '.data.semanticState // "unknown"' \
        <<<"$control_status")"
    capture="$(jq -r '.data.captureState // "unknown"' \
        <<<"$control_status")"
    [[ "$semantic" =~ ^(ready|degraded|unavailable|unknown)$ ]] || semantic=unknown
    [[ "$capture" =~ ^(ready|degraded|unavailable|unknown)$ ]] || capture=unknown
    input="$semantic"
    resident_json="$(jq -c \
        '{contract:.schema,generation:.generation}' <<<"$control_status")"
    add_check resident pass 'Target-native resident is ready'
else
    add_check resident fail 'Target-native resident is unavailable'
fi

if [[ "$semantic" == ready ]]; then
    add_check semantic pass 'Accessibility semantics are ready'
else
    add_check semantic fail 'Accessibility semantics are unavailable'
fi
if [[ "$capture" == ready ]]; then
    add_check capture pass 'Target-native capture is ready'
else
    add_check capture fail 'Target-native capture is unavailable'
fi
if [[ "$input" == ready ]]; then
    add_check input pass 'Target-native input is ready'
else
    add_check input fail 'Target-native input is unavailable'
fi

if [[ "$MACVM_FORBID_OUTER_UI" == true ]]; then
    outer=prohibited
    add_check outer pass 'Outer UI is prohibited by policy'
else
    outer=unknown
    add_check outer skip 'Outer recovery was not evaluated'
fi

ready=false
if [[ "$power" == running && "$administration" == ready &&
      "$desktop" == unlocked && "$resident" == ready &&
      "$semantic" == ready && "$capture" == ready && "$input" == ready ]]; then
    ready=true
fi

jq -cn \
    --argjson ready "$ready" \
    --arg power "$power" \
    --arg administration "$administration" \
    --arg desktop "$desktop" \
    --arg resident_state "$resident" \
    --arg semantic "$semantic" \
    --arg capture "$capture" \
    --arg input "$input" \
    --arg outer "$outer" \
    --argjson resident "$resident_json" \
    --argjson checks "$checks" \
    '{
        schema:"machine-control-doctor/v0",
        ready:$ready,
        target:{
            platform:"macos",
            profile:"macos-aqua-tart"
        },
        states:{
            power:$power,
            administration:$administration,
            desktop:$desktop,
            resident:$resident_state,
            semantic:$semantic,
            capture:$capture,
            input:$input,
            outer:$outer
        },
        resident:$resident,
        checks:$checks,
        lifecycleOperations:[
            "status","up","suspend","shutdown","force-stop"
        ],
        extensions:{
            administrationRoute:"selected_guest_transport",
            desktopSession:"aqua",
            privacyAuthority:"tcc"
        }
    }'

[[ "$ready" == true ]]
