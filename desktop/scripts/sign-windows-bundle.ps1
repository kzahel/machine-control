param([Parameter(Mandatory=$true)][string]$Path)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
try {
    $resolved = (Resolve-Path -LiteralPath $Path).Path
    $cliRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../src-tauri/native/mc-cli'))
    if ($resolved.StartsWith($cliRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
        # Tauri signs PE resources automatically. This immutable upstream runtime
        # instead uses the publisher-signed complete SHA-256 inventory: Windows
        # cannot Authenticode-sign every stripped DLL without changing its bytes.
        $catalog = Join-Path $cliRoot 'package.cat'
        $signature = Get-AuthenticodeSignature -LiteralPath $catalog
        if ($signature.Status -ne 'Valid' -or $null -eq $signature.TimeStamperCertificate -or
            $signature.SignerCertificate.GetNameInfo(
                [Security.Cryptography.X509Certificates.X509NameType]::SimpleName, $false) -cne $env:WINDOWS_SIGNER_NAME) {
            throw 'Python CLI inventory publisher/timestamp verification failed'
        }
        if ((Test-FileCatalog -Path (Join-Path $cliRoot 'files.json') -CatalogFilePath $catalog) -ne 'Valid') {
            throw 'Python CLI inventory catalog mismatch'
        }
        python (Join-Path $PSScriptRoot 'cli-payload.py') verify $cliRoot
        if ($LASTEXITCODE -ne 0) { throw 'Python CLI full-byte inventory mismatch before bundling' }
        Write-Output 'Preserved publisher-authenticated Python CLI resource'
        exit 0
    }
    & (Join-Path $PSScriptRoot 'sign-windows.ps1') -Path $resolved
} catch {
    # Tauri suppresses failed custom-command output. Keep only the exception
    # message for the workflow to surface; never write signing credentials.
    if ($env:RUNNER_TEMP) {
        $_.Exception.Message | Add-Content -LiteralPath (Join-Path $env:RUNNER_TEMP 'mc-signing-hook-error.txt')
    }
    throw
}
