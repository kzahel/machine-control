#Requires -RunAsAdministrator

$ErrorActionPreference = 'Stop'
$seed = Get-Volume -FileSystemLabel 'WINVM_SEED' -ErrorAction Stop |
    Select-Object -First 1
$seedRoot = "$($seed.DriveLetter):\"
$bootstrap = Join-Path $seedRoot 'bootstrap-openssh.ps1'
$publicKey = Join-Path $seedRoot 'controller.pub'
if (-not (Test-Path -LiteralPath $bootstrap) -or
    -not (Test-Path -LiteralPath $publicKey)) {
    throw 'WINVM_SEED is missing the OpenSSH bootstrap inputs'
}

$programDataRoot = Join-Path $env:ProgramData 'WinVM-Factory'
New-Item -ItemType Directory -Force -Path $programDataRoot | Out-Null
$report = Join-Path $programDataRoot 'first-logon-report.json'
& powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass `
    -File $bootstrap -PublicKeyPath $publicKey -ReportPath $report
if ($LASTEXITCODE -ne 0) {
    throw "OpenSSH bootstrap exited with $LASTEXITCODE"
}

[ordered]@{
    schema = 'winvm-image-factory-first-logon/v0'
    completed = $true
    ssh_bootstrap_report = $report
    seed_removal_required = $true
} | ConvertTo-Json | Set-Content -LiteralPath `
    (Join-Path $programDataRoot 'state.json') -Encoding utf8
