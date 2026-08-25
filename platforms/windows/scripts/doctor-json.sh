#!/usr/bin/env bash

set -uo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"
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
identity=unavailable
lifecycle_operations='["status","up","shutdown","force-stop"]'
lifecycle='{
    "suspend": {
        "availability": "unknown",
        "source": "provider",
        "reasons": ["provider-capabilities-unavailable"]
    },
    "defaultDownAction": "guest-shutdown"
}'

identity_detail="$($PROVIDER assert-target inspect --json 2>&1)"
identity_exit=$?
if [[ "$identity_exit" -eq 0 ]]; then
    identity=verified
    add_check identity pass 'Exact private target identity is verified'
elif [[ "$identity_detail" == *'could not resolve the configured target identity'* ]]; then
    add_check identity fail \
        'Pinned target is not registered in UTM; run winvm repair-registration before re-pinning'
elif [[ "$identity_detail" == *'identity is unpinned'* ]]; then
    add_check identity fail 'Target identity is unpinned in private inventory'
elif [[ "$identity_detail" == *'role is unclassified'* ]]; then
    add_check identity fail 'Target role is unclassified in private inventory'
elif [[ "$identity_detail" == *'does not match the provider target'* ]]; then
    add_check identity fail 'Private target identity does not match UTM'
else
    add_check identity fail 'Exact private target identity is unavailable'
fi

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

provider_capabilities="$($PROVIDER capabilities --json 2>/dev/null || true)"
if jq -e '
        .schema_version == 1 and
        (.lifecycle.suspend.availability |
            IN("available", "unavailable", "unknown")) and
        (.lifecycle.suspend.source | type == "string" and length > 0) and
        (.lifecycle.suspend.reasons | type == "array" and
            all(.[]; type == "string")) and
        (.lifecycle.default_down_action |
            IN("suspend", "guest-shutdown"))' \
        <<<"$provider_capabilities" >/dev/null 2>&1; then
    lifecycle="$(jq -c '{
        suspend:.lifecycle.suspend,
        defaultDownAction:.lifecycle.default_down_action
    }' <<<"$provider_capabilities")"
    if [[ "$(jq -r '.suspend.availability' <<<"$lifecycle")" == available ]]; then
        lifecycle_operations='["status","up","suspend","shutdown","force-stop"]'
    fi
fi

guest_probe=""
guest_probe_exit=1
if [[ "$power" == running ]]; then
    export WINVM_SSH_ALLOW_START=false
    read -r -d '' probe_script <<'POWERSHELL' || true
$ErrorActionPreference = 'Stop'
$runtime = Join-Path $env:ProgramData `
    'MachineControl\runtime\machine-control-windows.exe'

function Invoke-ControlProbe {
    param([Parameter(Mandatory = $true)][string]$Operation)
    if (-not (Test-Path -LiteralPath $runtime -PathType Leaf)) {
        return $null
    }
    try {
        $request = [ordered]@{ operation = $Operation } |
            ConvertTo-Json -Compress
        $output = @($request | & $runtime call 2>$null)
        $exitCode = $LASTEXITCODE
        if ($exitCode -ne 0) { return $null }
        return ($output -join "`n") | ConvertFrom-Json
    }
    catch {
        return $null
    }
}

$status = Invoke-ControlProbe -Operation 'status'
$capabilities = Invoke-ControlProbe -Operation 'capabilities'
[ordered]@{
    explorerPresent = [bool](
        Get-Process explorer -ErrorAction SilentlyContinue)
    status = if ($status) {
        [ordered]@{
            schema = $status.schema
            accepted = $status.accepted
            sessionLocked = $status.sessionLocked
            desktop = $status.desktop
            generation = $status.generation
        }
    }
    else {
        $null
    }
    nativeProvider = [bool]($capabilities.accepted -eq $true -and
        @($capabilities.data.providers |
            Where-Object {
                $_.id -eq 'windows-native' -and $_.state -eq 'native'
            }).Count -gt 0)
} | ConvertTo-Json -Depth 6 -Compress
POWERSHELL
    guest_probe="$(winvm_powershell_bounded \
        "$WINVM_DOCTOR_GUEST_TIMEOUT" "$probe_script" 2>/dev/null)"
    guest_probe_exit=$?
fi

if [[ "$guest_probe_exit" -eq 0 ]] &&
        jq -e 'type == "object"' <<<"$guest_probe" >/dev/null 2>&1; then
    administration=ready
    add_check administration pass 'Key-only PowerShell administration is ready'
elif [[ "$guest_probe_exit" -eq 124 ]]; then
    add_check administration fail 'Guest administration probe timed out'
else
    add_check administration fail 'Guest administration is unavailable'
fi

if jq -e '.explorerPresent == true' \
        <<<"$guest_probe" >/dev/null 2>&1; then
    desktop=unlocked
    add_check desktop pass 'Interactive Windows desktop is present'
else
    add_check desktop fail 'Interactive Windows desktop is unavailable'
fi

if [[ "$administration" == ready ]] &&
        jq -e '.status.schema == "machine-control/v0" and
            .status.accepted == true' \
            <<<"$guest_probe" >/dev/null 2>&1; then
    resident=ready
    if [[ "$(jq -r '.status.sessionLocked // false' \
            <<<"$guest_probe")" == true ]]; then
        desktop=locked
    elif [[ "$(jq -r '.status.desktop // "Default"' \
            <<<"$guest_probe")" != Default ]]; then
        desktop=protected
    fi
    resident_json="$(jq -c \
        '{contract:.status.schema,generation:.status.generation}' \
        <<<"$guest_probe")"
    add_check resident pass 'Target-native resident is ready'
else
    add_check resident fail 'Target-native resident is unavailable'
fi

if [[ "$resident" == ready ]] && jq -e '.nativeProvider == true' \
        <<<"$guest_probe" >/dev/null 2>&1; then
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
if [[ "$identity" == verified && "$power" == running &&
      "$administration" == ready &&
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
    --arg identity "$identity" \
    --argjson resident "$resident_json" \
    --argjson checks "$checks" \
    --argjson lifecycle_operations "$lifecycle_operations" \
    --argjson lifecycle "$lifecycle" \
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
        lifecycleOperations:$lifecycle_operations,
        extensions:{
            targetIdentity:$identity,
            administrationRoute:"key_only_ssh_powershell",
            desktopSession:"windows_interactive_console",
            protectedAuthority:"dedicated_test_appliance",
            lifecycle:$lifecycle
        }
    }'

[[ "$ready" == true ]]
