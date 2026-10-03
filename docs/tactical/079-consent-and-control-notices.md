# Durable Mac consent and control notices

Status: implementation and deterministic checks complete; native observation
and one independently verified AX action passed in the Mac appliance. Physical restart, takeover and presentation
acceptance remain part of Tactical 074.
Owning topics: [access admission and pause](../../topics/access-admission-and-pause.md),
[Mac locked use](../../topics/macos-locked-use.md).

## Objective and boundaries

Keep the operator's Until I Turn It Off choice separate from volatile grants,
queue entries and control sessions. Present polite pending control with
resource-wide deferral and distinct Pause, Resume, Cancel and Stop actions.
Use the existing native operator boundary and permission grants.

This slice persists Mac local consent and pause choices only. The same-console,
same-user, same-boot binding excludes fresh login and preboot use. Windows
retains timed, memory-only approval; its notice uses the existing desktop
profile. No authenticated YA delegation or shared outer reservation is claimed.

## Ordered work

1. Store bounded local consent and manual pause/deferral in owner-only files,
   using atomic replacement. Never persist grant IDs, offers or control sessions.
2. Derive fresh grants after identity, permission, audit and helper checks.
   Preserve exact remaining timed lifetime; fail closed on uncertain timing.
   Stop clears saved consent even before readiness permits a live grant.
3. Add native nonactivating Mac notices and the shared Windows notice window,
   with truthful caller assurance, countdown and maximum control duration.
   Start now cannot replace an active session or bypass composed blocks.
4. Expose policy/status and operator actions in the desktop UI and native Mac
   shell. Reset pending notices after policy/desktop changes; skip notices for
   prepared locked use. Graceful Quit ends sessions without revoking consent.
5. Bound asynchronous Mac reply buffering so large snapshots survive socket
   backpressure without blocking the operator or truncating replies.
6. Carry trusted in-process Windows ownership through the native safety gate.
   Public JSON cannot forge this context; lower-level dispatch rechecks it.

## Validation and result

**Current:** Mac consent fixtures cover private files, symlink refusal, exact
console binding, expiry, clock disagreement, restart, independent deferral,
Stop before restoration, fresh grant IDs and one-second remaining lifetime.
Admission fixtures cover notice reconfiguration, idempotence and refusal to
replace active control. Mac resident tests and platform static smoke pass;
ARM64 bridge and x86_64 resident compile. TypeScript/build and native Rust
checks pass. Windows contract tests, formatting and ARM64/x64 publishes pass.

**Current, native observation:** the claimed Mac appliance received the new
resident through its normal deploy command. Doctor reported ready. The common
standalone control client admitted a live owner and returned native window
observation. A separate fixture trial took a native snapshot and performed one
AX button action; independent fixture state increased exactly once. Connections
and the fixture process were closed afterward. The initial large-snapshot trial
exposed nonblocking reply truncation; the corrected bounded writer passed both
the socket-backpressure fixture and the repeated native trial. This is remote
inner semantic control evidence, not hardware takeover or keyboard acceptance.

**Open:** physical signed-app persistence and lock/quiet trials, notice focus
and assistive-technology checks, native Windows presentation, Windows durable
consent, authenticated agent integration and composed outer recovery. The
coordinating [Tactical 074](074-access-admission-and-pause.md) stays active.
