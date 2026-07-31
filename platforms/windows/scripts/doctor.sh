#!/usr/bin/env bash

set -uo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"
failures=0

pass() {
    printf '[ok]   %s\n' "$*"
}

fail() {
    printf '[fail] %s\n' "$*" >&2
    failures=$((failures + 1))
}

printf 'provider=%s guest=%s ssh=%s\n' \
    "$WINVM_PROVIDER" "$WINVM_GUEST_DRIVER" "$WINVM_SSH_HOST"

if status="$($WINVM_REPO_DIR/bin/winvm status 2>/dev/null)"; then
    if [[ "$status" == "started" ]]; then
        pass "VM status: $status"
    else
        fail "VM status is ${status:-unknown}; run: $WINVM_REPO_DIR/bin/winvm up"
        exit "$failures"
    fi
else
    fail "provider health check failed: $WINVM_PROVIDER"
    exit "$failures"
fi

addresses="$($WINVM_REPO_DIR/bin/winvm ip 2>/dev/null || true)"
ip="$(printf '%s\n' "$addresses" | awk '/^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$/ { print; exit }')"
if [[ -z "$ip" ]]; then
    fail 'provider did not report an IPv4 address'
    exit "$failures"
fi
pass "guest IPv4: $ip"

if winvm_tcp_check "$ip" "$WINVM_SSH_PORT" 2; then
    pass "TCP/$WINVM_SSH_PORT is reachable"
else
    fail "TCP/$WINVM_SSH_PORT is not reachable (check sshd and the guest firewall)"
fi

read -r -d '' powershell_script <<POWERSHELL || true
\$taskName = '$WINVM_UI_TASK_NAME'
\$task = Get-ScheduledTask -TaskName \$taskName -ErrorAction SilentlyContinue
\$taskInfo = Get-ScheduledTaskInfo -TaskName \$taskName -ErrorAction SilentlyContinue
\$statePath = Join-Path \$env:LOCALAPPDATA 'winvm-testbed\relay-state.json'
\$relayState = if (Test-Path -LiteralPath \$statePath) {
    Get-Content -LiteralPath \$statePath -Raw | ConvertFrom-Json
} else {
    \$null
}
[ordered]@{
    computer = \$env:COMPUTERNAME
    user = [Security.Principal.WindowsIdentity]::GetCurrent().Name
    ssh_session = (Get-Process -Id \$PID).SessionId
    sshd = [ordered]@{
        status = (Get-Service sshd -ErrorAction SilentlyContinue).Status.ToString()
        start_type = (Get-Service sshd -ErrorAction SilentlyContinue).StartType.ToString()
    }
    explorer_sessions = @(Get-Process explorer -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty SessionId -Unique)
    ui_task = if (\$task) {
        [ordered]@{
            state = \$task.State.ToString()
            last_result = ('0x{0:X8}' -f \$taskInfo.LastTaskResult)
            last_run = \$taskInfo.LastRunTime.ToString('o')
        }
    } else {
        \$null
    }
    relay = \$relayState
} | ConvertTo-Json -Depth 8 -Compress
POWERSHELL

if guest_json="$(winvm_powershell "$powershell_script" 2>/dev/null)" \
        && printf '%s' "$guest_json" | jq -e . >/dev/null 2>&1; then
    pass 'key-only SSH and PowerShell are working'
    printf '%s\n' "$guest_json" | jq .
else
    fail 'key-only SSH or the PowerShell diagnostic query failed'
fi

if health="$($WINVM_REPO_DIR/bin/winui health 2>/dev/null)"; then
    pass 'interactive UI relay is reachable from SSH session 0'
    printf '%s\n' "$health" | jq .
else
    fail 'interactive UI relay is unavailable (log on, then run: winvm deploy-ui)'
fi

if version="$($WINVM_REPO_DIR/bin/winui winapp --version 2>/dev/null)"; then
    pass "winapp: $(printf '%s' "$version" | tr '\n' ' ')"
else
    fail 'winapp CLI did not run through the interactive relay'
fi

if (( failures > 0 )); then
    printf '\n%s check(s) failed.\n' "$failures" >&2
    exit 1
fi

printf '\nAll Windows VM access checks passed.\n'
