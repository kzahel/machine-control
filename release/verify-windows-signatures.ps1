param([Parameter(Mandatory = $true)][string]$Directory,
      [Parameter(Mandatory = $true)][string]$ExpectedPublisher)
$ErrorActionPreference = 'Stop'
$policy=Join-Path ([IO.Path]::GetFullPath($Directory)) 'shared-policy'
if(Test-Path $policy){
    python (Join-Path $PSScriptRoot '../runtime/scripts/verify.py') $policy
    if($LASTEXITCODE -ne 0){throw 'Bundled policy full-byte verification failed'}
}
foreach ($file in Get-ChildItem -LiteralPath $Directory -Recurse -File |
        Where-Object { $_.Extension -in @('.exe', '.ps1', '.cat') }) {
    # Preserve the pinned upstream Node bytes; the signed runtime catalog
    # authenticates its complete payload.json inventory.
    if($file.FullName -eq (Join-Path $policy 'node.exe')){continue}
    $signature = Get-AuthenticodeSignature -LiteralPath $file.FullName
    if ($signature.Status -ne 'Valid' -or $null -eq $signature.TimeStamperCertificate -or
        $signature.SignerCertificate.GetNameInfo(
            [Security.Cryptography.X509Certificates.X509NameType]::SimpleName, $false) -cne $ExpectedPublisher) {
        throw "Publisher/timestamp verification failed: $($file.Name)"
    }
}
