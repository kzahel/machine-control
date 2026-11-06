# Accidental platform divergences in the common agent surface

Topic: `access-admission-and-pause`

Status: **Open — source review only; nothing repaired except guidance.**

## Origin

The [locked-console route gap](2026-11-06-prepared-console-platform-divergence.md)
prompted a source review of macOS, Windows and Linux residents and the common
client. The review looked for behavior that differs by platform without a
recorded decision or OS constraint. Three parallel read-only reviews covered
the admission channel, the CLI/status projections and the protected/locked-use
policy. **Verified** below means the controller re-read the cited source; the
other items are reviewer findings with file references. Nothing here was
exercised live.

All three residents share the Node admission policy (`runtime/src/admission.ts`).
The divergences come from each platform's channel, provider and status code
around it. `contracts/` has no v2 admission-channel or locked-use status
schema, so nothing enforces a common shape.

## Silent wrong effects (highest priority)

- **Verified — Windows `desktop input text|key --target APP` ignores the
  target.** `DesktopController.TypeText` never reads it. Help promises
  activation first. Text can land in whichever window has focus while the
  result reports acceptance. macOS activates the target; the Linux desktop
  provider refuses with `foreground_mismatch`.
- **Verified — the Linux appliance drops scroll deltas and drag start points.**
  The client sends `deltaX/deltaY` and `x,y,x2,y2`
  (`contracts/request-v0.schema.json`). `linuxcontrol.py` forwards only
  `dx/dy/x1/y1`. Scroll reports delivery with no movement.
- **Windows `desktop capture --scope window --target APP` returns the full
  screen.** Only `hwnd` is honored.

## Lost access or early task endings

- **Verified — a Windows guard failure turns all access Off.**
  `DesktopLockedUse` calls `grants.Stop("locked_use_guard_failed")`, which stops
  every surface and counts as a person's Stop. macOS deliberately ends only the
  task and retains consent since the
  [self-revocation gap](2026-10-25-locked-use-self-revocation.md).
- **Verified — macOS advertises renewal it then refuses.** The shared view
  always carries `renewal: owner_connection/v1`, and `AdmissionChannel.swift`
  never removes it. Delegated and outer channels and covered owners without
  helper `coveredRenewal` therefore advertise renewal. Their `control.renew`
  then refuses. The SDK closes on that refusal, so such an owner ends at about
  two thirds of its lease. Delegated YA sessions are the likely affected path;
  live confirmation is open.
- **Audit-storage failure** waits on Windows, is refused at open on Linux, and
  ends mid-task as a generic `cancelled` on macOS and Linux.

## Client gates and vocabulary

- **Verified — `browser --profile` is refused on every non-Windows target.**
  The client rejects it with `unsupported_browser_profile_selection`, although
  macOS and Linux advertise `profileSelectionSupported`.
- The deployment-policy field differs by platform: macOS
  `protectedAdministration`, Windows `operationSet`, Linux
  `protectedOperations`. The location also differs: macOS
  `status.data.deployment`, Linux spreads it into top-level status, and
  Windows exposes it only through `grant.status`.
- Lock and readiness status: only macOS reports `desktopState` and `lockedUse`
  in `desktop status`. Windows reports `sessionLocked`, and Linux has no lock
  field. Linux host doctor never reports `locked`. All hosts' doctor grant
  checks still assume per-request approval.
- `lockedUse.phase` vocabularies differ: Windows `idle|task_owned|relocking`;
  macOS `off|ready|paused|…|active`.
- Windows lacks `applications`, focus actions and `application.terminate`,
  although `topics/unified-desktop-client.md` lists them as common.
- The Linux appliance reads `desktopId`, not `applicationId`. Key-chord names
  are not translated per platform.
- The same condition gets different refusal codes:
  - stale references: `stale_or_unknown_reference` on Windows,
    `stale_reference` elsewhere;
  - missing browser profiles, bad surfaces, wrong schema, unknown channel
    operation and renewal duration: each has two or three spellings.
- macOS returns some open-time refusals (`admission_queue_full`, journal down)
  as v0 envelopes. The SDK reports these as `admission_unsupported`.
- Linux keeps a channel open after sequence violations and failed opens;
  `docs/access-admission.md` says ownership closes.
- Windows refuses at open (`prepared_console_required`) for a transiently
  not-ready console or a locked Browser-only request, where the others queue.
- macOS workstations advertise `session.unlock` and `authorization.*` in
  capabilities even though the broker refuses them.
- `grant request` help and the `approval_required` remediation still describe
  per-request grants that every resident now refuses.

## Recorded as intentional

These are not repair items; each has a recorded decision or OS constraint:

- Delegation and outer recovery are macOS-only (Tactical 086/087).
- Windows prepared owners do not renew yet.
- Linux has no unlock or locked use.
- Windows credentials use DPAPI enrollment, while macOS uses a password-free
  authorization plug-in.
- `uac.respond` versus `authorization.*` follows the OS prompt facilities.
- Native sudo is macOS-only.
- Both platforms relock only tasks that started locked.

## Proposed direction

Add v2 admission-channel, deployment-policy and locked-use status schemas
under `contracts/`. Then add one cross-platform conformance suite that sends
the same requests to every resident. Repair the silent-wrong-effect items
before vocabulary alignment.
