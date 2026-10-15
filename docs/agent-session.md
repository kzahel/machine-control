# Persistent Python session candidate

**Current:** the source checkout has a typed Python core and a stdio MCP facade.
Its guest-local macOS MCP slice passed native qualification and all 42 repeated
agent trials in the [comparison](evidence/agent-capability-comparison-2026-10.md).
[Tactical 123](tactical/123-persistent-agent-session.md) remains active for
installed packaging, the shell facade, remote acceptance and broader platform
conformance. This is bounded source acceptance, not general platform support;
the existing CLI remains supported.

This interface is a subset of Machine Control. Existing covered locked use,
browser extension/CDP, system-surface and VM lifecycle capabilities have their
own interfaces and acceptance records. Their integration into this session is
tracked by the [capability roadmap](../topics/computer-use-positioning.md).

Start the server with a logical target:

```sh
bin/machine-control --target TARGET mcp --reason 'Perform the requested UI task'
```

The server exposes `mc` (Python code) and `mc_reset`. Both require `session_id`,
the caller's published agent session ID. Read `AGENTCTL_SESSION_ID`,
`CLAUDE_CODE_SESSION_ID`, or `CODEX_THREAD_ID` in the agent's shell when needed;
MCP subprocesses do not necessarily inherit these variables. This identifier
is self-asserted attribution, not bearer authority. The interpreter binds to
the first session and refuses calls from a different one; use a separate MCP
server per agent session. Initialization and tool
discovery do not acquire a claim or operate the target. The first code call
uses target doctor, acquires a live queued claim, and opens the existing
resident admission channel. Outside a session-publishing agent host, supply
`--claimant-authority` and `--claimant-id` to override the default
`agent-session` attribution with truthful caller metadata.
Do not pass an existing global `--claim`: this session owns its claim lifecycle.

A coordinator may instead configure `--session-id-file PATH`, atomically
publishing the actual provider session ID in a regular mode-0600 file. The MCP
schema then makes `session_id` optional, and the description tells the agent to
omit it. The server reads only that explicit file on each call; it refuses a
missing publication, a conflicting supplied ID, or a changed owner. This avoids
assuming that MCP or tool shells inherit a late-published environment variable.
The experiment runner waits for YA's process ID to have its matching native
transcript before publishing it; a provisional launch ID is insufficient.
This file carries attribution, not authority or credentials.

```python
app = mc.app("TextEdit")
app.tree(query="Save")
```

Calls block; there is no `await`. Variables persist. The final expression and
`print` output are returned. Application handles offer `tree`, `press`, `click`
(element centre), `set_value`, `focus`, `activate`, `action`, `key`, `type`, `choose`, `scroll`,
and `screenshot`. Inspect a fresh tree before acting on a changed interface.
Call `mc.close()` when the task finishes, preferably at the end of its final
snippet. It releases claim/admission promptly and leaves applications open.
Native Open/Save panels take an absolute location through `choose(path)`;
follow-up prompts remain visible and require another decision.
`app.activate()` explicitly brings the target application forward and changes
target focus. Some app menus need foreground activation. This is separate from
focusing an element, and application lookup does not implicitly activate it.

Actions retain the full resident envelope in `result.raw` and print route,
delivery, effect, uncertainty, host interference and any reported focus
consequence. Host interference is not a claim that the target cursor/focus stayed
unchanged. By default they also observe
the resulting tree. `--observe explicit` disables that automatic observation;
call `tree()` explicitly when batching. Settling compares bounded samples;
two equal samples do not prove asynchronous application completion.

Element numbers are never inferred from labels, positions or tree paths.
Numbers persist only when the provider's opaque reference or declared native
identity persists. Providers that rotate references without stable identity
receive fresh numbers and full compact observations. Removed numbers cannot
be reused. The Mac native provider now supplies bounded observation identities
across qualified consecutive reads while issuing fresh action references for
every snapshot. Native actions require a reference from the latest snapshot
and revalidate its process and ancestor membership before dispatch. Observing
another application also expires prior native action references; observe the
intended application again before acting.

Native continuity retains one complete application's tree, at most 2,000
objects and 64 windows, with a maximum 30-second gap. Incomplete or ambiguous
reads, window/process changes and generation changes reset it. Cross-process
identity reuse remains unqualified. Missing process metadata or unverifiable
ancestor edges refuse actions; no identity is inferred from a label or frame.
The [bounded production acceptance](../research/platforms/macos.md#production-native-identity-acceptance)
records fixture and representative-app evidence. It does not establish a new
model-token or latency improvement. “No change” describes the compact semantic
projection: it omits geometry and hides menus by default. Current element
bounds and dispatch references still refresh.
Unknown coordinate spaces refuse element-centre clicks before sending input.

When semantics omit a control, `shot = app.screenshot()` attaches a window image.
`shot.click(x, y)` and `shot.scroll(x, y, "down", pixels=400)` use image pixels;
the client maps the image to the captured window and checks its process,
identity, bounds, visibility and resident generation before input. Any subsequent
session action invalidates that capture. Only the Mac Quartz exact-window
mapping is implemented; other capture routes remain viewable but refuse these
coordinate actions. These checks do not prove unchanged application content or
remove the final observation-to-input race. Pointer routes move the cursor and
may change focus. Independent effect checks remain necessary.

The claim renews under the existing policy; admission is bounded to fifteen
minutes and is never silently renewed. A local watchdog closes ownership and
releases the claim when that bound ends, including while the agent is idle.
Existing grants and operator decisions
remain authoritative. This first slice requires a ready doctor, so arrange
normal grant approval through the established CLI workflow first. It does not
arm protected operations or change resident privileges. Revocation, claim loss,
audit failure and channel loss do not trigger automatic action retries.

Code executes in a separate ordinary client process. This provides a killable
snippet deadline, not same-user containment. Timeout delivery is unknown and
the worker's live ownership ends; reset explicitly before starting a new
session, then observe the application. Reset in a live session clears Python
variables and element maps while keeping its claim and open applications.
Cleanup reuses the scoped runner's process-group / Windows Job Object handling
for ordinary child processes, including children that inherit the reply pipe.
An artifact-fetch claim or audit failure also closes ownership. The MCP worker
ends with a stopped transport, allowing a subsequent explicit reset to start
normal admission again; it never silently replays the failed code.
The pending broader design includes shell-session packaging and fuller
approval-aware deadlines; those are not implemented by this thin facade.

For library use, put `client/` on the import path and construct
`agent_session.Session(agent_session_transport.connect(...), target=...)`
inside a context manager. An image receiver is required for inline captures.
The core accepts a typed transport protocol so fixtures can test staleness and
delivery behavior without touching a desktop.

Validate the new modules with:

```sh
python3 -m unittest discover -s tests/client -p 'test_agent_session*.py'
uvx --from mypy==1.19.1 mypy --strict --follow-imports=silent client/agent_session*.py
```
