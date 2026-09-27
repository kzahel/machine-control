# Mac UTM Windows Factory Stages

Topics: [operational-workflow-automation](../../topics/operational-workflow-automation.md),
[windows-resident-control](../../topics/windows-resident-control.md)

Status: partial; the Mac stage projection is implemented, but fresh-candidate
stage-driven acceptance is still open.

## Objective and completion conditions

Give the Mac UTM route the same read-only stage meanings as Linux/KVM. Preflight
must inspect official installer media, the exact Pro index, generated seed and
FAT boot media, host tools, and an unused UTM destination. The claimed report
must observe the exact VM, guest completion, removable-media order, credential,
resident, and maintenance state. Completion requires a fresh UTM candidate
advanced by stage output through certification and clean stop.

## Boundaries

The inspector never mutates a VM, reads a password value, or infers a
successful install from command delivery. The existing factory commands own
all guarded actions. Private VM identities, paths, credentials, and artifacts
remain outside Git.

## Ordered work and validation

1. Add Mac precreation probes for ISO/seed/boot shapes and UTM destination.
2. Add UTM guest-agent and removable-drive probes to the claimed report.
3. Test malformed, missing, and valid media and drive states with fixtures.
4. Advance a fresh candidate using only reported actions, then certify and
   stop it.

## Result

Steps 1–3 are implemented. Factory image tests and stage fixtures pass; small
disposable ISOs made by macOS `hdiutil` verified the actual seed and FAT boot
formats. Live
Mac preflight identified missing source and seed inputs while verifying the
UTM host and unused destination. A claimed report on a stopped older candidate
correctly blocked an unfamiliar removable-drive shape. Step 4 remains open:
the host had about 54 GiB free, while the previous accepted UTM Windows run
used a roughly 53 GiB bundle in addition to its source and prepared ISOs.
No new candidate or installer media was created on this host.
