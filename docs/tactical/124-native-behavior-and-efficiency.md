# 124 — Native behavior and efficiency investigation

Status: active. Measurement and bounded experiments precede production session
implementation.
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

Use the five existing tasks as a pilot, initially five repetitions per route
where runtime availability permits. Report per-task outcomes, distributions,
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

## Final result

Pending.
