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

Pending. Portable grant/protocol tests, Linux platform smoke, frontend checks,
Linux native build/package verification, and claimed installed GNOME acceptance
are required before recording the corresponding support claim.
