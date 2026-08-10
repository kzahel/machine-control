# LinuxVM Testbed

Agent-friendly bootstrap, management, screenshots, input injection, and
accessibility-tree automation for Ubuntu Wayland virtual machines.

LinuxVM Testbed fills the gap between “UTM is running” and “an automated agent
can reliably operate the Linux desktop.” It combines UTM lifecycle and guest
execution, normalized screenshots, virtual keyboard/mouse recovery, and
semantic AT-SPI inspection and actions behind one CLI.

## Supported Today

| Layer | Current implementation |
| --- | --- |
| Host | Apple-silicon macOS |
| VM provider | UTM 4.7+ / QEMU |
| Guest | Ubuntu 24.04 LTS ARM64 with GNOME Wayland |
| Command channel | UTM `qemu-guest-agent` execution and file transfer |
| Semantic UI | AT-SPI in the active desktop user's D-Bus session |
| Resident facade | Active-user Unix socket with `machine-control/v0` envelopes |
| Inner capture | GNOME Wayland display and active-window PNG artifacts |
| Inner input | Root appliance broker with active-user-only virtual HID socket |
| Recovery | Normalized UTM capture, text, scan codes, mouse, and drag |

The initial target is the existing local UTM VM named `Linux`. A future pass
can add a reproducible unattended Ubuntu installation without changing the
daily command or UI contracts.

## Quick Start With The Existing VM

```bash
git clone https://github.com/kzahel/linuxvm-testbed.git ~/code/linuxvm-testbed
cd ~/code/linuxvm-testbed
bin/linuxvm up
bin/linuxvm deploy-ui
bin/linuxvm deploy-resident
bin/linuxvm doctor
```

If `up` reports that the guest agent is unavailable, follow
[the existing-image bootstrap](docs/bootstrap.md). It starts from the visible
UTM window and needs no SSH access.

## Daily Use

```bash
bin/linuxvm doctor
bin/linuxvm status
bin/linuxvm exec -- uname -a
bin/linuxvm user-exec -- id
bin/linuxvm gui-launch -- gnome-text-editor
bin/linuxvm control '{"operation":"status"}'
bin/linuxvm control-local '{"operation":"status"}'
capture="$(bin/linuxvm control '{"operation":"capture","target":"display"}')"
bin/linuxvm artifact "$(jq -r '.data.artifact.id' <<<"$capture")"
bin/linuxvm control '{"operation":"input.click","x":640,"y":400}'
bin/linuxvm control '{"operation":"input.text","text":"Hello, 世界 👋"}'
bin/linuxvm control \
  '{"operation":"application.launch","command":["/usr/bin/nautilus","--new-window"],"expectTarget":"org.gnome.Nautilus"}'
bin/linuxvm ip
bin/linuxvm suspend
```

Guest execution is root because QEMU's guest agent is a hypervisor management
channel. `user-exec` deliberately switches to the active logged-in user and
sets that user's runtime and D-Bus environment.

GUI applications should use `gui-launch`, not `user-exec`. It submits a
transient service to the active desktop user's systemd manager, verifies that
the manager has an imported Wayland or X11 display, prints the service unit,
and returns without tying the application to the guest-agent command. Inspect
or stop that unit with `user-exec -- systemctl --user ...`.

Discover and operate native GNOME controls:

```bash
bin/linuxvm ui apps
bin/linuxvm ui windows --app org.gnome.Nautilus
bin/linuxvm ui tree --app gnome-terminal-server --interactive --depth 8
bin/linuxvm ui find Close --app gnome-terminal-server
bin/linuxvm ui actions Close --app gnome-terminal-server
bin/linuxvm ui press 'New Tab' --app gnome-terminal-server
```

The persistent resident is the normal semantic contract. The outside wrapper
and installed guest-local CLI reach the same mode-`0600` Unix socket,
generation, snapshot references, routes, and result vocabulary:

```bash
bin/linuxvm control '{"operation":"applications"}'
bin/linuxvm control \
  '{"operation":"snapshot","target":"gnome-shell","query":"Activities","projection":"compact"}'
```

References are resident-generation and snapshot scoped. Provider restart or
snapshot eviction produces a typed stale-reference refusal rather than acting
on a newly resolved control.

Resident capture runs `gnome-screenshot` in the active user session. It writes
an owned, UUID-named PNG beneath `~/.cache/linuxvm-testbed/artifacts`; the
result reports its guest path, dimensions, size, and digest. `linuxvm artifact`
fetches only that bounded UUID namespace. `display` is full-display fidelity.
`active_window` means the window active when GNOME performs the capture; it is
not arbitrary hidden-window capture.

Pointer, click, drag, scroll, key, and Unicode text fallback use a root system
service that owns one `/dev/uinput` virtual HID device. Its mode-`0600` socket
is assigned to the active desktop user, so the resident can request only the
broker's bounded input operations. This is an intentionally privileged route
for a dedicated test appliance, reported as `root_test_appliance`; it is not a
same-user containment boundary. Unicode text uses a one-shot Wayland clipboard
offer followed by virtual Ctrl+V and reports that clipboard side effect.

`bin/linuxvm fixture reset` starts the deterministic GTK fixture. Its semantic
button, unexposed drawing canvas, text entry, keyboard events, drag, and scroll
effects are written independently to `bin/linuxvm fixture state`. The smoke
suite uses this oracle instead of trusting provider acknowledgement.

