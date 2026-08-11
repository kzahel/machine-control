#Requires -RunAsAdministrator

[CmdletBinding()]
param(
    [string]$InstallDirectory = "$env:LOCALAPPDATA\winvm-testbed",
    [string]$PipeName = 'winvm-ui',
    [string]$TaskName = 'WinVM UI Relay'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$relayPath = Join-Path $InstallDirectory 'ui-relay.ps1'
$clientPath = Join-Path $InstallDirectory 'ui-client.ps1'
foreach ($path in @($relayPath, $clientPath)) {
    if (-not (Test-Path -LiteralPath $path)) {
        throw "Required relay file not found: $path"
    }
}

$winAppCommand = Get-Command winapp.exe -ErrorAction Stop
$winAppPath = $winAppCommand.Source
$identity = [Security.Principal.WindowsIdentity]::GetCurrent().Name
$statePath = Join-Path $InstallDirectory 'relay-state.json'

Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 500
Remove-Item -LiteralPath $statePath -Force -ErrorAction SilentlyContinue

$actionArguments = @(
    '-NoLogo'
    '-NoProfile'
    '-NonInteractive'
    '-WindowStyle Hidden'
    '-ExecutionPolicy Bypass'
    "-File `"$relayPath`""
    "-PipeName `"$PipeName`""
    "-WinAppPath `"$winAppPath`""
    "-StateDirectory `"$InstallDirectory`""
) -join ' '

$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $actionArguments
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $identity
$principal = New-ScheduledTaskPrincipal `
    -UserId $identity `
    -LogonType Interactive `
    -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1)

Register-ScheduledTask `
    -TaskName $TaskName `
    -Description 'Interactive-session Windows UI Automation relay for WinVM Testbed.' `
    -Action $action `
    -Trigger $trigger `
    -Principal $principal `
    -Settings $settings `
    -Force | Out-Null

Start-ScheduledTask -TaskName $TaskName

$deadline = (Get-Date).AddSeconds(20)
do {
    if (Test-Path -LiteralPath $statePath) {
        try {
            $relayState = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
            if ([int]$relayState.session_id -gt 0) {
                break
            }
        } catch {
            # The relay may still be replacing the state file.
        }
    }
    Start-Sleep -Milliseconds 250
} while ((Get-Date) -lt $deadline)

if (-not (Test-Path -LiteralPath $statePath)) {
    $task = Get-ScheduledTaskInfo -TaskName $TaskName
    $logPath = Join-Path $InstallDirectory 'relay.log'
    $logTail = if (Test-Path -LiteralPath $logPath) {
        (Get-Content -LiteralPath $logPath -Tail 10) -join "`n"
    } else {
        '(no relay log)'
    }
    throw "Relay did not create state file; task result=$($task.LastTaskResult)`n$logTail"
}

$relayState = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
if ([int]$relayState.session_id -eq 0) {
    throw 'Relay started in session 0 instead of the interactive desktop session'
}

[ordered]@{
    installed = $true
    task_name = $TaskName
    task_state = (Get-ScheduledTask -TaskName $TaskName).State.ToString()
    user = $identity
    pipe_name = $PipeName
    relay_pid = $relayState.pid
    relay_session = $relayState.session_id
    winapp_path = $winAppPath
    install_directory = $InstallDirectory
} | ConvertTo-Json
