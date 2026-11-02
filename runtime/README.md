# Shared resident policy: first deterministic slice

This development-only module is the beginning of the
[shared resident core](../topics/shared-resident-core.md), not an installed
resident or a new public protocol. [Tactical 150](../docs/tactical/150-shared-resident-core.md)
records the motivating request, boundaries and acceptance.

With Node 24+, run the scenario and regressions without installing packages:

```sh
node tests/runtime/scenario.mjs
node --test tests/runtime/core.test.mjs
```

Install the pinned development compiler for strict checking:

```sh
pnpm --dir runtime install --frozen-lockfile
pnpm --dir runtime check
```

The TypeScript is erasable and has no runtime dependencies, Node imports,
timers, native I/O, Tauri or browser dependency. Node executes it directly;
type checking is a separate required check. Only the test runner needs Node
APIs. Node is the development host, not a settled installed-runtime choice.

## Boundary

`src/core.ts` owns bounded provider registration, exact-profile finite approval,
one typed browser click, queue/dispatch lifetime, deadlines and revocation.
`testing/reference-provider.ts` owns a manual clock and an independent counter
target with held replies. It has no grant/routing policy. The scenario checks
the counter separately from the core's delivery/effect result.

A future host must authenticate native peers and operator decisions before
calling `connect`/`approve`, validate incoming wire data, retain one serialized
owner of core state, schedule `tick()` at deadlines, and consume every returned
effect. The core itself never awaits/calls native code. These methods are not
agent operations: do not expose `approve` or accept caller-supplied handle
objects on a public transport. Object handles are runtime-local identity;
copied profile IDs, generations or objects convey no authority. This is not
same-user shell containment.

`request()` emits a queued dispatch. Immediately before provider submission,
call `begin(command)` and consume its effects. Only a true `started` permits
submission, in the same serialized turn with no intervening await. A provider
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
Label resolution, availability switches, owner admission, full reference
discovery, consent persistence, real native messaging, CDP, screenshots and
all installed/native security integration remain future work. Existing
Windows/Mac/Linux residents and the Python client remain unchanged.
