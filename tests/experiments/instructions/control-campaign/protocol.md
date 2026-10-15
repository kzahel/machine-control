# Bounded control campaign protocol

Current protocol; bounded live results are in the
[instruction comparison](../../../../docs/evidence/instruction-comparison-2026-10.md).
These are operator instructions. The existing discovery/quickstart agent prompts
are the treatments. No extra campaign prose is injected into their task prompts.

Prepare a private plan from a clean, committed selected checkout:

```sh
python3 tests/experiments/control_campaign.py plan \
  --source /private/frozen-checkout --output /private/control-campaign --seed 128
```

The default is Sol (`gpt-6.1-sol`), medium effort, standard/normal speed, CLI only:
one pilot block, then three paired blocks. Each block has discovery/quickstart
for two familiar scenarios (`load-unpacked-extension`, `textedit-menu`) and two
held-out scenarios (`finder-decoy`, `browser-form`): 8 pilot plus 24 paired
trials, 32 total. Development/browser, Finder and menu surfaces are represented.
`--include-current` adds an optional diagnostic arm. Provider/model/route options
are explicit expansions, never an automatic Cartesian product. Track current
provider availability and user constraints privately before starting a batch.

`plan` uses Git only; `report DIRECTORY` is offline. `run` is live and requires
separate authorization. Use `run --help` for required private target, SSH,
project and credential-file options. Never put secret values into arguments.
Run serially; never run two drivers against the same appliance.

The campaign invokes the selected checkout's `route_comparison.py` CLI once per
cell, with explicit revision/profile/route/arm/seed/task and `--task-root`.
Familiar tasks use `tasks/`; held-out tasks use `control-scenarios/`, without
changing the existing task registry. The selected runner must implement tracked,
source-pinned `--task-root` support. `--instruction-file` is unnecessary because
the campaign deliberately preserves the runner's existing instruction arms.
Each invocation retains the runner's journal, doctor, isolated workspace/claim,
secret handoff, oracle, transcript, usage, audit and disposal. The runner checks
the effective model/effort/speed; the campaign also checks receipt identity.

`run --runtime-config-file /private/selected-runtime.json` optionally supplies
an already selected, privately startup-probed genuine runtime configuration.
It forwards that exact controller file to the runner through the same option;
it does not reconstruct configuration from the environment or cache discovery.
The file must be nonempty, regular (no symlink), mode 0600 and outside the source
checkout. The campaign records only its canonical private path and SHA-256 in
private `runtime-config.json`, never its contents or environment values.
Its path/hash are pinned from the start, revalidated before every cell and
retained in each private attempt, including a refused dispatch. Pilot review
hashes include the config pin. Paired stages require the same selection; do not
add, omit or replace it after trials start. A file/mode change or disappearance
stops scheduling before the next runner call. The campaign-wide installed-runtime
fingerprint gate still applies independently. Without the option, the existing
runner default stays unchanged and no runtime-config pin is created.

The source must remain clean at the fixed commit before every cell. A selected
checkout must include the campaign fixtures and runner interface in that same
commit. Each cell has a private existing-runner batch below its own directory.
The runner repetition index is always 1; the campaign's block number is stored
in the plan. Runner seed = campaign seed + block index - 1, making fixture bytes
identical across arms/routes within each task/block. The seeded shuffle mixes
arm order within each block. There is no automatic retry or resume. Existing
cell directories cannot be overwritten. Failed product effects remain results;
invalid/profile/cleanup failures preserve their receipts and stop scheduling.
An exception before a receipt is retained with unknown usage/disposal.

The first pilot cell pins the installed-runtime identity in the private
campaign-wide `runtime-reference.json`. Every cell's observed `runtime.json`
and batch reference must match it, across both pilot and paired stages.
Missing, malformed or drifting fingerprints retain their attempt and evidence
but stop scheduling; a later cell cannot establish a replacement baseline.
Fingerprint status remains separate from effect and route review. The aggregate
shows status counts and reference fingerprints. Changing retained runtime
evidence is refused during report loading.

Run `--stage pilot` first. It exits after the pilot. A private `pause` file
pauses before the next trial; remove it to resume. A private `stop` file or
SIGINT/SIGTERM stops after the active runner finishes cleanup. Each runner is
owned in a separate process session/group, so terminal Ctrl-C or a signal sent
to the parent group cannot interrupt its cleanup. The parent waits and reaps
the child normally before stopping scheduling; it does not detach and exit.
There is no
continuation of a partially executed stage: inspect and create a new plan.

