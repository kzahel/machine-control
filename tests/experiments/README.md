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
