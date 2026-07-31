---
name: drive-macvm
description: Operate, diagnose, bootstrap, and recover the Tart macOS VM through MacVM Testbed. Use when Codex needs to run commands in the macOS guest, inspect or act on native UI, capture its display, inject recovery input, manage VM lifecycle, or bring up a fresh prepared or vanilla Tart guest.
---

# Drive MacVM

Operate the configured VM through `bin/macvm` from the repository root. Keep
credentials out of commands and preserve explicit macOS consent boundaries.

## Choose the control layer

1. Run `bin/macvm doctor` and inspect every failed boundary.
2. Use `bin/macvm exec` for files, processes, packages, and system facts.
3. Use `bin/macvm ui` for native applications and named Accessibility
   controls. Inspect with `windows`, `tree`, or `find` before acting.
4. Use `screenshot`, `click`, `type`, and `key` for bootstrap, consent UI, or
   recovery when semantic access is unavailable.
5. Ask the user to enter passwords directly in the guest. Never include one in
   chat, a command, `config.local`, or a repository file.

## Start and inspect

```bash
bin/macvm doctor
bin/macvm up
bin/macvm exec /usr/bin/sw_vers
bin/macvm ui apps
bin/macvm ui windows --app Finder
bin/macvm ui tree --app Finder --interactive --depth 6
```

An Accessibility failure is a permission boundary, not evidence that the UI is
absent. Run `bin/macvm authorize-ui` and follow the visible guest consent flow.
Do not edit or replace TCC databases.

## Use semantic actions

Use application names or bundle identifiers and selectors that can be
rediscovered:

```bash
bin/macvm ui find Save --app TextEdit --role button
bin/macvm ui actions Save --app TextEdit --role button
bin/macvm ui press Save --app TextEdit --role button
```

Treat printed `@N` references as diagnostic and invocation-local. Reinspect
after navigation or window recreation. Use `--exact`, `--role`, and `--nth`
when a query is ambiguous.

## Use visual recovery

Capture a fresh image immediately before coordinate actions. Screenshot pixels
map directly to guest coordinates:

```bash
shot="$(bin/macvm screenshot)"
bin/macvm click 512 384
bin/macvm drag 300 240 700 240
bin/macvm type 'text'
bin/macvm key cmd-shift-g
```

Coordinate input foregrounds the Tart window and moves the host pointer. Avoid
it while the user is operating another host application.

## Bootstrap and recover

Read `docs/bootstrap.md` completely before fresh bring-up, lost-password
recovery, or guest-agent repair. A vanilla IPSW guest initially supports only
Tart lifecycle and outer screenshot/input. Use the read-only repository share
and `guests/macos/bootstrap/bootstrap-guest.sh` to cross that boundary.

Prefer `suspend` for routine parking and `shutdown` for an OS restart boundary.
Use `force-stop` only for explicit recovery. Never delete, replace, revert, or
reset a VM without user authorization.

Read `docs/ui-automation.md` for selector and input details. Read
`docs/architecture.md` before changing a provider, guest driver, coordinate
mapping, or lifecycle semantics.
