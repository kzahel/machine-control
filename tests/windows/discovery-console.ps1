# Run in an owned real console, through the appliance's interactive runner.
param(
 [Parameter(Mandatory=$true)][string]$Install,
 [Parameter(Mandatory=$true)][string]$EvidencePath
)
$ErrorActionPreference='Stop'
$result=[ordered]@{passed=$false}
try {
 [Console]::Clear()
 [Console]::WriteLine('MC console oracle')
 $child=Start-Process (Join-Path $Install 'machine-control.exe') -ArgumentList '--help' -NoNewWindow -PassThru -Wait
 if($child.ExitCode -ne 0){throw 'Console help failed'}
 $size=$Host.UI.RawUI.BufferSize
 $area=[Management.Automation.Host.Rectangle]::new(0,0,$size.Width-1,[Math]::Min(100,$size.Height-1))
 $text=-join ($Host.UI.RawUI.GetBufferContents($area)|ForEach-Object {$_.Character})
 if(-not $text.Contains('MC console oracle')){throw 'Test runner inherited redirected handles; no real console output was observed'}
 if(-not $text.Contains('Usage: machine-control')){throw 'Help did not reach the calling console buffer'}
 $result.passed=$true
} catch {$result.error=$_.Exception.ToString();throw}
finally {$result|ConvertTo-Json|Set-Content $EvidencePath -Encoding UTF8}
