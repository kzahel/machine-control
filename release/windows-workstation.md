# Windows workstation preview

This package hosts ordinary desktop control in the logged-in console user's
session. It needs no source checkout, .NET SDK, privileged service, or global
Cua installation. It has no Tauri dependency or network listener. Elevated
applications, UAC, lock/login, RDP, and other user sessions are outside this
profile. The separate appliance deployment retains its protected capabilities.

Authenticate the downloaded archive with Machine Control's pinned package key
before extraction. A package.json hash inventory detects damage; it is not a
trust anchor. The lifecycle script additionally checks publisher signatures by
default, including a signed Windows catalog covering the complete payload and
its hash inventory. Supply the expected publisher from trusted consumer configuration.
For a locally built development package only, use `-AllowUnsigned` instead.

Run Windows PowerShell in the ordinary interactive user session:

```powershell
.\workstation.ps1 -Action Install -Instance default -ExpectedPublisher '<trusted publisher>'
.\workstation.ps1 -Action Start -Instance default -ExpectedPublisher '<trusted publisher>'
.\workstation.ps1 -Action Status -Instance default
.\workstation.ps1 -Action Stop -Instance default
```

Install a new package while stopped using its copy of workstation.ps1. Start it
and verify readiness and application effects. On failure, stop it, run
`-Action Rollback` with the same publisher expectation, and start the previous
package. `-Action Uninstall` requires stopped runtimes and removes that
instance's versions and artifacts. It retains an empty management directory and
lock file for concurrent-installer serialization. No login task or service is
registered: the consuming application supervises the process.

A consumer can instead supervise `machine-control-windows.exe user --instance
NAME` directly from a verified version directory. Send JSON through stdin to
`machine-control-windows.exe call --profile user --instance NAME`. From SSH,
pass `--session-id ID` for the actual interactive console session; the SSH user
must match the runtime's OS user. No in-guest agent is required. Without an
explicit `--profile user`, `call` retains the appliance service endpoint.

The protocol is machine-control/v0. `status` reports instance, profile, process,
runtime generation and desktop readiness. `capabilities` reports omissions and
provider availability. Supply expectedGeneration on actions and runtime.stop;
stale generations are refused. A successful input delivery still requires an
independent application effect assertion. Other same-user processes with shell
access are outside the containment boundary.

Provider binaries are bundle-relative. Writable captures are under the current
user's LocalApplicationData/MachineControl/workstation/INSTANCE/session-ID.
Appliance ProgramData storage is unchanged. Two instances have separate pipes,
state and provider processes, but still share the user's physical desktop;
callers must coordinate conflicting input.

## Optional unattended unlock

The preview also contains `unlock-setup.exe`, a separate elevated installation
entry. Ordinary installation does not install or arm it. See [unlock.md](unlock.md)
for account/controller approval, the dedicated credential transport, revocation,
and the current local-account limitations. This component is pending native
acceptance in the initial implementation revision.
