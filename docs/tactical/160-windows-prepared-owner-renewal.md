# 160 — Windows prepared-owner renewal

Owning topics: [access-admission-and-pause](../../topics/access-admission-and-pause.md),
[windows-protected-unlock](../../topics/windows-protected-unlock.md).
Related: [Tactical 144](144-renewable-control-owners.md) (macOS renewal),
[Tactical 159](159-platform-contract-alignment.md),
[Tactical 134](134-windows-native-unlock-enrollment.md) (enrollment).

Status: **active.**

## Objective

The operator asked to remove the 900-second ceiling on Windows locked
(prepared) tasks. Let a live prepared owner renew under its original consent,
as macOS owners already do. Every protected layer must acknowledge a finite
extension before the renewal commits.

## Current limits

Three independent fixed 900-second bounds end every prepared task:

- **Resident:** `AdmissionChannel` refuses `control.renew` for prepared owners
  and removes `renewal` from their views.
- **Service:** `DesktopUnlockControl.WatchAsync` stops pulsing after 900
  seconds.
- **Guardian:** `DesktopRelockGuardian` ends after 900 seconds of its own
  clock.

## Boundaries

- Never weaken finite bounds. Each acknowledged extension is at most 900
  seconds from acknowledgement, and the guardian never revives an expired
  deadline or extends once it is ending.
- Timed consent still ends at its original ceiling. Stop, Pause, consent
  replacement, takeover, disconnect, console change and helper loss still end
  the task immediately.
- An ended owner is never reopened. A heartbeat or claim renewal alone extends
  nothing.
- Renewal requests no credential use and dispatches no new unlock.
- Keep the guardian's independent watchdog, physical-input hook, covers and
  relock-before-exit rule unchanged.

## Design

1. **Resident:** for a live prepared owner, `control.renew` records a pending
   extension `{sequence, seconds}` and returns it in its guard-pipe reply,
   alongside `allowed`. It commits the shared admission renewal only after the
   service reports that same sequence as acknowledged. Within a bounded wait
   (about 5 seconds) a missing or mismatched acknowledgement refuses with
   `control_renewal_unavailable`. The owner then ends no later than its
   original deadline.
2. **Service:** `DesktopUnlockControl` validates `1 ≤ seconds ≤ 900` and a
   strictly increasing sequence. It replaces its fixed 900-second watch bound
   with a deadline that moves only after the guardian acknowledges. It
   forwards the extension in its pulse and reports
   `acknowledgedExtension: sequence` on its next resident query.
3. **Guardian:** it accepts an extension only while not ending, with the
   sequence strictly increasing and `1 ≤ seconds ≤ 900`. It sets its
   monotonic deadline to `max(current, now + seconds)` and echoes the sequence
   in its pulse reply. An unknown or invalid extension ends the guardian, which
   relocks.
4. **Advertisement:** prepared views carry `renewal: owner_connection/v1`
   only when the bound service and guardian support extension. The installed
   companion is version-pinned to the resident, so this is a protocol
   capability recorded at guardian start.

## Validation

- Contract tests cover the extension frame parsing and bounds, sequence
  monotonicity, expired-deadline refusal, a missing acknowledgement, and
  advertisement.
- Run `WindowsUnlock.Contracts` natively on the Windows VM.
- Run `dotnet format`, the contract tests, and ARM64/x64 publishes.
- Live, on the enrolled `windows` VM (Tactical 134 route):
  1. A prepared owner started locked unlocks at `control.accept`. This also
     closes Tactical 159's open cell.
  2. One owner renews across the old 900-second boundary with independent
     effects before and after it.
  3. Closing the owner relocks, observed independently.
  4. A guard failure ends the task and keeps consent (Tactical 159's other
     open cell).

## Result

Pending.
