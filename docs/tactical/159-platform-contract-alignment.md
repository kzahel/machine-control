# 159 — Platform contract alignment

Owning topics: [access-admission-and-pause](../../topics/access-admission-and-pause.md),
[unified-desktop-client](../../topics/unified-desktop-client.md),
[macos-locked-use](../../topics/macos-locked-use.md),
[windows-resident-control](../../topics/windows-resident-control.md),
[linux-resident-control](../../topics/linux-resident-control.md).

Status: **complete.** The Windows enrolled cells passed under Tactical 160.

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

**Current (2026-11-06):** all items are committed under
`Topic: platform-contract-alignment`. Live evidence is private; sanitized
results follow.

### Shared

- `547c687`: reasoned `cancel` (audit and guard endings).
- `cd2e56a`, `d35e90a`: v2 channel/status schemas, `control frames` and
  `tests/conformance/platform_contract.py`.
- Conformance runner passed 7/7 with the console unlocked and locked on:
  - the macOS appliance VM;
  - a `macos-exp` workstation workspace;
  - the Windows desktop profile;
  - the Linux desktop-product resident (frames sent in-guest).

  The Linux and Windows appliance residents report `no_v2_channel` plus a
  passing status check.

### macOS

Commits: `56d058e` renewal, `43fc13d` audit, `174a082` framing, `969a86b`
codes, `a49a4b2` prepared plain owners, `2a470fd` capabilities, `ae7554f`
doctor/phase, `9e1a0e3` harness.

243 Swift tests pass. In a development build in a disposable `macos-exp`
workspace:
- The covered harness passes 18/18. Flagless and prepared plain owners each
  unlock behind covers, produce one independent fixture effect and relock,
  with lock state read through `IOConsoleLocked`.
- A plain CLI `control call --prepared-console` on a locked console unlocks,
  returns, and relocks.
- A 30-second prepared owner renews twice and lasts 50 seconds. `renewal` was
  briefly absent in the first read after activation.
- Workstation capabilities omit `session.unlock` and `authorization.*`.

The appliance VM showed audit endings and channel-schema refusals. The base
image's appliance app (0.2.0) predates harness key support; it was replaced
only inside the disposable workspace.

### Windows

Commits: `3cad15d` targeted input/capture, `a98c3bd` guard keeps consent,
`4f3dcbf` audit, `6e35697` unlock at accept and queue-versus-refuse,
`36b64b7` framing/codes/capabilities/portable operations, `69dc511` general
key chords, `75c4bb6` status.

Live on the `windows` VM:
- Targeted text reached Notepad behind the fixture; an unknown target refused
  without typing.
- Window capture by target returned the fixture window.
- Focus plus a key, terminate, and chords all worked.
- Audit write-deny ended the owner and refused new opens.
- Locked-console refusals matched decision 2.
- Doctor reported `locked` and `unlocked`.

**Current (2026-11-07):** both enrolled cells pass live under
[Tactical 160](160-windows-prepared-owner-renewal.md#result):
- A prepared owner started locked unlocked at `control.accept`.
- A broken guard pipe ended the task with `locked_use_guard_failed`; the
  console relocked within about 7 seconds. Desktop stayed Automatic and a
  fresh prepared task worked.

### Linux

Commits: `b9c1100` appliance fields, `72117be` audit, `cf7638b` framing,
`fdcb698` codes, `f154749` status and locked refusal, `934632b`
`locked_use_unsupported`.

Live on the `linux` VM:
- The GTK fixture scrolled and dragged.
- `applicationId` activated Files.
- An audit block ended the owner.
- Lock detection reported `locked` through product status, appliance status
  and both doctors, with logind as the independent read.

`desktop_locked_browser_only` needs a connected browser profile and is
unit-tested only. Recovery from lock used a tracked reboot, because Linux has
no secret-safe lock-screen password route.

### Client

Commits: `a23d972` `browser --profile`, `53a9794` key names and grant
guidance, `303af1c` one locked route in the instructions and help, `ca234d0`
owner-ended reason, dash arguments and the `consoleUnlock` view.

345 client tests pass. Live on the VMs:
- Key translation works on all three platforms: Windows `control+a`,
  `cmd+r`→`win+r` (the Run dialog opened, not Ctrl) and `esc`; Linux
  `escape`, `ctrl+Return` and `cmd` (GNOME Overview); macOS `Command+A` and
  `return`.
- Dash-prefixed `--argument` values reach Windows programs.
- `controlOwner` reports `audit_storage_unavailable` after an audit
  write-deny. The first attempt failed because the resident ends the owner
  about 0.5 seconds after replying; `8173b95` bounds the recheck.
- On a locked Windows desktop profile, `--prepared-console` without
  enrollment refuses `prepared_console_unavailable`, and a plain owner
  refuses `prepared_console_required`.
- `browser --profile` now reaches the resident's profile check. The success
  path was skipped because no VM has a connected, approved browser profile.

### Follow-up repairs found during verification

- `c7bcf9d`: the Linux desktop relay dropped a reply sent just before the
  resident closed, so CLI `--prepared-console` showed
  `control_transport_closed`. After the fix: `locked_use_unsupported` 12/12
  live, and the new relay test fails on the old relay.
- `002decf`: the Linux resident closed policy owners it never opened. Each
  connection close logged an `admission_owner_mismatch` traceback; 11 before,
  0 after.
- `9ad0c4a`: Windows targeted typing into Notepad garbled text. This was not
  caused by activation. Notepad spell check combined with `VK_PACKET`
  Unicode input loses characters at word boundaries. Layout-typeable
  characters are now sent as real keystrokes, and the route is reported in
  `data.textInput`. Targeted Notepad errors went from 5/19 to 0/20, and the
  WinForms fixture had 0 errors throughout. Notepad still drops an occasional
  untargeted keystroke (about 3%), recorded in
  `platforms/windows/docs/problems.md`.
- `6221e35`: non-ASCII text arrived garbled at Windows residents because
  requests carried raw UTF-8 through adapter argv. Requests are now
  ASCII-escaped JSON. "Ab café €5! naïve ✓" read back exactly 5/5.

One-shot `desktop snapshot` references are stale in a later one-shot
`desktop action` on macOS. This is the documented owner-scoped reference
contract; use one `control stream` for related steps.

### Decided, not changed

- macOS keeps `grantMode: "surface_modes"` because live harnesses rely on it.
- An appliance policy with `protectedOperations: false` therefore looks like a
  workstation to the desktop UI. This is a recorded open edge.
- Windows prepared-owner renewal moved to Tactical 160, where it is now
  implemented.
- Plain Windows owners without the flag still refuse on a locked console,
  because that route uses a stored credential.

### Follow-ups

- Complete Windows protected enrollment on the VM, then run unlock at accept
  and guard-failure live.
- Refresh the `macos-exp` base appliance app.
- Ship the `desktop_channel.py` relay in the Linux desktop package, so
  `control frames` reaches it through the CLI.
- Consider a shared per-task readiness. The Windows fix for plain owners
  offered a locked desktop is Windows-local.
