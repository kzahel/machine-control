# Admission conformance moved to the shared engine

The former C# arbiter and its tests were removed at the Windows v2 cutover.
The policy corpus now lives in [admission.test.mjs](../runtime/admission.test.mjs)
and runs against the same TypeScript engine as the resident. It covers the
surface-mode matrix, atomic reservations, liveness, deferral, cooldown, approval
ceilings and stale ownership without a translated platform policy.

[WindowsDesktop.Contracts](../WindowsDesktop.Contracts/) verifies the native
adapter through the real shared process and live byte channels. The interactive
[activity actor](../WindowsUnlock.Contracts/ActivityLive.cs) qualifies native
notices and hooks; its physical signal is explicitly synthetic.
