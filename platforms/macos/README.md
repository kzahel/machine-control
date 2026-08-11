# MacVM Testbed

Agent-friendly bootstrap, management, screenshots, input injection, and
accessibility-tree automation for macOS virtual machines.

This directory is the canonical public source. The former
`macvm-testbed` repository is retained only as legacy history and a possible
future generated distribution.

MacVM Testbed fills the gap between “Tart is running” and “an automated agent
can reliably operate the Mac desktop.” It provides one CLI for VM lifecycle,
guest-agent commands, normalized screenshots, host-injected input, and native
macOS Accessibility inspection and actions.

## Supported Today

| Layer | Current implementation |
| --- | --- |
| Host | Apple-silicon macOS |
| VM provider | Tart 2.30+ / Virtualization.framework |
| Guest | macOS 26 prepared or vanilla image |
| Command channel | Configurable Tart guest agent or authorized SSH |
| Semantic UI | Native AXUIElement helper in the interactive guest session |
| Resident facade | Per-user Unix socket with `machine-control/v0` envelopes |
| Composition | Native AX/Quartz/CGEvent plus optional installed Cua |
| Administrator sheets | Strict SecurityAgent, System Settings, Installer, and Gatekeeper profiles plus a non-echoing one-shot credential channel |
| Privacy fixtures | Signed API triggers and independent policy/hardware oracle |
| Framework fixtures | Deterministic AppKit, SwiftUI, Java Swing, and Electron semantics with file oracles |
| Recovery | Tart-window screenshot and CoreGraphics keyboard/mouse input |

The semantic helper has no provider-packaged exclusions for the Dock, menu
bar, System Settings, or ordinary desktop applications. macOS consent and
integrity boundaries still apply.

## Quick Start With A Prepared Image

```bash
brew install cirruslabs/cli/tart
tart clone ghcr.io/cirruslabs/macos-tahoe-base:latest tahoe-base
cd ~/code/machine-control/platforms/macos
bin/macvm up
bin/macvm deploy-ui
bin/macvm authorize-ui
bin/macvm doctor
```

The final authorization opens an explicit guest macOS consent flow. Follow
[the bootstrap guide](docs/bootstrap.md); do not attempt to edit TCC storage.

## Daily Use

```bash
bin/macvm doctor
bin/macvm doctor --json
bin/macvm up
bin/macvm exec /usr/bin/sw_vers
bin/macvm control '{"operation":"capabilities"}'
bin/macvm control '{"operation":"applications"}'
bin/macvm shell
bin/macvm suspend
```

`macvm up` submits the graphical `tart run` process to the current user's
launchd GUI domain. The VM therefore remains running after the invoking shell
or non-interactive command runner exits. Routine suspend, shutdown, and stop
leave no launchd-owned Tart process; the next `up` replaces any inactive job.

Discover and operate semantic macOS controls:

```bash
bin/macvm ui apps
bin/macvm ui windows --app Safari
bin/macvm ui tree --app Safari --interactive --depth 8
bin/macvm ui find Downloads --app Safari
bin/macvm ui press Downloads --app Safari
bin/macvm ui launch TextEdit
```

The resident facade is the normal agent path. It starts lazily in the Aqua
session, reports the selected provider, and is callable through the host
wrapper or the same guest-local CLI:

```bash
bin/macvm control '{"operation":"status"}'
bin/macvm control-local '{"operation":"status"}'
```

