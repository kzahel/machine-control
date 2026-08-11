#!/usr/bin/env bash

set -uo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"
readonly WINVM="$WINVM_REPO_DIR/bin/winvm"
readonly PROVIDER="$(winvm_provider_path)"

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
        "$WINVM" ps '$true' >/dev/null 2>&1; then
    administration=ready
    add_check administration pass 'Key-only PowerShell administration is ready'
else
    add_check administration fail 'Guest administration is unavailable'
fi

desktop_probe=""
if [[ "$administration" == ready ]]; then
    read -r -d '' probe_script <<'POWERSHELL' || true
[ordered]@{
    explorerPresent = [bool](Get-Process explorer -ErrorAction SilentlyContinue)
} | ConvertTo-Json -Compress
POWERSHELL
    desktop_probe="$(winvm_powershell "$probe_script" 2>/dev/null || true)"
fi
if jq -e '.explorerPresent == true' \
        <<<"$desktop_probe" >/dev/null 2>&1; then
    desktop=unlocked
    add_check desktop pass 'Interactive Windows desktop is present'
else
    add_check desktop fail 'Interactive Windows desktop is unavailable'
fi

control_status=""
capabilities=""
if [[ "$administration" == ready ]] &&
        control_status="$($WINVM control \
            '{"operation":"status"}' 2>/dev/null)" &&
        jq -e '.schema == "machine-control/v0" and .accepted == true' \
            <<<"$control_status" >/dev/null 2>&1; then
    resident=ready
    if [[ "$(jq -r '.sessionLocked // false' <<<"$control_status")" == true ]]; then
        desktop=locked
    elif [[ "$(jq -r '.desktop // "Default"' <<<"$control_status")" != Default ]]; then
        desktop=protected
    fi
    resident_json="$(jq -c \
        '{contract:.schema,generation:.generation}' <<<"$control_status")"
    add_check resident pass 'Target-native resident is ready'
else
    add_check resident fail 'Target-native resident is unavailable'
fi

if [[ "$resident" == ready ]] &&
        capabilities="$($WINVM control \
            '{"operation":"capabilities"}' 2>/dev/null)" &&
        jq -e '.accepted == true and
            any(.data.providers[]?; .id == "windows-native" and
                .state == "native")' <<<"$capabilities" >/dev/null 2>&1; then
    semantic=ready
    capture=ready
    input=ready
fi
if [[ "$semantic" == ready ]]; then
    add_check semantic pass 'UI Automation semantics are ready'
else
    add_check semantic fail 'UI Automation semantics are unavailable'
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

if [[ "$WINVM_FORBID_OUTER_UI" == true ]]; then
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
            platform:"windows",
            profile:"windows-11-desktop"
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
            administrationRoute:"key_only_ssh_powershell",
            desktopSession:"windows_interactive_console",
            protectedAuthority:"dedicated_test_appliance"
        }
    }'

[[ "$ready" == true ]]
