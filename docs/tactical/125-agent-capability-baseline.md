# 125 — Agent capability baseline and instruction evaluation

Status: active. Both requested profiles completed guest YA/AAR qualification;
the runner now collects both transcript formats and verifies effective settings.
Seven scenarios and three CLI instruction arms are implemented. Sol/CLI has a
valid passing smoke on every scenario; Opus/JS TextEdit save also passed. The
frozen 105-trial campaign is active, with a review gate after its first round.
Broader model/route coverage remains pending; no broad baseline is claimed.
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
| App menu bar and sheet | Added; agent smoke pending | Use TextEdit Format/menu action and save resulting plain text; verify actual format/content. Review calls to establish menu use rather than a keyboard shortcut. Include cancel/confirm sheet handling. |
| Two windows and recovery | Added owned app fixture; agent smoke pending | Edit the intended document while another window is frontmost; reject stale references after a controlled window replacement; verify no wrong-window edits and record focus/cursor disturbance. |

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

Twenty-five offline checks pass. Guest qualification completed one arithmetic
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
also requires a registered, non-disabled entry and still needs agent smoke.

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
initial oracle rejected the untouched state. An agent rerun is still required.
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
repeated multi-model baseline remain the gate before session implementation.
