param([Parameter(Mandatory = $true)][string]$EvidencePath)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms
$form = New-Object Windows.Forms.Form
$form.Text = 'Machine Control Reference Fixture'
$form.Width = 500
$form.Height = 260
$script:state = @{ first = 0; second = 0; left = ''; right = '' }
function Save-State { $script:state | ConvertTo-Json | Set-Content $EvidencePath }
$first = New-Object Windows.Forms.Button
$first.Text = 'Start'
$first.SetBounds(20, 20, 180, 40)
$first.Add_Click({ $script:state.first++; Save-State })
$second = New-Object Windows.Forms.Button
$second.Text = 'Start'
$second.SetBounds(240, 20, 180, 40)
$second.Add_Click({ $script:state.second++; Save-State; $second.Dispose() })
$left = New-Object Windows.Forms.TextBox
$left.AccessibleName = 'Shared entry'
$left.SetBounds(20, 100, 180, 30)
$left.Add_TextChanged({ $script:state.left = $left.Text; Save-State })
$right = New-Object Windows.Forms.TextBox
$right.AccessibleName = 'Shared entry'
$right.SetBounds(240, 100, 180, 30)
$right.Add_TextChanged({ $script:state.right = $right.Text; Save-State })
$form.Controls.AddRange(@($first, $second, $left, $right))
Save-State
[Windows.Forms.Application]::Run($form)
