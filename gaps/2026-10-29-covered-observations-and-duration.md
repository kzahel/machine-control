# Covered control: delayed observations and early termination

Topic: `macos-locked-use`

Status: **Observed in interactive physical-macOS use; cause unisolated.**
This is an investigation record, not a runtime fix or conformance pass.
Private usage notes and claim audit events retain exact task attribution.
No private target configuration, UI contents or screenshots are included here.

## Observations

Two separate owner commands requesting 900 seconds ended with
`guardian_safety_unavailable` and `lockObserved: true`. Their reported
`transportElapsedMs` values were approximately 862,412 and 59,704. These are
owner-request transport durations including admission/cleanup, not isolated
measurements of active control. A fixed fifteen-minute cap does not explain
both. Subsequent inspection reported recovering or paused desktop control;
previously approved browser access remained available.

A later 600-second task showed another problem before its deadline. About
five and a half minutes into the command, status reported active control,
278 seconds remaining, a healthy helper, a last-positive sample age of 648 ms
and a 30-second silence limit. No pause or recovery reason was present.
Native AX reads of an editable browser field still showed the old value after
acknowledged edits. CoreGraphics key/text receipts named the intended
AXTextArea receiver but reported an unverifiable effect. Independent native
Computer Use reads also showed the old text at that point.

Clean completion and normal re-admission exposed edits that earlier reads
had not shown, including duplicate text from a retry. This does not distinguish
delayed application/input processing, stale AX data, stale presentation or a
combination. Do not automatically replay a write on this evidence. The
600-second command ended explicitly with `completed`, `lockObserved: true`
and a reported owner transport duration of 341,582 ms, before its deadline.

Normal completion/re-admission also produced read-only status races:
`control_generation_changed` and `locked_use_interrupted`. Fresh inspection
could subsequently show ready, healthy control, `lastEndedReason: completed`
and no pause. Separate those transition races from actual guardian failure.
A stale mutation must never be replayed to resolve an observation race.

Some attempts also contained caller mistakes: a helper retained an old claim,
and native global display points were mixed with another provider's window
screenshot pixels. These were corrected and must not be blamed on the broker.

## Bounded workaround

One exact replacement, clean completion, normal healthy re-admission and fresh
readback exposed the intended value. A Save draft accessibility action followed
by another clean cycle showed the exact value and a disabled save control.
Later edits used checkpoints and refused to save on locale/content mismatch.
This is costly task recovery, not proof of a repaired provider or a permanent
contract. Normal grant checks, covers and relock remained in place.

The task ultimately completed nineteen field comparisons after a full browser
reload. Its recovery path used 125 intentionally short 600-second owner
sessions; every recorded owner ended `completed` with observed lock. The
maximum measured owner wall time was 168,668 ms and maximum observed helper
sample age was 1,342 ms. During normal lifecycle transitions, read-only
inspection encountered 26 generation races and 13 interruption races before
fresh readiness settled. Private evidence retains per-owner timestamps and
693 minimized state observations. This successful workaround does not test
the full requested lease duration or establish that the earlier fault is fixed.

## Next diagnostics

- Compare an owned native text fixture and separate Chrome for Testing fixture
  outside and inside covered control. Use mock keychain and an owned profile;
  never launch the primary browser with a temporary profile.
- Add independent application-event, AX-value and rendered-frame counters.
  Compare ordering after input, after reads and across clean re-admission to
  separate input deferral from observation/presentation caching.
- Exercise 600- and 900-second leases. Record monotonic admission, start,
  deadline and end times, requested duration, and the component ending control:
  owner connection, resident, guardian or root broker.
- Retain a bounded private diagnostic ring of helper-positive sample age,
  watchdog deadline, owner heartbeat age, phase and transition generation.
- For input, record route, event origin/marker acceptance, focused role,
  coordinate space, display scale and target-generation metadata. Never log
  typed text, clipboard data, credentials or personal UI contents.
- Keep read-only status available during transitions, or return an atomic
  transition snapshot and generation. Test completion/start races separately
  from UI mutation admission.

No runtime code, watchdog behavior, security settings or helper installation
were changed during this investigation.
