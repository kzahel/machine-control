# 125 — Agent capability baseline and instruction evaluation

Status: active. Both requested profiles completed guest YA/AAR qualification;
the runner now collects both transcript formats and verifies effective settings.
Seven scenarios and three CLI instruction arms are implemented. Sol/CLI has a
valid passing smoke on every scenario; Opus/JS TextEdit save also passed. The
frozen baseline has completed its first 35-cell round after evaluator repairs:
33 passed, with a policy refusal and an agent discovery failure. All 36 attempts
(including one invalid oracle attempt) retain their costs and reviewed traces.
The original Python smoke passed 13 of 14 cells and stopped before repetitions.
The revised candidate passed its native activation/capture probe and all fourteen
agent smoke cells. Repeated baseline/candidate rounds are running; no repeated
broad baseline or candidate acceptance is claimed.
Owning topics: [operational workflow automation](../../topics/operational-workflow-automation.md),
[unified desktop client](../../topics/unified-desktop-client.md).

## Objective

The operator wants realistic developer workflows validated through guest YA,
with Codex GPT-6.1 Sol and Claude Opus 5.5 at medium effort and normal speed,
before implementing the supported session. Measure success, time, model tool
calls and tokens, and test whether better entry instructions reduce discovery
cost compared with simply pointing an agent at the repository.

Extend the existing evaluator. [Tactical 124](124-native-behavior-and-efficiency.md)
is a completed native study and one-task pilot, not this broader acceptance gate.

## Completion conditions

- Every scenario has deterministic setup and an independent application-effect
  oracle, including negative checks that reject an unchanged or wrong result.
- Both requested models complete a guest smoke through the intended AAR route;
  requested and effective model, effort and speed are independently retained.
  Missing or mismatched settings make a trial unqualified for that comparison.
- Each supported model/route/scenario cell has three valid baseline repetitions,
  with failures and infrastructure errors distinguished. Known product failures
  are results; missing infrastructure or a defective oracle is not a baseline.
- Instruction variants, tooling, source, apps and model settings are pinned.
  Raw transcripts, usage and intervention evidence remain private.
- Baseline inputs are frozen in an isolated checkout before session development;
  results are frozen before candidate acceptance. Candidate
  comparison uses the same conditions and reports every scenario, including
  regressions and unsuccessful-attempt resource use.

## Boundaries

Use disposable claimed guests, provisioning journals and verified credential
handoff. Guest-local YA launches agents; a host tunnel reaches YA loopback
(port 3400 in the existing appliance), and model traffic uses the existing
loopback AAR reverse tunnel. Do not launch a benchmark on the personal desktop.
Never change the sealed base during a batch or expose account/router secrets.
Model effort labels are provider-specific, not equal compute budgets.

## Scenario corpus

| Scenario | Current state | Required effect oracle / coverage |
| --- | --- | --- |
| Load unpacked extension | Existing fixture | Upgrade path-presence check to enabled extension plus a fixture-page behavior change; reject a disabled or merely registered extension. |
| Upload local file | Existing fixture | Upgrade filename-only check to received bytes/hash; retain native picker and direct upload as explicitly separate capability variants. |
| Finder rename and move | Seeded contents, exact-byte oracle | Destination name and exact original bytes; old paths absent. Add duplicate-name collision as a later recovery variant. |
| TextEdit save | Existing, repeated pilot | Saved document content and format/path; current text containment check is the initial baseline. |
| System Settings option | Existing fixture | Persisted setting value with setup proving the opposite initial value. |
| App menu bar and sheet | Sol/CLI smoke passed | Use TextEdit Format/menu action and save resulting plain text; verify actual format/content. Review calls to establish menu use rather than a keyboard shortcut. Include cancel/confirm sheet handling. |
| Two windows and recovery | Sol/CLI smoke passed | Edit the intended document while another window is frontmost; reject stale references after a controlled window replacement; verify no wrong-window edits and record focus/cursor disturbance. |

The existing deterministic native corpus separately checks menus, background
input, delayed/burst/continuous updates and tree observations without a model.
Run those checks when changing native routing/settling; agent task success is
not a substitute for delivery/interference conformance.

Keep a small held-out set out of instruction tuning: for example Preview
export, a browser popup/extension reload and a different app's file chooser.
Implement their oracles before using them to claim generalization. Seed task
paths/content so instructions cannot hard-code answers.

## Ordered work

### 1 — qualify YA launch settings and usage collection

