#!/usr/bin/env bash
# Sourced after common.sh. Values are private adapter configuration, never
# request-controlled endpoint overrides. Default remains the appliance.
resident_profile_powershell() {
    local profile="${WINVM_RESIDENT_PROFILE:-appliance}"
    case "$profile" in
        appliance)
            cat <<'PS'
$executable = Join-Path $env:ProgramData 'MachineControl\runtime\machine-control-windows.exe'
$artifactRoot = Join-Path $env:ProgramData 'MachineControl\artifacts'
$callArguments = @('call')
PS
            ;;
        user)
            local instance="${WINVM_USER_INSTANCE:-default}"
            local session="${WINVM_USER_SESSION_ID:-}"
            if [[ ! "$instance" =~ ^[a-z0-9][a-z0-9-]{0,47}$ ||
                  ! "$session" =~ ^[1-9][0-9]{0,8}$ ]]; then
                printf 'User profile requires a valid instance and explicit interactive session ID\n' >&2
                return 2
            fi
            cat <<PS
\$installation = Join-Path \$env:LOCALAPPDATA 'MachineControl/packages/$instance'
\$selection = Get-Content -LiteralPath (Join-Path \$installation 'active.json') -Raw | ConvertFrom-Json
if (\$selection.active -notmatch '^[a-f0-9]{64}$') { throw 'Invalid resident package selection' }
\$executable = Join-Path \$installation ('versions\' + \$selection.active + '\machine-control-windows.exe')
\$artifactRoot = Join-Path \$env:LOCALAPPDATA 'MachineControl/workstation/$instance/session-$session/artifacts'
\$callArguments = @('call', '--profile', 'user', '--instance', '$instance', '--session-id', '$session')
PS
            ;;
        *) printf 'Unknown resident profile\n' >&2; return 2 ;;
    esac
}
