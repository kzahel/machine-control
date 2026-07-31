#Requires -RunAsAdministrator

[CmdletBinding()]
param(
    [string]$InstallDirectory = "$env:LOCALAPPDATA\winvm-testbed",
    [string]$TaskName = 'WinVM UI Relay',
    [switch]$RemoveInstalledFiles
)

$ErrorActionPreference = 'Stop'

Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

if ($RemoveInstalledFiles -and (Test-Path -LiteralPath $InstallDirectory)) {
    Remove-Item -LiteralPath $InstallDirectory -Recurse -Force
}
