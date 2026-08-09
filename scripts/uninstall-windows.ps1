[CmdletBinding()]
param(
    [switch]$RemoveInstalledFiles
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$serviceName = 'MachineControlRuntime'
$installRoot = Join-Path $env:ProgramData 'MachineControl\runtime'
$artifactRoot = Join-Path $env:ProgramData 'MachineControl\artifacts'

if (Get-Service -Name $serviceName -ErrorAction SilentlyContinue) {
    Stop-Service -Name $serviceName -Force -ErrorAction SilentlyContinue
    & sc.exe delete $serviceName | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "sc.exe delete failed with $LASTEXITCODE"
    }
    $deleteDeadline = [DateTime]::UtcNow.AddSeconds(15)
    while ((Get-Service -Name $serviceName -ErrorAction SilentlyContinue) -and
        [DateTime]::UtcNow -lt $deleteDeadline) {
        Start-Sleep -Milliseconds 250
    }
    if (Get-Service -Name $serviceName -ErrorAction SilentlyContinue) {
        throw 'the service remained pending deletion'
    }
}

if ($RemoveInstalledFiles) {
    Remove-Item -LiteralPath $installRoot -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $artifactRoot -Recurse -Force -ErrorAction SilentlyContinue
}

[pscustomobject]@{
    service_present = [bool](Get-Service -Name $serviceName -ErrorAction SilentlyContinue)
    installed_files_present = Test-Path -LiteralPath $installRoot
    artifacts_present = Test-Path -LiteralPath $artifactRoot
} | ConvertTo-Json -Compress
