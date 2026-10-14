# 119 — VM route-comparison experiments

Status: active. Experiment base built; Machine Control route proven in the
guest; Computer Use installation, workspace proof, driver and tasks pending.
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

## Progress

### Experiment base (step 2, partial)

**Current:** The base is a Tart copy-on-write clone of the existing macOS
candidate, with its own private inventory entry, configuration, workspace and
claim state, and credential file, so the candidate stays unchanged for
conformance. The clone used no extra disk at creation, booted to an unlocked
session, and kept the resident's Accessibility and Screen Recording grants.

Inside the guest: Node 24 (already present), npm-installed Codex CLI and
YepAnywhere, a public machine-control clone, and Chrome for Testing. YA runs
as a per-user LaunchAgent on `127.0.0.1:3400`. Codex uses an `aar` model
provider at `http://127.0.0.1:8417/codex` with `env_key = "AAR_TOKEN"`; the
LaunchAgent wrapper reads the token from a 0600 file. The controller reaches
the guest over SSH with a dedicated key; the guest's host key is read through
the Tart guest agent and pinned under a host-key alias, not trusted on first
use. One SSH connection carries `-R 127.0.0.1:8417` to the controller's AAR and
`-L` to the guest YA. A dedicated AAR client grants only the Codex account.

### Open checks (step 1)

| Check | Result |
| --- | --- |
| Token reaches guest agents | **Pass:** a YA-launched guest Codex session saw `AAR_TOKEN` and completed through AAR |
| Guest YA through the tunnel | **Pass:** session created and polled from the controller via the forwarded port |
| Clones keep grants | **Pass** for a full clone; isolated workspace clones not yet checked |
| Gateway authentication | Unauthenticated request through the reverse forward returns 401 |
| Computer Use in the guest | **Open:** needs the ChatGPT app, Codex Computer Use and an operator decision on signing in |
| Computer Use through AAR | **Open** (operator expects it works) |

Guest-local `machine-control --target host target doctor` passes every check
under the appliance's standing policy, so guest agents drive the guest desktop
target-natively.

Notes: Chrome for Testing raises a keychain prompt unless launched with
`--use-mock-keychain --password-store=basic`; its published bundle is unsealed,
so strict signature verification fails everywhere. The guest volume has about
12 GiB free after setup.

## Final result

Pending.
