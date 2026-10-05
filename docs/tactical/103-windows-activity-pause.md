# Windows activity pause and quiet resumption

Status: source and focused x64 VM qualification complete; cleanup complete.
Physical hardware, ARM64 live and signed installed qualification remain open.
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

**Current:** the desktop activity contracts exercise quiet boundaries,
independent manual/unknown pauses, retained consent, retired action fences,
fresh session identities, injection flags and local-use protection. Formatting
verification, desktop/unlock contracts, one-shot controller tests, x64/ARM64
publishes, TypeScript and the embedded desktop build pass.

The staged desktop runtime SHA-256 is
`9796d574916e3d97f304c747fa8ecdf01b350af78c42e962a8dca88f44712a85`.
The separate native fixture references the same monitor/policy source; its
runtime binary SHA-256 is
`e8187a3aa71c46c84b8a3786b4ff49dbff92ef2bf0c915039bf790c485cc6a5a`.

| Run | Passed checks | Evidence and limit |
| --- | --- | --- |
| Native monitor fixture | 14 | Native hooks independently observe injected keyboard/mouse flags without pausing; a deterministic in-process policy signal tests the real quiet timer and fresh ownership. This signal is not physical HID evidence. |
| Real desktop covered regression | 15 | Operator setup, one-shot unlock, underlying GDI capture, independent click/key counter effects and relock pass. Independent VM presentation is fully opaque. |
| Real desktop takeover | 26 | A claimed independent virtual-keyboard diagnostic pauses ordinary control without locking, preserves consent and composes manual Pause. Covered takeover relocks, retains consent and admits fresh locked ownership after quiet without unlocking or replaying work. |

The virtual keyboard diagnostic sends a bounded modifier down/up pair through
the exact owned hypervisor resource. It does not change controller focus and is
not an ordinary application-control route. All fixture observation, actions,
capture and credential delivery remain target-native. Direct provider steps
and private evidence are recorded outside automatic common-CLI audit coverage;
that history explicitly does not reconstruct raw provider bypasses.

The initial native fixture's zero-distance mouse event was accepted by the API
without sufficient hook observation. A one-pixel out-and-back pair corrected
the oracle. An initial combined takeover run raised the protected settings
window over the fixture during Pause/Resume; pointer dispatch correctly refused
with `self_target_refused`. Restoring the fixture arrangement produced the
passing full run. Neither correction weakened the product's guards.

The VM required bounded scheduler recovery at boot and after cold-login
transitions before fresh acceptance runs. No uncertain credential or mutating
product action was automatically replayed. These infrastructure interventions
are separate from the feature evidence. Actual hardware keyboard/mouse,
owner-unlocked local-use acceptance, touch, remote-human input, sustained load,
Winlogon activity classification, ARM64 live and signed packages remain gates.

Owned helper/controller approval, scheduled actors, guest staging, two exact
hash-verified captures and the final fixture marker were removed. The shared
parent ACL was restored and temporary controller key/proposal/preparation
material deleted. Baseline resident readiness and canonical stored credential
verification passed. The VM reached independently confirmed power-off in
38.1 seconds using its declared 30-second scheduler assistance; this is not
unassisted shutdown evidence. The exclusive claim was promptly released.
Raw diagnostic observations remain in ignored private evidence, outside Git.
