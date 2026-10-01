param([Parameter(Mandatory=$true)][string]$Path)
$ErrorActionPreference = 'Stop'
foreach ($name in @('AZURE_SIGNING_ENDPOINT','AZURE_SIGNING_ACCOUNT','AZURE_CERTIFICATE_PROFILE',
                    'AZURE_CLIENT_ID','AZURE_CLIENT_SECRET','AZURE_TENANT_ID')) {
    if ([string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable($name))) {
        throw "Missing signing configuration: $name"
    }
}
& artifact-signing-cli --endpoint $env:AZURE_SIGNING_ENDPOINT --account $env:AZURE_SIGNING_ACCOUNT `
    --certificate $env:AZURE_CERTIFICATE_PROFILE $Path
if ($LASTEXITCODE -ne 0) { throw "Native signing failed: $([IO.Path]::GetFileName($Path))" }
