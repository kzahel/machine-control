# Tactical 038: Windows Factory Stage Diagnostics

Status: complete.

Topics: [`windows-resident-control`](../../topics/windows-resident-control.md)
and [`target-lifecycle-and-readiness`](../../topics/target-lifecycle-and-readiness.md).

## Objective and completion conditions

Move the Linux Windows factory's repeated bring-up diagnosis from an operator
reading a long runbook into a claimed, machine-readable stage command. A stage
reports its evidence and the next bounded adapter command. First-logon
completion remains usable after shutdown through an exact-candidate local
attestation. The agent retains control of when to run each mutation.

## Boundaries

- This slice covers a pinned candidate on the Linux libvirt provider. UTM
  continues to use its existing runbook and provider commands.
- Stage inspection never mutates the VM, starts SSH implicitly, or treats a
  command's delivery as proof of completion.
- The common CLI still owns target selection and claim dispatch; the platform
  adapter owns exact target identity, guest and media probes, and actions.
- The local receipt contains no password, endpoint, private path, or guest
  content. It is bound to the candidate UUID, stored mode 0600, and expires
  after four hours so stale local evidence cannot authorize media detachment.
- Do not invent a retry for an ambiguous install, password rotation, or media
  shape. Report a blocked stage so the agent can inspect and choose recovery.

## Ordered work

### 1 — expose exact factory-media state

Report the libvirt candidate's removable-media stage after UUID and pool-path
validation. Refuse unknown drive shapes. Keep volume names and paths out of
the result.

### 2 — inspect bring-up stages

Project exact identity, live first-logon report, SSH, media, credential, and
resident doctor evidence to stable states and next commands. Require a live
exclusive claim because inspection reaches the accepted guest.

### 3 — preserve first-logon proof across shutdown

Add an explicit claimed attestation command that requires the live guest's
completed factory report and writes an atomic local receipt. Use the receipt
only for the same UUID, and prefer a fresh contradictory guest observation.

### 4 — validate and explain the workflow

Test pending install refusal, exact media ordering, malformed media refusal,
and ready-guest projection. Exercise stage inspection on an existing stopped
Linux candidate and check that the claim is released. Document the command
near the start of the image-factory guide.

## Result

The provider now reports `installer_and_seed`, `seed_only`, or `detached`
without disclosing media paths. `factory-stages --json` reports six claimed,
read-only stage checks with their observed evidence and next adapter command.
`factory-stages attest-first-logon` records the exact candidate's live
completion before shutdown. Focused tests and a stopped-candidate live probe
passed; that candidate correctly reported detached media and a stored password
whose guest verification requires a boot. No new VM was created for this
diagnostic slice.

The remaining work is to move media rendering, creation, and bootstrap
repair decisions into similarly bounded commands, then add the Mac UTM stage
projection. The stage interface deliberately does not run all actions in a
single unattended loop.
