# Maintain the Windows desktop UAC helper across updates

This tactical belongs to the [Windows desktop](../../topics/windows-desktop.md)
and [native distribution](../../topics/native-distribution.md) topics.

Status: implementation and bounded Windows VM qualification complete.
Production-signed installer acceptance remains open.

## Objective

Carry the installed desktop UAC helper across signed per-user product updates
and preserve existing covered-desktop enrollment. The
[incident](../../gaps/2026-11-24-windows-uac-helper-upgrades.md) records the
0.7.5 mismatch and the loss of enrollment when using Remove helper.

## Completion conditions

- A legacy installation migrates in place with one administrator approval.
- A subsequent verified Windows update starts the matching protected runtime
  without another approval or credential prompt.
- A failed protected update leaves ordinary installation usable, preserves
  enrollment, and gives the operator an actionable helper status.
- An update cannot authorize an agent task. A previous explicit UAC choice
  can survive its deliberate update restart through a one-shot native handoff.

## Boundaries

The per-user installer requests maintenance of an already approved service.
The service independently authenticates the signed release manifest with the
product updater key. It verifies flat hashes of the full payload in
administrator-only staging. The typed update pipe exposes no path selection
or arbitrary execution. Service and resident retain an exact build match.
The credential vault, agent consent scopes, and protected relock authority
retain their existing boundaries.

macOS already maintains its approved helper through the native signed-update
path. Debian owns the Linux helper files and skips enrollment removal on
package updates. The Windows updater changes its separately copied service.

## Ordered work

1. Authenticate and stage complete helper releases. Add a bounded
   maintenance request from the ordinary Windows installer.
2. Switch to a versioned protected runtime, check the service's identity,
   and restore the previous service image on a failed health check.
3. Show actual helper readiness and preserve the protected option for an
   operator-initiated update.
4. Exercise a legacy hop and a prompt-free hop with signed fixture inventories
   on the claimed ARM64 VM. Verify tamper and downgrade refusal, and compare
   enrollment metadata across the hops. Separately qualify production-signed
   NSIS and protected task effects with the release acceptance harnesses.

## Validation

An exact claimed Windows 11 ARM64 VM started with the fixed-path legacy
helper and existing unlock enrollment. An elevated interactive actor
migrated it in place. An interactive Limited token then installed a second
fixture-key-signed inventory through the protected service and resolved the
exact matching helper. The previous build fell back to its bundled companion.
The service refused tampered bytes and a validly signed downgrade. A separate
signed payload with an unstartable executable exercised failed activation.
The service returned a refusal, restored its previous executable path, and
Windows reported a new PID for the restarted previous helper. Protected
enrollment file metadata stayed the same throughout.

Windows desktop and unlock authorization contracts passed on the VM. The
frontend build, release tests, and x64 and ARM64 runtime publishes passed on
the development host. Opus 5.5 reviewed the Windows trust, activation,
rollback, and handoff paths before the final fixture runs.

The signed build checks the exact installed installer payload through the
shipped verifier. A production-signed NSIS update, the live UAC-setting
handoff, protected task effects after upgrade, and a hard interruption
during a switch have separate acceptance cells.
