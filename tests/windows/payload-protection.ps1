# Bounded filesystem-only acceptance; no installed app or registry is changed.
param([Parameter(Mandatory=$true)][string]$Helper,
      [Parameter(Mandatory=$true)][string]$Python)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$root = Join-Path $env:TEMP ('mc-payload-test-' + [Guid]::NewGuid().ToString('n'))
$outside = $root + '-outside'
$junction = Join-Path $root 'mc-cli\linked'
function Assert($Value, [string]$Message) { if (-not $Value) { throw $Message } }
function Refuses([scriptblock]$Operation) {
    $refused = $false
    try { & $Operation } catch { $refused = $true }
    Assert $refused ('Expected filesystem operation to refuse: ' + $Operation.ToString().Trim())
}
function Payload {
    New-Item -ItemType Directory (Join-Path $root 'mc-cli\client'),(Join-Path $root 'runtime') -Force | Out-Null
    Set-Content -LiteralPath (Join-Path $root 'mc-cli\client-runtime.json') -Value '{"schema":"machine-control-client-identity/v1"}'
    Set-Content -LiteralPath (Join-Path $root 'runtime\desktop-runtime.json') -Value '{"schema":"machine-control-desktop-runtime/v0"}'
    Set-Content -LiteralPath (Join-Path $root 'mc-cli\client\fixture.py') -Value 'value = 1'
}
try {
    Payload
    $state = Join-Path $root 'user-state.txt'
    Set-Content -LiteralPath $state -Value 'preserve'
    & $Helper -Action protect -Directory $root
    & $Helper -Action protect -Directory $root
    Refuses { Set-Content -LiteralPath (Join-Path $root 'mc-cli\new.py') -Value 'accidental' }
    Refuses { Set-Content -LiteralPath (Join-Path $root 'mc-cli\client\fixture.py') -Value 'accidental' }
    & $Python -I (Join-Path $PSScriptRoot 'payload-write-probe.py') (Join-Path $root 'mc-cli\client')
    Assert ($LASTEXITCODE -eq 0) 'Ordinary Python payload write or import check failed'
    & $Helper -Action unprotect -Directory $root
    New-Item -ItemType Directory (Join-Path $root 'mc-cli\client\__pycache__') | Out-Null
    Set-Content -LiteralPath (Join-Path $root 'mc-cli\client\__pycache__\obsolete.pyc') -Value 'stale'
    Set-Content -LiteralPath (Join-Path $root 'runtime\old-license.txt') -Value 'stale'
    & $Helper -Action protect -Directory $root
    & $Helper -Action prepare -Directory $root
    Assert (-not (Test-Path -LiteralPath (Join-Path $root 'mc-cli'))) 'Repair left old CLI files'
    Assert (-not (Test-Path -LiteralPath (Join-Path $root 'runtime'))) 'Repair left old runtime files'
    Assert ((Get-Content -LiteralPath $state -Raw).Trim() -eq 'preserve') 'Repair changed user state'
    # Simulate an older uninstaller removing receipts but leaving obsolete files.
    Payload
    Remove-Item -LiteralPath (Join-Path $root 'mc-cli\client-runtime.json'),(Join-Path $root 'runtime\desktop-runtime.json')
    Refuses { & $Helper -Action prepare -Directory $root }
    Assert (Test-Path -LiteralPath (Join-Path $root 'mc-cli\client\fixture.py')) 'Refused cleanup removed a file'
    & $Helper -Action prepare -Directory $root -RegisteredDirectory $root
    Assert (-not (Test-Path -LiteralPath (Join-Path $root 'mc-cli'))) 'Registered repair left old files'
    Payload
    New-Item -ItemType Directory $outside | Out-Null
    Set-Content -LiteralPath (Join-Path $outside 'keep.txt') -Value 'preserve'
    New-Item -ItemType Junction -Path $junction -Target $outside | Out-Null
    Refuses { & $Helper -Action prepare -Directory $root }
    Assert (Test-Path -LiteralPath (Join-Path $root 'runtime\desktop-runtime.json')) 'Link refusal partially removed payload'
    Assert ((Get-Content -LiteralPath (Join-Path $outside 'keep.txt') -Raw).Trim() -eq 'preserve') 'Cleanup followed a junction'
    [IO.Directory]::Delete($junction)
    & $Helper -Action protect -Directory $root
    # Uninstall can delete protected resources without requiring write access.
    Remove-Item -LiteralPath (Join-Path $root 'mc-cli') -Recurse -Force
    Write-Output 'PASS Windows payload writes, direct Python, repair, ownership, junction refusal, and removal'
} finally {
    if (Test-Path -LiteralPath $junction) { [IO.Directory]::Delete($junction) }
    if (Test-Path -LiteralPath $root) { Remove-Item -LiteralPath $root -Recurse -Force }
    if (Test-Path -LiteralPath $outside) { Remove-Item -LiteralPath $outside -Recurse -Force }
}
