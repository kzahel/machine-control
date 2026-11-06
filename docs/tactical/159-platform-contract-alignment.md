# 159 — Platform contract alignment

Owning topics: [access-admission-and-pause](../../topics/access-admission-and-pause.md),
[unified-desktop-client](../../topics/unified-desktop-client.md),
[macos-locked-use](../../topics/macos-locked-use.md),
[windows-resident-control](../../topics/windows-resident-control.md),
[linux-resident-control](../../topics/linux-resident-control.md).

Status: **active.**

## Objective

Repair the accidental platform divergences recorded in
[the locked-console route gap](../../gaps/2026-11-06-prepared-console-platform-divergence.md)
and [the agent-surface divergence gap](../../gaps/2026-11-06-accidental-platform-divergences.md).
The operator asked for one consistent agent contract, with each repair
committed and verified on the matching dedicated VM.

## Completion conditions

- Every accidental item in both gaps is repaired, or this tactical records why
  it was deferred.
- Each repair has focused source tests, its own commit, and a live check on
  the appropriate VM (`windows`, `linux` or `macos`). The check follows the
  doctor/claim/release workflow and records the evidence location.
- The agent instructions and CLI help describe the one resulting contract.

## Boundaries

- Do not weaken locked-use safety: covers, task-origin relock, guardians,
  finite leases and watchdogs stay as they are.
- Intentional differences listed in the gap stay unchanged.
- Use dedicated VMs only; no physical-host locking, publication or release.
- Keep compatibility fields where an older client may read them, and add the
  common field next to them.

## Common decisions

1. **Locked Desktop route.** Agents open a Desktop owner with `preparedConsole:
   true` (`--prepared-console`) on every desktop platform. After acceptance the
   owner is usable; no separate unlock dispatch is needed.
   - macOS accepts the flag from a plain caller and treats it as the same
     covered owner it grants a flagless plain owner. Flagless plain owners
     keep working for compatibility.
   - Windows performs its prepared unlock at `control.accept`. An explicit
     `session.unlock` inside the owner stays accepted as an idempotent no-op
     once unlocked.
   - Plain Windows owners without the flag still refuse while the console is
     locked, because they would use a stored credential.
2. **Waiting versus refusing.** `prepared_console_required` is returned at open
   only for a Desktop request on a locked console. Transiently not-ready
   consoles and locked Browser-only requests queue as `resource_unavailable`,
   as on macOS and Linux.
3. **Guard failure keeps consent.** A locked-use guard failure ends the task
   with terminal reason `locked_use_guard_failed` and fences dispatch, but it
   does not Stop access. This is the macOS rule from the
   [self-revocation gap](../../gaps/2026-10-25-locked-use-self-revocation.md).
4. **Renewal advertisement.** A view carries `renewal: owner_connection/v1`
   only when that owner's `control.renew` can succeed.
5. **Audit storage unavailable.** An open is refused with
   `audit_storage_unavailable`. An active or queued intent ends with that
   terminal reason, never with a generic `cancelled`.
6. **Channel framing.** Every refusal after a `control.open` frame uses the
   channel schema. Ordering violations and failed opens close the channel.
7. **Refusal vocabulary.** These codes are common:

   | Condition | Code |
   | --- | --- |
   | Browser surface without profiles | `exact_browser_profile_required` |
   | Profiles on a Desktop-only request | `invalid_browser_profiles` |
   | Bad surfaces | `invalid_admission_surfaces` |
   | Wrong schema | `unsupported_admission_schema` |
   | Unknown channel operation | `unsupported_admission_operation` |
   | Bad renewal interval | `invalid_renewal_duration` |
   | Stale element reference | `stale_reference` |
   | `operations` outside the requested surfaces | `invalid_admission_operations` |

8. **Status projection.** `status.data` carries the following on every
   platform; existing platform fields may remain alongside:
   - `desktopState`: `locked|unlocked|no_session|unknown`.
   - `deployment`: `{policy:{preset, grantMode, protectedAdministration},
     availability:{paused, blockingReasons}, browserOnlyWhileLocked}`.
   - `lockedUse` with a common `phase`: `off|ready|paused|recovering|
     waiting_for_lock|unlocking|active|relocking`.
   - Host doctor maps `desktopState` directly, including `locked`.
9. **Capabilities.** Protected and unlock operations are advertised only when
   the current policy and preparation would admit them.
10. **Targeted input and capture.** `input.text`/`input.key` with a `target`
    activate that application and report `data.keyboardReceiver`, or refuse
    with `target_unavailable`. A window capture with `target` captures that
    application's window or refuses. Neither silently uses the foreground or
    the full screen.
11. **Common request fields.** Residents accept the common names
    (`deltaX/deltaY`, `x/y/x2/y2`, `applicationId`) and normalize them
    internally.

## Ordered work

### 1 — repair silent wrong effects

- Windows: targeted `input.text`/`input.key` (decision 10) and window capture
  by `target`.
- Linux appliance: scroll/drag field names; `applicationId`.
- Client: remove the Windows-only `browser --profile` gate.

### 2 — keep access and full leases

- Windows guard failure (decision 3).
- macOS renewal advertisement (decision 4).
- Audit-storage outcome (decision 5).

### 3 — one locked Desktop route

- Decision 1 on macOS and Windows, then decision 2.
- Update the instructions, help and the platform guides.

### 4 — channel and refusal alignment

- Decisions 6, 7 and 9.
- Windows `applications`, `focus` and `application.terminate`.
- Key-name aliases in the client.

### 5 — status projection and contracts

- Decision 8.
- Add `contracts/` schemas for the v2 admission channel view, deployment
  policy and locked-use status.
- Add a cross-platform conformance runner that sends the same requests to
  each resident and checks against those schemas.

## Validation

- **Per repair:** focused unit tests, then the platform's VM.
  - Windows: `windows` with `bin/winvm` deploy of the source resident.
  - Linux appliance: `linux`.
  - macOS: `macos`, the Tart candidate.
- Locked-route checks start each owner with the console locked. They confirm
  unlock and the effect independently, and they observe relock.
- Evidence stays in private output outside the checkout. This tactical
  records only sanitized results.

## Result

Pending.
