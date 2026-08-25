# WinVM Testbed Agent Guide

This platform directory is the canonical public source. Do not make
implementation changes in the legacy `winvm-testbed` checkout.

This repository starts, diagnoses, and controls a Windows VM. The supported
configuration is currently a Windows 11 guest in UTM/QEMU on macOS.

## Start Here

Start at the repository root. Run
`bin/machine-control --target windows target doctor` before operating the VM;
the common client supplies the controller's private inventory without exposing
it. Then inspect or acquire an exclusive claim, record the claimed target's
initial power state, use the returned claim ID on every operation, and release
it promptly:

```bash
mc=bin/machine-control
claim="$($mc --target windows claim acquire --duration 30m \
  --reason 'describe this work' --claimant-authority example-agent \
  --claimant-id session-42)"
claim_id="$(jq -r '.data.claim.claimId' <<<"$claim")"
started_by_caller=false
cleanup() {
  local exit_code=$?
  if [[ "$started_by_caller" == true ]]; then
    $mc --target windows --claim "$claim_id" target shutdown || exit_code=1
  fi
  $mc --target windows claim release "$claim_id" || exit_code=1
  trap - EXIT
  exit "$exit_code"
}
trap cleanup EXIT
initial_power="$($mc --target windows --claim "$claim_id" target status | \
  jq -r '.data.powerState')"
if [[ "$initial_power" == off || "$initial_power" == suspended ]]; then
  started_by_caller=true
fi
$mc --target windows --claim "$claim_id" target ensure-ready
# Perform bounded work here; cleanup runs before claim release.
```

Use caller metadata from the current environment; do not assume a particular
coordinator or put secrets and private infrastructure values in it. Renew a
long-running claim and release it from cleanup even after failure. If the
caller started an initially off or suspended VM, cleanly shut it down while
the claim is still held unless the task explicitly requires it to remain
running. If the VM was already running, leave it running unless its owner or
the task says otherwise. A failed clean shutdown leaves the VM running and is
reported; it does not authorize UTM Quit, suspend, or force-stop. Use
`bin/machine-control --target windows testbed -- help` for the native
command surface and read `skills/drive-winvm/SKILL.md` for the operating
workflow. Invoke `bin/winvm` directly only when ignored configuration or the
documented `WINVM_*` inventory environment is already present.

If doctor reports that the exact pinned target is not registered in UTM, use
the existing UUID pin to acquire a claim, then run the native
`repair-registration` command through that claim. The operation verifies the
on-disk bundle against the existing private name and UUID before registering
it and does not boot the VM. Do not re-pin first; a re-pin is appropriate only
when the verified bundle repair refuses a genuine private-inventory mismatch.
If no exact UUID is pinned yet, `target-id` and `pin-target` are the bounded
native inventory-bootstrap commands; rerun doctor before acquiring a claim.

Routine lifecycle, administration, and target-native desktop work uses an
ordinary claim. Provider screenshot and input recovery requires a claim
acquired with `--disruptive`. If unplanned outer recovery becomes necessary,
release the ordinary claim and acquire a new disruptive claim with a truthful
recovery reason; do not reuse the released ID. A platform-owner outer-UI
prohibition remains absolute.

Prefer control channels in this order:

1. PowerShell over key-only SSH for system and file operations.
2. WinApp semantic UI Automation through `bin/winvm ui`.
3. Provider screenshot and input recovery through `bin/winvm screenshot`,
   `type`, `key`, `scan`, and `click`.
4. Ask the user for the smallest necessary manual action.

Inspect the accessibility tree before invoking controls. Capture the visible
state before coordinate input. Do not close or modify unrelated user windows.
Use `bin/winvm down` for routine teardown so the provider can select a supported
lifecycle operation. An unavailable or unknown suspend capability selects
guest shutdown, never suspend. Do not quit UTM as a VM lifecycle operation. Do
not force-stop a VM unless the user explicitly authorizes that recovery action
after safe shutdown has failed.

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
