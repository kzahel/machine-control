# Tactical 018: Appliance Readiness and Promotion

Status: complete.

Topics: `windows-resident-control`, `linux-resident-control`,
`cross-platform-coordinator`, `target-lifecycle-and-readiness`, and
`vm-workspaces-and-storage-policy`.

## Objective

Restore one stateful controller-ready Windows development appliance and the
existing Linux appliance without proliferating large VMs. Prove cold-boot
administration and resident readiness on both targets, complete native checks
inside Windows, add an explicitly mutating common readiness operation, and
make candidate validation and promotion to private development/ready-base
roles deliberate and auditable.

## Completion conditions

- The existing retained Windows candidate is reused in place; no Windows full
  clone is created unless a later capacity audit and explicit user decision
  supersede this tactical.
- Windows is bound to an exact private candidate identity before mutation.
- Windows reaches key-only inner administration, restores the installed
  resident stack, and returns those routes after a cold reboot without routine
  UTM-window input.
- The exact checked-in source passes portable and Windows-native checks from
  inside Windows and is removed afterward.
- The existing guarded Linux candidate restores QEMU guest-agent, desktop, and
  resident readiness after a cold reboot without creating another Linux VM.
- `target ensure-ready` is explicitly mutating, reports each bounded action,
  invokes only adapter-declared inner readiness steps, and never weakens the
  read-only `doctor` contract or silently uses outer UI.
- Candidate validation separates running readiness evidence from the final
  stopped provider identity. Promotion changes private development/ready-base
  declarations only after both observations pass.
- Windows and Linux each use at most one stateful development VM and may let
  that stopped VM double as the ready base. Existing protected sources or
  generalized registrations are not deleted by this tactical.
- One UTM disposable rehearsal per newly proven ready base demonstrates that
  a target-local marker is absent after release and persistent restart.
- Public results and committed evidence contain no concrete target name, UUID,
  endpoint, account, path, or private receipt contents.

## Boundaries

- Do not create libvirt/KVM support, generated focused repositories, or a
  generic hypervisor API.
- Do not delete, rename, compact, or move an existing VM merely to reclaim
  space. Report exact recoverable cleanup candidates for a separate user
  decision.
- Do not persistently boot a generalized seal or reclassify it as a ready
  development appliance.
- Do not make `doctor` mutating. `ensure-ready` may start an exact guarded
  target and call a bounded platform repair operation, but it may not log in,
  enter credentials, grant consent, use outer input, force-stop, or guess a
  repair.
- Do not treat successful transport delivery as readiness. Re-run the common
  doctor and preserve independent administration, desktop, resident,
  semantic, capture, and input observations.
- Do not let a workspace handle act as promotion authority. The adapter must
  resolve its private receipt and exact provider identity; private inventory
  remains the final role authority.
- Do not clone a ready base merely to run routine feature work. Persistent is
  the default; isolated remains explicit and bounded to one concurrent
  disposable workspace.

## Ordered work

### 1 — audit exact targets and storage

Record only minimized state and capacity evidence. Match existing private
selections to provider identities, classify protected and reusable roles, and
verify that no active workspace receipt already owns a target. Prefer repair
of an existing candidate over derivation.

### 2 — define readiness and promotion contracts

Add normalized results for `target ensure-ready` and candidate validation,
stopping, and promotion preparation. Keep provider-specific seal or Sysprep
operations behind the Windows adapter. Promotion must fail if readiness is
stale, the candidate is running when a stopped handoff is required, or the
provider identity no longer matches.

### 3 — restore the Windows candidate

Pin the existing retained candidate in private configuration. Try existing
inner routes first. If both SSH and guest-agent administration are absent, use
only the checked-in deterministic bootstrap/recovery path and the smallest
explicit outer step permitted by the Windows guide. Restore key-only SSH,
automatic services, the resident facade, and the interactive companion.

### 4 — prove Windows reboot and native execution

Run the common doctor, cold reboot, and repeat it. Transfer the exact committed
source through the authoritative administration route, verify its digest, run
portable plus Windows-native checks, remove temporary source, and cleanly shut
down. Validate and promote the stopped exact candidate in private inventory.

### 5 — restore and reboot-prove Linux

