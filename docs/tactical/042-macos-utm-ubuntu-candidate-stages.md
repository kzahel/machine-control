# Tactical 042: Mac UTM Ubuntu Candidate Stages

Status: active; implementation and focused checks complete, fresh candidate
acceptance pending.

Topics: [`linux-resident-control`](../../topics/linux-resident-control.md)
and [`operational-workflow-automation`](../../topics/operational-workflow-automation.md).

## Objective and completion conditions

Project an exact, claimed UTM Ubuntu candidate from first boot through
cloud-init, resident readiness, seed removal, and a clean stopped handoff.
Keep inspection read-only and make the agent choose each action. Complete when
refusal tests, platform smoke, and a fresh ARM64 candidate prove each stage,
including a changed boot and exact-source certification.

## Boundaries

- UTM guest-agent probes run only against the selected running candidate and
  never start it. They observe cloud-init status, boot ID, and a matching
  NoCloud completion record.
- The stopped UTM configuration can prove a two-drive seed shape or the
  absence of the second drive. It cannot authenticate copied media bytes
  inside UTM's sandbox. The guest NoCloud record supplies separate evidence.
- Cloud-init completion is recorded only by an explicit, claimed command.
  The mode-0600 local receipt is UUID-bound and valid for 24 hours; inspection
  itself does not write it.
- An older or manually configured UTM candidate with a different drive order
  remains `unverified`. The inspector does not suggest detachment for it.
- A running resident doctor may use the existing guest administration
  transport. It performs no factory transition or repair.

## Ordered work

### 1 — inspect exact candidate and guest progression

Check identity, power, guest-agent readiness, current boot ID, cloud-init,
matching NoCloud files, and resident doctor. Preserve waiting and uncertainty.

### 2 — make the stopped media boundary explicit

Project the UTM drive shape, require a separate cloud-init attestation before
suggesting shutdown or seed detachment, and verify the final stopped shape.

### 3 — validate a fresh Mac candidate

Run focused refusal tests, the platform smoke suite, and a fresh ARM64 image
through create, pin, doctor, claim, cloud-init, bootstrap, seed removal,
certification, and clean stop. Keep private media and receipts out of Git.

## Result to date

Focused tests cover absent guest agent, missing cloud-init attestation,
unfinished cloud-init, a private UUID-bound completion receipt, and a locked
desktop. The stopped-stage report ran
under a claim on a retained candidate and correctly reported its older drive
shape as unverified. UTM AppleScript syntax and exact-candidate refusal were
checked. A subsequent claimed running check could not begin because this
retained VM failed to report an IP address within its startup timeout; it was
returned to the stopped state and the claim was released. The platform smoke
gate from tactical 041 still has an unresolved host-pointer comparison.
Fresh factory media and end-to-end candidate evidence remain open.
