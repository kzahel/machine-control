$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$Python = Get-Command py -ErrorAction SilentlyContinue
if ($Python) {
    & $Python.Source -3 (Join-Path $RepoRoot "quest.py") @args
    exit $LASTEXITCODE
}
$Python = Get-Command python3 -ErrorAction SilentlyContinue
if (-not $Python) {
    $Python = Get-Command python -ErrorAction SilentlyContinue
}
if (-not $Python) {
    Write-Error "Python 3 was not found. Install Python 3.10 or later."
}
& $Python.Source (Join-Path $RepoRoot "quest.py") @args
exit $LASTEXITCODE
