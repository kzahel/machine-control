# Shared resident policy and browser adapter

This development-only module is the beginning of the
[shared resident core](../topics/shared-resident-core.md), not an installed
resident or a new public protocol. [Tactical 150](../docs/tactical/150-shared-resident-core.md)
records the first deterministic slice; [Tactical 151](../docs/tactical/151-shared-core-real-browser.md)
records the real extension/native-messaging follow-up.

With Node 24+, run the scenario and regressions without installing packages:

```sh
node tests/runtime/scenario.mjs
node --test tests/runtime/core.test.mjs tests/runtime/extension.test.mjs
```

Install the pinned development compiler for strict checking:

```sh
pnpm --dir runtime install --frozen-lockfile
pnpm --dir runtime check
```

The policy and extension adapter are erasable TypeScript with no runtime
dependencies, Node imports, timers, native I/O or Tauri. Node-specific framing
is isolated under `node/`; the private fixture host under `testing/` composes
real sockets and scheduling with the same core. Node executes the TypeScript
directly; strict checking is a separate required check. Node is the development
host, not a settled installed-runtime choice.

For real-browser acceptance on Mac/Linux, install the existing desktop's
pinned Playwright and its full test browser (not headless-shell only):

```sh
pnpm --dir desktop install --frozen-lockfile
pnpm --dir desktop exec playwright install chromium --no-shell
pnpm --dir runtime browser
```

Linux CI also uses Playwright's `--with-deps` installer for browser libraries.
The runner uses only the bundled separately identified browser, two scratch
persistent profiles and their private native-host manifests. It needs no VM,
display server, installed resident, account sign-in or registration in the
user's real browser. Chromium's sandbox is explicitly disabled for these empty
fixtures; this does not qualify sandboxed production-browser operation.
Browsers/relays are closed and scratch directories removed in cleanup.

## Boundary

`src/core.ts` owns bounded provider registration, exact-profile finite approval,
typed browser tabs/snapshots/clicks, queue/dispatch lifetime, deadlines and revocation.
`testing/reference-provider.ts` owns a manual clock and an independent counter
target with held replies. It has no grant/routing policy. The scenario checks
the counter separately from the core's delivery/effect result.

`src/extension-provider.ts` implements `ProviderAdapter` over the existing
protocol-v1 worker, projects exact core authority to grant messages, correlates
wire replies to exact dispatch handles, normalizes bounded observations and
forwards cancellation. Native framing caps each JSON object at 1 MiB and
output backlog at 2 MiB. Discovery bounds are 256 tabs and 64 interactive
snapshot elements. Budgets are rechecked at dispatch; less than the worker's
100 ms minimum refuses without forwarding. Unknown provider failure delivery
is conservative. Malformed replies close only the affected route.

A future host must authenticate native peers and operator decisions before
calling `connect`/`approve`, validate incoming wire data, retain one serialized
owner of core state, schedule `tick()` at deadlines, and consume every returned
effect. The core itself never awaits/calls native code. These methods are not
agent operations: do not expose `approve` or accept caller-supplied handle
objects on a public transport. Object handles are runtime-local identity;
copied profile IDs, generations or objects convey no authority. This is not
same-user shell containment.

`request()` emits a queued dispatch. The shared `dispatchToProvider()` host
helper calls `begin(command)`, submits only after a true `started`, passes the
remaining budget and consumes expiry effects. Both the reference and real
browser hosts use it; adapters must not call `begin()` again. Submission is
in the same serialized turn with no intervening await. A provider
adapter doing asynchronous preparation must place this boundary after that
preparation. Sending work is distinct from receiving an answer or observing
an effect. `complete(connection, command, reply)` correlates the exact handles;
an authenticated wire adapter must own the map back to those handles.

Stop invalidates approval before producing cancellation/results. Queued work
reports refused delivery; dispatched work reports unknown delivery/effect.
Already executed provider effects are not undone by cancellation. A successful
reply confirms delivery only; the reference fixture independently proves its
counter effect. Late/duplicate/foreign replies never produce a second terminal
result or restore authority, even when public request labels are reused.

An unsettled dispatched call retains its capacity after Stop, timeout,
disconnect and reapproval until that exact provider completion arrives.
If it never returns, that slot stays unavailable; a future native host needs
an explicit independently confirmed quiescence/process-retirement contract
before reclaiming it. The first slice deliberately does not infer physical
completion from cancellation or disconnection. Returned effects are consumed
by the host; the core retains no unbounded event/result history.

The API currently requires explicit profile IDs and provider-bound references.
The fixture host assigns identities through private endpoint configuration;
approval is an in-process fixture operator call, never a socket method. This
does not implement production native peer authentication, durable extension
profile names, same-process Chrome profiles, operator UI, consent persistence,
full owner admission, CDP or screenshots. Existing Windows/Mac/Linux residents
and the Python client remain authoritative and unchanged.
