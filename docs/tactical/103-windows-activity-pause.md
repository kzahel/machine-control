# Windows activity pause and quiet resumption

Status: implementation active; native VM validation pending.
Owning topics: [access admission and pause](../../topics/access-admission-and-pause.md),
[Windows desktop](../../topics/windows-desktop.md).

## Objective

Bring Windows desktop access up to the Mac activity-aware behavior: yield to
human input, retain consent, and require fresh ownership after interruption.
Keep task-end lock authority restricted to tasks that started locked.

## Completion conditions and boundaries

Ordinary keyboard and pointer activity pauses admission for 30 seconds of
quiet. Agent-injected input does not count as human activity. Manual Pause,
operator deferral, readiness, relock and activity uncertainty compose.
Covered takeover retains consent and waits for independently observed relock
and conservative session quiet. Owner-unlocked local use stays paused until
relock plus quiet or explicit Resume. No action or finite session is replayed.

Default-desktop low-level hooks do not supply secure-desktop semantics.
The independent SYSTEM guardian retains covered suppression and relock.
Session last-input observations can delay quiet after synthetic activity;
they never classify that activity as human takeover. Physical HID, remote-human
input, touch, noisy devices, sustained load and signed installed qualification
require separate evidence. No new public activity injection endpoint exists.

## Ordered work and validation

1. Add a reusable activity policy with independent pause reasons and fresh
   ownership/generation fences. Test boundaries and unknown observations.
2. Add target-native pass-through keyboard/mouse monitoring and conservative
   locked-session idle observation. Keep hook callbacks free of provider locks.
3. Expose operator status and compose covered takeover with existing cleanup.
4. Run formatting, desktop/unlock contracts, x64/ARM64 publishes, native monitor
   fixtures and real desktop covered/unlocked VM scenarios. Remove owned
   helpers/fixtures, verify appliance readiness and credentials, shut down and
   release the exact target claim.

## Result

Pending. Deterministic signals must be distinguished from genuine physical
input, and VM presentation evidence from physical hardware qualification.
