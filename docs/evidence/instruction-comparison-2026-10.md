# Does a CLI quickstart help agents use Machine Control?

**Current, bounded result:** yes for token use and discovery overhead in this
sample. Both instruction styles passed all 12 measured tasks. The quickstart
used fewer tokens and calls; an end-to-end speed improvement is not established.
This tests instructions, not the newer native identity implementation.

## Main result

Codex `gpt-6.1-sol`, medium effort, standard/normal speed through YA, using the
Machine Control CLI. Four macOS tasks, three repetitions per instruction style.
Values below are medians across the 12 successful tasks in each arm.

| Measure | Look at the repo and use it | Frozen quickstart |
| --- | ---: | ---: |
| Reviewed task success | 12/12 | 12/12 |
| Agent time | 97.25 s | 88.64 s |
| Model tool calls | 16 | 13.5 |
| Input + output tokens | 720,366.5 | 474,868.5 |
| Calls before first UI attempt | 5 | 2 |
| Full invocation, including VM lifecycle | 197.34 s | 191.37 s |

The quickstart's median token count was 34% lower. Comparing each task with its
matching repetition gives a median difference of **3 fewer calls, 228,902 fewer
tokens and 6.96 fewer agent seconds**. The median paired full-invocation difference
was only 0.41 seconds faster. Differences between arm medians and medians of
paired differences are different statistics.

## Results by task

Each entry is discovery → quickstart, with three trials per arm. Finder and the
browser form were held out from instruction development.

| Task | Median agent seconds | Median calls | Median tokens, thousands |
| --- | ---: | ---: | ---: |
| Load an unpacked extension | 73.67 → 67.28 | 12 → 13 | 502.3 → 401.9 |
| TextEdit menus | 113.13 → 102.15 | 19 → 15 | 915.4 → 678.7 |
| Finder rename/move, preserving a decoy | 96.35 → 94.18 | 15 → 11 | 645.8 → 415.3 |
| Browser form, exactly one correct submission | 98.15 → 90.82 | 20 → 16 | 887.8 → 546.8 |

One quickstart browser trial recovered from four provider-reported overload
errors. Its 350.52 agent seconds include 270.10 seconds between turns. It
submitted the form exactly once and passed; all its time and tokens remain in
the comparison. Across all 12 trials, quickstart therefore consumed **more total
agent time** (1,312.87 versus 1,155.16 seconds), despite its lower median.
Per-task paired differences and min/max ranges are in the
[aggregate data](instruction-comparison-2026-10.json); ranges are not confidence
intervals. Three repetitions per task do not establish a population effect.

## What was tested

The [protocol](../../tests/experiments/instructions/control-campaign/protocol.md)
fixes source `e9a51f38401dd455bb84137b4a3ee4e94a7f54fd`, model settings, CLI
route, runtime and appliance base. The treatments are that revision's
[discovery](../../tests/experiments/instructions/mc-discovery.md) and
[quickstart](../../tests/experiments/instructions/mc-quickstart.md) instructions.
Seeded order varies; fixtures match within each scenario/repetition pair.
Every trial uses a fresh disposable guest. Eight qualified pilot observations
are counted once and excluded from the 24 measured trials and 12 paired estimates.

Success requires an independent task-effect check plus review of the actual
route, confirmation behavior and cleanup. All 32 pilot/measured trials also
passed the separate bounded lifecycle checks: doctor, claim, workspace, oracle,
credential handoff and disposal. An independent raw-transcript arithmetic check
agreed with the frozen reporter. Final controller checks found no remaining
experiment workspaces and correlated released claims with stored credentials.

Token counts are task-session input plus output, including repeated context
across model calls. Cached input is a subset of input; reported reasoning is a
subset of output. Neither is added again. These are not unique prompt lengths
or dollar costs. Coordinator, development and review usage is excluded. Agent
time includes model/tool work and recovered waits; full invocation includes
setup and disposal too. Those time scopes overlap and must not be added.

## Retained failures and experiment cost

An initial Finder oracle mistakenly rejected ordinary `.DS_Store` metadata.
The corrected oracle still verifies exact payload/decoy bytes and rejects
symlinks; the complete pilot was rerun. The original Finder outcome stays
unknown. A first measured phase then stopped on a VM startup failure after 13
successful tasks; no model task started in the failed invocation. Its retained
clone was subsequently discarded. The startup cause remains unknown.

The primary comparison restarts all 24 measured trials with identical inputs,
reusing only the byte-identical qualified pilot. The interrupted observations
do not enter its estimates. A reporting correction placed existing lifecycle
annotations where the reporter expects them; original reviews and receipts
were preserved. Exact provenance and raw evidence remain private.

| Separate population | Attempts | Known agent seconds | Known calls | Known tokens | Invocation seconds |
| --- | ---: | ---: | ---: | ---: | ---: |
| Primary measured comparison | 24 | 2,468.03 | 359 | 14,956,377 | 4,839.12 |
| Qualified pilot, counted once | 8 | 786.44 | 126 | 5,245,727 | 1,577.47 |
| Interrupted measured phase | 14 | 1,178.07 | 192 | 7,992,526 | 2,403.87 |
| Earlier inconclusive pilot | 2 | 176.46 | 25 | 968,105 | Unknown |

Model measurements cover 13/14 interrupted attempts; the pre-model failure's
usage is unknown, not zero. Its invocation lasted 10.36 seconds. Later recovery
cost is outside that invocation and is not estimated. The aggregate data keeps
measurement coverage, input/cache/output breakdowns and outcome counts.

## Practical conclusion and limits

Provide a short entry guide rather than requiring repeated repo discovery.
The [proposed current guide](../../info/use-machine-control.md) also addresses
observed app-selection, shell-grammar and truncated-output mistakes. It differs
from the tested quickstart and has not itself been benchmarked.

The next performance test should compare the new native identity/diff behavior
under equal claim enforcement and identical instructions. This experiment does
not resolve Python versus JavaScript, compare models, or show a native-code
speedup. The earlier [seven-scenario baseline](agent-capability-comparison-2026-10.md)
owns those broader route observations.

These results apply to a prepared macOS appliance with standing grants and SIP
disabled. Bootstrap identity for appliance promotion remains unverified; stored
inherited passwords were checked without a fresh password login in every trial.
There was no independent focus/cursor interference sentinel. Some tool output
was truncated, limiting review of omitted UI content. Small sample size, cache
state and provider timing limit generalization to other apps, hosts or models.
