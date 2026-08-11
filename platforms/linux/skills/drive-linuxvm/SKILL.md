---
name: drive-linuxvm
description: Operate, diagnose, bootstrap, upgrade, and recover the UTM Ubuntu Wayland VM through LinuxVM Testbed. Use when Codex needs to run commands or transfer files in the Linux guest, inspect or act on native GNOME UI, capture the display, inject recovery input, manage VM lifecycle, or restore a missing QEMU guest-agent or AT-SPI channel.
---

# Drive LinuxVM

Operate the configured UTM guest through `bin/linuxvm` from the repository
root. Keep credentials out of commands and distinguish root guest-agent work
from non-root desktop-session work.
Lifecycle mutations require ignored/private configuration that binds the
candidate or disposable role to the exact selected VM name and UUID; never
disable the default mutation guard to make a public example work.

## Choose the control layer

1. Run `bin/linuxvm doctor` and inspect every failed boundary.
2. Use `bin/linuxvm exec --` for packages, services, files, and system facts.
   QEMU guest-agent execution is root-equivalent.
3. Use `bin/linuxvm user-exec --` for commands owned by the logged-in user.
4. Use `bin/linuxvm gui-launch --` to start graphical applications through
   the active user's imported systemd environment.
5. Use `bin/linuxvm ui` for GNOME applications and named AT-SPI controls.
   Inspect with `apps`, `windows`, `tree`, or `find` before acting.
6. Use `screenshot`, `click`, `drag`, `type`, `key`, or `scan` for lock screens,
   bootstrap, or recovery when semantic access is unavailable.
7. Ask the user to enter passwords directly in the guest. Never include one in
   chat, a command, `config.local`, or a repository file.

## Start and inspect

```bash
bin/linuxvm doctor
bin/linuxvm up
bin/linuxvm exec -- uname -a
bin/linuxvm user-exec -- id
bin/linuxvm gui-launch -- gnome-text-editor
bin/linuxvm ui apps
bin/linuxvm ui tree --app gnome-terminal-server --interactive --depth 8
```

AT-SPI requires an active desktop user and that user's session D-Bus. A locked
or logged-out session is a boundary, not evidence that the guest is down.

## Use semantic actions

Discover roots and repeated labels before acting:

```bash
bin/linuxvm ui find 'New Tab' --app gnome-terminal-server
bin/linuxvm ui actions 'New Tab' --app gnome-terminal-server
bin/linuxvm ui press 'New Tab' --app gnome-terminal-server
```

Queries are case-insensitive. Exact accessible names win; otherwise the first
tree-order match is used. Reinspect after navigation or window recreation.

## Use visual recovery

Capture immediately before coordinate actions. Screenshot pixels are guest
coordinates at the configured logical resolution:

```bash
shot="$(bin/linuxvm screenshot)"
bin/linuxvm click 640 400
bin/linuxvm drag 300 240 700 240
bin/linuxvm type 'text'
bin/linuxvm key ctrl-alt-t
```

Before `spice-vdagent` exists, prefer keyboard scan-code shortcuts because the
pointer may be captured and relative. Coordinate input foregrounds UTM and can
move the host pointer; avoid it while the user is operating another host app.

## Bootstrap and recover

Read `docs/bootstrap.md` completely before guest-agent repair, full upgrades,
or future fresh-image work. When `utmctl exec` is missing, use the visible UTM
desktop and `key ctrl-alt-t`, then install and start `qemu-guest-agent` with the
documented one-line command. Let the user perform any password entry.

Prefer `suspend` for routine parking, `reboot` for a tracked guest restart, and
`shutdown` for an orderly power-down. `shutdown` waits for the provider to
report `stopped`; a successful return is a terminal lifecycle boundary.
Use `force-stop` only for explicit recovery. Never delete, replace, revert, or
reset a VM without user authorization.

Read `docs/ui-automation.md` for Wayland, application-root, and input details.
Read `docs/architecture.md` before changing provider, completion-sentinel,
identity, coordinate, or lifecycle behavior.
