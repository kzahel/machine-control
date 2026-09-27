# Tactical 041: Mac UTM Ubuntu Precreation Stages

Status: complete; fresh Mac precreation and platform smoke passed.

Topics: [`linux-resident-control`](../../topics/linux-resident-control.md)
and [`operational-workflow-automation`](../../topics/operational-workflow-automation.md).

## Objective and completion conditions

Report whether an ARM64 Ubuntu UTM candidate can be created from the selected
cloud image and key-only NoCloud seed without starting or changing a VM. The
report must check the actual seed content, available Mac tools, loaded UTM
inventory, and unused destination. It may suggest `factory-create` only when
all checks pass. Complete with refusal tests, a Mac report against available
private media, and the platform smoke gate.

## Boundaries

- This slice ends before candidate creation. Claimed guest stages and fresh
  candidate acceptance belong to [tactical 042](042-macos-utm-ubuntu-candidate-stages.md).
- The QCOW2 check proves image shape, not Ubuntu publisher or architecture.
  Boot and guest checks must establish those later facts.
- The precreation report has no target claim because the candidate has no UUID.
  It must not open or repair the UTM library or expose private inventory.
- The seed contains a public key and a locked account, never a password or
  private key. Generated seed media remains ignored and mode `0600`.

## Ordered work

### 1 — inspect Mac media and UTM destination

Reuse the Linux report vocabulary while adding native ISO content checks and
UTM registration and staging collision checks. Report an unloaded or uncertain
UTM inventory as a blocker.

### 2 — validate and document the report

Test missing inputs, duplicate destinations, unloaded UTM, and real Mac seed
content. Run the platform smoke gate and inspect one report with local media.

## Final result

The Mac report passed focused refusal tests and a local dry run using a
shape-only QCOW2 and a generated key-only CIDATA seed. All precreation stages
reported complete and only then offered `factory-create`; the report emitted
no private path. A registered UTM name was blocked. The Mac check also probes
UTM Apple Events because its inventory can remain readable while scripting
is unresponsive.

The initial retained-VM smoke attempt failed its independent host-pointer
comparison after a guest click. Fresh-candidate work then used a signed and
checksum-verified official Ubuntu 24.04 ARM64 release image and a new key-only
seed. Every precreation stage passed before creation. The full platform smoke
suite passed on that candidate before and after seed detachment; see
[tactical 042](042-macos-utm-ubuntu-candidate-stages.md) for the claimed
candidate and certification result.
