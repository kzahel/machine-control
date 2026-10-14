# 123 — Persistent agent session interface

Status: proposed. Planning only; the experiment prototype is
`tests/experiments/mc-repl`.
Owning topics: [unified desktop client](../../topics/unified-desktop-client.md),
[installed agent CLI](../../topics/installed-agent-cli.md).
Evidence: [Tactical 119](119-vm-comparison-experiments.md) and the
[Sky dossier](../../research/providers/sky-computer-use.md).

## Objective and completion conditions

In route-comparison trials, a persistent JavaScript session over the Mac
resident passed five tasks with about half the tool calls and time of the CLI,
close to Codex Computer Use. The operator asked how to make it a real option
rather than an experiment, and noted that agents without such a tool need a
fallback.

Complete when an installed Machine Control offers one supported persistent
session interface that:

- holds target selection, a renewed claim, grants and owner admission for the
  whole session, and audits every operation like the CLI;
- returns compact numbered observations, refreshed after actions, with
  inline images;
- is reachable as an MCP tool, from a plain shell, and as a library, so
  agents without MCP still get the persistence benefit;
- works locally and against a remote target through the same adapter; and
- matches or beats the experiment prototype in repeated trials with more than
  one agent family.

## What made the prototype faster

- One long-lived process: no per-call CLI start, registry load, adapter spawn
  or claim check (roughly 1–2 s of each CLI call).
- Several actions per model call, written as code.
- Indented text trees with small numbers instead of JSON with long
  references, a one-line no-change reply, and the refreshed tree returned with
  each action.
- Screenshots inline instead of a capture, a path and a separate image read.
- Element-centre clicks when an element cannot be pressed.

Only the first needs a persistent process. Compact text observations, small
numbers and element clicks also help the CLI and should land there too.

## Boundaries

The session is an untrusted client: model-written code runs in the client
process, never in the resident or a protected broker, and can call only typed
operations. It must not bypass claims, grants, live ownership, generation
checks or audit, unlike the experiment, which talks to the resident socket
directly. Delivery, effect and uncertainty stay available behind the compact
text. The existing CLI remains supported.

## Ordered work

### 1 — build the Python session and keep a JavaScript A/B

**Decision:** the supported session is Python: the installed CLI already
bundles and signs it, and the claim, admission and audit client is Python.
Design it for agents: blocking calls (no `await` to forget), one persistent
globals namespace, the last expression echoed, and each snippet run in a
killable session process with a timeout. Type-check its new modules strictly.

Keep a JavaScript variant that runs only with the system's Node as an
experiment route, so trials can compare languages per model family (Codex and
Claude at least, three or more repetitions per task) on success, calls, time
and tokens. A material advantage for JavaScript would justify packaging a
runtime such as Bun later; it does not block the Python path.

### 2 — build the session core in the client

Reuse `ControlSession`, claim acquisition and renewal, `control stream` owner
admission and the audit journal. Add the observation layer: per-read element
numbering mapped to generation-bound references, stale-number refusal, the
compact text renderer with menu collapsing, diffs or a no-change sentinel,
settle-then-observe after actions, element-centre clicks, `dialog.choose` and
inline capture. Keep it platform-neutral so Windows and Linux residents work
through their adapters.

### 3 — expose three facades over one core

- `machine-control mcp`: a stdio MCP server with the code tool and reset.
- `machine-control session start|run|stop`: a background session per agent
  with short `run 'code'` calls over a private local socket, for agents that
  only have a shell.
- An importable library for scripts and tests.

Remote targets use the same facades with `--target`; the core forwards typed
operations through the existing adapter.

### 4 — package and teach it

Ship it in the installed CLI on every desktop platform, advertise it in
`agent instructions`, and update the host and VM skills to prefer it where
available, with the CLI as the fallback.

### 5 — bring compact observations to the CLI

Text projection with small numbers for `desktop snapshot`, element-centre
click, and a press fallback, so CLI-only agents improve as well.

## Validation

Unit tests for numbering, staleness, rendering, diffs and claim lifecycle;
mock-adapter contract tests for each facade; live Mac fixture conformance;
route-comparison batches with repetitions before and after, recorded in
Tactical 119.

## Final result

Pending.
