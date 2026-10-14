# Route-comparison experiments

`route_comparison.py` runs paired trials of the tasks under `tasks/` in
disposable isolated workspaces of the macOS experiment base: once through
Machine Control and once through Codex Computer Use, each in a fresh clone.
Setup, the agent's work and the oracle all run inside the guest; the
controller only drives the clone, the SSH tunnel and guest YA.

```bash
tests/experiments/route_comparison.py --task settings-scrollbars
tests/experiments/route_comparison.py --repetitions 2
```

A task directory holds `task.json` (id, title, timeout), `prompt.md`
(route-neutral), `setup.sh` and `oracle.sh` (guest shell; the oracle prints one
JSON line with `passed` and `detail`). Oracles read application state, not the
agent's report.

Results, transcripts, usage notes, audit history and final captures go to a
private run directory under `~/.local/state/machine-control/experiments/`.
They contain session identifiers and screenshots and never belong in Git. The
runbook is [comparison experiments](../../docs/comparison-experiments.md).
