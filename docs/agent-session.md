# Persistent Python session candidate

**Current:** the source checkout has a typed Python core and a stdio MCP facade.
It is under qualification in [Tactical 123](tactical/123-persistent-agent-session.md).
Do not interpret offline tests as live platform acceptance or packaging support.
The existing CLI remains the qualified path while the baseline runs.

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

```python
app = mc.app("TextEdit")
app.tree(query="Save")
```

Calls block; there is no `await`. Variables persist. The final expression and
`print` output are returned. Application handles offer `tree`, `press`, `click`
(element centre), `set_value`, `focus`, `action`, `key`, `type`, `choose`, and
`screenshot`. Inspect a fresh tree before acting on a changed interface.
Native Open/Save panels take an absolute location through `choose(path)`;
follow-up prompts remain visible and require another decision.

Actions retain the full resident envelope in `result.raw` and print route,
delivery, effect, uncertainty and interference. By default they also observe
the resulting tree. `--observe explicit` disables that automatic observation;
call `tree()` explicitly when batching. Settling compares bounded samples;
two equal samples do not prove asynchronous application completion.

Element numbers are never inferred from labels, positions or tree paths.
Numbers persist only when the provider's opaque reference or declared native
identity persists. Providers that rotate references without stable identity
receive fresh numbers and full compact observations. Removed numbers cannot
be reused. The current Mac native provider rotates references each snapshot;
stable identity and useful no-change diffs still need native qualification.
Unknown coordinate spaces refuse element-centre clicks before sending input.

The claim renews under the existing policy; admission is bounded to fifteen
minutes and is never silently renewed. Existing grants and operator decisions
remain authoritative. This first slice requires a ready doctor, so arrange
normal grant approval through the established CLI workflow first. It does not
arm protected operations or change resident privileges. Revocation, claim loss,
audit failure and channel loss do not trigger automatic action retries.

Code executes in a separate ordinary client process. This provides a killable
snippet deadline, not same-user containment. Timeout delivery is unknown and
the worker's live ownership ends; reset explicitly before starting a new
session, then observe the application. Reset in a live session clears Python
variables and element maps while keeping its claim and open applications.
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
