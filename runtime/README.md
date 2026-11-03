# Shared resident policy and browser adapter

This module implements the [shared resident core](../topics/shared-resident-core.md)
and the Windows browser coordinator. [Tactical 152](../docs/tactical/152-shared-runtime-windows-adoption.md)
owns adoption and native/package qualification. The reference target uses the
same policy with modeled browser effects; it is not another policy engine or
a public approval service. The Python CLI/client remains the agent interface.

With Node 24+, run the dependency-free reference scenario:

```sh
node tests/runtime/scenario.mjs
```

Install pinned development dependencies for the complete regression suite and strict checking:

```sh
pnpm --dir runtime install --frozen-lockfile
pnpm --dir runtime check
pnpm --dir runtime test
```

The policy and extension adapter are erasable TypeScript with no runtime
dependencies, Node imports, timers, native I/O or Tauri. Node-specific framing
is isolated under `node/`. The [private inherited process inlet](PROTOCOL.md)
composes policy and the extension adapter in a child; the fixture parent under
`testing/` owns sockets and process cleanup. Node executes TypeScript directly;
strict checking is a separate required check. The production Node transport
adapter uses pinned `ws`; the pure policy has no external runtime dependency.

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

## Executable qualification

`toolchains.json` pins Node archives by version and SHA-256. Packaging copies
only the runtime, upstream LICENSE and owned policy source, without npm or
headers. The alternative Bun compiler must match its pinned version. Outputs
are unsigned qualification payloads, with file/source digests and verified
Mach-O, ELF or PE architecture, not accepted desktop packages.

```sh
python3 runtime/scripts/package.py --engine node --target all --output .artifacts/policy-node
node tests/runtime/qualify.mjs .artifacts/policy-node/darwin-arm64 --browser
```

Choose the matching target on other hosts. The portable scratch native-host
runner is Mac/Linux only. Windows uses
[`tests/windows/browser-profiles-live.py`](../tests/windows/browser-profiles-live.py)
in an interactive, exclusively claimed dedicated appliance session. That runner
requires a separately identified test Chromium and a staged native companion;
`--settings` also exercises the staged Tauri operator through UI Automation.
The outside controller owns claims, credential lookup and power restoration.
The runner owns its scratch profiles and temporary native-host registration.
The qualifier checks file hashes, executes EOF/kill/expiry tests against that
payload and samples startup/shutdown plus self-reported RSS. `--browser` runs
the real extension against the packaged child. To evaluate Bun, use
`--engine bun --bun /path/to/pinned/bun`; compiled evaluation artifacts are not
authorized for redistribution by this script. No system installation changes.

## Boundary

The shared host now owns ordinary browser policy and CDP endpoint/session
lifetime, with `profiles.ts` and `streams.ts` providing portable selection,
identity and reservation policy. `node/cdp.ts` supplies bounded WebSocket I/O
using pinned `ws` 8.22.1 (MIT); Node payloads retain its upstream LICENSE.
Every stream is bound to native owner checks and payload-free native audit
acknowledgements. The native parent supplies safety and caller authority facts.

`src/core.ts` owns bounded provider registration, exact-profile approval,
original-consent checkpoints, typed browser operations, queue/dispatch lifetime,
deadlines and revocation. Production approval may be timed or until Stop.
`testing/reference-provider.ts` owns a manual clock and an independent counter
target with held replies. It has no grant/routing policy. The scenario checks
the counter separately from the core's delivery/effect result.

`src/extension-provider.ts` implements `ProviderAdapter` over the existing
protocol-v1 worker, projects exact core authority to grant messages, correlates
wire replies to exact dispatch handles, normalizes bounded observations and
forwards cancellation. Chrome-directed native messages are capped at 1 MiB;
provider observations and the private child channel allow bounded 16 MiB frames.
The original small tabs/snapshot fixture retains its stricter discovery limits;
production operations use the bounded ordinary browser contract. Budgets are rechecked at dispatch; less than the worker's
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
An authenticated dead transport may explicitly retire its correlation capacity;
this does not assert that the application effect stopped or was undone. A
late reply still cannot complete or retarget a newer request. Returned effects are consumed
by the host; the core retains no unbounded event/result history.

The Windows desktop adapter now authenticates native peers and operator
choices before invoking the production inlet. Extension-local UUIDs and labels
supply profile identity; exact operator selection supplies authority. Native
code retains session/owner safety, audit storage and artifact writes. The
shared host owns browser scope, lifetime, routing, references and CDP streams.
Its bundled Node runtime is required in Windows desktop companion payloads.
Run `pnpm --dir runtime install --frozen-lockfile` before packaging.
Windows signing preserves the pinned upstream Node executable. The publisher
catalog authenticates `payload.json`; `scripts/verify.py` checks its full-byte
inventory before signing/bundling and during installed verification.

`testing/browser-host.ts` retains a private fixture inlet for the original
real-browser regression. `testing/reference-browser.ts` supplies the complete
ordinary-operation model behind the production inlet. Neither proves native
Windows integration by itself. Mac and Linux residents have not adopted this
boundary. The Python CLI/client remains in Python; `browser --profile` checks
resident capability before dispatch and refuses an incompatible resident.
