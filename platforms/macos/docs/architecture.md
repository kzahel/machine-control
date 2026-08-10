# Architecture And Extension Points

## Boundaries

MacVM Testbed separates operations by what they depend on:

```text
bin/macvm
  +-- scripts/common.sh
  +-- providers/tart-macos/
  |     Tart lifecycle/IP, host window capture, host input
  +-- Tart guest agent
  |     command execution in the logged-in user session
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

The same application hosts the ordinary-session resident facade. A
LaunchServices-started, `LSUIElement` process owns a mode-`0600` Unix socket in
the interactive user's Application Support directory. The guest-local
`~/bin/machine-control` client and host `macvm control` wrapper reach that same
socket and generation. Resident references fail closed after restart.

Provider selection is per operation and disclosed in every result. Native AX,
Workspace, Quartz, and CGEvent routes are the platform baseline. If a
separately installed and consented Cua daemon is present, the facade can use
its session-scoped AX, exact-window capture, and background input. Cua remains
replaceable and is not bundled by this repository.

Normal Aqua administrator sheets use a separate credential boundary. The
resident first fingerprints the active `SecurityAgent` requester, prompt,
secure field, buttons, process, and exact window, then issues a short-lived,
generation-bound, single-use lease. A guest-local helper reads one credential
without echo and streams it through a staged exchange on the same mode-`0600`
socket. The secret is never part of the JSON facade or a process argument,
environment variable, file, log, capture, or result. Target-local physical key
events submit it; the fixture or calling workflow remains the authority for
whether the intended privileged effect occurred.

The helper is compiled and ad-hoc signed with an explicit stable designated
requirement as `MacVM UI.app`. `tart exec` asks
LaunchServices to run a fresh helper command, then collects its output and exit
status from a private temporary directory. macOS therefore attributes
Accessibility responsibility to the stable app identity rather than the
guest-agent parent process. MacVM Testbed does not modify TCC databases and
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
  -> start resident facade in the Aqua session
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
- starting through `macvm up` enables suspendability, guest system-key
  capture, and a read-only repository share by default;
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