Use the existing exact candidate. Diagnose the missing QEMU guest-agent from
the documented independent layers, run the idempotent guest bootstrap once an
inner root channel exists, and prove guest-agent, logged-in desktop, resident,
and common doctor readiness before and after cold reboot. Promote only the
stopped exact candidate.

### 6 — add bounded ensure-ready

Implement the common command after the platform paths are known. An adapter
declares whether it supports start-only readiness or a named idempotent repair.
The result records initial doctor state, requested actions, completion status,
final doctor state, and uncertainty. Unsupported or protected boundaries
return typed refusals.

### 7 — prove disposable outcomes

For each newly proven stopped shared ready base, acquire one isolated UTM
workspace, create a harmless target-local marker, release it, start the
persistent target, and independently verify the marker is absent. Cleanly
shut down and leave receipt inventory empty.

### 8 — close evidence and policy

Update the owning topics, the cross-platform tactical follow-up, platform
guides, and private inventory. Run portable/native/platform/private-inventory
tests, audit the public diff, commit coherent stages, push both repositories,
and verify hosted CI.

## Validation

- `python3 bin/check --portable`
- `python3 bin/check --native`
- Windows ARM64/x64 publishes and `dotnet format --verify-no-changes`
- Windows and Linux platform static/smoke tests
- dotfiles private-inventory tests
- common doctors before and after cold reboot
- exact-source portable/native execution inside Windows
- one marker-based disposable outcome per proven UTM ready base
- empty workspace inventories and stopped persistent targets at handoff

## Result

Completed on 2026-08-11 without creating, deleting, renaming, or compacting a
VM. The capacity audit rejected a full Windows clone because it would cross
the configured storage reserve; the existing retained Windows and Linux
candidates were repaired and promoted in place instead.

The common client now exposes explicitly mutating `target ensure-ready`, fresh
`target validate-candidate`, and stopped `target prepare-promotion` results.
Readiness records initial/final doctor states and bounded actions, starts only
through the adapter-declared `up` operation, and reports repair required rather
than guessing a running-target bootstrap. Promotion rejects workspace handles,
requires a minimized exact candidate assertion with no receipt ownership,
observes full running readiness, cleanly shuts down, and repeats the identity
assertion in the off state. Private inventory remains the only role authority.

The retained Windows candidate required one bounded outer recovery after both
ordinary SSH and the first normal provider shutdown path were unavailable.
The guest-agent path staged the checked-in idempotent OpenSSH bootstrap; an
explicit elevated PowerShell launch restored key-only SSH and automatic
services. Thereafter every operation used the inner route. A changed Windows
boot epoch returned SSH, the interactive desktop, resident, UI Automation,
capture, and input with a new generation. The exact committed archive matched
SHA-256 in the guest and passed portable and Windows-native checks after the
stateful development appliance received public Python 3.13 and .NET 8 tooling.
The run also fixed the check runner to use a per-process PowerShell policy.
All named guest and host staging artifacts were removed.

Linux needed no outer recovery. Its static device-activated QEMU guest-agent
returned on guarded start, followed by auto-login GNOME Wayland, AT-SPI,
resident, capture, and input with outer UI prohibited. The platform reboot
observed a changed boot ID and a new resident generation. A later persistent
restart exposed a race where guest execution preceded the first UTM IPv4
sample; the provider now polls addresses within its existing boot timeout, a
delayed-address fixture covers the behavior, and the live off-to-ready retry
passed.

Both exact candidates produced a fresh running-ready validation and clean
stopped promotion handoff. Private policy now lets each single stateful VM
double as its ready base, permits one temporary workspace, reserves 64 GiB,
and prohibits implicit full-copy fallback. Each base then passed one UTM
disposable rehearsal: a target-local marker existed during the isolated run,
was absent after release and persistent restart, and the receipt inventory
ended empty. Both persistent targets were left stopped.

Final validation passed the portable corpus, macOS native checks, Windows
provider smoke tests, Linux provider static tests including the delayed-IP
race, Windows ARM64/x64 publishes, and private-inventory unit tests. The live
Windows archive independently passed the portable and native build corpus from
inside Windows. Public diff inspection found no concrete target identity,
endpoint, account, path, receipt, or captured UI.
