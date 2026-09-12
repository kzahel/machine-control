[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$ApplianceExecutable,
    [Parameter(Mandatory=$true)][string]$Package,
    [Parameter(Mandatory=$true)][string]$ExpectedPublisher,
    [Parameter(Mandatory=$true)][ValidateSet('CancelInstall','RejectUnsigned','Install','CancelArm','Arm','Revoke','Uninstall')][string]$Stage,
    [ValidatePattern('^[a-z0-9][a-z0-9-]{0,47}$')][string]$Instance = 'unlock-conformance',
    [string]$Proposal,
    [string]$EvidencePath = (Join-Path $env:TEMP 'unlock-setup-conformance.json')
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$setup = Join-Path $Package 'unlock-setup.exe'
$root = Join-Path $env:ProgramFiles "MachineControlUnlock\$Instance"
$state = Join-Path $env:ProgramData "MachineControlUnlock\$Instance"
$serviceName = "MachineControlUnlock_$Instance"
$grantPath = Join-Path $state 'grant.json'
$summary = [ordered]@{ schema='machine-control-unlock-setup-conformance/v0'; stage=$Stage; passed=$false }
function Control([hashtable]$Request) {
    $result = ($Request | ConvertTo-Json -Depth 12 -Compress | & $ApplianceExecutable call) | ConvertFrom-Json
    if ($LASTEXITCODE -ne 0 -or -not $result.accepted) { throw "Appliance harness refused $($Request.operation): $($result.errorCode)" }
    return $result
}
function Wait-Desktop([string]$Name) {
    $deadline = [DateTime]::UtcNow.AddSeconds(30)
    do {
        $result = Control @{operation='status'; scope='system'}
        if ($result.desktop -eq $Name) { return }
        Start-Sleep -Milliseconds 200
    } while ([DateTime]::UtcNow -lt $deadline)
    throw "Desktop did not become $Name"
}
function Button([string]$Name, [string]$WindowQuery) {
    $deadline = [DateTime]::UtcNow.AddSeconds(30)
    do {
        $request = @{operation='snapshot'; scope='system'; maxDepth=16; maxElements=150}
        if ($WindowQuery) {
            $inventory = Control @{operation='windows'; scope='system'; query=$WindowQuery; maxElements=20}
            $windows = @($inventory.data.windows | Where-Object {$_.visible})
            if ($windows.Count -ne 1) { Start-Sleep -Milliseconds 200; continue }
            $request.hwnd = [long]$windows[0].hwnd
        }
        $snapshot = Control $request
        $buttons = @($snapshot.data.elements | Where-Object { $_.controlType -eq 'Button' -and $_.name -eq $Name -and -not $_.offscreen })
        if ($buttons.Count -eq 1) {
            if ($WindowQuery) {
                & (Join-Path $PSScriptRoot 'unlock-consent-button.ps1') -WindowHandle $request.hwnd -ExpectedProcessId $windows[0].processId -Button $Name
                return
            }
            # Protected desktop workers are disposable; resolve the observed
            # unique button again by name.
            $invoke=@{operation='invoke'; scope='system'; query=$Name; allowVisualFallback=$true}
            if ($request.ContainsKey('hwnd')) { $invoke.hwnd=$request.hwnd }
            Control $invoke | Out-Null
            return
        }
        Start-Sleep -Milliseconds 200
    } while ([DateTime]::UtcNow -lt $deadline)
    throw "Unique consent button not found: $Name"
}
try {
    $signature = Get-AuthenticodeSignature -LiteralPath $setup
    if ($signature.Status -ne 'Valid' -or -not $signature.TimeStamperCertificate -or
        $signature.SignerCertificate.GetNameInfo([Security.Cryptography.X509Certificates.X509NameType]::SimpleName,$false) -cne $ExpectedPublisher) {
        throw 'Unexpected bootstrap publisher'
    }
    $policy = Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System'
    if ($policy.EnableLUA -ne 1 -or $policy.PromptOnSecureDesktop -ne 1 -or $policy.ConsentPromptBehaviorAdmin -eq 0) {
        throw 'The test requires stock UAC consent on the secure desktop'
    }
    Wait-Desktop 'Default'
    $ordinary = Control @{operation='status'}
    if ($ordinary.data.integrityRid -ne 8192 -or $ordinary.data.isLocalSystem) { throw 'Requester is not Medium' }
    $before = if (Test-Path $grantPath) { (Get-FileHash $grantPath).Hash } else { $null }
    $action = switch ($Stage) {
        'CancelInstall' {'Install'}
        'RejectUnsigned' {'Install'}
        'CancelArm' {'Arm'}
        default {$Stage}
    }
    if ($action -eq 'Install' -and ((Get-Service $serviceName -ErrorAction SilentlyContinue) -or (Test-Path $root))) {
        throw 'Conformance instance already exists'
    }
    $arguments = "$action $Instance"
    if ($Stage -eq 'RejectUnsigned') { $arguments += ' - --allow-unsigned' }
    if ($action -eq 'Arm') {
        if (-not $Proposal -or -not (Test-Path -LiteralPath $Proposal)) { throw 'Public approval proposal required' }
        $arguments += ' "' + $Proposal + '"'
    }
    $launch = Control @{operation='app.launch'; executablePath=$setup; arguments=$arguments}
    $setupProcess = Get-Process -Id $launch.data.processId
    [void]$setupProcess.Handle
    Wait-Desktop 'Winlogon'
    $summary.uacObserved = $true
    Button $(if ($Stage -eq 'CancelInstall') { 'No' } else { 'Yes' }) ''
    Wait-Desktop 'Default'
    if ($action -eq 'Arm') {
        # Restrict the snapshot to the elevated grant dialog, not any unrelated
        # app with Yes/No buttons on the same desktop.
        Button $(if ($Stage -eq 'CancelArm') { 'No' } else { 'Yes' }) 'approve unattended unlock'
        $summary.elevatedGrantDialogObserved = $true
    }
    if (-not $setupProcess.WaitForExit(90000)) { throw 'Setup did not finish' }
    $expectedExit = if ($Stage -in @('CancelInstall','CancelArm')) {1223} elseif ($Stage -eq 'RejectUnsigned') {1} else {0}
    if ($setupProcess.ExitCode -ne $expectedExit) { throw "Unexpected setup exit: $($setupProcess.ExitCode)" }
    $summary.exitCode = $setupProcess.ExitCode
    $deadline = [DateTime]::UtcNow.AddSeconds(90)
    $observed = $false
    do {
        $service = Get-Service $serviceName -ErrorAction SilentlyContinue
        $grant = Test-Path -LiteralPath $grantPath
        switch ($Stage) {
            'CancelInstall' { $observed = -not $service -and -not (Test-Path $root) }
            'RejectUnsigned' { $observed = -not $service -and -not (Test-Path $root) }
            'Install' { $observed = $service -and $service.Status -eq 'Running' -and -not $grant }
            'CancelArm' {
                $after = if ($grant) { (Get-FileHash $grantPath).Hash } else { $null }
                $observed = $after -ceq $before
            }
            'Arm' {
                if ($grant) {
                    $approved = Get-Content -LiteralPath $grantPath -Raw | ConvertFrom-Json
                    $proposed = Get-Content -LiteralPath $Proposal -Raw | ConvertFrom-Json
                    $observed = $approved.revision -ceq $proposed.revision -and
                        $approved.targetUserSid -ceq $proposed.targetUserSid -and
                        $approved.transportUserSid -ceq $proposed.transportUserSid -and
                        $approved.controllerPublicKey -ceq $proposed.controllerPublicKey
                }
            }
            'Revoke' { $observed = -not $grant -and $service -and $service.Status -eq 'Running' }
            'Uninstall' { $observed = -not $service -and -not (Test-Path $root) -and -not (Test-Path $state) }
        }
        if ($observed) { break }
        Start-Sleep -Milliseconds 250
    } while ([DateTime]::UtcNow -lt $deadline)
    if (-not $observed) { throw "Independent setup state did not confirm $Stage" }
    if ($Stage -in @('Install','Arm','Revoke')) {
        $status = & (Join-Path $root 'machine-control-windows.exe') unlock --status --instance $Instance | ConvertFrom-Json
        if ($LASTEXITCODE -ne 0 -or $status.stage -ne 'status') { throw 'Authenticated service status failed' }
        $expectedState = if ($Stage -eq 'Arm') {'armed'} else {'unarmed_or_invalid'}
        if ($status.state -ne $expectedState) { throw 'Grant state mismatch' }
        $summary.serviceState = $status.state
    }
    $summary.passed = $true
} finally {
    # No credentials or concrete account/key identities enter the evidence.
    $summary | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $EvidencePath
    $summary | ConvertTo-Json -Depth 8
}
