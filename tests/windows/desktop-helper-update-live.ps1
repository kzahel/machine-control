[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$Migration,
    [Parameter(Mandatory)][string]$Incoming,
    [Parameter(Mandatory)][string]$Tampered,
    [Parameter(Mandatory)][string]$Evidence,
    [string]$Broken
)

# Run from the unlocked test account's interactive High token. The actual
# update requests run under separate interactive Limited tasks.
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$name = 'MachineControlDesktopUac'
$root = Join-Path $env:ProgramFiles $name
$versions = Join-Path $root 'versions'
$legacy = Join-Path $root 'machine-control-windows.exe'
$key = "HKLM:\SYSTEM\CurrentControlSet\Services\$name"
$owner = [Security.Principal.WindowsIdentity]::GetCurrent().Name
$baseline = (Get-ItemProperty -LiteralPath $key).ImagePath
$lock = Join-Path $root 'maintenance.lock'
$hadLock = Test-Path $lock
$before = @(Get-ChildItem -LiteralPath $versions -Directory -ErrorAction SilentlyContinue |
    ForEach-Object Name)
$hadVersions = Test-Path -LiteralPath $versions
$priorReceipts = @(Get-ChildItem -LiteralPath $root -File -Filter 'maintenance-result-*' |
    ForEach-Object Name)
$checks = [Collections.Generic.List[string]]::new()

function Assert([bool]$Condition, [string]$Message) {
    if (-not $Condition) { throw $Message }
    $checks.Add($Message)
}

function Install-Image([string]$Folder) {
    Join-Path $Folder 'machine-control-windows.exe'
}

function Invoke-Limited([string]$Image, [string]$Command) {
    $token = [Guid]::NewGuid().ToString('N')
    $task = "MachineControlHelperUpdateFixture-$token"
    $result = Join-Path (Split-Path $Evidence) "$token.txt"
    $program = @'
$ErrorActionPreference = 'Stop'
& '{0}' '{1}' > '{2}.pending'
Add-Content -LiteralPath '{2}.pending' -Value "exit=$LASTEXITCODE"
Move-Item -LiteralPath '{2}.pending' -Destination '{2}'
'@ -f $Image, $Command, $result
    $encoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($program))
    $powershell = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
    $action = New-ScheduledTaskAction -Execute $powershell -Argument "-NoProfile -NonInteractive -EncodedCommand $encoded"
    $principal = New-ScheduledTaskPrincipal -UserId $owner -LogonType Interactive -RunLevel Limited
    try {
        Register-ScheduledTask -TaskName $task -Action $action -Principal $principal | Out-Null
        Start-ScheduledTask -TaskName $task
        $until = [DateTime]::UtcNow.AddMinutes(5)
        do {
            Start-Sleep -Milliseconds 200
            if (Test-Path $result) {
                $lines = @(Get-Content -LiteralPath $result)
                if ($lines.Count -and $lines[-1] -match '^exit=(\d+)$') {
                    return @{ Code = [int]$Matches[1]; Output = @($lines | Select-Object -SkipLast 1) }
                }
            }
        } while ([DateTime]::UtcNow -lt $until)
        throw "The Limited $Command actor did not report a result"
    } finally {
        Stop-ScheduledTask -TaskName $task -ErrorAction SilentlyContinue
        Unregister-ScheduledTask -TaskName $task -Confirm:$false -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $result -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath "$result.pending" -ErrorAction SilentlyContinue
    }
}

function Current-Image {
    ((Get-ItemProperty -LiteralPath $key).ImagePath -split '"')[1]
}

function Enrollment-Metadata {
    $folder = Join-Path $env:ProgramData 'MachineControlUnlock\desktop'
    @(Get-ChildItem -LiteralPath $folder -File -ErrorAction SilentlyContinue |
        Where-Object Name -ne 'admin.lock' |
        Sort-Object Name | Select-Object Name,Length,LastWriteTimeUtc |
        ConvertTo-Json -Compress)
}

