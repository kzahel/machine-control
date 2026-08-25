# Windows Claimed Direct Transport

Status: active

Owning topics:

- [`target-use-claims`](../../topics/target-use-claims.md)
- [`unified-desktop-client`](../../topics/unified-desktop-client.md)
- [`windows-resident-control`](../../topics/windows-resident-control.md)

## Objective

Remove recursive claim, target-identity, lifecycle, and address discovery from
ordinary Windows administration and resident-control calls while preserving
the exact-target and exclusive-use guarantees introduced by Tactical 026.
An outside agent should reach the already-ready target through one guarded
Windows adapter dispatch and a direct key-only SSH connection instead of
re-entering the standalone self-guarding SSH proxy.

## Completion conditions

- The common client still requires a live claim before meaningful Windows VM
  use, and the authoritative Windows adapter rechecks that claim before the
  requested operation.
- One guarded Windows operation performs no recursive `winvm` invocation from
  its SSH transport and resolves the provider target and guest connection only
  once inside that adapter dispatch.
- The optimized connector addresses the exact pinned provider identity,
  preserves the configured SSH host-key identity, never prints the private
  guest endpoint, and never invokes outer capture or input.
- Windows administration, resident control, artifact retrieval, WSL, and the
  optional WinApp comparison route use the optimized connector where their
  existing operation semantics permit it.
- The configured standalone SSH alias retains its self-guarding proxy for
  callers that enter outside an already-guarded adapter dispatch.
- Fixture tests prove claim enforcement, exact-target refusal, direct SSH
  option construction, no recursive proxy use, and unchanged stopped-target
  and role policy.
- A live claimed run records cold readiness separately from warm direct SSH,
  common OS, resident status, doctor, and artifact-path latency. The target is
  returned to its inherited power state and the claim is released.
- If connection setup remains a material fraction of warm operation latency,
  the slice adds an explicitly owned claim-scoped session or bounded batch
  transport. It must close on expiry, release, fencing-generation replacement,
  target-generation change, or transport failure; an ambient background
  `ControlMaster` is not acceptable.

## Boundaries

- Do not weaken exact UUID/role checks, key-only SSH, host-key verification,
  claim expiry, fencing, or adapter-side claim enforcement.
- Do not treat a caller-provided environment flag as proof that validation
  already occurred.
- Do not expose the resolved address in common JSON, logs, documentation,
  arguments returned to the caller, or committed fixtures.
- Do not make a Windows-native agent session, RDP session, or visible UTM
  console a prerequisite for ordinary outside control.
- Do not broaden the resident into a generic network listener or arbitrary
  privileged service.
- Keep the public SSH proxy safe when invoked directly. The optimized path is
  an internal handoff within the authoritative adapter, not a replacement for
  the independently callable guard.
- Do not add persistent connection machinery merely to improve a small
  residual handshake cost. Prefer the smallest lifecycle-owned mechanism
  justified by live measurements.

## Work

### 1 — characterize claim and transport composition

Record the current dispatch sequence and add fixture observability for claim
checks, exact provider assertions, power/address discovery, SSH options, and
remote command delivery. Distinguish coordination-store latency from provider
resolution, SSH handshake, guest shell startup, and resident execution.

### 2 — add one guarded direct connector

Give the UTM Windows provider an internal connection operation that verifies
the exact target and role once, performs the existing bounded start/address/
port readiness behavior, and then executes OpenSSH against that resolved
address while retaining the logical alias as the host-key identity. Route the
ordinary Windows administration and installed-resident wrappers through it.

### 3 — preserve standalone and comparison routes

Keep the configured SSH alias proxy self-guarding for independent use. Move
the optional WinApp comparison client to the same guarded internal connector
without weakening its direct-entry claim check. Leave maintenance, bootstrap,
certification, and recovery on their existing deliberately bounded paths
unless measurements show the same safe composition applies.

### 4 — decide session reuse from evidence

Compare fresh direct connections with a bounded shared connection after the
recursive provider work is removed. If the remaining difference materially
affects agent iteration, implement an explicit claim-scoped session or batch
surface with deterministic ownership and teardown. Otherwise record the
measured reason for deferring persistent machinery.

### 5 — prove live outside control and cleanup

Run the selected-target doctor, acquire a truthful exclusive claim, preserve
the initial power state, and exercise warm administration and resident calls
without outer UI. Confirm that the actual route remains target-native and that
claim conflict/refusal behavior is unchanged. Restore the initial power state,
release the claim, and retain only minimized timings and outcomes.

### 6 — publish the resulting contract

Update the owning topics with the implemented transport shape, performance
evidence, remaining limits, and session-reuse decision. Mark this tactical
complete only after portable, provider, Windows static/smoke, and proportional
live validation pass.

## Validation

- `python3 -m unittest discover -s tests/client -v`
- `python3 -m unittest discover -s providers/claims/tests -v`
- `bash platforms/windows/tests/smoke.sh`
- `python3 bin/check --portable`
- `python3 bin/check --native`
- a claimed live Windows timing and resident-status probe with outer UI unused;
- clean shutdown only when this caller started the target, followed by prompt
  claim release and an empty workspace receipt check.

## Result

Active. The originating live diagnosis measured approximately 0.4 seconds for
a fresh SSH call to an already-resolved guest, 6.1 seconds through the
self-guarding alias, and 8.3–10.4 seconds through the complete common Windows
administration path. A correctly owned shared SSH connection reduced the
already-direct call only to approximately 0.23 seconds. These measurements
make recursive provider validation the first implementation target; session
reuse remains conditional on the post-change residual.
