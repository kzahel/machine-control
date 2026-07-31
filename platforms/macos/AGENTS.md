# MacVM Testbed Agent Guide

This repository starts, diagnoses, and controls a macOS VM. The supported
configuration is currently a macOS guest in Tart on an Apple-silicon Mac.

## Start Here

Run `bin/macvm doctor` before operating the VM. Use `bin/macvm help` for the
command surface and read `skills/drive-macvm/SKILL.md` for the operating
workflow.

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
explain the consent surface; the user enters any password directly in the VM.

## Fresh Guest Boundary

Prepared Cirrus base images already contain the Tart guest agent. A vanilla
IPSW guest does not. Read `docs/bootstrap.md` before fresh bring-up. Until the
guest agent is installed, only Tart lifecycle plus host screenshot/input are
available. The read-only repository share and the guest bootstrap script are
the intended bridge into a new interactive desktop.

## Configuration And Deployment

Machine configuration belongs in ignored `config.local` or `MACVM_*`
environment variables. Never commit credentials, private keys, machine
identifiers, personal screenshots, VM images, or TCC databases.

After changing `guests/macos/ui/macui.swift`, deploy and verify it:

```bash
bin/macvm deploy-ui
bin/macvm doctor
```

Run `tests/smoke.sh` before committing. Do not add AI co-author trailers to
commit messages.
