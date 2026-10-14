# 123 — Persistent agent session interface

Status: active. A typed Python core, claim/admission/audit transport and killable
MCP facade are implemented as a [source candidate](../agent-session.md).
Thirty-six focused offline tests and strict type checking pass.
Codex and Claude TextEdit, window and Settings smokes passed;
broader live qualification and matched comparison remain pending.
The direct-socket JavaScript
experiment remains `tests/experiments/mc-repl`.
The completed [native efficiency investigation](124-native-behavior-and-efficiency.md)
prioritizes a thin claim-aware slice before broad packaging. Its repeated pilot
does not isolate the prototype's combined changes.
The [agent capability baseline](125-agent-capability-baseline.md) now gates the
thin implementation: realistic scenarios, explicit model/effort/speed profiles,
provider-correct tokens and separately measured instruction improvements.
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
- passes the scenario/effect regression gate on more than one agent family,
  with repeated time/call/token comparisons and enforcement differences stated.

## Candidate sources of the prototype's efficiency difference

- One long-lived process reduces repeated CLI startup and adapter work. The
  prototype also omits claim/controller-audit checks; those must be restored,
  and their cost was not separately measured.
- Several actions per model call, written as code.
- Indented text trees with small numbers instead of JSON with long
  references, a one-line no-change reply, and the refreshed tree returned with
  each action.
- Screenshots inline instead of a capture, a path and a separate image read.
- Element-centre clicks when an element cannot be pressed.

Only the first needs a persistent process. Compact text observations, small
numbers and element clicks also help the CLI and should land there too.
These were combined changes, not individually established causal speedups.

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

### 0 — freeze the realistic agent baseline

Complete [Tactical 125](125-agent-capability-baseline.md)'s model-profile smoke
and scenario/oracle qualification, then freeze its source and runtime inputs.
Run the repeated baseline from that isolated pin while developing the candidate;
baseline results remain a gate before candidate acceptance. Include the
existing five workflows, dedicated menu and two-window
recovery cases, and instruction comparisons. The earlier fifteen-trial result
covers TextEdit on one model only. Preserve a baseline that the thin slice can
actually rerun, including token use and failed-attempt costs.

**Execution refinement:** serial disposable-guest setup makes the full matrix
long-running. A detached private baseline checkout and per-batch source bundles
keep candidate development out of its inputs. This removes an idle development
dependency; it does not remove any comparison or acceptance check.

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
Tactical 125. Task success/effect regressions block acceptance even if time or
tokens improve. Use the same model settings, prompts, fixtures and enforcement
when attributing a change to persistence, observation policy or language.

## Final result

Pending.

The first live Codex/Python smoke stopped before UI dispatch because its MCP
process lacked the caller's published session environment. This exposed an
integration requirement, not an application-effect regression. Tool calls now
carry an explicit session ID, bind the interpreter to one caller session, and
use that ID for claim and controller audit attribution. A different session
is refused instead of sharing state; startup failures require explicit reset.
The failed attempt remains in private resource accounting. The rerun saved the
requested TextEdit document in 52.426 seconds and seven model tool calls, with
nineteen controller command results under the published session identity. This
single smoke does not establish a speedup. Cleanup instructions now explicitly
release the session at task end, and a watchdog releases it at the admission
bound even if the agent goes idle. The Settings CLI trace required scrolling
and pixel input because its AX radio options were absent, so the candidate now
has capture-bound pointer actions. The separate conformance results below
qualify that fallback; capture checks do not remove the observation-to-input race.

The next window and Settings attempts both stopped before UI work: their YA
tool shells exposed none of the published session environment variables. They
remain failed attempts with complete resource accounting. The optional MCP
coordinator publication now supplies the actual provider ID without requiring
model discovery. The harness waits for an exact matching native transcript,
because YA's launch ID can be provisional; the server still refuses identity
changes and retains normal admission and audit. The Sol window rerun passed
(68.158 seconds, seven model calls), preserving Protected and both windows.
Sol Settings passed (56.323 seconds, eight calls), as did Opus Settings
(33.094 seconds, five calls). These are single smoke observations. Both Settings
agents used semantic radio-button actions, so neither qualifies capture input.
All three reruns recorded the actual provider identity and prompt claim release
before VM disposal. Opus window and TextEdit smokes also passed (39.752 seconds /
seven calls and 40.583 seconds / eight calls), with normal profiles and cleanup.

The separate deterministic capture probe passed with a 2× image scale, an actual
mouse callback and revision change, a 180-point scroll-offset change, unchanged
sentinel content, and refusal of reused or externally moved captures before
input. Its first library attempt failed before admission because the guest's
system Python 3.9 supplied process-local monotonic origins to separate claim
processes. The queue now uses Mac kernel uptime for shared deadlines; 37 claim
tests and 30 claim/control client tests pass, and the same guest probe succeeds
through those older adapter processes. This preserves expiry and clock-rewind
fencing. A mixed-version check also passed with a modern-Python claim owner and
a system-Python checker. A separate Sol visual-grounding turn passed in 72.988
seconds and three model calls: it forwarded the inline image, selected image
coordinates, used `Capture.click`, and closed the session. Independent pointer
down/up callbacks establish the effect; the model correctly described the
provider's own effect report as unverified. This remains a single conformance
smoke, not a repeated efficiency comparison.

Failure-path review added regressions for artifact-fetch claim/audit loss,
terminal transport reset, and a timed-out worker whose child inherits stdout.
Ownership now closes on those artifact failures, stopped transports end their
MCP interpreter, and worker cleanup reuses the existing scoped process-tree
owner. No same-user containment or automatic replay is introduced. The focused
suite passes all 36 checks. The updated full client run passes 283 tests; eight
CLI packaging checks and strict mypy over all three new modules also pass.
