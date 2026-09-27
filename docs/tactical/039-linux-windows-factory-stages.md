# Tactical 039: Linux Windows Factory Stages

Status: in progress.

Topics: [`windows-resident-control`](../../topics/windows-resident-control.md)
and [`operational-workflow-automation`](../../topics/operational-workflow-automation.md).

## Objective and completion conditions

Make a fresh native x86_64 Windows appliance progress through explicit,
observed Linux/libvirt stages from source media to a certified stopped
candidate. The agent chooses each bounded mutation and sees a stable blocker
or next command instead of reconstructing order from the image-factory guide.
Completion requires focused refusal tests, the Windows smoke suite, and a
fresh claimed candidate with independently observed first logon, stored and
verified login credential, media removal, resident readiness, and clean stop.

## Boundaries

- This slice is only the Linux libvirt route. UTM remains an open W1 path.
- Precreation inspection may check host and private media but cannot acquire a
  target claim before the new VM has an exact UUID. Pin, doctor, and claim are
  mandatory before subsequent target operations.
- The Windows ISO catalog identifies the selected edition/index; it does not
  authenticate the source download. Generated ISO presence is narrower than
  provenance or guest effect. The actual renderer and factory retain guards.
- Stage inspection never starts, stops, repairs, detaches, or re-credentials
  the target. Missing guest-agent evidence during installation is `waiting`.
- Setup and current login passwords stay in mode-0600 private local files and
  never enter JSON, logs, or Git. No unknown password is guessed.

## Ordered work

### 1 — inspect media and unused destination

Add a read-only precreation projection, a unique Windows 11 Pro image-index
probe, and exact libvirt host/pool/domain/volume collision checks.

### 2 — explain bootstrap and guest-agent waits

Keep the claimed postcreation inspector responsive before the agent exists.
Distinguish an absent resident installation from installed support needing
repair, and add an exact-candidate bootstrap command.

### 3 — validate a fresh candidate

Run focused stage/provider tests and the platform smoke suite. On an isolated
private candidate, rerun preflight after each media action; pin, doctor, and
claim after creation; observe first logon, key-only SSH, media, stored password,
resident doctor, certification, and final clean stop. Record any partial live
boundary accurately.

## Result

Pending exact-source certification and final clean stop. The precreation stage
projection and exact Pro catalog probe passed against local media. A separate
KVM candidate was created, pinned, and claimed; its initial running stage
correctly reported waiting for guest-agent/first-logon evidence. A subsequent
guest report proved completed first logon. The claimed attestation survived
clean shutdown; the guarded installer-then-seed sequence removed the media.
Key-only SSH, stored and guest-verified password, development bootstrap, and
full common doctor then passed after a cold start. The first post-update audit
identified a pending development-package reboot; explicit repair/reboot and
the one-shot stored-password login observed a changed boot and restored full
doctor and audit readiness. All eight claimed stages then passed. All
generated media, inventory, claim, and password material are ignored or in
the local secret store.
