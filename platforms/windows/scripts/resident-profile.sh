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
        user|desktop)
            local instance="${WINVM_USER_INSTANCE:-default}"
            local session="${WINVM_USER_SESSION_ID:-}"
            [[ "$profile" != desktop ]] || instance=desktop
            if [[ ! "$instance" =~ ^[a-z0-9][a-z0-9-]{0,47}$ ||
                  ! "$session" =~ ^[1-9][0-9]{0,8}$ ]]; then
                printf 'User profile requires a valid instance and explicit interactive session ID\n' >&2
                return 2
            fi
            if [[ "$profile" == desktop ]]; then
                local directory="${WINVM_DESKTOP_INSTALL_DIR:-}"
                local encoded
                encoded="$(printf '%s' "$directory" | base64 | tr -d '\n')"
                cat <<PS
\$installation = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('$encoded'))
if (-not \$installation) { \$installation = Join-Path \$env:LOCALAPPDATA 'Machine Control' }
\$metadata = Get-Content -LiteralPath (Join-Path \$installation 'runtime/desktop-runtime.json') -Raw | ConvertFrom-Json
if (\$metadata.schema -ne 'machine-control-desktop-runtime/v0' -or \$metadata.profile -ne 'ordinary_user_desktop' -or \$metadata.instance -ne 'desktop') { throw 'Not a desktop product installation' }
\$executable = Join-Path \$installation 'runtime/machine-control-windows.exe'
PS
            else
                cat <<PS
\$installation = Join-Path \$env:LOCALAPPDATA 'MachineControl/packages/$instance'
\$selection = Get-Content -LiteralPath (Join-Path \$installation 'active.json') -Raw | ConvertFrom-Json
if (\$selection.active -notmatch '^[a-f0-9]{64}$') { throw 'Invalid resident package selection' }
\$executable = Join-Path \$installation ('versions\' + \$selection.active + '\machine-control-windows.exe')
PS
            fi
            cat <<PS
\$artifactRoot = Join-Path \$env:LOCALAPPDATA 'MachineControl/workstation/$instance/session-$session/artifacts'
\$callArguments = @('call', '--profile', 'user', '--instance', '$instance', '--session-id', '$session')
PS
            ;;
        *) printf 'Unknown resident profile\n' >&2; return 2 ;;
    esac
}