Both calls reach one socket and one resident generation. Semantic references
are scoped to that generation and fail closed after restart. If the native
app lacks a TCC grant but an installed Cua daemon is healthy, results disclose
that composition and route rather than pretending the native provider ran.
Normal Aqua administrator sheets use the same resident through a strict,
short-lived lease and an interactive non-echoing credential helper; see
[macOS UI automation](docs/ui-automation.md#administrator-authorization-sheets).
The accepted logged-in Aqua corpus also covers settings-managed privacy,
native panels and sheets, notifications, Safari downloads, DMGs, Gatekeeper,
Installer, AppKit, SwiftUI, Java Swing, Electron, and target-local visual
fallback. The execution
record and original environment omissions live in the sibling machine-control
repository's
[`Tactical 010`](../machine-control/docs/tactical/010-macos-full-aqua-software-testing.md);
the Java/Electron closure is
[`Tactical 011`](../machine-control/docs/tactical/011-macos-java-electron-framework-coverage.md).

`doctor --json` emits the minimized `machine-control-doctor/v0` projection for
the common client. It reports independent power, administration, Aqua desktop,
resident, semantic, capture, input, and outer states without publishing the
configured machine identity, guest user, or network address. It is read-only
and exits nonzero when the accepted resident surface is not ready.

Set `MACVM_FORBID_OUTER_UI=true` for ordinary software-test acceptance. In
that mode, Tart-window screenshot, click, drag, type, and key commands fail
closed while lifecycle, the selected guest command transport, and resident
control remain available.

`bin/macvm host-state` is a read-only acceptance oracle for the controller
host's cursor and frontmost application. It remains available under the guard
so conformance tests can prove that target-resident input did not manipulate
the host desktop; it does not observe guest pixels or inject input.

The prepared appliance can carry checksum-pinned, user-local ARM64 build
runtimes without Homebrew or a system-wide package installer:

```bash
bin/macvm install-framework-runtimes
bin/macvm framework-runtime-status
bin/macvm deploy-java-fixture
bin/macvm deploy-electron-fixture
```

The runtime manifest pins Eclipse Temurin 21 LTS, Node 24 LTS, and Electron to
immutable official archives and SHA-256 values. Deployment builds a Swing app
with `jpackage` and packages an Electron app under stable bundle identifiers;
both expose native semantics and write independent file oracles. Fixture
removal retains the reusable runtimes. Native AX drives Swing. The accepted
Electron semantic cell uses the installed Cua adapter after target activation:
live differential evidence found native AX acknowledged the Chromium button
without changing its oracle, while Cua produced the effect.

A resident capture returns a guest artifact path. Fetch that bounded artifact
without reading arbitrary guest files through the artifact interface:

```bash
result="$(bin/macvm control '{"operation":"capture","scope":"display"}')"
bin/macvm artifact-fetch "$(jq -r '.data.artifactPath' <<<"$result")"
```

Use the provider-level Tart-window path only for bootstrap or explicit
recovery when the resident surface is unavailable:

```bash
bin/macvm screenshot
bin/macvm click 512 384
bin/macvm drag 300 240 700 240
bin/macvm type 'hello from the host'
bin/macvm key cmd-space
```

Screenshots are normalized to the configured Tart guest display. A screenshot
pixel `(x, y)` is therefore the coordinate accepted by `macvm click x y`,
independent of Retina scale and the host Tart title bar.

## Control Layers

```text
Host agent
  |
  +-- tart exec or SSH --------- guest shell and file operations
  |
  +-- selected transport -> macui
  |                              semantic Accessibility tree/actions
  |
  +-- selected transport -> resident
  |                              owned facade over native/Cua providers
  |
  +-- Tart window -------------- screenshot and injected input recovery
  |
  +-- tart CLI ----------------- lifecycle, IP, suspend, stop
```

The UI helper is compiled and ad-hoc signed with an explicit stable designated
requirement inside the guest as
`~/Applications/MacVM UI.app`. Tart's interactive user agent requests each
LaunchServices invocation and returns its output, while macOS sees one stable
app identity for Accessibility consent. This avoids the Windows-style
session-0 relay, but requires a logged-in Aqua session and one explicit grant.

## Fresh And Broken Guests

Prepared non-vanilla Cirrus images contain the guest agent needed by
`tart exec`. A VM created directly from an IPSW does not. MacVM Testbed can
still see and drive Setup Assistant through the Tart window, then install the
guest agent from the read-only repository share.

Read [docs/bootstrap.md](docs/bootstrap.md) for the complete prepared-image,
vanilla-image, lost-password, TCC, and recovery procedures.

## Repository Layout

```text
bin/macvm                         Main agent-facing CLI
bin/macui                         Guest semantic-control wrapper
providers/tart-macos/             Lifecycle, capture, and raw input
guests/macos/bootstrap/           Fresh-guest installation assets
guests/macos/ui/macui.swift       Native Accessibility helper
guests/macos/fixture/             Deterministic native conformance fixture
guests/macos/admin-fixture/       Harmless administrator-sheet fixture
guests/macos/privacy-fixture/     Privacy API and System Settings fixture
guests/macos/swiftui-fixture/     Deterministic SwiftUI semantic fixture
guests/macos/java-fixture/        Deterministic Java Swing semantic fixture
guests/macos/electron-fixture/    Deterministic Electron semantic fixture
guests/macos/framework-runtimes/  Pinned runtime manifest
scripts/                          Deployment and diagnostics
skills/drive-macvm/               Reusable agent operating skill
```

See [docs/architecture.md](docs/architecture.md) before adding another host
provider or guest implementation.

Open automation gaps found while driving real applications are tracked in
[docs/problems.md](docs/problems.md).

## Requirements

Host:

- Apple-silicon macOS with Tart
- Bash, `jq`, Swift, and the built-in `screencapture` utility
- Screen Recording and Accessibility permission for the invoking terminal or
  agent host

Guest:

- macOS with a logged-in desktop user
- Tart guest agent for `exec` and reliable IP discovery
- or an explicitly authorized SSH account/key when SSH is selected as the
  guest command transport
- Xcode Command Line Tools to compile the semantic helper
- Accessibility permission for the deployed MacVM UI app

## Security

- No credential is accepted in JSON, arguments, environment, or files. The
  administrator-sheet helper reads one credential from an interactive terminal
  without echo and streams it directly to the resident.
- Initial TCC consent still requires direct guest-user interaction because the
  resident does not yet have Accessibility permission.
- The repository share is read-only by default.
- The UI helper is non-root and cannot bypass TCC or macOS integrity levels.
- The resident socket is owned by the interactive user with mode `0600`.
- Privacy resets use supported APIs and `tccutil`; the testbed never edits a
  TCC database. Local Network and notification decisions are settings-managed
  because `tccutil` does not expose a supported reset for them.
- Ignored target-role/name guards can fail closed before clone mutation.
- `force-stop` is an explicit recovery operation, never routine lifecycle.

## License

MIT
