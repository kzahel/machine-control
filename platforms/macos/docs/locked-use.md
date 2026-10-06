# Covered locked use on Mac

**Current:** experimental source implementation for macOS 14 or later, an
awake Mac with an open lid, and its existing console session. VM acceptance
is recorded in [Tactical 064](../../../docs/tactical/064-macos-locked-use.md);
the native Permissions setup revision is recorded separately in
[Tactical 065](../../../docs/tactical/065-macos-helper-permission.md).
One SIP-enabled physical completion trial passed covered native control,
capture and relock; see [Tactical
067](../../../docs/tactical/067-macos-physical-unlock-trigger.md). Idle-lock
retention, two successive unattended tasks and bounded expiry also passed on the
physical Mac. Operator-confirmed hardware takeover/recovery is live-tested with
a scripted timing caveat in [Tactical
070](../../../docs/tactical/070-macos-locked-access-retention.md); the full
scripted takeover cell still needs independent lock readback before recovery.
Inactive-display
startup is recorded in [Tactical
073](../../../docs/tactical/073-macos-locked-display-wake.md).
Multiple displays, notarized distribution, and every supported OS revision
require further qualification. This does not support closed lids,
sleep, fresh login, FileVault/preboot, or another user's session.

## Operator setup

Open the desktop app's **Permissions** tab and complete Accessibility and
Screen Recording setup. Set up **Machine Control helper** there; macOS manages
its approval in **Login Items & Extensions**. System Settings owns any required
administrator authentication. The app does not display a command/password
prompt or receive your password. Preparation installs the authorization plug-in
and watchdog, pins the signed app, preserves password fallback, and exercises
covered capture while you are present. Initial setup leaves locked use off;
later preparation preserves your existing checkbox choice.

After Permissions reports the helper ready, enable **Allow Machine Control
while screen is locked** in Settings. This checkbox only changes the local
preference; it never requests permission, installs software, or triggers
capture consent. Missing preparation links back to Permissions. Accessibility
and Screen Recording grants are reused. They do not themselves authorize
system-level helper installation.

Approve ordinary access in **Access**, or approve the agent's request. Enabling
locked use grants no access. Approvals remain target-wide for same-user callers.
The app and helper do not store your login password. A signed update can change
the pinned code hash. While the console is unlocked and idle, native maintenance
refreshes an existing approved managed helper automatically, preserving your
checkbox choice. Ordinary launches of the same build do not restart the helper.
Permissions still offers Repair for actual failures. Maintenance does not grant
ordinary Access; restarting the app clears that in-memory approval.

Lock the Mac normally before the agent starts its bounded covered task.
Every display receives an opaque, nonactivating cover before the existing
console is temporarily unlocked. Operator windows are hidden while covered
and restored after relock, so their self-interface protection does not block application pointer targets. The
resident's native display capture excludes the cover and operator app; native
application semantics and input continue.
If the awake Mac's display is inactive, authorized task startup briefly wakes
it while the console remains locked, then installs covers before unlocking.
That temporary native assertion is released after readiness or bounded failure;
it does not change power settings or prevent system sleep.
The physical display says **Machine Control is working** and tells you how
to take over. Full-display capture currently selects the main display, as in
ordinary native capture; multi-display coverage is implemented but not accepted.

Use the keyboard or pointer to take over. Hardware-origin events are swallowed
while covered, initiate relock, and temporarily pause otherwise valid access.
The current source permits a fresh covered task after the same console is
locked and physically quiet. If the owner unlocks to work, the local-use pause
continues until re-lock plus quiet or explicit operator Resume. Manual Pause
remains independent; Stop revokes access. Revised genuine physical takeover
and unattended resumption still require qualification in Tactical 074.
Stop access, task completion, expiry, owner
disconnect, display changes, sleep, and failures also terminate temporary use.
Covers are removed after observed lock, or after the bound console is replaced.
Tasks that start unlocked finish without requesting lock. If an ordinary task
encounters an idle or user lock, it ends without unlocking that screen; a fresh
locked-origin task can enter covered control under the existing approval.
This task-origin correction is source implemented, with native Mac validation
still pending in [Tactical 102](../../../docs/tactical/102-windows-covered-control.md).

Turning the setting off immediately persists local revocation and ends active
use without another administrator prompt. The idle installed helper has no
unlock grant. Remove the helper separately in Permissions while the Mac is unlocked.

## Agent task lifecycle

Use doctor, an exclusive claim, ordinary approval, and fresh status/capabilities
as usual. A launcher or agent must explicitly own the task connection; the
setting does not infer a task from unrelated one-shot requests.

```bash
bin/machine-control --target host --claim "$claim_id" desktop session control --duration 5m
```