$failure = $null
try {
    Assert ((Current-Image) -eq $legacy) 'Legacy fixed-path helper is the starting service'
    Assert (-not (Test-Path (Join-Path $root 'helper-release.json'))) 'Legacy helper has no signed upgrade manifest'
    $enrollment = @(Enrollment-Metadata)
    Assert ($enrollment.Count -gt 0) 'Legacy helper has existing enrollment metadata'
    & (Install-Image $Migration) 'uac-update-migrate'
    Assert ($LASTEXITCODE -eq 0) 'Interactive administrator migrated the legacy helper in place'
    $first = Current-Image
    Assert ($first -ne $legacy -and (Get-Service $name).Status -eq 'Running') 'SCM started the first versioned helper'
    $resolved = Invoke-Limited (Install-Image $Migration) 'uac-resolve'
    Assert ($resolved.Code -eq 0 -and $resolved.Output[0] -eq $first) 'Medium resident resolves its matching migrated image'

    $updated = Invoke-Limited (Install-Image $Incoming) 'uac-update'
    Assert ($updated.Code -eq 0) 'Medium caller completed the signed update without elevation'
    $second = Current-Image
    Assert ($second -ne $first -and (Get-Service $name).Status -eq 'Running') 'SCM started the second versioned helper'
    $resolved = Invoke-Limited (Install-Image $Incoming) 'uac-resolve'
    Assert ($resolved.Code -eq 0 -and $resolved.Output[0] -eq $second) 'Medium resident resolves its matching upgraded image'
    $resolved = Invoke-Limited (Install-Image $Migration) 'uac-resolve'
    Assert ($resolved.Code -eq 0 -and $resolved.Output[0] -eq (Install-Image $Migration)) 'Stale per-user copy cannot select the newer privileged payload'

    Assert ((Invoke-Limited (Install-Image $Tampered) 'uac-update').Code -ne 0) 'Tampered signed payload was refused'
    Assert ((Current-Image) -eq $second) 'Tampering did not change the healthy service image'
    Assert ((Invoke-Limited (Install-Image $Migration) 'uac-update').Code -ne 0) 'Signed downgrade was refused'
    Assert ((Current-Image) -eq $second) 'Downgrade did not change the healthy service image'
    if ($Broken) {
        $beforeFailure = (Get-CimInstance Win32_Service -Filter "Name='$name'").ProcessId
        $failed = Invoke-Limited (Join-Path $Broken 'fixture-update-client.exe') 'uac-update'
        Assert ($failed.Code -eq 4) 'The signed but unstartable helper reported activation failure'
        $restoredService = Get-CimInstance Win32_Service -Filter "Name='$name'"
        Assert ((Current-Image) -eq $second -and $restoredService.State -eq 'Running' -and
            $restoredService.ProcessId -ne $beforeFailure) 'SCM restarted the previous helper after activation failed'
    }
    Assert ((Enrollment-Metadata) -join '' -ceq ($enrollment -join '')) 'Helper maintenance did not change enrollment metadata'
} catch {
    $failure = $_.Exception.Message
} finally {
    try {
        if ((Get-ItemProperty -LiteralPath $key).ImagePath -ne $baseline) {
            Stop-Service $name
            $service = Get-CimInstance Win32_Service -Filter "Name='$name'"
            $restored = Invoke-CimMethod -InputObject $service -MethodName Change -Arguments @{ PathName = $baseline }
            if ($restored.ReturnValue -ne 0) { throw 'Could not restore the legacy service image' }
            Start-Service $name
        }
        Get-ChildItem -LiteralPath $versions -Directory -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -notin $before -and $_.Name -match '^[a-f0-9]{32}$' } |
            Remove-Item -Recurse -Force
        if (-not $hadVersions -and (Test-Path -LiteralPath $versions)) {
            if (@(Get-ChildItem -LiteralPath $versions -Force).Count -eq 0) { Remove-Item -LiteralPath $versions }
        }
        Get-ChildItem -LiteralPath $root -File -Filter 'maintenance-result-*' |
            Where-Object { $_.Name -notin $priorReceipts -and $_.Name -match '^maintenance-result-[a-f0-9]{32}(\.tmp)?$' } |
            Remove-Item -Force
        if (-not $hadLock) { Remove-Item -LiteralPath $lock -Force -ErrorAction SilentlyContinue }
    } catch {
        $failure = "$failure [cleanup: $($_.Exception.Message)]"
    }
    [pscustomobject]@{ passed = $null -eq $failure; checks = @($checks.ToArray()); failure = $failure } |
        ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $Evidence -Encoding UTF8
}
if ($failure) { throw $failure }
