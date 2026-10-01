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
publishes, frontend build, portable repository checks, and 43 release tests pass.
Exact signed installed UI/browser and update acceptance remain pending.

Local inventory presently has no registered Windows target or ready
credential handoff. The accepted remote x64 target has verified identity and a
stored credential. Local ARM64 provisioning is a separate target-selection
question; no ARM64 execution is inferred from cross-build or prior component
acceptance.
