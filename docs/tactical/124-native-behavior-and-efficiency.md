# 124 — Native behavior and efficiency investigation

Status: complete, bounded research campaign. Native probes, measurement
hardening and a focused five-repeat agent pilot are complete. Production
session implementation and broader evaluation remain separate.
Owning topics: [unified desktop client](../../topics/unified-desktop-client.md),
[operational workflow automation](../../topics/operational-workflow-automation.md).

## Objective and completion conditions

The operator asked to front-load research into Computer Use's native behavior
and explain its efficiency before implementing the supported session. Extend
the existing comparison harness rather than build a second agent evaluator.

Complete when measurement is reproducible, the four native questions below
have results or explicit instrumentation blockers, and an evidence-backed
implementation order is recorded. Separate mechanism inference, observed
behavior, and application effects. A pilot does not prove population success
rates or general application compatibility.

## Boundaries

- Use dedicated disposable macOS workspaces with doctor, claims, provisioning
  journals, verified credential handoff, and finally-style release. Never use
  the controller desktop as the experiment target.
- Use genuine Computer Use with its normal policy wrapper. Do not patch,
  re-sign, or weaken platform protections to attach a tracer.
- Proprietary extracts, exact upstream pins, and detailed tracing belong in
  the private spike/local research store. Public code is original fixture and
  measurement infrastructure; public findings are sanitized summaries.
- Keep MC claims, grants, audit and generation checks in supported routes.
  Label the direct-socket prototype's bypass explicitly in comparisons.
- Freeze revisions and fixtures within a batch. Agent trials and deterministic
  native probes answer different questions and have separate results.

## Ordered work

### 1 — make route measurements reproducible

Pin the guest checkout to a controller-selected commit; record fixture hashes,
seed and execution order. Report actual transcript turn timestamps separately
from controller polling time, and fail closed on missing completion. Capture
tool calls, output bytes and available token usage without treating string
matches as native operation counts. Preserve unknown metrics as unavailable.
Exercise timeout, malformed transcript, setup and cleanup paths offline.

### 2 — probe native behavior without a model

Use an owned fixture with independent state/event output and another focused
window. Run repeated scripted operations with both providers where supported:

1. Background input: button, editable field, menu and sheet, with target effect
   and foreground/cursor/other-window observations.
2. Settling: delayed change, bursts, continuous updates and unchanged state;
   measure return time and freshness against fixture timestamps.
3. Tree work: cold, unchanged and single-element changes at multiple sizes;
   measure latency and output volume; use scoped native profiling when allowed.
4. Action selection: accessible press versus a pointer-only control; distinguish
   fixture event evidence from inferred native implementation.

Record service/runtime versions and hashes privately. Probe profiler attach
capability before deeper traces. Compare traced/untraced behavior; sampled
stacks are not complete call counts, and absence from a trace does not prove
an API is unused. Keep all four questions visible even when blocked.

### 3 — repeat agent tasks and isolate changes

Keep the five existing tasks in the corpus. Begin this bounded campaign with
five repetitions per route of TextEdit save; retain broader task and model
coverage as the next evaluation gate. Report per-task outcomes, distributions,
timeouts and infrastructure failures separately. Freeze prompts/model settings;
do not aggregate failed tasks into a speedup. Add held-out tasks before claiming
generalization. Compare observation policy and output shape on an equivalent
session core before attributing differences to Python versus JavaScript.

### 4 — publish decisions and limits

Update the provider dossier and platform report with bounded live findings,
then the owning topic and Tactical 123 with the implementation order. Keep
private evidence locators out of the public repository. Commit measurement
improvements separately from findings.

## Validation

Offline harness regression tests; controlled guest fixture effects; independent
focus/cursor and non-target input observations; repeated timing samples; exact
workspace cleanup and private journal closure. No provider acknowledgement is
an application-effect oracle.

## Native execution result

