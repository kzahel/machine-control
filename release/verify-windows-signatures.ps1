param([Parameter(Mandatory = $true)][string]$Directory,
      [Parameter(Mandatory = $true)][string]$ExpectedPublisher)
$ErrorActionPreference = 'Stop'
foreach ($file in Get-ChildItem -LiteralPath $Directory -Recurse -File |
        Where-Object { $_.Extension -in @('.exe', '.ps1', '.cat') }) {
    $signature = Get-AuthenticodeSignature -LiteralPath $file.FullName
    if ($signature.Status -ne 'Valid' -or $null -eq $signature.TimeStamperCertificate -or
        $signature.SignerCertificate.GetNameInfo(
            [Security.Cryptography.X509Certificates.X509NameType]::SimpleName, $false) -cne $ExpectedPublisher) {
        throw "Publisher/timestamp verification failed: $($file.Name)"
    }
}
