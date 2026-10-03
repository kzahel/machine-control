# Physical Mac covered locked-use trial

Owning topic: [macOS locked use](../../topics/macos-locked-use.md).

Status: bounded physical trial complete; covered-use acceptance remains open.

## Objective

The person requested a physical Mac test of the first open-lid version. Verify
native helper preparation and attempt the unattended path: temporarily unlock
an already locked console behind covers, exercise native fixture effects, then
relock when the task ends. Physical takeover is a separate acceptance cell.

## Completion conditions

- Use read-only doctor and an exclusive target-use claim, with person-owned
  native setup, preference enablement, ordinary approval, and manual recovery.
- Distinguish accepted input from independently observed fixture and OS effects.
- Record the actual result without promoting VM evidence to physical acceptance.
- End owned control/access, stop the owned fixture, and release the claim.

## Boundaries

One physical ARM64 Mac running macOS 26.6.2 with SIP enabled; awake and open
lid. No password storage, protection-policy weakening, closed-lid support,
process-failure injection, or primary-browser test profile. Use native CLI and
read-only OS diagnostics. Keep machine identity, captures, and authentication
logs in private local evidence rather than this repository.

## Ordered work

### 1 — complete native preparation

The person approved the Machine Control helper through macOS and enabled the
prepared preference. Resident status reported helper approval, health, and
permission readiness. Ordinary access required its separate native approval.
This used the signed candidate from Tactical 065.

### 2 — establish lock and attempt covered activation

An initial fixture key request refused with `target_activation_failed`.
Read-only AppKit state showed a running regular application; explicit native
activation succeeded, and a subsequent key reached the independent fixture
oracle. No product activation change was made from this diagnostic.

The synthetic lock shortcut was accepted but OS lock was not observed. The
runner timed out in `waiting_for_lock`. Add `--manual-lock` so physical tests
can establish their starting condition through the person's normal lock action.
After manual lock, the guardian attempted covered activation but ended with
`covered_unlock_not_observed` before any covered fixture/capture cell.

### 3 — verify recovery and capture the gap

The failure left the OS locked, zero covers, no active control session,
ordinary access revoked, and automatic unlock paused. The person unlocked
normally; the observer then reported unlocked and the pause cleared, with no
ordinary access or control session restored automatically.
The owned fixture and its state were removed, and the cleanup claim released.
The person's helper approval and enabled preference remain in place.

OS authentication logs showed the installed authorization mechanism being
evaluated during manual recovery and normal password fallback succeeding.
No corresponding mechanism evaluation was observed during the automatic
attempt. This supports investigating the unlock trigger, but does not establish
whether focus, event delivery, wake state, or another cause blocked it.

## Validation and result

**Current:** native helper setup and preference readiness passed on this
SIP-enabled physical Mac. Failed activation cleanup and manual recovery were
observed. Covered native AX, pointer, key, capture, task-end relock, and hardware
takeover remain untested here because automatic unlock did not succeed.

The runner now supports manual lock, retains typed refusal details, and reports
an ended control session immediately instead of waiting out activation timeout.
Python compilation, CLI help, and whitespace validation cover this runner edit;
the failed live trial used manual-lock support before the final diagnostic edit.

**Open:** repair and revalidate the automatic covered-unlock path on physical
hardware. Preserve the bounded connection, opaque covers, failure pause,
watchdog, and normal password fallback. The successful VM cells in Tacticals
064 and 065 remain separate evidence.