**Current:** original AppKit fixture and sentinel, five repetitions per case,
produced 138 records through each provider; a further 33 records isolate MC's
compact projection at three tree sizes. Requests were accepted, but independent
menu-item effects failed for MC in all five repetitions. Pointer/text reached
the intended target while disturbing sentinel focus/cursor. Sky's corresponding
effects passed with no disturbance observed at the fixture's 20-ms sampling
resolution. The [platform report](../../research/platforms/macos.md#native-efficiency-and-background-effects)
owns the comparison; the [provider dossier](../../research/providers/sky-computer-use.md#deterministic-native-behavior-study-2026-10-14)
owns Sky findings and evidence limits.

**Current:** bounded syscall and stack profiling completed, including untraced
controls. Sampled stacks confirm batch/hierarchy reads and AX actions. User-space
API count probes failed at runtime despite exit zero and are explicitly invalid.
No platform protections were changed. The prepared guest already had SIP
disabled; protected attachment and exact private event-posting functions remain
open. One pointer workload became invalid when a text value changed the label;
it was corrected and rerun with workload-error rejection.

**Current:** thirteen offline regressions pass: nine for timing/waiting, two
for independent-effect reports and two for incomplete/invalid batch reports.
Swift fixture compilation and live fixture execution pass.
The 23 retained earlier agent trials all have matched completion events;
reanalysis found 0.2–9.4 seconds of polling excess. The new harness pins source,
fixtures and runtime identities and separates transcript duration from waiting.

**Current, cleanup:** the native workspace credential was stored mode 0600 and
verified through OpenDirectory with dedicated SSH stdin delivery. Owned fixture
and MCP processes were stopped and the controller workspace discarded. The old
guest CLI refused the attempted release syntax; discarding its VM destroyed that
guest claim store. The private journal records the distinction. The base stayed
unchanged and stopped. Detailed pins/methods are in the
[private spike study](../../../machine-control-spike/docs/sky-native-efficiency.md).

## Implementation order

1. Prove retained claim-aware dispatch plus compact stable observations/diffs.
   MC's reported resident work is a minority of the observed CLI interval;
   preserve authorization/audit while measuring client/adapter costs separately.
2. Qualify window-addressed pointer/text and exact background menu effects.
   Adopt only routes whose effect and interference checks pass per app family.
3. Compare explicit observation, observation per action and observation per
   snippet with bounded waits and effect predicates. Continuous change is not
   a reason to wait forever or declare completion from quietness.
4. Investigate batching/cache invalidation further only after measuring the
   first controls. An unchanged rendered tree still incurred native AX reads.
5. Compare Python/JS over equivalent enforcement and observation policy, then
   expand to held-out tasks and another agent family before broad packaging.

## Final result

**Current:** fifteen TextEdit-save trials completed, five per route, in seeded
order with one disposable clone per trial. All passed the independent saved-file
oracle, with no timeouts, invalid transcripts, infrastructure or cleanup
failures. Every recorded tool-call argument was reviewed: GUI work stayed on
the assigned route, with no direct file-writing shortcut.

| Route | Passed | Agent seconds, median (range) | Model tool calls, median (range) | Median output bytes |
| --- | --- | --- | --- | --- |
| Computer Use | 5/5 | 33.8 (27.8–37.0) | 5 (5–6) | 37,995 |
| MC CLI | 5/5 | 53.0 (46.8–69.8) | 8 (7–12) | 65,255 |
| Experimental JS session | 5/5 | 37.4 (32.9–38.1) | 5 (5–6) | 17,278 |

Timing uses matched transcript task events; calls count model tool invocations,
not native operations. Output bytes count serialized transcript tool results.
All transcripts identify `gpt-6.1-sol`; they do not expose a reasoning-effort
setting. Source, task files and installed runtime fingerprints stayed fixed.
Exact pins, transcripts, order and manual-review hashes remain private.

Two CLI trials first misdiscovered the claim-help grammar and recovered after
`claim_required` responses. The prototype also incurred application-launch
discovery. These are whole-workflow measurements including startup and command
discovery. The prototype omits claims/controller audit and changes output,
observation and batching behavior, so its difference cannot be attributed to
persistence alone. Five samples of one task/model are a pilot, not a general
success-rate or performance claim.

**Current, cleanup:** all fifteen workspace discards were confirmed, journals
closed with paired command records, and inherited credential files rechecked
as mode 0600 with matching canonical bytes. Final workspace inventory was empty,
the controller claim was available, and the base and golden copy were stopped.

**Decision:** proceed with the thin claim-aware session and compact observation
slice in the implementation order above. Retain all five existing agent tasks,
then add held-out applications and another model family. Cold-process/cache
behavior, paste/clipboard restoration, protected attach, reliable API counts
and exact event-posting mechanisms remain open; this study does not imply those
questions were resolved.
