# Architecture and Extension Points

## Boundaries

WinVM Testbed separates operations by what they depend on:

```text
bin/winvm
  +-- scripts/common.sh             configuration and transport helpers
  +-- providers/<host-provider>/    VM lifecycle, IP, capture, raw input
  +-- guests/<guest-driver>/        guest bootstrap and semantic relay
  +-- bin/winui                     Windows session relay protocol
```

The CLI reads ignored `config.local`, then selects `WINVM_PROVIDER` and
`WINVM_GUEST_DRIVER`. Provider commands must implement:

- `status`, `capabilities`, `up`, and `ip`
- `down`, `suspend`, `shutdown`, and `force-stop`
- `screenshot`, `type`, `click`, `key`, and `scan` when available
- `stage-bootstrap` for the selected guest when an out-of-band file channel
  exists

Guest drivers own SSH bootstrap, guest-side deployment, semantic automation,
and session-boundary behavior.

## Current UTM/macOS Provider

The provider uses UTM's bundled `utmctl` for lifecycle, QEMU guest-agent IP
discovery, and file transfer. UTM's AppleScript dictionary supplies text, raw
PC/AT scan-code, and absolute mouse input. CoreGraphics locates the live UTM
window and `screencapture` captures it without System Events UI scripting.

UTM guest-agent process execution was unreliable on the original test VM, so
it is not trusted as a command channel. The design uses guest-agent transfer
only for bootstrap and SSH afterward.

Provider capture finds the visible layer-0 UTM window, records its logical
geometry, captures its Retina backing pixels, removes the macOS title bar, and
normalizes the guest viewport to `WINVM_DISPLAY_WIDTH` ×
`WINVM_DISPLAY_HEIGHT`. UTM mouse input consumes that same guest coordinate
space. Keep the configured dimensions aligned with the Windows logical display
mode; screenshot pixels can then be passed directly to `winvm click`.

## Windows Guest Driver

The bootstrap installs and hardens Windows OpenSSH. The semantic UI layer uses
Microsoft WinApp CLI. Because OpenSSH runs in session 0, an interactive-logon
scheduled task starts `ui-relay.ps1` in the desktop session. `ui-client.ps1`
crosses the session boundary over a same-user named pipe.

The relay accepts JSON requests, launches GUI processes in its session, runs
WinApp commands, and returns output or base64 PNG captures. It is intentionally
non-elevated and cannot operate secure desktops or higher-integrity windows.

## Adding Host Providers

Linux and Windows hosts can reuse the Windows guest driver and SSH/UI protocol.
A new provider needs a `providers/NAME/provider.sh` with the command contract
above. Hypervisor-native screenshots and input are optional but should be
implemented where possible because they are the recovery path when SSH fails.

Examples include libvirt/QEMU on Linux, UTM on a future non-macOS host, VMware,
Parallels, or Hyper-V/PowerShell Direct.

## Adding Guest Drivers

A macOS guest should live under `guests/macos/` and retain the same high-level
CLI where possible. Its command channel can use OpenSSH, but semantic UI
automation will need macOS Accessibility permission, TCC-aware deployment,
and a logged-in launch-agent bridge. AppleScript alone is unlikely to provide
the same coverage as Windows UI Automation.
