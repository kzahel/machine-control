param(
    [Parameter(Mandatory=$true)][string]$Installer,
    [Parameter(Mandatory=$true)][string]$Directory,
    [Parameter(Mandatory=$true)][string]$Target,
    [Parameter(Mandatory=$true)][string]$Version,
    [Parameter(Mandatory=$true)][string]$Revision,
    [Parameter(Mandatory=$true)][string]$ExpectedPublisher
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
function Signature([string]$Path) {
    $sig=Get-AuthenticodeSignature -LiteralPath $Path
    if ($sig.Status -ne 'Valid' -or $null -eq $sig.TimeStamperCertificate -or
        $sig.SignerCertificate.GetNameInfo([Security.Cryptography.X509Certificates.X509NameType]::SimpleName,$false) -cne $ExpectedPublisher) {
        throw "Publisher/timestamp verification failed: $([IO.Path]::GetFileName($Path))"
    }
}
Signature $Installer
$installRoot=Join-Path $env:TEMP ('mc-installer-verify-'+[Guid]::NewGuid().ToString('n'))
$installed=$false
try {
    $install=Start-Process -FilePath (Resolve-Path $Installer) -ArgumentList @('/S',('/D='+$installRoot)) -Wait -PassThru
    if ($install.ExitCode -ne 0) {throw "Installer failed: $($install.ExitCode)"}
    $installed=$true
    foreach ($name in @('machine-control.exe','runtime\machine-control-windows.exe','runtime\providers\cua\cua-driver.exe','uninstall.exe')) {
        Signature (Join-Path $installRoot $name)
    }
    $runtimeRoot=Join-Path $installRoot 'runtime'
    Signature (Join-Path $runtimeRoot 'package.cat')
    if ((Test-FileCatalog -Path $runtimeRoot -CatalogFilePath (Join-Path $runtimeRoot 'package.cat') -FilesToSkip 'package.cat') -ne 'Valid') {
        throw 'Installed runtime catalog mismatch'
    }
    $runtime=Get-Content (Join-Path $runtimeRoot 'desktop-runtime.json') -Raw | ConvertFrom-Json
    $expectedRuntime=if($Target -eq 'x86_64-pc-windows-msvc') {'win-x64'} elseif($Target -eq 'aarch64-pc-windows-msvc') {'win-arm64'} else {throw 'Unsupported target'}
    if ($runtime.schema -ne 'machine-control-desktop-runtime/v0' -or $runtime.sourceRevision -ne $Revision -or $runtime.runtime -ne $expectedRuntime) {
        throw 'Installed companion identity mismatch'
    }
    $provider=Join-Path $runtimeRoot 'providers\cua\cua-driver.exe'
    if ((Get-FileHash -LiteralPath $provider -Algorithm SHA256).Hash.ToLowerInvariant() -ne $runtime.providerDigest) {throw 'Installed provider digest mismatch'}
    $info=(Get-Item (Join-Path $installRoot 'machine-control.exe')).VersionInfo
    if ($info.ProductVersion -ne $Version) {throw 'Installed product version mismatch'}
    $cliRoot=Join-Path $installRoot 'mc-cli'
    Signature (Join-Path $cliRoot 'package.cat')
    if ((Test-FileCatalog -Path $cliRoot -CatalogFilePath (Join-Path $cliRoot 'package.cat') -FilesToSkip 'package.cat') -ne 'Valid') {
        throw 'Installed Python CLI catalog mismatch'
    }
    $cli=Get-Content (Join-Path $cliRoot 'client-runtime.json') -Raw | ConvertFrom-Json
    if ($cli.schema -ne 'machine-control-client-identity/v1' -or $cli.clientProtocol -ne 1 -or
        $cli.sourceRevision -ne $Revision -or $cli.version -ne $Version -or $cli.target -ne $Target) {
        throw 'Installed CLI identity mismatch'
    }
    # TEMP may use an 8.3 alias while enumeration expands the user's name.
    # Derive the root from the same canonical file representation.
    $payloadRoot=(Get-Item -LiteralPath (Join-Path $installRoot 'machine-control.exe')).DirectoryName
    $files=@(Get-ChildItem -LiteralPath $payloadRoot -Recurse -File | Sort-Object FullName | ForEach-Object {
        @{name=[IO.Path]::GetRelativePath($payloadRoot,$_.FullName).Replace('\','/'); size=$_.Length;
          sha256=(Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()}
    })
    @{schema='machine-control-desktop-payload/v0';sourceRevision=$Revision;target=$Target;version=$Version;files=$files} |
        ConvertTo-Json -Depth 6 | Set-Content (Join-Path $Directory 'payload.json') -Encoding utf8
    Write-Output 'Installed publisher signatures, runtime catalog, source, version, and provider digest verified'
} finally {
    if ($installed) {
        $uninstaller=Join-Path $installRoot 'uninstall.exe'
        if (Test-Path $uninstaller) { $remove=Start-Process -FilePath $uninstaller -ArgumentList '/S' -Wait -PassThru; if($remove.ExitCode -ne 0){throw 'Candidate uninstall failed'} }
    }
    if (Test-Path $installRoot) {Remove-Item -LiteralPath $installRoot -Recurse -Force}
}
