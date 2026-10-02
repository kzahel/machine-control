# 054 — Windows browser integration and ARM64 desktop acceptance

Status: active.

Owning topics: [Windows desktop](../../topics/windows-desktop.md),
[browser control](../../topics/browser-control.md), and
[native distribution](../../topics/native-distribution.md).

## Objective and completion conditions

Extend the shared Windows desktop product with the existing Chrome extension
and native-messaging contract. Prove scope enforcement, independent browser
fixture effects/capture, and signed installed lifecycle on available Windows
VMs. Execute the signed ARM64 product in ARM64 Windows when a claimed target
with a verified credential handoff is available.

## Boundaries

Preserve the separate component/appliance profiles. Browser authority belongs
to the resident grant broker, not the extension or WebView. Native-messaging
registration is per user and explicit. Authenticate the bundled provider using
kernel-observed client process identity; never expose approval on that pipe.
Do not install protected unlock as part of ordinary browser setup. Keep the
person's installed browser/profile separate from dedicated test browsers.
Physical hardware and public Windows publication remain subsequent work.

## Ordered work

### 1 — resolve available Windows targets

Run common read-only doctor and credential lookup. Repair exact private
identity when supported; never guess credentials or infer a healthy ARM64 VM
from earlier records. Acquire exclusive claims for target operations, preserve
initial power state, and release after cleanup.

### 2 — connect the Chrome provider

Reuse the extension protocol and operation vocabulary. Add bounded native
framing, an authenticated provider pipe, browser/devtools scopes, state changes,
revocation, artifacts, and truthful action/effect results. Register the native
host through a closed operator command and expose concise existing setup UI.
Browser-level CDP attachment remains separately scoped.

### 3 — prove browser enforcement and effects

Use a dedicated Chrome for Testing installation/profile and an independent
fixture oracle. Test off-state refusal, browser versus devtools authority,
prompt pause, stale generations/references, origin/provider rejection, timeout,
disconnect/restart, Stop/expiry, semantic effects, navigation, and PNG/hash
verification. Exercise raw CDP and streamed events if implemented. Do not use
API acknowledgement alone as an effect oracle.

### 4 — accept exact signed packages

Run native contracts/format/static checks and ARM64/x64 publishes, then build
signed candidates with meaningful notes. Validate final provenance/signatures
and exact installed bytes before browser, tray, grant/lifecycle, and update
acceptance. Run on each available architecture without projecting x64 results
onto ARM64. Restore registration, test browsers, app installation, temporary
fixture trust, VM power state, credentials, and claims.

## Validation

Portable browser/broker contracts; native Windows format, build, and static
checks; ARM64/x64 publishes; TypeScript/build and Rust checks; release/workflow
checks; independent browser fixture and installed signed acceptance. Update the
[desktop matrix](../desktop-acceptance.md) with actual observed cells.

## Result

Source-native x64 browser conformance passes with a dedicated Chrome for
Testing profile: independent counter/text effects, navigation, capture/hash,
browser versus DevTools scopes, prompt pause, denial/narrowing/request timeout,
Stop/expiry, stale grant/snapshot/provider references, bounded operation timeout
with unknown delivery/no replay, provider reconnect, and origin/process refusal.
The native host exits when the resident ends while Chrome remains alive.
Registration and owned test processes/profiles are restored after the probe.

Portable contracts, native static/build/format checks, both self-contained
publishes, frontend build, portable repository checks, and 46 release tests pass.
Exact signed 0.4.4 x64 installed grant, Cua, tray, lifecycle and startup
registration acceptance passes. The 0.4.3 to 0.4.4 update relaunches correctly.
Signed 0.4.4 browser setup, native approvals, independent effects/capture,
DevTools separation, Stop, stale references and operator restart also pass.

The 0.4.4 to 0.4.5 browser-open update exposes a replacement blocker: Chrome
retries native messaging after the sender exits and keeps the old executable
open. NSIS installs the operator but pauses at the resident file-write prompt;
this is not an accepted update. The incoming 0.4.6 installer temporarily hides
only the owning manifest, waits for those processes to exit, then restores its
exact bytes and unchanged registry value after extraction. Startup recovers an
interrupted maintenance marker. Native ownership, collision, invalid-origin,
restoration and noninteractive uninstall probes pass. Real Chrome also passes
maintenance pause, retry suppression, interrupted-state startup recovery and
reconnection with access off. Exact signed 0.4.4 to 0.4.6 replacement now passes
with Chrome open: installer completion, automatic relaunch, exact payload,
retained registration/manifest/startup, fresh generation, access off, stale
reference refusal, provider reconnect and an independent new browser effect.
Lock then revokes the browser grant and generation. Native logoff followed by
stored-credential sign-in starts 0.4.6 in background with access off; this is
not in-place unlock. Real cold-boot/sign-in startup of 0.4.5 also passed.
A separate SSH transport failure was
recovered through the claimed native lifecycle route, without outer UI.

The updated exact signed 0.4.6 package passes all 128 installed UI checks,
including the real-login background restart path, native approvals, expiry,
Cua effects/capture, self-interface refusal, tray actions and failure cleanup.
Its bundled ordinary-user component passes protected-operation refusal,
independent Cua effects/capture, provider failure/recovery, disclosed fallback
and interrupted IPC. The final 0.4.6 browser task also passes local/outside
effects and exact PNG transfer.

Ordinary 0.4.6 uninstall with connected Chrome exposed an asynchronous
native-host image-release race: registration/startup and other files disappear,
but the host executable remains despite a successful exit. Candidate 0.4.7
moves Tauri's path-bound operator stop before unregistering, then retries only
that owned image before removing the rest of the payload. Failure returns an
error while the remaining installation is still available for retry. Signed
acceptance of this correction remains pending. Chrome's extension directory
watcher can separately retain empty directories after all payload files are gone.

Local inventory presently has no registered Windows target or ready
credential handoff. The accepted remote x64 target has verified identity and a
stored credential. Local ARM64 provisioning is a separate target-selection
question; no ARM64 execution is inferred from cross-build or prior component
acceptance.

Exact candidate identities:

| Version | Source | Workflow | Accepted boundary |
| --- | --- | --- | --- |
| 0.4.4 | `9890fbc65eb9ad1ebb2c7340d5cb1816601c9a17` | [36932907245](https://github.com/kzahel/machine-control/actions/runs/36932907245) | x64 installed UI/lifecycle and browser tasks; both architecture packages verified |
| 0.4.5 | `37608c6e8094a2ee54d56ab0a0a7924bf6fec072` | [36935615977](https://github.com/kzahel/machine-control/actions/runs/36935615977) | x64 browser task, outside/local effects/artifacts and real login startup; both packages verified; browser-open update not accepted |
| 0.4.6 | `fae55064c042cfc026071880333916a573658bb9` | [36941024448](https://github.com/kzahel/machine-control/actions/runs/36941024448) | Both architecture packages verified; x64 installed UI, browser-open update, lock revocation and actual sign-in startup pass |
