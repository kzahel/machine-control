# Tactical 018: Appliance Readiness and Promotion

Status: active.

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

Active. Record exact implementation, minimized live evidence, deviations, and
remaining manual or storage work here before completion.
