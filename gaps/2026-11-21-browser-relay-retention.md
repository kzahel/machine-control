# Browser relay memory and connection retention

Topic: `shared-resident-core`

Status **Repaired in source.** Isolated fixtures reproduced heap growth in
the macOS Chrome native-messaging helper and bounded retained browser state
in the Linux relay and Windows managed transport.

## macOS Chrome helper retains incoming buffers

`runBrowserHost` receives Chrome messages with `FileHandle.readData` on a
detached thread without a per-message autorelease pool. A scratch build of
the production helper relayed complete 8 KiB messages between a pipe and a
local socket fixture. After warmup, another 8,192 Chrome-to-resident frames
added 32,800 live default-zone blocks and raised the footprint from 10.4 MB
to 139.7 MB. A scratch variant with per-message pools added zero live blocks
and stayed near 2.4 MB on the same workload. The resident-to-Chrome loop
showed zero live-block growth in the original helper. This helper runs in a
separate process from the resident policy reader.
[macOS Chrome helper](../platforms/macos/resident/Sources/macui/BrowserHost.swift),
[policy reader incident](2026-11-21-macos-policy-reader-heap-growth.md)

The helper drains the incoming thread's pool after each complete message.
The allocation fixture checks byte-for-byte delivery and clean helper exit.

## Linux endpoint lookups retain duplicate authority

Each `browser.endpoint` request adds a fresh native authority under the same
live owner, and endpoint completion keeps the entry even if the shared
policy refuses to create an endpoint. The shared stream layer reuses an
endpoint for the same authority ID, connection and authorization generation.
The Windows and macOS adapters reuse authority IDs for repeated lookups by
the same live owner. [Linux relay](../desktop/native/linux/browser.py),
[shared endpoint store](../runtime/src/streams.ts),
[Windows relay](../src/MachineControl.Windows/BrowserRelay.cs),
[macOS relay](../platforms/macos/resident/Sources/macui/BrowserRelay.swift)

With the production Python relay and a real local policy child, the first 16
lookups for one authorized profile succeeded. The seventeenth returned
`browser_stream_capacity`. Further refusals left 128 native records occupied,
at which point the native limit also refused the next request. The relay's
owner-ended handler removed all 128. This is bounded retention with a
capacity failure during the active owner.

All three native relays now reuse a valid authority for the same live owner
and preserve it while overlapping endpoint lookups are in flight. The last
refusal releases an authority that issued no endpoint. The Linux and macOS
regressions cover a refusal followed by an overlapping success and show
that the successful endpoint is still reused.

## Interrupted attachment can leave a stale connected profile

Policy can attach a browser profile before the native parent learns its
connection ID. On Linux the disconnect handler needs that ID, and the late
completion skips closed peers. In a fixture that delayed the completion
until after disconnect, the production relay had zero peers while the real
policy child still reported the profile connected. Reattaching the same
profile returned `profile_conflict`. The macOS relay has the same early-exit
shape in source when a peer disappears before its attach callback.
[Linux attach completion](../desktop/native/linux/browser.py),
[macOS attach completion](../platforms/macos/resident/Sources/macui/BrowserRelay.swift)

The Windows relay awaits the attach reply with the handshake cancellation
token and only assigns the connection ID after that await. A portable .NET
fixture used the actual Windows `SharedBrowserHost` and real `PolicyHost`,
holding the attach reply while the child reported the profile connected.
Cancelling the await and then delivering the late reply left the transport
healthy and a repeat attach returned `profile_conflict`. The Windows
named-pipe timing was source-reviewed. [Windows relay](../src/MachineControl.Windows/BrowserRelay.cs),
[managed policy transport](../src/MachineControl.Windows/SharedBrowserHost.cs)

An orphan occupies one of the shared core's 16 provider slots. The native
relays now order detach after attach on the same policy pipe using a fresh
transport tag. The child retires only that peer's connection. The shared
regression also checks that an obsolete detach leaves a replacement and a
second profile connected.

## VM verification

- **macOS ARM64:** The locally signed app installed and its bundled
  native-messaging helper successfully attached, disconnected, and
  reattached to the same profile through the running resident. A separate
  old/new Swift relay fixture measured 32,800 additional live blocks and a
  footprint increase from 10.1 MiB to 139.3 MiB in the old incoming loop.
  After the same 8,192 frames the pooled loop added zero blocks and stayed
  at about 2.1 MiB. The reverse direction added zero blocks in both builds.
- **Linux ARM64:** The six focused tests ran in a disposable guest with
  the production Python relay and the pinned Node policy package. They
  exercised endpoint reuse, refused and overlapping lookups, and profile
  reconnection after the native peer closed before attach completion.
- **Windows ARM64:** The native .NET contract suite passed against the
  pinned policy child. The managed IPC fixture held a successful attach
  reply, cancelled its native waiter, detached by tag, and reattached the
  profile. Windows overlapped lookup handling and the named-pipe relay's
  handoff remain source-reviewed.

## Shared endpoints remain allocated after owner release

**Fixed in source, fixture-tested.** The shared policy used to retain
endpoint slots for a still-current Browser approval even after the native
owner ended. [Shared endpoint table](../runtime/src/streams.ts)

A bounded probe against the production policy granted 16 sequential owners
one endpoint each under the same browser approval. The probe closed each
owner through the production admission path, observed its yield, and
checked that active owner count returned to zero. Owner 17 received
`browser_stream_capacity`. Stopping Browser and reapproving it let the next
owner obtain an endpoint. This exhausted a fixed table shared by the three
desktop adapters. A second probe closed an owner while the first endpoint
was waiting for the loopback listener to start. The policy still published
an accepted endpoint reply after the owner yielded. The native boundary
rejected use by that ended owner.

The repair follows the admitted session through yield. A production policy
fixture now cycles 18 owners under one approval, closes the released
owner's live WebSocket, refuses its old endpoint before native admission,
and keeps an unrelated profile and stream live. A separate fixture closes
the first owner during listener startup and receives a typed refusal.
These are shared policy and loopback tests on a local host.
[Loopback bridge](../runtime/node/cdp.ts)

## A late CDP authorization can strand a native audit

**Open, fixture-tested in the shared bridge.** The policy resolves an
unanswered native CDP `begin` after three seconds. The WebSocket upgrade
refuses the connection and sends no `result` if that response is false.
A delayed native side can already have created the audit entry when the
policy times out.

A probe used the production policy, a loopback WebSocket client, and a
native fixture that recorded the audit but delayed its positive reply
past the deadline. The socket closed, the late reply arrived, and the
fixture still held one audit without a result. The desktop adapters limit
their live audit tables to 256 entries. Exhaustion of a live native
adapter's table remains source-reviewed.
[Shared bridge](../runtime/node/cdp.ts),
[native check deadline](../runtime/node/policy-host.ts)
