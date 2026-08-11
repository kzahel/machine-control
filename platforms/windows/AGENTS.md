# WinVM Testbed Agent Guide

This repository starts, diagnoses, and controls a Windows VM. The supported
configuration is currently a Windows 11 guest in UTM/QEMU on macOS.

## Start Here

Run `bin/winvm doctor` before operating the VM. Use `bin/winvm help` for the
command surface and read `skills/drive-winvm/SKILL.md` for the operating
workflow.

Prefer control channels in this order:

1. PowerShell over key-only SSH for system and file operations.
2. WinApp semantic UI Automation through `bin/winvm ui`.
3. Provider screenshot and input recovery through `bin/winvm screenshot`,
   `type`, `key`, `scan`, and `click`.
4. Ask the user for the smallest necessary manual action.

Inspect the accessibility tree before invoking controls. Capture the visible
state before coordinate input. Do not close or modify unrelated user windows.
Use `bin/winvm down` for routine teardown so the provider can select a supported
lifecycle operation. Do not force-stop a VM unless the user requested it or
normal shutdown and recovery paths have failed.

## Session Boundary

SSH runs in Windows session 0. Desktop applications run in the logged-in
interactive session. Launch GUI programs with `bin/winvm ui launch`, never
with raw SSH. A cold Windows boot requires a user login before semantic UI
automation is available unless the guest has explicitly authorized auto-logon.
Auto-logon credentials must remain guest-local and must never be stored in this
repository, shell history, or command output.

## Configuration and Deployment

Machine configuration belongs in ignored `config.local` or `WINVM_*`
environment variables. Never commit credentials, private keys, addresses,
hostnames, VM UUIDs, or personal screenshots.

After changing files under `guests/windows/ui/`, deploy and verify them:

```bash
bin/winvm deploy-ui
bin/winvm doctor
```

Run `tests/smoke.sh` before committing. Do not add AI co-author trailers to
commit messages.