The inspected YA API accepts `provider`, `model`, `thinking` and `serviceTier`
on `POST /api/projects/PROJECT_ID/sessions`. `thinking: "medium"` maps to
explicit effort. The host catalog resolves `gpt-6.1-sol` and the Claude `opus`
alias to `claude-opus-5-5`; this is host evidence, not proof of guest access.
Prefer the exact model ID, with no silent alias/model fallback.
The [official Sol model page](https://developers.openai.com/api/docs/models/gpt-6.1-sol)
lists medium support; the inspected local Codex catalog reports a different
default from the API page, reinforcing the need for an explicit selection.

Qualify these profiles in the guest first:

| Profile | Provider/model | Requested execution |
| --- | --- | --- |
| Codex baseline | `codex` / `gpt-6.1-sol` | medium effort, normal speed |
| Claude baseline | `claude` / `claude-opus-5-5` | medium effort, normal speed |

Normal speed must be verified in the installed provider's effective settings;
omission alone may inherit a saved fast setting. Resolve the installed YA/CLI
normal-tier representation, disable fast overrides in the disposable guest,
and retain acknowledgements/config provenance. Record any AAR model/tier
rewrite. Do not infer effective effort from the requested body or zero reported
reasoning tokens. Fail qualification rather than silently calling it medium.
The earlier pilot inherited base settings and cannot be relabeled retrospectively.

Add explicit runner profiles and retain a sanitized request plus actual settings
in each receipt. Suppress optional recap/helper/suggestion work or account for
it separately. Freeze exposed tool inventories and instruction hashes. The
previous runner only collected Codex JSONL; the implementation now has a Claude
transcript path, completion semantics, usage deduplication and MCP registration.
Do not reuse the Codex parser or assume Codex MCP config enables Claude tools.

### 2 — establish comparable metrics

Record independent success, wrong-window effects, timeouts, route violations,
claim/grant refusals, retries, human requests and infrastructure/cleanup failures.
Separate transcript task time from setup/polling and record model tool calls,
serialized result volume and available provider-operation counts.

Report total input, cache reads, non-cached input, cache writes where reported,
output, reasoning where reported and total input plus output. Codex input
already includes cache; Claude's raw input excludes its separate cache classes.
Reasoning is an output breakdown and must not be added again. Use session totals,
not context-window size or a sum of repeated cumulative events. Deduplicate
Claude usage by actual API message/request, including streamed updates.
Missing counters remain unknown with coverage; tokenizers differ across models.

Show successful-task distributions and all-attempt token/time totals, including
failed attempts and invalid runs separately. Cost-per-success is total trial
resource use divided by successes, with complete accounting and zero-success
handling; never silently drop failed spend. Subscription tokens are not dollars.
Dollar estimates require pinned provider/tier prices and disclosed cache rules.

**Current:** `report_batch.py` exposes normalized successful and all-recorded
usage distributions and coverage. It reads a single batch and reports failure-separated resource totals and
all-attempt resources per success only with complete coverage. Cross-profile
comparison uses separately pinned batches.
Claude collection follows YA's resolved provider session ID and deduplicates
usage by API message ID. Raw usage stays available for later reconciliation.

### 3 — compare instructions without changing the runtime

Keep three versioned instruction arms, with identical tasks and route restrictions:

- **Discovery:** the ordinary repository-pointer instruction the operator uses.
- **Current guide:** the existing route/skill instruction (the Tactical 124 arm).
- **Quickstart:** one short entry point explaining doctor, exact claim lifecycle,
  app launch/addressing, observation, native panels and effect verification.

The quickstart is task-independent: no element IDs, task-specific click sequence
or oracle answers. Include one small generic working example and links for rare
operations. Avoid loading the entire research corpus to perform a UI task.
Measure documentation/help calls and tokens before the first useful UI action,
as well as whole-task success/time/tokens. Include instruction tokens in costs.

Tune on a declared development subset (extension, Finder and TextEdit), then
freeze instructions before confirmation on the remaining/held-out scenarios.
Compare the discovery/current-guide arms with quickstart on the same CLI first;
do not simultaneously change persistence, language and prompts. Promote winning
instructions to the real skill/agent entry point only after confirmation.

### 4 — run the baseline and candidate gates

First smoke each supported cell once to validate setup, model settings, tools,
transcript collection and oracle. Then run three seeded repetitions per cell,
serially within appliance limits. Start with CLI and JS prototype on both agent
families, plus Computer Use on Codex. Computer Use on Claude is unsupported
unless separately demonstrated; do not treat that missing cell as a failure.
Seven scenarios across those five cells and three repeats is 105 trials, so
keep smoke, instruction tuning and confirmation as separately bounded batches.
Do not start the full matrix before the smoke/accounting checks pass.

Freeze baseline inputs before Tactical 123's thin implementation slice. The
serial matrix may run from its isolated pin during candidate development;
complete and freeze its results before candidate acceptance. Rerun the
same suite for the supported Python session with equivalent claims/audit and
observation policy. A candidate must have no unexplained success/effect regression
on previously passing scenarios; speed or fewer tokens cannot offset a wrong
result. Investigate each new failure. Report median/range with three samples,
then use five repetitions on changed or noisy cells. Avoid population claims.
Only compare Python and JS language effects once their enforcement, operations,
output and observation policies match. Preserve the original unsafe-to-generalize
prototype label until then.

## Validation and final result

Thirty-three offline checks pass. Guest qualification completed one arithmetic
turn per requested model: Codex rollout model/effort and YA live standard-tier
selection agree; Claude native records report exact model, medium effort and
standard speed/tier. Codex's rollout omits speed, so its evidence does not attest
upstream billing. The prepared guest's YA remaps Claude's launch session ID;
the collector now follows `process.sessionId` rather than finding an empty file.

The original Swift window fixture compiled and ran. Its oracle rejected the
initial state, accepted a replaced/edited target, and rejected a changed protected
field. The current resident rejected a destroyed reference as `delivery_failed`,
not a typed stale-reference error. Upload content and extension behavior passed
positive controls and rejected the untouched state. Menu verifier controls
rejected missing/wrong-format results and accepted correct plain text; those
controls do not establish real menu interaction. A subsequent extension check
also requires a registered, non-disabled entry; its agent smoke passed below.

The first real Opus/JS TextEdit save passed (27.461 s, seven model tool calls),
with complete reported usage across seven API messages. Sol/CLI extension
installation passed the stronger oracle (85.585 s, fourteen model tool calls).
Both retained the qualified profiles and discarded their clones. Transcript
review found UI work on the assigned routes; Opus used read-only shell checks
to verify its saved file. These are smoke observations, not repeated estimates.
The collector now leaves session usage unknown if any observed Claude API
message lacks usage, instead of reporting a partial sum as a session total.
Finder verifier controls reject the initial state and extra bytes, and accept
the exact renamed/moved contents. Settings setup verifies the opposite value.

Sol/CLI upload and menu smokes also passed (80.783 s / thirteen calls and
111.369 s / sixteen calls). Transcript review confirmed native picker use and
actual TextEdit File/Format menu actions with the conversion sheet. The window
smoke was invalid: a missing plist heredoc terminator swallowed the fixture's
launch commands while Bash returned zero. The fixture now verifies its process,
initial values and both visible windows; shell parse warnings fail an offline
check. The corrected fixture remained live across separate SSH calls and its
initial oracle rejected the untouched state. The agent rerun is described below.
Oracle infrastructure errors now stop a batch after evidence collection and
cleanup, and the window fixture retains diagnostic state privately.

The corrected window agent rerun passed, as did the remaining Sol/CLI Finder,
Settings and TextEdit smokes. All seven CLI scenarios therefore have one valid
passing calibration trial. Window interference counters include fixture launch
and task activity sampled every 20 ms, not an attribution of every transition
to the agent. The repeated campaign has separate provider manifests and freezes
its older client/fixtures independently of the Python candidate. Its first
round is a review gate before subsequent repetitions.

Three instruction arms are versioned, including the task-independent CLI
quickstart. They have not yet been compared. Seven-scenario agent smoke and
repeated multi-model baseline remain the gate before candidate acceptance.
Private route reviews are now bound to transcript hashes and distinguish
oracle/profile passes from reviewed route-conforming passes. Explicit call
annotations record discovery overhead and the available pre-UI usage checkpoint;
the latter is not exact causal token attribution. The first four campaign traces
were reviewed as route-conforming. The remaining matrix is still pending.

### Evaluator repairs during the first round

The extension trial exposed conflicting evidence: its fresh-page screenshot
showed the seeded title and the agent's UI tree showed an enabled extension,
but the oracle reported failure. It read Chrome's asynchronously written
preferences only once. The repaired oracle polls registration and fresh-page
behavior together, records each separately, and treats unreadable or conflicting
evidence as unqualified. Live requalification confirmed registration initially absent, then present
after 5.1 seconds while behavior was already correct. The original attempt
must not be counted as a product failure or silently changed into a pass.

A separate Opus/window trial passed its effect oracle but the parser counted
`isMeta: true` image-size metadata as another user request. The native transcript
contains the final `end_turn`; this was a parser defect, not incomplete output.
The parser now excludes internal metadata from user-task counts and retains
real additional user turns as unqualified. Reanalysis can recover its duration
without rerunning the model; preserve the original receipt and parser provenance.

Forty-two offline experiment tests pass, including delayed registration,
disabled/wrong-path extensions, inconclusive evidence and image metadata.

Campaign continuation now snapshots prior receipts and reviews into a new
manifest, retains invalid-attempt costs, and retries only unqualified cells.
Qualified product failures are never retried to improve a score. Source changes
require individually declared evaluator paths; runtime and prompt changes must
start a new comparison. The recovered Opus/window duration is 65.114 seconds.

A recovered Codex capacity error exposed another accounting defect: summing
active turn durations omitted YA's twenty-second retry backoff. Elapsed agent
time now spans first start to last completion; active durations, inter-turn
gaps and provider errors are separate. A terminal unresolved provider error is
unqualified. Explicit report-time reanalysis preserves original receipts and
records parser/input hashes, including for carried attempts. The upload example
was 52.169 seconds elapsed, versus 32.213 active; two earlier campaign attempts
also had capacity backoff. These waits must remain in efficiency and cost
accounting. Forty-three offline experiment checks pass.

The first-round traces also distinguish observation ergonomics from native
capability. One CLI Settings attempt needed a deeper snapshot to expose the
Always radio control; the candidate's default depth already covers it. One
Opus/CLI extension attempt instead recovered through window capture and
coordinate input when its semantic snapshots omitted the page controls.
Neither observation proves a permanent native AX omission. Claims were released
and independent effects passed. These combined interface differences must not
be attributed to persistence or language alone.

The first qualified unsuccessful cell was Computer Use extension loading. The
agent enabled Developer mode, then reported a policy requirement for fresh
confirmation before non-marketplace installation and stopped in the unattended
trial. Its native transcript contains `RESULT: blocked`; YA's summary text was
empty. The oracle correctly found no registration or behavior. This is an
unattended-workflow refusal, not evidence that the native API cannot install an
extension. Preserve it in success/cost accounting and do not silently retry or
weaken provider consent rules to improve the score.

The second repetition installed the extension and passed both effect checks,
but the delivered tool instructions contained the same action-time confirmation
requirement and the trace had no fresh confirmation. Record an effect pass
with a confirmation-policy violation, not a clean unattended-workflow success.
This is variation in model adherence, not evidence that the native API lacked
the capability in the first run. Review annotations and reports now separate
confirmation compliance from route adherence and effect success; omitted policy
reviews remain unknown. All 51 offline experiment checks pass. Original
receipts and resource costs remain unchanged.

Interference scope is bounded: the counters describe the guest fixture, not
the controller desktop. The existing Mac provider launches a graphical Tart
runner; benchmark control remains entirely guest-native and never manipulates
that window. Controller-side startup/focus effects and a headless operating
profile need separate qualification. Keep lifecycle mode fixed within this
campaign and do not claim controller noninterference from guest measurements.

One JS window-recovery trace showed misdirected input despite final success:
an unprinted tree refresh rebound the displayed Replace button's number to
a text field. The next press clicked the field; subsequent visible observations
and recovery completed the task. The final-state oracle does not certify every
intermediate action. Keep this incident as a prototype identity/output hazard;
[Tactical 123](123-persistent-agent-session.md) records the Python refusal test.
The second Sol/JS window repetition reproduced that same mistargeted press,
then recovered to a passing final state. Retain both the task pass and the
intermediate targeting failure in the comparison.

Sol/JS TextEdit save stopped after two tool-discovery calls without any UI
operation. Both filters exclude the pinned tool metadata: JavaScript word
boundaries do not separate underscore-delimited names, and the description did
not contain either searched phrase. Empty filtered lists are not proof that the
server failed to register. Retain this as a discovery failure, with unfiltered
availability unknown, rather than rerunning it as an infrastructure repair.
This supports testing a precise, task-independent entry instruction separately
from runtime changes; it does not establish that such an instruction wins.


### First-round review gate

All 35 model/route/scenario cells have a qualified result, with 33 effect passes.
Both CLI profiles and Opus/JS passed all seven scenarios. Sol/Computer Use passed
six with the extension policy refusal above; Sol/JS passed six with the TextEdit
discovery failure above. Every attempt has reported usage and a hash-bound route
review; every disposable workspace was discarded without a release error.
One additional attempt remains invalid because of the repaired extension oracle,
and its resources remain in the all-attempt totals.

Report-time reanalysis includes provider recovery backoff and records parser and
input hashes without replacing original receipts. The first-round report has
one qualified observation per cell, so it is a setup/coverage gate, not a median
comparison or a population reliability estimate. Baseline repetitions remain
paused while the pinned Python candidate runs the corresponding fourteen-cell
smoke. No model, prompt, runtime or lifecycle changes enter the frozen baseline.

The candidate audit further bounds causal interpretation: its first UI call
opens a retained owner session, including the resident's configured ten-second
admission notice. Reviewed CLI traces use the existing direct grant path, with
claims and command audit but no retained owner session. Python therefore changes
the control lifecycle as well as persistence and observation output. Keep the
notice in elapsed time and do not call this an isolated persistence benchmark.
The JS prototype additionally omits claims/controller audit. A later parity
experiment must hold these contracts fixed before attributing language effects.

A verifier review added six direct menu-oracle controls. A missing or non-file
source previously raised an infrastructure error after otherwise correct output;
it now produces a failed source-preservation verdict. Missing output, changed
source and rich-text output are also rejected, while intact source plus correct
plain text passes. All 49 offline experiment checks pass. Existing qualified
positive results are unchanged; apply this evaluator-only repair through a
recorded campaign continuation before repeated runs, without changing clients,
task prompts or setup. The shorter revised Opus menu trace used the save panel's
Keep changes in original document checkbox, not activation or duplicate/cancel;
it cannot establish an activation speedup.


### Revised candidate smoke and repetition gate

All fourteen revised Python cells passed, with complete reported usage,
route-conforming reviews and normal ownership closure before guest disposal.
The original 13/14 candidate remains a separate development observation with
its failure and recovery costs. This is coverage evidence, not repeated
performance or general desktop acceptance.

Before repetitions, evaluator-only continuation carries the menu-source repair
into both matrices and the already-qualified elapsed-time/terminal-error parser
into the baseline collector. Earlier receipts are preserved and explicitly
reanalyzed. Client behavior, prompts, fixture setup and model profiles stay
pinned. Remaining rounds alternate baseline then candidate, retaining each
matrix's seeded order and using one guest at a time; round-boundary pause guards
prevent an unattended overlap. Baseline completion still gates final candidate
acceptance. Report distributions and all-attempt accounting only when the
corresponding planned batch is complete.

The second-round development traces reproduced a shell-wrapper failure in
Opus/CLI Finder and extension loading: a scalar containing the executable and
arguments was treated as one command by Zsh. Both agents recovered with a shell
function. The untested quickstart arm now gives that portable function example
and explains its per-tool-call lifetime. This is instruction development from
the declared subset, not a change to the running current-guide baseline or a
claim that the quickstart improves results. The example's argument forwarding
was checked in both Bash and Zsh without controlling a target.

### Second-round baseline gate

The baseline completed two repetitions of all 35 cells: 68 of 70 qualified
trials passed their effect oracles, including 35 of 35 in the second round.
One of those effect passes has the confirmation-policy violation above, and
both Sol/JS window passes contain an intermediate mistargeted action. These
counts therefore do not certify clean workflow conformance.

All 71 recorded attempts, including the earlier invalid oracle attempt, have
hash-bound route reviews, reported usage and confirmed guest disposal. Explicit
report-time reanalysis preserves timing corrections and all attempt costs.
The corresponding Python second round then passed all fourteen effect oracles.
Its cumulative 28 trials have complete usage, route-conforming reviews and
normal ownership closure before disposal. Recovery from stale references and
menu activation remains visible in the costs; final success is not evidence
that these workflows were frictionless. The baseline third round is running
while Python remains paused after cleanup; its final round follows.

During the third round, report review exposed that retained guest focus/cursor
counters were absent from aggregate reports. Reporting now includes their
distributions, coverage and sample intervals, including failed/invalid attempts
without treating missing data as zero. This changes no trial behavior. The
report labels fixture-startup inclusion, missed-transition risk and the absence
of controller-host measurement. All 52 offline experiment checks pass; the final
client tree also passes 285 client tests and strict typing of the session modules.
