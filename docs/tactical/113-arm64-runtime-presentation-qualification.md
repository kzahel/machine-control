# 113 — ARM64 runtime and presentation qualification

Status: active.
Owning topic: [runtime and presentation](../../topics/runtime-and-presentation.md).
Parent: [112](112-runtime-presentation-acceptance-review.md).

## Objective and completion conditions

Close the Windows and Linux ARM64 build/native-execution gaps using the
existing local VMs, then repeat hardened Mac ARM64 effects in Tart. Qualify
one pinned implementation through all three profiles, independent safety UI,
CLI recovery, native/browser effects, cancellation and restart. Distinguish
development authentication from production publisher and installed-update
evidence. Record exact source and artifact identity, fixes and remaining gates.

## Boundaries

No public release or replacement of the operator's installed host app.
Use claimed dedicated targets and target-native administration/control;
preserve appliance policy and the separate ordinary-user product boundary.
Use separately identified test browsers. Keep credentials, target identity,
captures, signing material and raw evidence private. Preserve existing guest
installations or explicitly back them up for bounded install/update trials.
Restore initial power and promptly release claims in cleanup. No forced
shutdown, VM deletion, reversion or outer-input fallback is authorized.

## Ordered work

### 1 — prepare and qualify Windows ARM64

Doctor and claim the existing target. Inspect tooling and resources; provision
missing native development dependencies within this dedicated appliance.
Stage exact source, build the full ARM64 Tauri/.NET package, run meaningful
contracts, authenticate the candidate and execute the existing native profile,
browser and lifecycle runners. Restore owned deployment/trust state and power.

### 2 — prepare and qualify Linux ARM64

Use the supported Ubuntu/GNOME Wayland target. Build release-mode Debian and
AppImage with bounded build parallelism, authenticate exact bytes and exercise
native profiles, portal/browser effects, fault/cancellation, recovery and
restart. Qualify installed replacement where a reversible dedicated-target
fixture is available. Preserve the root appliance route as a separate profile.

### 3 — repeat Mac ARM64 regression and reconcile evidence

Build and locally sign the same implementation source. Use a claimed Tart
target, persistent staging and restoration backups to repeat profile/safety,
native/browser effects, CLI recovery and restart after hardening. Keep broader
protected/physical and Intel GUI scope explicit. Update topic/platform/matrix
evidence and commit coherent fixes and final results.

## Validation and execution

Starting implementation source: `38750bd`; the pending queue/test edits from
the review are now committed and the controller worktree is clean. Subsequent
documentation commits do not alter executable implementation. If qualification
finds a product defect, record the replacement source and rerun affected gates.

The selected Windows and Linux targets are configured ARM64 hardware-accelerated
guests. Both start powered off, with canonical credential files ready. Concrete
identity, claims, journals, tool inventories and raw reports remain private.
