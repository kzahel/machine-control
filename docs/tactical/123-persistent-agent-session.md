# 123 — Persistent agent session interface

Status: proposed. Planning only; the experiment prototype is
`tests/experiments/mc-repl`.
The [native efficiency investigation](124-native-behavior-and-efficiency.md)
precedes broad implementation to isolate the prototype's combined changes.
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

## API draft

**Proposal.** Inputs: the Computer Use interface study (local reference,
summarized in the [Sky dossier](../../research/providers/sky-computer-use.md)),
the `mc-repl` experiment, and the operations the Mac, Windows and Linux
residents already share. Names are Pythonic and every call blocks until its
result is known; the agent never writes `await`.

### Session and lifecycle

```python
mc.target            # logical target and platform, e.g. "host (macos)"
mc.state()           # running apps, windows, browsers; partial failures listed
mc.apps(); mc.windows()
app = mc.app("TextEdit")        # by name, bundle/app id, pid or window id
app = mc.launch("com.apple.TextEdit")
mc.help(topic=None)  # API notes; re-shows notes after context compaction
```

- A session holds one target, one claim (renewed in the background), the
  grants it needs and, where the platform requires it, live owner admission.
  `mc.app()` binds an application (Windows/Linux: a window) and shows its full
  tree once.
- Snippets run in one persistent namespace; the value of a final expression
  is shown. Each snippet has a timeout that excludes time spent waiting for a
  person's approval. A timeout or kill releases held keys, buttons and drags.
- Facades: `machine-control mcp` (tools: run code, reset), `machine-control
  session start|run|stop` for shell-only agents, and an importable library.
  Reset clears the namespace but keeps the claim and open apps; stop releases.

### Observation

```python
app.tree(query=None, full=False)   # diff by default; full=True forces a tree
app.screenshot()                   # attached inline; never advances the diff
app.observe(screenshot=False)      # tree (and optionally image) in one call
```

- Text, one line per element, indented by depth: `12 button "Save"`, with
  states in parentheses (focused, selected, checked, expanded, disabled,
  settable), value, and non-default actions. Prune empty non-interactive
  leaves, merge adjacent static text, drop labels repeated from the parent,
  and collapse menu bars to one line unless queried.
- After the tree, short sections for the focused element, the selection and
  document text when the provider reports them.
- Numbers stay stable for the same native element across reads within one
  resident/provider generation, so diffs are meaningful; a generation change
  invalidates every number. A number not in the current map is refused with a
  prompt to re-read, never retargeted.
- Diffs mark changed and added lines and summarize removed numbers as ranges;
  an unchanged tree is one line. Above a line budget the full tree is sent.
  Output per call is capped, with explicit truncation notes.
- The first read of an app may add one short hint, for example to use
  `choose()` in Open and Save panels.
- Settling happens inside observation (wait for the UI to stop changing, with
  a cap), not as fixed sleeps after actions; agents are told not to sleep.

### Actions

```python
app.press(n)                         # semantic press; clicks the centre if n cannot be pressed
app.click(n | (x, y), button="left", count=1, modifiers=None, hold_ms=None)
app.set_value(n, text); app.focus(n); app.action(n, "AXShowMenu")
app.type(text); app.paste(text); app.key("cmd+s")
app.scroll(n | (x, y), "down", pages=None, pixels=None)
app.drag(a, b)
app.select_text(n, text, prefix=None, suffix=None, caret=None)
app.choose("/absolute/path", confirm=True)   # native Open/Save panel
```

- Each action returns one line: what it did, the route used (for example
  semantic press or centre click), delivery and observed effect. Full
  delivery/effect/uncertainty data stays available as attributes.
- **Open:** whether to re-observe automatically. Candidates: nothing (the
  agent batches a `tree()` call), a tree after every action (the prototype),
  or one settled diff at the end of a snippet that acted without observing.
  Measure all three in Tactical 119 batches.
- Unsupported calls fail before any input is sent and name the platform's
  alternative. Coordinates from a screenshot are bound to that capture.

### Errors

Typed exceptions with `code`, `retryable`, `delivered` (`no`, `yes`,
`unknown`) and a one-line next step:

| Exception | Meaning and next step |
| --- | --- |
| `StaleElement` | number no longer valid; re-read (the fresh diff is attached when cheap) |
| `UserIntervened` | the person used the app; re-observe, then continue |
| `Stopped` | the person stopped or revoked access; every later call fails until re-admitted |
| `ApprovalRequired` / `ApprovalDenied` | a grant is needed or refused; never retried in a loop |
| `ClaimLost` | the target-use claim expired or was taken; stop |
| `Locked` | desktop locked; use an armed locked-use route if the target offers one |
| `Unsupported` | the platform lacks the operation; nothing was sent |
| `Timeout` | always `delivered=unknown`; observe before acting again, never replay |

Unlike a fire-and-forget action API, a refusal and an uncertain delivery
are never reported the same way.

### Inputs from the native study

**Proposal**, mostly for the residents behind the session (see the
[Sky dossier](../../research/providers/sky-computer-use.md)):

- Batch attribute reads, cache trees and invalidate them from accessibility
  notifications; settle on notification quiet rather than sleeps.
- Implement tree clean-up as named, separately tested passes, and keep
  element numbers keyed to the underlying element across reads.
- Capture the target window with its attached sheets and menus, which also
  excludes Machine Control's own overlays.
- Prefer window-addressed input posted to the target process, which leaves
  the person's cursor alone, with focus guards; report this route and
  measure it per app family before relying on it.
- Detect the person's input by excluding our own synthetic events, and turn
  it into the `UserIntervened` error.
- Keep private-API use explicit and reported, unlike runtime-hidden
  resolution, and keep locked use behind Machine Control's own claim, grant
  and lease checks.

### Platform mapping

| Call | macOS resident | Windows resident | Linux companion |
| --- | --- | --- | --- |
| apps, windows, tree, screenshot | yes | yes | yes |
| press, focus, set_value | yes | invoke, set.value | action, set_value |
| click, key, type, scroll, drag | yes | yes | yes |
| launch, activate, terminate | yes | launch, activate | yes |
| choose | yes | **Open** (common file dialog) | **Open** (portal/GTK chooser) |
| select_text, paste with restore | **Open** | **Open** | **Open** |
| diffs, stable numbers | client-side first | client-side first | client-side first |

Diffing and numbering start in the client so all three residents gain them;
moving them into residents is an optimization once measured.

## Research gate and revised sequencing

**Decision (Tactical 124):** first prove a thin retained, claim-aware client with
compact/diff observations over existing operations. Do not package all three
facades before measuring it. The native fixture study found substantial CLI
cost outside resident-reported work and a large unchanged-output difference.
Window-addressed pointer/text and background menu behavior are the next native
qualification targets; notification/cache optimization follows measurement.

**Clarification:** a settled observation has a deadline and reports what was
observed. It cannot promise asynchronous application completion. The study's
continuous producer was still changing when Sky returned; effect predicates
must remain separate. See the [provider findings](../../research/providers/sky-computer-use.md#deterministic-native-behavior-study-2026-10-14).

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
