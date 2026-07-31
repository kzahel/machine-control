[CmdletBinding()]
param(
    [string]$PipeName = 'winvm-ui',
    [string]$WinAppPath = "$env:LOCALAPPDATA\Microsoft\WindowsApps\winapp.exe",
    [string]$StateDirectory = "$env:LOCALAPPDATA\winvm-testbed"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

New-Item -ItemType Directory -Force -Path $StateDirectory | Out-Null
$captureDirectory = Join-Path $StateDirectory 'captures'
New-Item -ItemType Directory -Force -Path $captureDirectory | Out-Null
$logPath = Join-Path $StateDirectory 'relay.log'
$statePath = Join-Path $StateDirectory 'relay-state.json'
$script:stopRequested = $false
$env:WINAPP_CLI_TELEMETRY_OPTOUT = '1'

function Write-RelayLog {
    param([string]$Message)

    Add-Content -LiteralPath $logPath -Encoding utf8 -Value "$(Get-Date -Format o) $Message"
}

function ConvertTo-WindowsArgument {
    param([AllowEmptyString()][string]$Argument)

    if ($Argument.Length -gt 0 -and $Argument -notmatch '[\s"]') {
        return $Argument
    }

    $builder = New-Object System.Text.StringBuilder
    [void]$builder.Append('"')
    $backslashes = 0

    foreach ($character in $Argument.ToCharArray()) {
        if ($character -eq '\') {
            $backslashes++
            continue
        }

        if ($character -eq '"') {
            [void]$builder.Append(('\' * (($backslashes * 2) + 1)))
            [void]$builder.Append('"')
            $backslashes = 0
            continue
        }

        if ($backslashes -gt 0) {
            [void]$builder.Append(('\' * $backslashes))
            $backslashes = 0
        }
        [void]$builder.Append($character)
    }

    if ($backslashes -gt 0) {
        [void]$builder.Append(('\' * ($backslashes * 2)))
    }
    [void]$builder.Append('"')
    return $builder.ToString()
}

function Join-WindowsArguments {
    param([string[]]$Arguments)

    return (($Arguments | ForEach-Object { ConvertTo-WindowsArgument $_ }) -join ' ')
}

function Invoke-WinAppProcess {
    param(
        [string[]]$Arguments,
        [int]$TimeoutMilliseconds = 120000
    )

    $TimeoutMilliseconds = [Math]::Max(1000, [Math]::Min(600000, $TimeoutMilliseconds))

    $startInfo = New-Object System.Diagnostics.ProcessStartInfo
    $startInfo.FileName = $WinAppPath
    $startInfo.Arguments = Join-WindowsArguments $Arguments
    $startInfo.WorkingDirectory = $StateDirectory
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $true
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true

    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $startInfo
    if (-not $process.Start()) {
        throw 'Failed to start winapp'
    }

    $stdoutTask = $process.StandardOutput.ReadToEndAsync()
    $stderrTask = $process.StandardError.ReadToEndAsync()
    if (-not $process.WaitForExit($TimeoutMilliseconds)) {
        try {
            $process.Kill()
        } catch {
            Write-RelayLog "Failed to kill timed-out winapp process: $($_.Exception.Message)"
        }
        throw "winapp timed out after $TimeoutMilliseconds ms"
    }

    $process.WaitForExit()
    return [ordered]@{
        exit_code = $process.ExitCode
        stdout = $stdoutTask.Result.TrimEnd()
        stderr = $stderrTask.Result.TrimEnd()
    }
}

function New-RelayPipe {
    $pipeSecurity = New-Object System.IO.Pipes.PipeSecurity
    $pipeSecurity.SetAccessRuleProtection($true, $false)
    $currentSid = [Security.Principal.WindowsIdentity]::GetCurrent().User
    $systemSid = New-Object Security.Principal.SecurityIdentifier('S-1-5-18')

    foreach ($sid in @($currentSid, $systemSid)) {
        $rule = New-Object System.IO.Pipes.PipeAccessRule(
            $sid,
            [System.IO.Pipes.PipeAccessRights]::FullControl,
            [Security.AccessControl.AccessControlType]::Allow
        )
        $pipeSecurity.AddAccessRule($rule)
    }

    return New-Object System.IO.Pipes.NamedPipeServerStream(
        $PipeName,
        [System.IO.Pipes.PipeDirection]::InOut,
        1,
        [System.IO.Pipes.PipeTransmissionMode]::Byte,
        [System.IO.Pipes.PipeOptions]::Asynchronous,
        65536,
        65536,
        $pipeSecurity
    )
}

function Get-RequestArguments {
    param($Request)

    $property = $Request.PSObject.Properties['arguments']
    if (-not $property -or $null -eq $property.Value) {
        return @()
    }
    return @($property.Value | ForEach-Object { [string]$_ })
}

function Get-RequestTimeout {
    param($Request)

    $property = $Request.PSObject.Properties['timeout_ms']
    if (-not $property -or $null -eq $property.Value) {
        return 120000
    }
    return [int]$property.Value
}

function Invoke-RelayRequest {
    param($Request)

    $operation = [string]$Request.op
    switch ($operation) {
        'health' {
            $explorerSessions = @(Get-Process explorer -ErrorAction SilentlyContinue |
                Select-Object -ExpandProperty SessionId -Unique)
            return [ordered]@{
                ok = $true
                operation = 'health'
                relay_pid = $PID
                relay_session = (Get-Process -Id $PID).SessionId
                user = [Security.Principal.WindowsIdentity]::GetCurrent().Name
                explorer_sessions = $explorerSessions
                winapp_path = $WinAppPath
                started_at = $script:startedAt
            }
        }
        'winapp' {
            $result = Invoke-WinAppProcess `
                -Arguments (Get-RequestArguments $Request) `
                -TimeoutMilliseconds (Get-RequestTimeout $Request)
            return [ordered]@{
                ok = ($result.exit_code -eq 0)
                operation = 'winapp'
                exit_code = $result.exit_code
                stdout = $result.stdout
                stderr = $result.stderr
            }
        }
        'capture' {
            $capturePath = Join-Path $captureDirectory "capture-$([guid]::NewGuid().ToString('N')).png"
            try {
                $arguments = @('ui', 'screenshot') + (Get-RequestArguments $Request) + @('--output', $capturePath, '--json')
                $result = Invoke-WinAppProcess `
                    -Arguments $arguments `
                    -TimeoutMilliseconds (Get-RequestTimeout $Request)
                if ($result.exit_code -ne 0) {
                    return [ordered]@{
                        ok = $false
                        operation = 'capture'
                        exit_code = $result.exit_code
                        stdout = $result.stdout
                        stderr = $result.stderr
                    }
                }
                if (-not (Test-Path -LiteralPath $capturePath)) {
                    throw "winapp reported success without creating $capturePath"
                }
                return [ordered]@{
                    ok = $true
                    operation = 'capture'
                    exit_code = 0
                    stdout = $result.stdout
                    stderr = $result.stderr
                    content_type = 'image/png'
                    data_base64 = [Convert]::ToBase64String([IO.File]::ReadAllBytes($capturePath))
                }
            } finally {
                Remove-Item -LiteralPath $capturePath -Force -ErrorAction SilentlyContinue
            }
        }
        'launch' {
            $arguments = @(Get-RequestArguments $Request)
            if ($arguments.Count -lt 1) {
                throw 'launch requires an executable as its first argument'
            }

            $startInfo = New-Object System.Diagnostics.ProcessStartInfo
            $startInfo.FileName = $arguments[0]
            $startInfo.Arguments = Join-WindowsArguments @($arguments | Select-Object -Skip 1)
            $startInfo.WorkingDirectory = $StateDirectory
            $startInfo.UseShellExecute = $true
            $process = [System.Diagnostics.Process]::Start($startInfo)
            return [ordered]@{
                ok = $true
                operation = 'launch'
                pid = $process.Id
                file = $arguments[0]
            }
        }
        'shutdown' {
            $script:stopRequested = $true
            return [ordered]@{
                ok = $true
                operation = 'shutdown'
            }
        }
        default {
            throw "Unknown relay operation: $operation"
        }
    }
}

if (-not (Test-Path -LiteralPath $WinAppPath)) {
    throw "winapp executable not found at $WinAppPath"
}

$relaySession = (Get-Process -Id $PID).SessionId
if ($relaySession -eq 0) {
    throw 'The UI relay must run in an interactive Windows session, not session 0'
}

$script:startedAt = (Get-Date).ToString('o')
[ordered]@{
    pid = $PID
    session_id = $relaySession
    user = [Security.Principal.WindowsIdentity]::GetCurrent().Name
    pipe_name = $PipeName
    winapp_path = $WinAppPath
    started_at = $script:startedAt
} | ConvertTo-Json | Set-Content -LiteralPath $statePath -Encoding utf8

Write-RelayLog "Relay started: pid=$PID session=$relaySession pipe=$PipeName"

try {
    while (-not $script:stopRequested) {
        $pipe = $null
        $reader = $null
        $writer = $null
        try {
            $pipe = New-RelayPipe
            $pipe.WaitForConnection()
            $encoding = New-Object System.Text.UTF8Encoding($false)
            $reader = New-Object System.IO.StreamReader($pipe, $encoding, $false, 65536, $true)
            $writer = New-Object System.IO.StreamWriter($pipe, $encoding, 65536, $true)
            $writer.AutoFlush = $true

            $requestLine = $reader.ReadLine()
            if ([string]::IsNullOrWhiteSpace($requestLine)) {
                throw 'Empty relay request'
            }

            try {
                $request = $requestLine | ConvertFrom-Json
                $response = Invoke-RelayRequest $request
            } catch {
                Write-RelayLog "Request failed: $($_.Exception.Message)"
                $response = [ordered]@{
                    ok = $false
                    operation = 'error'
                    exit_code = 1
                    error = $_.Exception.Message
                }
            }

            $writer.WriteLine(($response | ConvertTo-Json -Depth 20 -Compress))
        } catch {
            Write-RelayLog "Pipe failure: $($_.Exception.Message)"
        } finally {
            if ($writer) { $writer.Dispose() }
            if ($reader) { $reader.Dispose() }
            if ($pipe) { $pipe.Dispose() }
        }
    }
} finally {
    Remove-Item -LiteralPath $statePath -Force -ErrorAction SilentlyContinue
    Write-RelayLog 'Relay stopped'
}
