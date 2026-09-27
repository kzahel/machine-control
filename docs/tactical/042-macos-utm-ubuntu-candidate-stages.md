# Tactical 042: Mac UTM Ubuntu Candidate Stages

Status: complete; fresh Mac candidate certified and stopped.

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

## Final result

Focused tests cover absent guest agent, missing cloud-init attestation,
unfinished cloud-init, a private UUID-bound completion receipt, a locked
desktop, and UTM's silent cloud-init command. An older retained candidate's
unfamiliar drive order remained unverified. It was replaced with a fresh UTM
candidate from a signed and checksum-verified official Ubuntu 24.04 ARM64
release image. The key-only seed, unused destination, stopped creation,
exact pin, doctor, and exclusive claim all passed.

The claimed stage report observed first-boot NoCloud completion, a changed
boot ID, the explicit completion receipt, resident readiness, one-time media
removal, and the later boot with cloud-init disabled. UTM returned no stdout
for `cloud-init status --format=json`; the report now reads the completed
runtime records and, after media removal, the disabled marker. Both routes
still require the matching persisted NoCloud instance files. Bootstrap and
the common doctor were healthy. Two full platform smoke runs passed, one on
each side of media removal. A controller login key stored outside Git was
verified over SSH against the guest host key, including noninteractive sudo.

Exact committed source at `5dbca39` passed development-profile certification:
healthy audits before and after a boot-ID-changing reboot, portable and
Linux-native guest checks, staging cleanup, and clean shutdown. The final
stage report marked the stopped source complete, and the claim was released.
