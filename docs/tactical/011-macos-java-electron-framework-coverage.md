# Tactical 011: macOS Java and Electron Framework Coverage

Status: complete.

Topics: `macos-resident-control` and `capabilities-and-results`.

Research:
[`macOS platform report`](../../research/platforms/macos.md).

Authoritative testbed:
[`macvm-testbed`](../../../macvm-testbed/README.md).

## Objective

Close the prepared Tart appliance's Java and Electron omissions without
weakening the accepted inner-only control posture. Install reproducible ARM64
build runtimes, package deterministic Swing and Electron applications, and
prove compact semantic actions, independent effects, exact-window capture,
guest-local/remote parity, reboot persistence, cleanup, and zero host-desktop
interference.

## Completion conditions

- Runtime sources are immutable official ARM64 archives with checked-in exact
  versions and SHA-256 values. Installation is user-local, guarded, repeatable,
  and does not require Homebrew or a host-side installer UI.
- Runtime status distinguishes recorded metadata from runnable Node, Temurin,
  and Electron binaries.
- Stable Java Swing and Electron app bundles expose labelled semantic controls
  and write independent JSON effect oracles.
- Both caller placements observe and press controls in AppKit, SwiftUI, Swing,
  and Electron fixtures. Each framework supplies an exact-window artifact and
  reports its actual route, observation size, latency, and host-interference
  posture.
- Outer Tart capture/input is fail-closed throughout acceptance. A read-only
  host oracle remains unchanged.
- A full guest restart retains the runtimes and reproduces the four-framework
  result. Corpus fixtures, oracles, build inputs, and captures are then removed
  while reusable runtimes remain installed.
- Testbed smoke tests and relevant machine-control static checks pass, and the
  accepted candidate is stopped normally.

## Boundaries

- This slice covers Java Swing and Electron because those were concrete image
  omissions in Tactical 010. It is not an open-ended framework survey.
- Runtime installation is scoped to the dedicated prepared test appliance. It
  does not claim a portable system package policy for personal Macs.
- The fixture applications are correctness probes, not production app
  templates. Their file oracles, not action acknowledgements, establish effect.
- SIP-disabled protected-data enforcement and absent virtual camera/microphone
  hardware remain separate appliance limitations.

## Implementation steps

### 1 — pin and install the framework runtimes

Record exact Node LTS, Eclipse Temurin LTS, and Electron ARM64 archives and
upstream SHA-256 values. Add a guarded installer and a status report that runs
the installed binaries.

### 2 — package deterministic Swing and Electron fixtures

Build Swing with the pinned JDK's `javac`, `jar`, and `jpackage`. Embed a
minimal context-isolated application in the pinned Electron distribution.
Give each a stable bundle identifier, native semantic controls, and an atomic
file oracle.

### 3 — extend the common framework corpus

Replace omission detection with a required runtime-health check. Exercise
compact semantic observation and action through both placements for all four
frameworks, independently verify effects, capture each exact window, and
record useful efficiency evidence.

### 4 — prove reboot retention and clean owned state

Run the corpus before and after a normal guest restart with outer UI forbidden.
Remove all four fixture applications and their state, verify the reusable
runtimes remain healthy, run repository validation, and stop the candidate
normally.

### 5 — publish the closed omission

Update the macOS topic, platform report, testbed runbook, corpus entry point,
and Tactical 010's historical omission note. Record the exact accepted matrix
and any remaining limitation here.

## Validation record

Completed on the guarded prepared Tart candidate with outer UI prohibited.
The appliance retained checksum-verified ARM64 Node 24.19.0, Eclipse Temurin
21.0.12+8 LTS, and Electron 43.2.0 distributions under the guest user's
application-support directory. Status independently ran all three installed
binaries and matched the recorded manifest.

The first live differential exposed a meaningful provider distinction. Native
AX returned Electron's labelled Chromium button and acknowledged `AXPress`, but
the file oracle remained unchanged. Cua returned the same semantic control and
its background accessibility action changed the oracle. A newly activated
Electron target can briefly yield an empty Cua tree, so the accepted corpus
uses a bounded readiness retry and still requires the exact labelled button and
independent effect. It never falls back to target coordinates or outer UI.

The accepted four-framework matrix passed twice, once before and once after a
normal full guest shutdown and unattended bring-up:

- AppKit, SwiftUI, and Java Swing used native AX for compact snapshots and
  actions. Remote/local observations were roughly 1 KB at 45–134 ms.
- Electron used explicit Cua semantics. Remote/local compact observations were
  roughly 1.6 KB at 729–872 ms, including the provider's background semantic
  route.
- Both placements changed independent file oracles for every framework. Every
  framework also produced a non-empty exact-window artifact through the
  resident facade.
- Runtime health, resident semantics, capture, and both providers returned
  ready after reboot. Every result reported one agent round trip and
  `hostInterference: none`; the read-only host cursor/frontmost-app oracle was
  unchanged.

The corpus then terminated and removed all AppKit, SwiftUI, Swing, and Electron
fixture bundles, deployed sources/build roots, state, and captures. The pinned
reusable runtimes remained healthy. The testbed smoke suite passed, including
script syntax, host Swift type checks, resident readiness, semantic inspection,
and the explicitly separate recovery-capture check. The candidate was stopped
normally after validation.
