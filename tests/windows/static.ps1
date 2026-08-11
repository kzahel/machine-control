[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$Repository = Resolve-Path (Join-Path $PSScriptRoot '..\..')
$parseFailures = [System.Collections.Generic.List[string]]::new()
Get-ChildItem -LiteralPath $Repository -Recurse -File -Filter '*.ps1' |
    Where-Object {
        $_.FullName -notmatch '[\\/](obj|node_modules|\.git)[\\/]'
    } |
    ForEach-Object {
        $tokens = $null
        $errors = $null
        [void][System.Management.Automation.Language.Parser]::ParseFile(
            $_.FullName,
            [ref]$tokens,
            [ref]$errors)
        foreach ($parseError in $errors) {
            $parseFailures.Add("$($_.FullName): $($parseError.Message)")
        }
    }
if ($parseFailures.Count -gt 0) {
    throw ($parseFailures -join [Environment]::NewLine)
}

$projects = @(
    'src\MachineControl.Windows\MachineControl.Windows.csproj',
    'src\MachineControl.Fixture\MachineControl.Fixture.csproj',
    'src\MachineControl.ElevatedFixture\MachineControl.ElevatedFixture.csproj'
)
foreach ($project in $projects) {
    & dotnet build (Join-Path $Repository $project) `
        --configuration Release --nologo
    if ($LASTEXITCODE -ne 0) {
        throw "dotnet build failed for $project"
    }
}

Write-Output 'Windows native static and build checks passed'
