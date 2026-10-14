# 119 — VM route-comparison experiments

Status: proposed. Runbook drafted; no guest work has started.
Owning topic: [operational workflow automation](../../topics/operational-workflow-automation.md).
Runbook: [route-comparison experiments](../comparison-experiments.md).

## Objective and completion conditions

After the first manual comparison ([Tactical 118](118-usage-friction-journal.md)),
the operator asked for a repeatable way to run many such experiments: YA and
agents inside a macOS Tart guest, model access through the host's
agent-auth-router, and host YA analyzing results to find Machine Control
gaps relative to Codex Computer Use.

Complete when a batch of at least five tasks, each run several times per
route in disposable clones, produces oracle results and a host analysis
without manual UI intervention.

## Boundaries

Guests are dedicated appliances; the controller's desktop is never a trial
target. AAR keeps its loopback bind; guests reach it only through a per-trial
SSH reverse forward and a dedicated revocable client token. Transcripts,
captures, tokens and private inventory stay out of this repository.

## Ordered work

### 1 — prove the open checks

Run the five checks in the runbook's step 0: Computer Use through AAR,
Computer Use in a guest, token visibility in guest agents, grants surviving
clones, and guest YA session creation through the tunnel.

### 2 — build and seal the experiment base

Prepared image, appliance resident, TCC grants, credential handoff, guest YA,
Codex, Computer Use, Chrome with the extension, AAR client configuration,
fixtures; prove it as the workspace ready base under a provisioning journal.

### 3 — write the trial driver and first tasks

Driver: workspace, tunnels, setup, guest session, oracle, collection,
release. Tasks: load unpacked extension, save through a native Save panel,
web upload through a native Open panel, a System Settings toggle and a Finder
rename/move, each with an application-state oracle.

### 4 — run a batch and analyze it

Two concurrent trials at most. Host analyst session produces the gap
classification; record sanitized results here and act on the largest gaps.

## Validation

Each check in step 1 is recorded with its evidence level. A trial counts only
with an oracle result; agent self-reports are secondary.

## Final result

Pending.
