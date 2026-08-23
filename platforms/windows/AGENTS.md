# WinVM Testbed Agent Guide

This platform directory is the canonical public source. Do not make
implementation changes in the legacy `winvm-testbed` checkout.

This repository starts, diagnoses, and controls a Windows VM. The supported
configuration is currently a Windows 11 guest in UTM/QEMU on macOS.

## Start Here

Start at the repository root. Run
`bin/machine-control --target windows target doctor` before operating the VM;
the common client supplies the controller's private inventory without exposing
it. Use `bin/machine-control --target windows testbed -- help` for the native
command surface and read `skills/drive-winvm/SKILL.md` for the operating
workflow. Invoke `bin/winvm` directly only when ignored configuration or the
documented `WINVM_*` inventory environment is already present.

If doctor reports that the exact pinned target is not registered in UTM, use
`bin/machine-control --target windows testbed -- repair-registration`. That
operation verifies the on-disk bundle against the existing private name and
UUID before registering it and does not boot the VM. Do not re-pin first; a
re-pin is appropriate only when the verified bundle repair refuses a genuine
private-inventory mismatch.

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

A UTM `started` state is not proof that Windows, OpenSSH, or the resident is
ready. Update/recovery boots may take up to the configured boot timeout (ten
minutes by default). Do not shut down, restart, or force-stop a target merely
because guest-agent IP, SSH, or resident readiness has not appeared during
that interval. Continue bounded read-only probes and inspect the console only
after an inner route is unavailable.

## Session Boundary

SSH runs in Windows session 0. Desktop applications run in the logged-in
interactive session. Launch GUI programs with `bin/winvm ui launch`, never
with raw SSH. A cold Windows boot requires a user login before semantic UI
automation is available unless the guest has explicitly authorized auto-logon.
Auto-logon credentials must remain guest-local and must never be stored in this
repository, shell history, or command output.

## Configuration and Deployment

Machine configuration belongs in the controller's private inventory, ignored
`config.local`, or `WINVM_*` environment variables. Never commit credentials,
private keys, addresses, hostnames, VM UUIDs, or personal screenshots here.

After changing files under `guests/windows/ui/`, deploy and verify them:

```bash
bin/winvm deploy-ui
bin/winvm doctor
```

Run `tests/smoke.sh` before committing. Do not add AI co-author trailers to
commit messages.
