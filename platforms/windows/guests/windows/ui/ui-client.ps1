[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$RequestBase64,
    [string]$PipeName = 'winvm-ui',
    [int]$ConnectTimeoutMilliseconds = 10000
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

try {
    $requestJson = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($RequestBase64))
    $pipe = New-Object System.IO.Pipes.NamedPipeClientStream(
        '.',
        $PipeName,
        [System.IO.Pipes.PipeDirection]::InOut,
        [System.IO.Pipes.PipeOptions]::Asynchronous
    )

    try {
        $pipe.Connect($ConnectTimeoutMilliseconds)
        $encoding = New-Object System.Text.UTF8Encoding($false)
        $reader = New-Object System.IO.StreamReader($pipe, $encoding, $false, 65536, $true)
        $writer = New-Object System.IO.StreamWriter($pipe, $encoding, 65536, $true)
        $writer.AutoFlush = $true

        try {
            $writer.WriteLine($requestJson)
            $responseJson = $reader.ReadLine()
            if ([string]::IsNullOrWhiteSpace($responseJson)) {
                throw 'UI relay closed the pipe without a response'
            }
            Write-Output $responseJson
            $response = $responseJson | ConvertFrom-Json
            if (-not $response.ok) {
                exit 1
            }
        } finally {
            $writer.Dispose()
            $reader.Dispose()
        }
    } finally {
        $pipe.Dispose()
    }
} catch {
    [ordered]@{
        ok = $false
        operation = 'client-error'
        exit_code = 1
        error = $_.Exception.Message
    } | ConvertTo-Json -Compress | Write-Output
    exit 1
}