Run this command concurrently with the task and keep its connection alive.
It sends heartbeats and returns the final termination result. Poll
`desktop status`: `data.lockedUse` reports phase, exact `controlSessionId`,
remaining time, covered display count, helper health, and manual-unlock pause.
The command defaults to five minutes and accepts one second through fifteen
minutes, capped by the ordinary access grant's remaining lifetime. Until-stopped
access still gets a finite control session. Heartbeats prove liveness; they do
not extend the maximum deadline. A new lease requires current valid approval.
Prepared, enabled and unpaused locked use retains that approval across idle
locks and clean completion in the same console, so a subsequent task can start
without a manual unlock or another approval. Grant expiry and revocation still
apply. Until-stopped consent may survive restart for the verified same console
and boot; queue entries and active sessions never survive restart.

In the task's `finally` cleanup, end that exact session before releasing its
target-use claim:

```bash
bin/machine-control --target host --claim "$claim_id" desktop session end --session-id "$control_session_id"
```

The ID permits stopping only; it is not bearer authority. A stale ID refuses.
Disconnection or five seconds without a heartbeat ends the lease. Rediscover
references after lock/unlock and completion. Use `macos-native` while covered;
Cua is refused in this first version. A physical takeover returns
`interrupted_by_physical_presence`; treat the old session as terminal and observe
availability before obtaining fresh ownership. Do not replay an uncertain
effect. Ordinary `session.unlock` remains
appliance-only and cannot bypass this workstation profile.

The same typed operations work locally or through the configured transport.
No worker agent or visible hypervisor window is needed for ordinary control.
The common CLI instructions advertise this lifecycle; integrations must use it
to bind their actual task completion to relock.

## Failure boundary and removal

A separate signed companion owns covers and the hardware event tap. It monitors
the resident and retains covers through resident stall/death until OS lock is
observed. The root broker independently binds the console identity and maximum
deadline, requires companion heartbeats, and records active coverage before
arming unlock so a broker restart requests relock. Unexpected termination
persists the manual-unlock pause in root-owned state. Session replacement
invalidates authority instead of retargeting control or locking another user.

This uses the measured private `SACLockScreenImmediate` OS entry point. It is an
experimental compatibility boundary. Covers and event taps are ordinary user
processes, not a secure desktop. A killed cover process can lose its windows
before the root watchdog relocks; no zero-frame exposure guarantee is claimed.
Same-user shell access is not contained. The short authorization grant is
session-wide rather than authenticating an individual agent.

For the native workstation installation, use **Remove** beside **Machine
Control helper** in Permissions. It disables locked use, removes only Machine
Control's entry from the shared screensaver authorization rule, removes the
plug-in, and unregisters the macOS service. Other plug-ins' entries in that
rule are preserved; an unrecognized rule shape refuses removal instead of
overwriting another owner's changes.

Other products, such as Codex Computer Use, can install their own entries in
`system.login.screensaver`. Setup joins that shared one-of-n rule immediately
before the password fallback and Permissions lists the other entries, each of
which can independently unlock the Mac. If another product later drops
Machine Control's entry, the helper reports `unlock_policy_entry_missing` and
**Set up** restores it. Helper refusals show their specific code.

The legacy administrator installer remains available for explicit cleanup of
legacy installations. For that profile, unlock and quit the app, then invoke
the bundled installer through native administrator authentication:

```text
mc-sudo -- <app-resources>/unlock/mc-unlock-install uninstall
```

The explicit administrator installer likewise edits only its own rule entry
and refuses an unsupported rule shape rather than overwrite another owner's
policy. No SIP, password, or lockout policy is weakened. The separate
[appliance unlock guide](session-unlock.md) describes the explicit test-appliance
profile, which leaves the desktop exposed after one-shot unlock.

## Reusable acceptance

After installing a candidate, approving ordinary access, manually unlocking,
and launching the native fixture, use
[locked-use-live.py](../../../tests/macos/locked-use-live.py) under an existing
exclusive claim. Each invocation runs one cell and leaves the target locked.
Use `--manual-lock` to wait for the person to lock normally when testing on a
physical Mac; an accepted synthetic lock shortcut is not proof of OS lock.
Local tests may instead supply `--session-lock` with the compiled native
[lock runner](../../../tests/macos/session-lock.m) to establish lock without a
person performing each starting lock. Failure pause still requires manual
recovery; the runner cannot approve access or clear that pause.
`--executable` and `--socket` select a guest candidate without replacing the
standard resident. Completion, expiry, disconnect, resident stall/crash, and
guardian crash are explicit cells. The caller owns native setup and subsequent
manual recovery. Hardware takeover requires separately authorized outer input
or a real device; captures and credentials must stay out of public evidence.
