# 056 — Linux desktop application

Status: in progress

Owning topics: [Linux desktop](../../topics/linux-desktop.md),
[Linux resident control](../../topics/linux-resident-control.md),
[host control](../../topics/host-control.md), and
[native distribution](../../topics/native-distribution.md).

## Objective and completion conditions

Bring the Linux shared Tauri app to the Mac/Windows product contract, beginning
with an ordinary-user Ubuntu GNOME Wayland profile and honest support boundaries.

- Native grants gate provider dispatch; approval, denial, narrowing, expiry,
  prompt pause, Stop, session loss, restart, and replacement invalidate access.
- Native consent and operator surfaces cannot be controlled through the app.
- Target-native semantics, portal capture, pointer, keyboard, and Unicode input
  produce independently observed fixture effects without appliance privilege.
- The compact settings UI and tray provide Open, Settings, Updates, Stop, Quit,
  startup, and a truthfully reported emergency Stop route.
- Browser integration has independent scope and lifecycle evidence.
- Exact Debian/AppImage candidates carry source/payload receipts and updater
  authentication; all supported platforms share one release transaction.
- Installed lifecycle, automatic replacement, stale references, and existing
  appliance compatibility are tested; untested architectures remain explicit.

## Boundaries

No root input broker, permission-store edits, shell extension installed silently,
protected desktop control, or weakened session/lock policy. Portal consent is
visible and cancellable. Prefer the existing AT-SPI implementation over a new
provider; compositor APIs stay behind an ordinary-user adapter.

Use read-only doctor and exclusive common claims before VM work. Preserve initial
power and canonical stored credentials, clean up owned application/test state,
and keep private captures, target identity, tokens, and logs outside Git.

## Ordered work

### 1 — establish ordinary-user portal control

Measure RemoteDesktop/ScreenCast on the accepted GNOME VM. Implement consent,
session closure, capture, input, and capability reporting without root virtual
HID. Reuse native semantics; preserve independently observed effects.

### 2 — enforce access and connect the operator

Add the native grant broker, bounded public socket, private inherited operator
channel, GTK approvals, operator/consent protection, session monitor, and process
supervision. Connect the shared UI, tray, startup, Stop, and restart.

### 3 — integrate browser and packages

Reuse the extension protocol, add Linux native messaging and scope enforcement,
package Debian/AppImage with native dependencies and source receipts, and extend
the unified candidate/release/download/updater path.

### 4 — accept exact installed candidates

Prove independent semantics, pixels and input, refusal and lifecycle cases,
browser-open replacement, startup, local/outside parity, cleanup, and appliance
compatibility. Record architecture-specific results in the acceptance matrix.

## Validation and final result

Source-native acceptance passed 51 x64 GNOME VM checks: off/refusal, native
denial/approval, prompt pause, Stop, generations, portal consent, capture/hash,
pointer and Unicode file effects, sharing closure, old references, expiry,
update exclusion, Quit, and endpoint removal. Eight portable grant tests,
150 common-client tests, frontend build, Linux compile/Clippy, and 33 Linux static
tests pass. Installed product gates remain.

Source-native browser acceptance passes 29 headed Chrome for Testing checks:
native host registration, scope separation, independent click and Unicode HTTP
effects, capture/hash, unavailable upload, DevTools evaluation, Stop, stale
references, and reconnect with Chrome alive through operator replacement.
The existing Linux appliance live smoke passes with the companion installed as
a separate ordinary-user profile. Native Linux Clippy passes after the
supervisor's AppImage environment cleanup and compiled identity additions.

Development AppImage acceptance passes 43 native product checks: compact UI,
single instance, the five tray actions, Stop and self-interface refusal, startup
registration/removal, actual shortcut effect, native denial/approval and pause,
expiry, portal consent and capture/hash, Restart revocation and sharing closure,
close-to-tray, reopen, and Quit. GStreamer/GTK search-prefix leakage from AppImage
was found in installed testing and removed from the system Python companion.
Foreground identity uncertainty refuses input rather than choosing another app.

Initial signed x64 and ARM64 candidates from source `ee90c05` in Linux workflow
`36968445205.1` pass native container inventories, both final signatures,
authenticated versions, receipt identities, and tamper rejection. They precede
the environment fix and are not the final installed acceptance candidates.

Portable grant/protocol tests, Linux platform smoke, frontend checks,
Linux native build/package verification, and claimed installed GNOME acceptance
are required before recording the corresponding support claim.
