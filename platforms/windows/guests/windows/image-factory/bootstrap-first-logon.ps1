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

$guestTools = @(Get-ChildItem -LiteralPath $seedRoot -File |
    Where-Object Name -Like 'utm-guest-tools-*.exe')
if ($guestTools.Count -ne 1) {
    throw 'WINVM_SEED must contain exactly one UTM guest-tools installer'
}
$guestToolsProcess = Start-Process -FilePath $guestTools[0].FullName `
    -ArgumentList '/S' -Wait -PassThru
if ($guestToolsProcess.ExitCode -notin @(0, 3010)) {
    throw "UTM guest-tools installer exited with $($guestToolsProcess.ExitCode)"
}
$guestAgent = Get-Service -Name qemu-ga -ErrorAction SilentlyContinue
if (-not $guestAgent) {
    throw 'UTM guest tools did not install the QEMU guest agent service'
}
Set-Service -Name qemu-ga -StartupType Automatic
if ($guestAgent.Status -ne 'Running') {
    Start-Service -Name qemu-ga
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
    guest_tools_installer = $guestTools[0].Name
    guest_tools_exit_code = $guestToolsProcess.ExitCode
    guest_agent_state = (Get-Service -Name qemu-ga).Status.ToString()
    guest_agent_start_mode = (Get-CimInstance Win32_Service `
        -Filter "Name='qemu-ga'").StartMode
    ssh_bootstrap_report = $report
    seed_removal_required = $true
} | ConvertTo-Json | Set-Content -LiteralPath `
    (Join-Path $programDataRoot 'state.json') -Encoding utf8
