# Tactical 008: macOS Ordinary-Session Resident Control

Status: complete.

Topics: `macos-resident-control`, `architecture`, and
`capabilities-and-results`.

Research:
[`macOS platform report`](../../research/platforms/macos.md).

Authoritative testbed:
[`platforms/macos`](../../platforms/macos/README.md).

## Objective

Bring a prepared Tart macOS appliance to ordinary-session parity with the
useful Windows resident-control shape without rebuilding the OS or making
Tart-window input routine. Install an owned facade over target-native macOS
providers, expose the same operation/result experience locally and through
`tart exec`, exercise real applications and system surfaces, and retain a
stopped copy-on-write appliance only after acceptance and cleanup.

This tactical does not assume Cua is the winner. Begin with the existing
consented native AX helper, compare Cua on identical cases where its prior
evidence predicts value, and compose or reject it operation by operation.

## Completion conditions

- The prepared source remains protected and a distinctly selected
  copy-on-write candidate is used for every mutation.
- Available disk space is checked before clone/build/deployment and monitored
  during the slice; low-space failure stops safely rather than deleting
  another appliance implicitly.
- A stable target-resident facade runs in the logged-in Aqua session and
  reports session, generation, provider inventory, route, delivery, effect,
  uncertainty, focus/cursor consequences, and bounded failures.
- Local guest callers and authenticated `tart exec` callers use the same
  operation vocabulary and produce equivalent independent effects.
- Application/window inventory, AX snapshots/actions, exact capture, native
  launch, guest-local keyboard/input, and window lifecycle work without
  focusing Tart or moving/typing through the host desktop.
- Finder, Dock, menu bar or Control Center, System Settings, TextEdit, and
  Safari receive representative semantic, visual, input, and cleanup coverage.
- Discovery and action share stable selection behavior; changing UI or helper
  generation invalidates stale references honestly.
- Cua and the native route are compared only on identical fixture/system cells.
  Any adopted operation names the measured advantage; otherwise Cua remains
  optional evidence rather than an installed dependency.
- TCC status is reported honestly. Any required consent is performed through
  normal macOS UI, with no password in commands or evidence and no TCC database
  modification.
- Generated applications, documents, captures, sockets, logs, and temporary
  deployment files are removed. The accepted candidate is stopped, the source
  is unchanged, and all repositories are clean.

## Boundaries

- Use the prepared Tart base and its existing guest agent. A vanilla IPSW and
  Setup Assistant are not required for this slice.
- Do not use outer Tart input after ordinary resident readiness except for an
  explicitly declared consent or recovery step.
- Do not silently preserve a host-input fallback in ordinary worker tools.
- Do not weaken TCC, SIP, secure input, or code-signing checks.
- Do not put VM names, account names, paths, credentials, screenshots, machine
  identifiers, or TCC state in this public repository.
- Do not claim loginwindow, FileVault, authorization-sheet, or unrestricted
  root control. Record them for the later protected-plane tactical.
- Do not copy the Windows service implementation where macOS launchd, TCC, AX,
  capture, or application semantics require a different component boundary.

## Implementation steps

### 1 — protect the source and establish a candidate

Inspect the suspended prepared source, verify guest-agent and existing AX
readiness, stop it cleanly, clone it under ignored private selection, and prove
that all subsequent mutation targets only the candidate. Record allocated disk
growth without committing private identity.

### 2 — define and package the macOS facade

Reuse the exercised `machine-control/v0` result shape. Implement a macOS
resident/session boundary with capabilities, status, application/window
inventory, snapshot, action, capture, input, lifecycle, generation, and bounded
artifact behavior. Package it under one stable application identity suitable
for normal TCC consent and launchd supervision.

### 3 — adapt the existing native provider

Make macvm-testbed's AX/application primitives callable behind the facade.
Unify tree and action selection, return compact machine-readable elements and
generation-scoped references, preserve values as well as labels, and verify
effects rather than treating AX acknowledgement as success.

### 4 — eliminate routine outer input

Add guest-native keyboard and pointer delivery with disclosed focus/cursor
consequences. Prove shortcuts and text against a deterministic fixture and
real applications. Ordinary failures must remain target-local or return a
typed refusal; they must not foreground Tart.

### 5 — compare optional common and deep providers

Run identical exact-window semantic/action/capture cells through the native
route and Cua where packaging and existing consent permit. Consult Peekaboo
patterns for identity, system surfaces, and capture gaps. Adopt only measured
operation-level advantages.

### 6 — exercise real macOS surfaces

Run a sustained workflow across Finder, Dock, menu bar or Control Center,
System Settings, TextEdit, and Safari. Confirm launch, window selection,
semantic state/action, capture, input, lifecycle, application/file effects,
preservation of pre-existing state, and cleanup from remote and target-local
placements.

### 7 — prove lifecycle, recovery, and cleanup

Restart the resident helper, reject stale references, re-establish readiness,
and verify a bounded application effect. Stop the candidate normally, restart
it without outer input, rerun a small resident smoke, remove owned artifacts,
and leave the accepted candidate stopped. Update the topic, platform corpus,
root entry point, testbed runbook, and this record with measured results and
remaining protected boundaries.

## Validation record

Completed on the guarded copy-on-write candidate.

- The prepared source remained suspended and unchanged throughout the slice.
  More than 200 GiB of host free space remained after the initial redundant
  appliance cleanup; no implicit pruning or second appliance deletion was
  needed.
- The resident facade was deployed under a stable application identifier and
  a user-owned `0600` Unix socket. Guest-local and `tart exec` calls reached
  the same generation and returned the same `machine-control/v0` envelope.
- Native Accessibility and Screen Recording were granted through normal macOS
  Privacy & Security UI. A stale pre-existing Accessibility identity had to be
  removed and requested again after the signing requirement changed. Rebuild
  and full reboot then retained both grants. No password entered a command,
  artifact, or repository, and no TCC database was modified.
- Native and Cua adapters now normalize application, window, semantic element,
  and capture data before returning it. Compact native queries filter rather
  than returning the full application tree.
- Identical native and Cua fixture cells passed for compact snapshot, semantic
  press, independently observed file effect, and exact-window capture. Native
  AX was deeper for Dock and Control Center; Cua returned typed, no-fallback
  refusals for unsupported system-surface cells.
- Native CoreGraphics text events reached the focused fixture and incremented
  its independent key-event oracle but did not change the AppKit text value.
  Cua did change the value, so default `input.text` uses Cua when ready. Native
  key input, AX, Workspace, Quartz capture, Dock, and Control Center remain the
  default routes. Explicit provider requests never fall back.
- Remote and target-local conformance passed separately, including launch,
  keyboard input, text insertion, checkbox/button/text-field semantics,
  exact-window capture, resident restart, and stale-reference refusal.
- The real-application workflow passed across Finder, System Settings,
  TextEdit, Safari, and an application menu bar while preserving pre-existing
  processes and cleaning owned windows and applications. The provider corpus
  additionally opened, inspected, captured, and closed Control Center through
  native semantics and exercised the Dock.
- A normal guest shutdown followed by `macvm up` restored the logged-in Aqua
  session without outer input. Native semantics, native capture, and Cua all
  returned ready; a bounded Finder launch/snapshot/close effect passed.
- The fixture application, file oracle, capture artifacts, caches, sockets at
  shutdown, and old one-shot command scratch directories were removed. The
  accepted candidate is stopped and the prepared source is still suspended.

Remaining work is intentionally outside this ordinary-session tactical:
protected authorization, lock/loginwindow, FileVault/preboot, multi-display
and Spaces coverage, localization, and longer soak testing.
