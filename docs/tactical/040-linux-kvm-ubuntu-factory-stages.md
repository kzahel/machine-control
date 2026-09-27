# Tactical 040: Linux KVM Ubuntu Factory Stages

Status: in progress.

Topics: [`linux-resident-control`](../../topics/linux-resident-control.md)
and [`operational-workflow-automation`](../../topics/operational-workflow-automation.md).

## Objective and completion conditions

Give the native x86_64 libvirt Ubuntu factory an observable path from an
unused destination and NoCloud seed to a claimed, provisioned, stopped
candidate. The inspector reports stable states and explicit next commands;
the agent makes each mutation and rechecks the result. Completion requires
focused refusal tests, the Linux smoke suite, and one fresh candidate through
cloud-init, resident bootstrap, seed detachment, exact-source certification,
and clean stop.

## Boundaries

- This slice covers the Linux controller's libvirt/KVM route. UTM remains open.
- Precreation has no target claim because the candidate has no UUID. After
  creation, pin exact identity, run doctor, and acquire a claim before use.
- A plausible QCOW2 shape does not prove source provenance or architecture.
  The actual native KVM boot and guest checks provide later route evidence.
- The seed creates a locked key-only login. Its matching controller private
  key remains in a mode-0600 local secret store; no password is invented.
- Stage inspection does not mutate the VM or infer a guest effect from command
  delivery. An unresponsive guest agent and running cloud-init stay waiting.

## Ordered work

### 1 — inspect native media and unused destination

Check the QCOW2 input, exact key-only NoCloud seed content and private file
mode, KVM host, dedicated pool, and unused domain/volume names.

### 2 — explain claimed guest progression

Expose identity, power, QEMU guest-agent, current-boot cloud-init, full
resident doctor, exact NoCloud attachment, and final stopped source as
read-only stages. Keep bootstrap, shutdown, and media removal as explicit
guarded commands.

### 3 — validate a fresh Ubuntu candidate

Run focused stage/provider tests and the platform smoke suite, then drive a
separate candidate through each stage, certification, and cleanup under one
renewed claim. Record observed results and any remaining boundary.

## Result

Pending fresh-candidate completion. Native preflight passed using local
private media, the candidate was created and claimed, and its stage report
observed guest-agent readiness followed by completed NoCloud cloud-init in
the current boot. Resident bootstrap is in progress.
