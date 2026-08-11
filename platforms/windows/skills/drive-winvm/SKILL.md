---
name: drive-winvm
description: Start, diagnose, administer, inspect, and interact with a Windows VM through WinVM Testbed. Use for UTM Windows VM lifecycle, SSH or PowerShell commands, WSL commands, Windows accessibility-tree automation, screenshots, keyboard or mouse recovery, fresh-guest bootstrap, and relay repair.
---

# Drive a Windows VM

Use the repository's deterministic CLI instead of reimplementing UTM,
PowerShell, or UI relay commands.

**Tool path:** `~/code/machine-control/platforms/windows/bin/winvm`

## Begin Every Task

```bash
~/code/machine-control/platforms/windows/bin/winvm doctor
```

Read the result before acting:

- If the VM is stopped, run `winvm up` and repeat `doctor`.
- If TCP/SSH fails, capture the UTM window and use provider recovery. Read
  `docs/bootstrap.md` when OpenSSH needs repair.
- If SSH works but the UI relay fails, check whether Explorer has an
  interactive session. Wait for configured auto-logon or ask the user to log
  into Windows after a cold boot; then run `winvm deploy-ui` if the relay
  remains unavailable.
- If all checks pass, use SSH for system work and semantic UI automation for
  desktop work.

## Choose the Least Fragile Channel

1. Use `winvm ps` or `winvm ssh` for files, processes, services, registry,
   packages, networking, and other system operations.
2. Use `winvm ui` for desktop applications. Inspect controls before invoking
   them; prefer names/selectors over coordinates.
3. Use `winvm screenshot`, raw input, and mouse coordinates only for recovery
   or inaccessible app content.
4. Ask for the smallest necessary user action when Windows requires a login,
   consent prompt, or secure desktop.

Do not launch GUI apps through raw SSH because SSH is in session 0. Use:

```bash
winvm ui launch notepad.exe
```

## Quick Reference

```bash
winvm status | up | ip
winvm capabilities --json
winvm ssh
winvm ps 'Get-Service sshd'
winvm wsl -- uname -a
winvm down

winvm ui health
winvm ui windows
winvm ui inspect -a APP --interactive --depth 8
winvm ui search PATTERN -a APP
winvm ui invoke SELECTOR -a APP
winvm ui click SELECTOR -a APP
winvm ui set-value SELECTOR VALUE -a APP
winvm ui screenshot -a APP

winvm screenshot
winvm type TEXT
winvm key enter
winvm key ctrl-shift-escape
winvm click X Y left
winvm scan CODE...
```

Treat element tokens returned by `inspect` or `search` as ephemeral; rediscover
them after navigation or window recreation. List windows when application-name
targeting is ambiguous and use `-w HWND`.

## Protect User State

- Capture or inspect current state before clicking.
- Do not close, edit, or foreground unrelated user applications.
- Use `down` for routine VM teardown. It suspends only when the provider
  positively declares support and otherwise performs a clean guest shutdown.
  Do not use `force-stop` without clear authorization or exhausted safe
  recovery paths.
- Never put passwords, private keys, PINs, machine identifiers, or screenshots
  in this repository or command logs.
- Treat auto-logon as an explicit test-appliance choice. Never place its
  credential in this repository, shell history, or command output.

## Setup and Repair

For a new guest:

```bash
winvm stage-bootstrap ~/.ssh/id_ed25519.pub
winvm ssh-config WINDOWS_USER
winvm deploy-ui
winvm doctor
```

The staged bootstrap includes one unavoidable elevated interactive action.
Follow `docs/bootstrap.md` exactly. Read `docs/ui-automation.md` for session
architecture and application limitations. Read `docs/architecture.md` only
when extending host providers or guest drivers.
