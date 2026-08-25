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
`WINVM_GUEST_DRIVER`. A provider-native immutable identity pin and target role
are checked before mutation; a public name is only a selector. Provider
commands must implement:

- `status`, `capabilities`, `up`, and `ip`
- `down`, `suspend`, `shutdown`, and `force-stop`
- `seal`, `disposable-up`, and exact-confirmed `delete` when image lifecycle is
  available
- `screenshot`, `type`, `click`, `key`, and `scan` when available
- `stage-bootstrap` for the selected guest when an out-of-band file channel
  exists
- `target-id` and `assert-target OPERATION` when provider-native identity is
  available

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

Provider capture finds the layer-0 UTM window, records its logical geometry,
and requests a window-ID capture, including for another macOS Space. It fails
closed when macOS cannot capture that surface rather than reading an
overlapping host region. Capture removes the configured macOS title-bar height
and Retina backing scale. With UTM dynamic resolution, the remaining live
viewport is the guest coordinate space consumed by UTM mouse input. A
fixed-resolution guest may explicitly configure both output dimensions when
its display does not follow the console. Screenshot pixels can then be passed
directly to `winvm click` even after the dynamic console is resized.

The provider also exposes UTM's full stopped-VM clone as `seal` and its
non-persistent start mode as `disposable-up`. A seal requires a stopped source,
a distinct unregistered destination name, and remains a provider-owned VM
rather than a portable generalized Windows image. Deletion requires the exact
configured stopped VM name twice: once through configuration and once through
`--confirm`.

The workspace adapter composes those primitives without exposing them as the
portable intent. `persistent` reuses an explicitly proven, identity-pinned
development VM. `isolated` starts an explicitly proven stopped base through
UTM disposable mode and releases it only with a normal shutdown request; it
never deletes the base. `candidate` treats UTM clone cost as a full copy and
refuses it unless private policy and storage headroom explicitly allow it.

Every selection is backed by a mode-protected private receipt. Later commands
resolve `MACHINE_CONTROL_WORKSPACE_HANDLE` to the exact receipt identity and
then pass through the existing UUID/role assertion. Cleanup dry-run publishes
only opaque handles and normalized mechanism/state.

UTM's AppleScript VM UUID is that provider's identity. Every mutating
operation compares it to the ignored configured pin before applying the
source/candidate/seal role policy. SSH's proxy performs the same assertion, so
a missing override cannot silently fall back to the default stopped source and
start it merely because an alias was reused.

## Current libvirt/Linux Provider

The Linux provider uses system libvirt over QEMU/KVM and accepts only native
x86_64 `kvm` domains. Host doctor proves KVM access, Q35/OVMF, QEMU's KVM
accelerator, the selected network and dedicated storage pool, and required
capacity. Every start and workspace derivation revalidates the exact private
UUID, architecture, domain type, emulator, Q35 machine, and guest-agent
channel. Windows additionally requires enrolled-key Secure Boot and an
emulated TPM 2.0. There is no TCG or cross-architecture fallback.

Persistent intent reuses the proven stopped development domain. Isolated
intent creates a receipt-bound transient domain and QCOW2 backing overlay;
release verifies exact identities before removing both. Administration and
ordinary resident calls use guest networking. Typed QEMU guest-agent calls and
headless QMP display/input remain bootstrap or explicit recovery routes. The
outer-UI guard prohibits them during ordinary acceptance.

## Windows Guest Driver

The bootstrap installs and hardens Windows OpenSSH. The semantic UI layer uses
Microsoft WinApp CLI. Because OpenSSH runs in session 0, an interactive-logon
scheduled task starts `ui-relay.ps1` in the desktop session. `ui-client.ps1`
crosses the session boundary over a same-user named pipe.

The relay accepts JSON requests, launches GUI processes in its session, runs
WinApp commands, and returns output or base64 PNG captures. It is intentionally
non-elevated and cannot operate secure desktops or higher-integrity windows.

## Adding Host Providers

The accepted libvirt/Linux provider demonstrates reuse of the Windows guest
driver and resident protocol. Another provider needs a
`providers/NAME/provider.sh` with the command contract above.
Hypervisor-native screenshots and input are optional but should be implemented
where possible because they are the recovery path when guest administration
fails. Hyper-V/PowerShell Direct is the next Windows-host candidate; VMware
and other hypervisors remain unselected.

## Adding Guest Drivers

A macOS guest should live under `guests/macos/` and retain the same high-level
CLI where possible. Its command channel can use OpenSSH, but semantic UI
automation will need macOS Accessibility permission, TCC-aware deployment,
and a logged-in launch-agent bridge. AppleScript alone is unlikely to provide
the same coverage as Windows UI Automation.