Review pilot transcripts using existing `review_trial.py`, including route and
confirmation-policy judgments, oracle independence and cleanup. To open the
paired gate, write private `pilot-review.json` and create a private `continue`
file. The review shape is:

```json
{
  "campaignSha256": "SHA256_OF_CAMPAIGN_JSON",
  "evidenceHashes": {"cell-0001/attempt.json": "SHA256_OF_ATTEMPT_JSON"},
  "decision": "continue",
  "notes": "Reviewed pilot effects, failures, instructions, routes and cleanup"
}
```

Populate `evidenceHashes` using `pilot_evidence_hashes(Path(DIRECTORY))` from
`control_campaign.py`; it includes all attempts, receipts, transcripts,
evaluations, route reviews, lifecycle annotations, invocation timings and the
campaign-wide runtime reference plus each cell's runtime evidence. A complete clean,
profile-qualified, route/policy-reviewed pilot is required; a product effect
failure need not be concealed to proceed. Then run `--stage paired` with the
same source, campaign and private connection options. This review opens a
scheduling gate; it provides no target authority.

`report` reads hash-bound existing evaluations/reviews and preserves every
attempt. UI success requires qualified profile, independent oracle pass,
conforming route, conforming/not-applicable confirmation policy, and confirmed
workspace/tunnel cleanup. Unknown review is unverified. Pilot results remain
separate. Paired latency deltas include only pairs with both effects verified;
all failed/invalid attempts retain usage sums, distributions and coverage.
`runnerInvocationSeconds` measures the complete subprocess invocation, including
readiness/acquisition, setup, agent work, oracle, cleanup/disposal and journal
completion. `postAcquisitionPreCleanupSeconds` is the runner's original
`wallSeconds` interval, starting after workspace acquisition and ending before
owned-session, tunnel and workspace cleanup; it is not lifecycle elapsed time.
Original receipts remain unchanged. Invocation timing and coverage include
nonzero exits and launch/driver failures, and appear in all outcome buckets.

Discovery calls and pre-UI usage are reported checkpoints, not causal token
attribution. Cache/reasoning breakdowns overlap totals, not additional tokens
or dollar estimates. Route comparisons cannot identify a Python/JavaScript
language effect because implementations/instructions/enforcement differ.

Lifecycle acceptance stays separate from UI score: doctor, claim, workspace,
oracle execution, disposal and credential handoff. Existing receipts directly
cover only some checks. Write the private lifecycle annotation at
`CAMPAIGN/cell-NNNN/acceptance.json`, beside `attempt.json`. The reporter reads
that cell-level location; an `acceptance.json` beside the nested `trial.json`
is retained evidence but is not automatically applied. In contrast, the route
review belongs beside `trial.json`. Publish the lifecycle annotations before
hashing the pilot continuation decision. They can supply reviewed evidence for
the remaining checks, bound to the original trial receipt:

```json
{
  "receiptSha256": "SHA256_OF_TRIAL_JSON",
  "checks": {
    "doctor": {"status": "pass", "evidence": "Private exact-identity doctor receipt"},
    "claim": {"status": "pass", "evidence": "Private claim acquisition/use/release audit"},
    "workspace": {"status": "pass", "evidence": "Private isolated workspace receipt"}
  }
}
```

Statuses are pass/fail/unknown. Never place secrets in evidence. Reviews cannot
override a known disposal failure. Whole-package acceptance within these four
scenarios needs complete coverage, UI success and lifecycle evidence; a UI
latency win alone cannot pass it. Audit doctor identity, claim use/release,
oracle independence, credential locator/mode/value and actual owned-process and
workspace disposal before recording pass. Reviewer assertions are not
cryptographically authenticated identity or authority.

The held-out fixtures have offline positive/negative oracle tests and bounded
live qualification in that report. Finder checks exact moved bytes and an untouched same-named
decoy. Browser uses the existing separately identified Chrome for Testing
launcher and an owned loopback HTTP server; exactly one matching server-side
submission is required. Workspace disposal owns their process cleanup. Fixture
wrappers assume the runner's conventional guest checkout location. A different
guest project layout needs a future fixture-path contract; do not silently run
against a different checkout. Keep fixtures outside instruction tuning, freeze
all inputs before live use, and report the four-scenario/platform scope. Offline
tests do not establish browser, Finder, generalization or cross-platform success.