`application.launch` submits an argv array—not a shell string—to a uniquely
named user-systemd transient unit and can wait boundedly for an expected
AT-SPI application. Termination accepts only that owned unit namespace or the
PID published by an exact AT-SPI target. `application.activate` prefers a
desktop application's registered `desktopId`; GNOME Wayland may reject generic
top-level AT-SPI focus, in which case the operation returns a typed refusal.

Use the provider-level path when AT-SPI is absent, the session is locked, or
an application exposes an incomplete accessibility tree:

```bash
bin/linuxvm screenshot
bin/linuxvm click 640 400
bin/linuxvm drag 300 240 700 240
bin/linuxvm type 'hello from the host'
bin/linuxvm key ctrl-alt-t
```

The screenshot is normalized to the configured 1280×800 guest display. Its
pixel `(x, y)` is the coordinate accepted by `click` and `drag`; UTM's macOS
title bar is excluded.

Keep this recovery route disabled during ordinary acceptance with
`LINUXVM_FORBID_OUTER_UI=true`.

`linuxvm shutdown` does not return until UTM reports `stopped`, or until the
configured `LINUXVM_SHUTDOWN_TIMEOUT` expires.

## Guarded Acceptance

Ordinary target-native acceptance should select a clone in ignored
`config.local` and bind mutation to both its exact name and UTM UUID:

```bash
LINUXVM_REQUIRE_MUTATION_GUARD=true
LINUXVM_TARGET_ROLE=candidate
LINUXVM_EXPECTED_NAME=EXPECTED_CLONE_NAME
LINUXVM_EXPECTED_UUID=EXPECTED_CLONE_UUID
LINUXVM_FORBID_OUTER_UI=true
```

`bin/linuxvm guard-status` reports whether the selected target passed that
check without disclosing its name or UUID. Under the outer-UI guard,
`screenshot`, `click`, `drag`, `type`, `key`, `scan`, and `window-info` fail
closed. Lifecycle and QEMU guest-agent transport remain available because they
do not observe or manipulate the graphical console. `host-state` is a
read-only oracle for the controller host's cursor and frontmost application;
it does not inspect guest pixels or inject input.

## Control Layers

```text
Host agent
  |
  +-- utmctl + qemu-ga -------- root commands, files, IP, lifecycle
  |
  +-- runuser + session D-Bus - AT-SPI tree, actions, text, values
  |
  +-- active-user Unix socket -- semantics and target-native capture
  |
  +-- root appliance broker --- active-user-scoped virtual HID operations
  |
  +-- UTM window -------------- pixels, virtual HID, lock/setup recovery
```

These layers are independent. A broken desktop does not remove root command
access. A broken guest agent does not remove visible keyboard and screenshot
recovery. A Wayland compositor restriction does not block UTM's virtual input.

## Reliable Command Completion

UTM 4.7 can report a compound guest command before all of its side effects are
visible. `linuxvm exec` does not trust that return boundary. It redirects each
command into a private guest run directory, writes status last, polls that
sentinel, then returns captured stdout, stderr, and the real exit code.

## Wayland And Accessibility

This project does not use `xdotool`. GNOME applications publish semantic UI
through AT-SPI, and the resident captures through GNOME's in-session screenshot
provider. A narrow in-guest `/dev/uinput` broker supplies the visual fallback.
AT-SPI requires an active desktop session but no macOS-style per-helper consent
grant.

Read [docs/ui-automation.md](docs/ui-automation.md) for application-root
selection, lock-screen behavior, and semantic limitations.

Open automation gaps found while driving real applications are tracked in
[docs/problems.md](docs/problems.md).

## Repository Layout

```text
bin/linuxvm                     Main agent-facing CLI
bin/linuxui                     Guest AT-SPI wrapper
providers/utm-macos/            Lifecycle, capture, files, and raw input
guests/ubuntu/bootstrap/        Existing-image integration packages
guests/ubuntu/ui/linuxui.py     Semantic accessibility helper
guests/ubuntu/ui/linuxcontrol.py Persistent resident and socket client
scripts/                        Deployment and diagnostics
skills/drive-linuxvm/           Reusable agent operating skill
```

## Requirements

Host:

- macOS with UTM and its bundled `utmctl`
- Bash, `jq`, Swift, and the built-in `screencapture` utility
- Screen Recording and Accessibility permission for the invoking terminal or
  agent host

Guest:

- Ubuntu GNOME with an active Wayland desktop session
- `qemu-guest-agent` and `spice-vdagent`
- Python 3, PyGObject, the AT-SPI introspection data, `gnome-screenshot`,
  `python3-evdev`, and `wl-clipboard`
- A stable configured display size (1280×800 by default)

SSH is optional and inactive on the original guest. It is not part of the
default trust or transport path.

## Security

- No password, SSH key, or portal token is stored or accepted by the CLI.
- Guest-agent commands are root-equivalent and remain explicit.
- Semantic UI commands run as the logged-in non-root desktop user.
- The dedicated-appliance input broker runs as root, owns `/dev/uinput`, and
  exposes only a mode-`0600` active-user socket with bounded input operations.
- Password and Polkit authentication remain user-entered inside the guest.
- `force-stop` is an explicit recovery operation, never routine lifecycle.

## License

MIT
