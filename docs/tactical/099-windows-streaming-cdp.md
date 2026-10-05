# 099 — Windows streaming CDP

Status: completed source implementation and focused x64 candidate acceptance.
Signed release and broader platform qualification remain separate.
Owning topics: [browser control](../../topics/browser-control.md) and
[Windows desktop](../../topics/windows-desktop.md).

## Objective and completion conditions

Add streaming per-tab CDP to the Windows desktop app, reusing the extension's
existing raw session protocol and the Mac bridge's CDP wire vocabulary. Retain
Windows live ownership, DevTools scope, audit and Pause/Stop fences. Validate
real commands and events in a claimed Windows VM with an independent effect
oracle, clean up the candidate and restore initial power, then commit.

## Boundaries

Host a bounded IPv4 loopback WebSocket listener in the ordinary desktop
resident. An endpoint lends the existing owner's authority; it creates no
grant or admission session and does not heartbeat ownership. Reject web-page
Origins. Bind tokens and requests to owner, grant and provider generations.
Use a separately identified Chrome for Testing, the real operator UI, target
native messaging and retained SDK channel. Keep concrete inventory, paths,
tokens, profiles and evidence private. Browser-level target emulation, tunnel
automation, signed release and other execution architectures are separate.

## Ordered work

### 1 — expose owner-bound per-tab streams

Advertise `browser.endpoint` under DevTools scope, permit owned dispatch and
return the common `devtoolsEndpoint` template. Relay raw session open, command,
result, event and close frames through the authenticated native provider.
Recheck owner/grant/provider authority at dispatch and forwarding. Fence shared
worker session open/commands when DevTools is unavailable. Refuse automatic
one-shot ownership for an endpoint whose URL would immediately expire.

### 2 — bound transport and record truthful outcomes

Validate strict HTTP upgrades and text CDP command shapes. Bound connections,
per-tab attachment, input/output sizes, queued bytes, outstanding commands and
deadlines. Close on authority changes, malformed traffic or backpressure. Audit
attachment and command intent/results using payload-free metadata. Preserve
confirmed provider delivery versus unverifiable application effect; do not
replay uncertain commands.

### 3 — prove the real browser and cleanup

Exercise page reads, subscribed debugger events, correlated concurrent commands
and provider errors. Independently observe synthetic HTTP effects exactly once.
Check browser-only refusal, absent ownership, bad tokens/Origins, duplicate tab
connections, Pause/Resume, owner disconnect, native-host restart and Stop.
Run format/contracts, extension/client tests and x64/ARM64 publishes. Restore
registration, stop access, reap owned processes, remove staging, verify stored
credentials, restore initial power and release the exact claim.

## Validation and result

**Current — conformance-tested for the staged x64 desktop route:** all 28
checks pass in a claimed Windows-hosted VirtualBox VM with the real operator
UI and a fresh Chrome for Testing 154.0.8037.92 profile. The retained SDK owner
uses `chrome.extension/cdp`. Raw page-main-world reads, console events, multiple
outstanding command IDs and CDP errors pass. Three deliberate synthetic effects
are independently observed by the loopback HTTP server exactly once each.
An unresolved `awaitPromise` leaves another command responsive, and Pause
interrupts the pending work. No commands are automatically replayed.

Browser-only grants and owners cannot mint an endpoint; standing DevTools
access requires a live owner. Wrong tokens and every Origin header, including
empty ones, refuse. A second connection to the same tab refuses. Pause/Resume,
owner disconnect, native-host termination/reconnect and Stop close streams and
invalidate old endpoints. Malformed commands close their connection before
another fixture effect. The fresh worker hash is independently verified.

Contract fixtures additionally prove malformed/duplicate HTTP headers, forged
fields, duplicate JSON keys, oversized/binary frames, duplicate outstanding IDs,
the 16-command bound, grant expiry, unavailable provider and failed audit storage.
Revoked URLs remain invalid after availability recovers. Attachment and command
intent/results record confirmed delivery or unknown completion without raw
tokens, method names, parameters or returned data. Shared worker fixtures prove
browser-only session refusal, concurrent commands during pending work, cleanup
and late-result suppression after session close.

Validation passes: runtime and desktop-contract format verification, desktop
and unlock contracts, self-contained x64/ARM64 publishes, all eight extension
lifecycle tests and all 232 common-client tests (nine platform skips). Python
fixture compilation and Git whitespace checks pass. Frontend/native shell code
is unchanged; the existing debug Tauri shell is exercised by the real UI actor.
The accepted self-contained runtime SHA-256 is
`25ef30a6081a6bc65589f92725d94135c7cb61f7103e0ea5cb171ce4d14f44f0`;
the shared worker SHA-256 is
`6fbe7b48f0f2971dbb000b7f3696ec158269e6a17f1ed232b6c1862dddb27374`.
This is an unsigned development working-tree assembly, not signed installed
release evidence. ARM64 live, physical targets, other browsers, browser-level
attachment, automatic tunnel setup, hostile same-user containment and live
exhaustion of every timeout/backpressure bound are not established.

The actor stops access, closes ownership, restores registration and reaps its
app, browser and HTTP server. Independent inspection confirms zero owned
processes, no candidate registration, and the expected worker hash. Final
controller inspection confirms the owned staging directory and scheduled task
are absent. Canonical stored-credential verification passes. The VM returns to
its initial powered-off state in 38.021 seconds with the existing configured
shutdown scheduling assist; no forced power cut is used. The exact target-use
claim is released. This does not establish unassisted VirtualBox shutdown.

Testbed friction: cold boot stalled both sign-in and SSH administration. One
exact claimed pause/resume restored the route, followed by canonical stored
credential login without console input. A repeated fixture initially attempted
reconnection before native detach cleanup completed; it now waits for bounded
connection establishment without replaying commands. Reusing a profile retained
the old Manifest V3 worker and masked the concurrent-command change; each run
now creates a fresh profile. The final fresh-profile run passes. The native
audit-outage fixture uses a read-only sharing lease on Windows to avoid racing
directory rename against active file/scanner handles.

The [operator guide](../../desktop/WINDOWS-STREAMING-CDP.md) owns usage, limits
and the target-loopback forwarding boundary. The repeatable actor is
[`browser-cdp-live.py`](../../tests/windows/browser-cdp-live.py), with its
standard-library tab client in [`cdp_socket.py`](../../tests/windows/cdp_socket.py).
