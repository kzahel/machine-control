# Architecture And Extension Points

## Boundaries

MacVM Testbed separates operations by what they depend on:

```text
bin/macvm
  +-- scripts/common.sh
  +-- providers/tart-macos/
  |     Tart lifecycle/IP, host window capture, host input
  +-- Tart guest agent
  |     optional command execution in the logged-in user session
  +-- authorized SSH
  |     alternate command transport to the same target-resident surface
  +-- guests/macos/ui/macui.swift
        resident facade, guest-native providers, optional Cua adapter
```

The host provider and guest driver are conceptually separate even though this
first repository implements one of each. A future UTM or Parallels provider
should preserve the guest UI contract; a future Linux guest should preserve
the lifecycle/control distinctions without claiming macOS Accessibility
semantics.

## Tart Host Provider

Tart owns VM creation, execution, IP discovery, suspend, and stop. Prepared
Cirrus images run `tart-guest-agent` as both a privileged launch daemon and an
interactive-user launch agent. `tart exec` uses the interactive agent, so
commands run as the desktop user rather than a root daemon.

The visible Tart window is the out-of-band control surface:

- CoreGraphics identifies the layer-0 Tart window named for the VM.
- `screencapture` captures that window without System Events scripting.
- the capture is cropped and resampled to the Tart guest display, excluding
  host window chrome and Retina scale;
- pointer positions map from those guest-display coordinates back into the
  Tart content view; and
- keyboard events are posted to the Tart process. `--capture-system-keys` is
  required when guest shortcuts overlap host shortcuts.

This path depends on host Screen Recording and input-posting consent, but it
does not depend on guest networking, guest Accessibility, or a healthy guest
agent.

## macOS Semantic Driver

`macui` uses AXUIElement directly. It can:

- enumerate running applications and windows;
- traverse a bounded accessibility tree;
- filter elements by text and role;
- list supported element actions;
- press, focus, and set values; and
- report bounds and state for visual correlation.

Every invocation gets new element references. Printed `@N` values are
diagnostic, not durable selectors. State-changing commands rediscover the
element from application, text, role, exactness, and occurrence arguments.

The same application hosts the ordinary-session resident facade. A per-user
Aqua LaunchAgent starts the stable signed `LSUIElement` process at login and
keeps it available after reboot or a crash. The process owns a mode-`0600` Unix
socket in the interactive user's Application Support directory. Doctor probes
that socket without bootstrapping the job. The guest-local
`~/bin/machine-control` client and host `macvm control` wrapper reach that same
socket and generation. The host wrapper may arrive through Tart's guest agent
or an explicitly configured authorized SSH transport; transport does not
change the resident route or contract. Resident references fail closed after
restart.

The native provider enumerates active display bounds in global macOS points,
captures the full display through Quartz in physical pixels, and posts pointer,
scroll, and keyboard events through CoreGraphics inside the guest session.
Retina scale is explicit in capture metadata. Resident artifacts are bounded
to a private cache root and the host wrapper will fetch only paths beneath that
root. These routes do not focus Tart or use the host pointer.

## Guest Command Transports

`MACVM_GUEST_TRANSPORT=tart` uses `tart exec` and guest-agent IP resolution.
`MACVM_GUEST_TRANSPORT=ssh` uses batch-mode SSH, an optional ignored identity
file, and either an ignored endpoint or Tart ARP/DHCP discovery. Both execute
as the configured interactive guest user and both call the same resident.

SSH is an alternate inner transport, not a desktop provider and not an outer
pixel/input fallback. Real endpoints, keys, known-host policy overrides, and
inventory remain in ignored local configuration. Tart still owns VM lifecycle
regardless of command transport.

Provider selection is per operation and disclosed in every result. Native AX,
Workspace, Quartz, and CGEvent routes are the platform baseline. If a
separately installed and consented Cua daemon is present, the facade can use
its session-scoped AX, exact-window capture, and background input. Cua remains
replaceable and is not bundled by this repository.

Normal Aqua administrator sheets use a separate credential boundary. The
resident first applies an exact allowlisted profile for SecurityAgent,
Installer, an inline System Settings sheet, or Gatekeeper's
LocalAuthentication sheet. The profile binds requester and prompt text, secure
field, buttons, process, and exact window before issuing a short-lived,
generation-bound, single-use lease. A guest-local helper reads one credential
without echo and streams it through a staged exchange on the same mode-`0600`
socket. The secret is never part of the JSON facade or a process argument,
environment variable, file, log, capture, or result. Target-local physical key
events are posted to the verified owner process; the calling workflow's
independent oracle remains authoritative for the privileged effect.

The helper is compiled and ad-hoc signed with an explicit stable designated
requirement as `MacVM UI.app`. The selected host command transport asks
LaunchServices to run a fresh helper command, then collects its output and
exit status from a private temporary directory. macOS therefore attributes
Accessibility responsibility to the stable app identity rather than the
transport's parent process. MacVM Testbed does not modify TCC databases and
does not claim control of loginwindow or higher-integrity UI through AX.

## Bootstrap Boundary

A prepared Cirrus base image begins above the guest-agent boundary. A vanilla
IPSW begins below it:

```text
vanilla VM
  -> Tart graphical window
  -> Setup Assistant and desktop login
  -> read-only repository share
  -> guest bootstrap script
  -> Tart guest launch daemon + launch agent
  -> tart exec
  -> deploy macui
  -> install and start the resident Aqua LaunchAgent
  -> explicit Accessibility grant
```

The outer control path must remain usable at every bootstrap and recovery
stage. See [bootstrap](bootstrap.md) for the operational contract.

## Lifecycle Semantics

- `shutdown` asks guest macOS to halt normally.
- `stop` asks Tart to terminate gracefully and uses Tart's bounded fallback.
- `suspend` works only when the VM was launched with `--suspendable`.
- `force-stop` sets Tart's graceful timeout to zero and requires explicit
  recovery intent.
- starting through `macvm up` enables suspendability and a read-only repository
  share by default. Guest system-key capture defaults off and acceptance mode
  suppresses it even if ignored local configuration requests it;
- `macvm up` runs Tart as a transient per-user launchd GUI job so ownership is
  independent of the invoking shell or agent process group; and
- normal shutdown and stop unload that transient job after Tart has completed
  the lifecycle transition. Suspend lets Tart exit naturally so its saved
  state is retained; the next `up` replaces the inactive launchd job.

An optional ignored mutation guard combines an expected provider name with a
`candidate` or `disposable` role. Deployment and control mutations then
refuse if selection drifts. Tart clones preserve guest hardware identity, so
the exact Tart name is the available host-side clone assertion.

The VM's disk and suspended state are not a session-ownership authority.
Restoring or cloning a VM that contains provider state must not make it an
eligible writer without a separate current ownership check.

Workspace policy builds on this guard. `persistent` reuses the explicitly
guarded development VM. `isolated` and `candidate` clone an explicitly proven
stopped base through Tart's APFS copy-on-write mechanism; isolated clones are
receipt-owned and deleted on release, while candidates remain retained. A
configuration may deliberately use the stopped development VM as its own base
to support a one-VM layout, but separate development and ready-base roles
remain the safer default.

An opaque workspace handle selects later commands by resolving a mode-`0600`
private receipt, changing the exact Tart name, and reapplying the mutation
guard. Derived work defaults to the Tart guest-agent transport so a clone does
not inherit a controller-specific SSH endpoint. Release refuses to delete the
configured development or base VM even if a receipt is malformed.
