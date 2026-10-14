# Route-comparison experiments

`route_comparison.py` runs paired trials of the tasks under `tasks/` in
disposable isolated workspaces of the macOS experiment base: once through
Machine Control and once through Codex Computer Use, each in a fresh clone.
Setup, the agent's work and the oracle all run inside the guest; the
controller only drives the clone, the SSH tunnel and guest YA.

```bash
tests/experiments/route_comparison.py --credential-file /private/base-login.secret --task settings-scrollbars
tests/experiments/route_comparison.py --credential-file /private/base-login.secret --repetitions 5 --seed 42
```

A task directory holds `task.json` (id, title, timeout), `prompt.md`
(route-neutral), `setup.sh` and `oracle.sh` (guest shell; the oracle prints one
JSON line with `passed` and `detail`). Oracles read application state, not the
agent's report.

Results, transcripts, usage notes, audit history and final captures go to a
private run directory under `~/.local/state/machine-control/experiments/`.
They contain session identifiers and screenshots and never belong in Git. The
runbook is [comparison experiments](../../docs/comparison-experiments.md).

After a batch (or while inspecting a partial run):

```bash
python3 tests/experiments/report_batch.py /private/results/run-ID
```

The report omits session IDs and raw UI output, keeps unsuccessful/invalid
trials out of successful-latency summaries, and reports missing trials. Review
it before promoting any minimized result into public research.

Profiles are explicit: `--provider codex` defaults to `gpt-6.1-sol`, medium
effort and standard thread tier. `--provider claude --route machine-control`
defaults to `claude-opus-5-5`, medium effort and standard speed, and requires
`--gateway-credential-file` naming a mode-0600 scoped AAR client token. It is
delivered over SSH stdin into a private guest file read by Claude's key helper.
Computer Use is not a qualified Claude route. The sealed base is unchanged.

`--instructions discovery|current|quickstart` selects the CLI instruction arm;
the default is the previous current-guide prompt. Other routes retain their
own tool instructions. Actual composed prompts are hashed in private receipts.
Task content seeds are stable across routes for a given seed/task/repetition.
Each batch uses one provider/model/instruction profile; compare separate pinned
batches without mixing their cells. Effective-profile failures stop the batch.

`--route mc-python` selects the typed persistent Python MCP candidate. It uses
the claim/admission/audit path; `--route mc-repl` retains the direct-socket JS
prototype with its explicitly different enforcement. Both support the two
model profiles. Do not attribute their differences to language alone. Candidate
results stay separate from the frozen baseline and require live qualification.

`campaign.py --source /private/frozen-checkout --target TARGET
--credential-file /private/base-login.secret --gateway-credential-file
/private/gateway.secret --pause-after-smoke` runs the five supported baseline
model/route cells serially. Seven scenarios and three rounds produce 105 trials.
The first 35 trials are the smoke round; a private `continue` file permits the
remaining rounds after review. A private `pause` file pauses the active driver
between trials, and removing it resumes; `stop` ends after current cleanup.
The driver does not restart an interrupted campaign automatically. It records
separate provider manifests/reports and the driver hash, and never reads guest
fixtures or client code outside the selected frozen checkout. Configure the normal
private inventory provider for the detached source checkout explicitly.

`--matrix python` runs the two supported Python model cells: fourteen first-round
smokes and 42 trials across three rounds. Its source must implement `mc-python`.
Keep its source and receipts separate from the baseline. `--start-paused`
prepares either matrix with a private pause file before any VM is acquired;
remove that file only after the preceding driver confirms between-trial cleanup.
Do not run two drivers against one appliance concurrently.
