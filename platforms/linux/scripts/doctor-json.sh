#!/usr/bin/env bash

set -uo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"
readonly LINUXVM="$LINUXVM_REPO_DIR/bin/linuxvm"
readonly PROVIDER="$(linuxvm_provider_path)"

checks='[]'
failures=0

add_check() {
    local id="$1" status="$2" summary="$3"
    checks="$(jq -cn --argjson current "$checks" --arg id "$id" \
        --arg status "$status" --arg summary "$summary" \
        '$current + [{id:$id,status:$status,summary:$summary}]')"
    if [[ "$status" == fail ]]; then
        failures=$((failures + 1))
    fi
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

status="$($PROVIDER status 2>/dev/null || true)"
case "$status" in
    started|running)
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
        $PROVIDER exec /usr/bin/true >/dev/null 2>&1; then
    administration=ready
    add_check administration pass 'QEMU guest-agent administration is ready'
else
    add_check administration fail 'Guest administration is unavailable'
fi

desktop_user=""
session_type=""
if [[ "$administration" == ready ]]; then
    for _ in {1..60}; do
        desktop_user="$($LINUXVM desktop-user 2>/dev/null || true)"
        session_type="$($PROVIDER exec /usr/bin/bash -lc \
            'pid=$(pgrep -n -x gnome-shell); tr "\0" "\n" < "/proc/$pid/environ" | sed -n "s/^XDG_SESSION_TYPE=//p"' \
            2>/dev/null || true)"
        if [[ -n "$desktop_user" && "$session_type" == wayland ]]; then
            break
        fi
        sleep 1
    done
fi
if [[ -n "$desktop_user" && "$session_type" == wayland ]]; then
    desktop=unlocked
    add_check desktop pass 'Logged-in GNOME Wayland session is ready'
else
    add_check desktop fail 'Logged-in GNOME Wayland session is unavailable'
fi

ui_health=""
if [[ "$desktop" == unlocked ]]; then
    for _ in {1..30}; do
        if ui_health="$($LINUXVM ui health 2>/dev/null)" &&
                jq -e '.atspiAvailable == true' \
                    <<<"$ui_health" >/dev/null 2>&1; then
            break
        fi
        ui_health=""
        sleep 1
    done
fi
if [[ -n "$ui_health" ]]; then
    semantic=ready
    add_check semantic pass 'AT-SPI semantics are ready'
else
    add_check semantic fail 'AT-SPI semantics are unavailable'
fi

control_status=""
if [[ "$desktop" == unlocked ]]; then
    for _ in {1..30}; do
        if control_status="$($LINUXVM control \
                '{"operation":"status"}' 2>/dev/null)" &&
                jq -e '.schema == "machine-control/v0" and
                    .accepted == true' <<<"$control_status" >/dev/null 2>&1; then
            break
        fi
        control_status=""
        sleep 1
    done
fi
if [[ -n "$control_status" ]]; then
    resident=ready
    capture="$(jq -r '.data.captureState // "unknown"' \
        <<<"$control_status")"
    input="$(jq -r '.data.inputState // "unknown"' \
        <<<"$control_status")"
    [[ "$capture" =~ ^(ready|degraded|unavailable|unknown)$ ]] || capture=unknown
    [[ "$input" =~ ^(ready|degraded|unavailable|unknown)$ ]] || input=unknown
    resident_json="$(jq -c \
        '{contract:.schema,generation:.generation}' <<<"$control_status")"
    add_check resident pass 'Target-native resident is ready'
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
else
    add_check resident fail 'Target-native resident is unavailable'
    add_check capture fail 'Target-native capture is unavailable'
    add_check input fail 'Target-native input is unavailable'
fi

if [[ "$LINUXVM_FORBID_OUTER_UI" == true ]]; then
    outer=prohibited
    add_check outer pass 'Outer UI is prohibited by policy'
elif permissions="$($PROVIDER permissions 2>/dev/null)" &&
        jq -e '.screenCapture == true and .postEvent == true' \
            <<<"$permissions" >/dev/null 2>&1 &&
        $PROVIDER window-info >/dev/null 2>&1; then
    outer=ready
    add_check outer pass 'Outer recovery is available'
else
    outer=unavailable
    add_check outer warn 'Outer recovery is unavailable'
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
            platform:"linux",
            profile:"ubuntu-24.04-gnome-46-wayland"
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
            administrationRoute:"qemu_guest_agent",
            desktopSession:"gnome_wayland",
            inputPrivilege:"root_test_appliance"
        }
    }'

[[ "$ready" == true ]]
