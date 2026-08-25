# MacVM Testbed Agent Guide

This platform directory is the canonical public source. Do not make
implementation changes in the legacy `macvm-testbed` checkout.

This repository starts, diagnoses, and controls a macOS VM. The supported
configuration is currently a macOS guest in Tart on an Apple-silicon Mac.

## Start Here

Start from the repository root with
`bin/machine-control --target macos target doctor`. Once it resolves exact
private identity, acquire an exclusive target-use claim with a reason,
caller-chosen authority, and claimant ID. Carry the returned claim ID with
`--claim` on every operation,
renew it during long work, and release it from cleanup. This metadata is
coordinator-neutral and self-asserted; use identifiers the current execution
environment can truthfully provide, never secrets or private endpoints. If
doctor cannot resolve exact identity, repair the ignored/private inventory and
rerun doctor before claiming or operating the VM. Use `bin/macvm help` for the
direct platform command surface and read `skills/drive-macvm/SKILL.md` for the
operating workflow.

Routine lifecycle, administration, and target-native desktop work uses an
ordinary claim. Tart-window screenshot and input recovery requires a claim
acquired with `--disruptive`. If unplanned outer recovery becomes necessary,
release the ordinary claim and acquire a new disruptive claim with a truthful
recovery reason; do not reuse the released ID. A platform-owner outer-UI
prohibition remains absolute.

Prefer control channels in this order:

1. `tart exec` for system and file operations.
2. `macvm ui` semantic Accessibility inspection and named actions.
3. Host-level Tart screenshot, pointer, and keyboard recovery.
4. Ask the user for the smallest necessary manual credential or consent
   action.

Inspect the accessibility tree before invoking controls. Capture the visible
state before coordinate input. Do not close or modify unrelated guest windows.
Do not force-stop, revert, delete, or replace a VM unless the user explicitly
requests it or the documented normal recovery paths have failed.

## Permission Boundary

MacVM Testbed never edits the guest TCC database. Host Screen Recording and
Accessibility access, and guest Accessibility access for the deployed MacVM
UI app, are explicit macOS consent decisions. An agent may navigate to and
explain the initial consent surface; the user enters any password directly in
the VM while MacVM UI is not yet trusted. After Accessibility is granted, a
matching normal Aqua administrator sheet uses `authorization.begin` and the
interactive, non-echoing `authorization-submit` helper. Never place a
credential in request JSON, arguments, environment, files, logs, captures, or
result values, and never retry a failed credential automatically.

## Fresh Guest Boundary

Prepared Cirrus base images already contain the Tart guest agent. A vanilla
IPSW guest does not. Read `docs/bootstrap.md` before fresh bring-up. Until the
guest agent is installed, only Tart lifecycle plus host screenshot/input are
available. The read-only repository share and the guest bootstrap script are
the intended bridge into a new interactive desktop.

## Configuration And Deployment

Machine configuration belongs in the controller's private inventory, ignored
`config.local`, or `MACVM_*` environment variables. Never commit credentials,
private keys, machine identifiers, personal screenshots, VM images, or TCC
databases here.

After changing `guests/macos/ui/macui.swift`, deploy and verify it:

```bash
bin/macvm deploy-ui
bin/macvm doctor
```

Run `tests/smoke.sh` before committing. Do not add AI co-author trailers to
commit messages.
