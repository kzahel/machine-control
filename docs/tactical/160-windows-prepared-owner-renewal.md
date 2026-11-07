# 160 — Windows prepared-owner renewal

Owning topics: [access-admission-and-pause](../../topics/access-admission-and-pause.md),
[windows-protected-unlock](../../topics/windows-protected-unlock.md).
Related: [Tactical 144](144-renewable-control-owners.md) (macOS renewal),
[Tactical 159](159-platform-contract-alignment.md),
[Tactical 134](134-windows-native-unlock-enrollment.md) (enrollment).

Status: **complete** for the source runtime on the enrolled Windows VM; signed
package qualification is separate.

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

**Current (2026-11-07):** `31aef6e` implements the design in all three layers.
- The resident commits renewal only after the guardian acknowledges it.
  Without an acknowledgement within 5 seconds it refuses with
  `control_renewal_unavailable`, and the original deadline stands.
- The service's 900-second watch and its 920-second connection timeout move
  only on acknowledgement.
- The guardian's deadline only moves forward, never once ending or expired.
  An invalid extension exits with reason 12, `extension_invalid`.
- Views carry `renewal` only after the guardian reports support at start.

`WindowsDesktop.Contracts` passes, `WindowsUnlock.Contracts` and full
`dotnet format --verify-no-changes` pass natively on Windows, and the ARM64 and
x64 publishes pass.

Live on the enrolled `windows` VM, with a source runtime and a matching
protected helper; enrollment was preserved by cancelling the update prompt
with its hashes unchanged:

- **Renewal:** one `control stream --prepared-console --duration 5m` owner
  unlocked at acceptance (independent session-lock read) and renewed 5 times,
  about every 200 seconds. WinForms fixture effects at 10, 300, 850, 965 and
  1,000 seconds all read back from the fixture's own file, with the console
  unlocked at 965 and 1,000 seconds. The guardian ran about 1,016 seconds.
  The console relocked about 6 seconds after stdin closed.
- **Guard failure:** suspending the resident broke the guard pipe. The next
  dispatch refused with `locked_use_guard_failed`, and the console relocked
  within about 7 seconds. Desktop stayed Automatic, locked use returned to
  `ready`, and a fresh prepared task unlocked, acted and relocked.
- **Conformance:** the runner passed 7/7 on the locked desktop profile.

**Not live:**
- The renewal-refusal cell needs a test-only guardian hook to withhold an
  acknowledgement, so it is covered by contract tests only.

**Open follow-ups:**
- The first prepared owner after a fresh resident start once failed with
  `enrolled_unlock_refused`. A guard-pipe reply exceeded the service's
  2-second timeout before any credential was read. Later owners succeeded.
  This may be the flakiness recorded in Tactical 134.
- Code review suggests the resident may hold the relock barrier
  indefinitely if the service or guardian dies without reporting completion.
  This is unverified.
