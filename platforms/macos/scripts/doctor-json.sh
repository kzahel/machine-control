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
desktop=unknown
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

# The shared probe observes lock independently of helper installation and TCC.
if [[ "$administration" == ready ]]; then
    observation="$(macvm_exec "$(macvm_remote_ui_binary)" session-state 2>/dev/null || true)"
    desktop="$(jq -r '.desktopState // "unknown"' <<<"$observation" 2>/dev/null || printf unknown)"
    [[ "$desktop" =~ ^(unlocked|locked|no_session|unknown)$ ]] || desktop=unknown
fi
unlock_json='{"support":"experimental","installation":"unknown","policy":"unknown","callerEligibility":"unknown","readiness":"unknown","reasons":["resident_unreachable"]}'
display_state=unknown

control_status=""
if [[ "$administration" == ready ]] &&
        control_status="$(macvm_resident_request \
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
    input=unknown
    # Older residents reported unlocked from console ownership alone. Do not
    # promote that legacy assertion into a fresh lock-state observation.
    if jq -e '.data.observationSource == "iokit.console-session" and
            (.data.desktopGeneration | type == "string")' \
            <<<"$control_status" >/dev/null; then
        input="$(jq -r '.data.inputState // "unknown"' <<<"$control_status")"
        desktop="$(jq -r '.data.desktopState // "unknown"' <<<"$control_status")"
    else
        semantic=unknown
    fi
    [[ "$desktop" =~ ^(unlocked|locked|no_session|unknown)$ ]] || desktop=unknown
    [[ "$input" =~ ^(ready|degraded|unavailable|unknown)$ ]] || input=unknown
    unlock_json="$(jq -c '.data.unlock // {support:"experimental",
        installation:"unknown",policy:"unknown",callerEligibility:"unknown",
        readiness:"unknown",reasons:["resident_upgrade_required"]}' <<<"$control_status")"
    display_state="$(jq -r '.data.displayState // "unknown"' <<<"$control_status")"
    resident_json="$(jq -c \
        '{contract:.schema,generation:.generation}' <<<"$control_status")"
    add_check resident pass 'Target-native resident is ready'
else
    add_check resident fail 'Target-native resident is unavailable'
fi

if [[ "$desktop" == unlocked ]]; then
    add_check desktop pass 'OS reports an unlocked console session'
else
    add_check desktop fail "Desktop state: $desktop"
fi
add_check unlock skip "Unlock readiness: $(jq -r '.readiness // "unknown"' <<<"$unlock_json"); $(jq -r '(.reasons // []) | join(", ")' <<<"$unlock_json")"

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
    --argjson unlock "$unlock_json" \
    --arg display_state "$display_state" \
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
            privacyAuthority:"tcc",
            unlock:$unlock,
            displayState:$display_state
        }
    }'

[[ "$ready" == true ]]
