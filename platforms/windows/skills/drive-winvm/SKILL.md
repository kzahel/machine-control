---
name: drive-winvm
description: Start, diagnose, administer, inspect, and interact with a Windows VM through WinVM Testbed. Use for UTM Windows VM lifecycle, SSH or PowerShell commands, WSL commands, Windows accessibility-tree automation, screenshots, keyboard or mouse recovery, fresh-guest bootstrap, and relay repair.
---

# Drive a Windows VM

Use the repository's deterministic CLI instead of reimplementing UTM,
PowerShell, or UI relay commands.

**Common tool path:** `~/code/machine-control/bin/machine-control`

The common client auto-discovers an adjacent private dotfiles inventory when
available and injects its ignored target configuration into the public Windows
adapter. Use the platform CLI directly only when that inventory environment is
already configured.

## Begin Every Task

```bash
cd ~/code/machine-control
bin/machine-control inventory status
bin/machine-control inventory credentials winvm
bin/machine-control --target windows target doctor
```

Read the result before acting:

- Acquire a target-use claim before mutation and record the power state while
  holding it. If the VM is stopped, run `target ensure-ready` with that claim
  and remember that this caller owns the corresponding cleanup.
- If the required login credential is not `ready`, stop treating the VM as
  fully handed off. Do not guess password variants; create, rotate, or recover
  the credential through the Windows setup procedure and update the declared
  host-local file in the same task.
- If the identity check says the pinned target is not registered in UTM, run
  `bin/machine-control --target windows testbed -- repair-registration` and
  repeat doctor. The repair accepts only the on-disk bundle whose name and
  embedded UUID match private inventory, and it does not boot the guest. Do not
  re-pin unless this exact-bundle repair reports a real mismatch.
- If UTM is started but guest-agent IP, SSH, or resident readiness is still
  unavailable, allow the full configured boot timeout (ten minutes by
  default). Windows update/recovery and delayed post-boot services can be
  healthy but slow. Continue bounded read-only probes; do not shut down,
  restart, or force-stop the target during this interval.
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

## Credential Login

Private inventory stores a typed locator next to the VM metadata and keeps the
password bytes in an untracked controller-local file. With a live target-use
claim in `claim_id`, resolve the ready locator and stream it through the
dedicated login helper:

```bash
WINVM_LOGIN_SECRET_FILE="$(
  bin/machine-control inventory credentials winvm --json |
    jq -er '.testbeds[] | select(.id == "winvm") | .credentials[] |
      select(.id == "guest-login-password" and .state == "ready") | .file'
)"

MACHINE_CONTROL_CLAIM_ID="$claim_id" \
  scripts/login-windows.sh winvm password < "$WINVM_LOGIN_SECRET_FILE"
unset WINVM_LOGIN_SECRET_FILE
```

Use this only for a confirmed Windows credential surface. The protected login
route refuses before secret submission when provider or field discovery is
uncertain. Submit once; do not retry a failed or unknown result. Creating,
rotating, or recovering the password is incomplete until `inventory
credentials winvm` reports the declared file as `ready`.

## Quick Reference

```bash
mc=~/code/machine-control/bin/machine-control
$mc --target windows target status
$mc --target windows target ensure-ready
$mc --target windows target capabilities
$mc --target windows testbed -- ssh
$mc --target windows testbed -- ps 'Get-Service sshd'
$mc --target windows testbed -- wsl -- uname -a
$mc --target windows testbed -- down

$mc --target windows testbed -- ui health
$mc --target windows testbed -- ui windows
$mc --target windows testbed -- ui inspect -a APP --interactive --depth 8
$mc --target windows testbed -- ui search PATTERN -a APP
$mc --target windows testbed -- ui invoke SELECTOR -a APP
$mc --target windows testbed -- ui click SELECTOR -a APP
$mc --target windows testbed -- ui set-value SELECTOR VALUE -a APP
$mc --target windows testbed -- ui screenshot -a APP

$mc --target windows testbed -- screenshot
$mc --target windows testbed -- type TEXT
$mc --target windows testbed -- key enter
$mc --target windows testbed -- key ctrl-shift-escape
$mc --target windows testbed -- click X Y left
$mc --target windows testbed -- scan CODE...
```

Treat element tokens returned by `inspect` or `search` as ephemeral; rediscover
them after navigation or window recreation. List windows when application-name
targeting is ambiguous and use `-w HWND`.

## Protect User State

- Capture or inspect current state before clicking.
- Do not close, edit, or foreground unrelated user applications.
- If this caller started an initially off or suspended VM, run `target
  shutdown` while its claim is still held, then release the claim. Leave an
  inherited running VM running unless the task or its owner says otherwise.
- Use `down` when native routine teardown is required. It suspends only when
  the provider positively declares support; unavailable or unknown support
  selects a clean guest shutdown. A private profile may disable suspend to
  avoid saved-state storage entirely.
- If clean shutdown fails, leave the VM running and report it. Do not quit UTM
  or silently substitute suspend or `force-stop`.
- Keep passwords and PINs only in their declared controller-local credential
  files. Never put them, private keys, machine identifiers, or screenshots in
  this repository or command logs.
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
