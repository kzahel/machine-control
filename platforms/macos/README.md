# MacVM Testbed

Agent-friendly bootstrap, management, screenshots, input injection, and
accessibility-tree automation for macOS virtual machines.

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
| Command channel | Tart guest agent through `tart exec` |
| Semantic UI | Native AXUIElement helper in the interactive guest session |
| Recovery | Tart-window screenshot and CoreGraphics keyboard/mouse input |

The semantic helper has no provider-packaged exclusions for the Dock, menu
bar, System Settings, or ordinary desktop applications. macOS consent and
integrity boundaries still apply.

## Quick Start With A Prepared Image

```bash
brew install cirruslabs/cli/tart
tart clone ghcr.io/cirruslabs/macos-tahoe-base:latest tahoe-base
git clone https://github.com/kzahel/macvm-testbed.git ~/code/macvm-testbed
cd ~/code/macvm-testbed
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
bin/macvm up
bin/macvm exec /usr/bin/sw_vers
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

Use the provider-level path when semantic automation is unavailable:

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
  +-- tart exec ---------------- guest shell and file operations
  |
  +-- tart exec -> macui ------- semantic Accessibility tree/actions
  |
  +-- Tart window -------------- screenshot and injected input recovery
  |
  +-- tart CLI ----------------- lifecycle, IP, suspend, stop
```

The UI helper is compiled and ad-hoc signed inside the guest as
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
- Xcode Command Line Tools to compile the semantic helper
- Accessibility permission for the deployed MacVM UI app

## Security

- No password is stored or accepted by the CLI.
- Guest authentication is entered directly into guest macOS consent UI.
- The repository share is read-only by default.
- The UI helper is non-root and cannot bypass TCC or macOS integrity levels.
- `force-stop` is an explicit recovery operation, never routine lifecycle.

## License

MIT
