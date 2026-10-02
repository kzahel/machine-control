# 056 — Linux desktop application

Status: complete for the ordinary-user GNOME Wayland x64 preview

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

The accepted package source is `51bb77c` in unified workflow
`36978723452.1`, version 0.5.0. All six Mac/Windows/Linux native architecture
jobs pass. Linux x64 and ARM64 final Debian/AppImage containers pass exact
16-file runtime inventories, compiled identity, source/workflow receipts,
authenticated versions, both package signatures, and tamper rejection.
Publication was skipped; these are candidates, not a public Linux release.

| Acceptance | Ubuntu 24.04 GNOME 46 Wayland x64 VM |
| --- | --- |
| Source-native desktop contract baseline | 53 checks; independent semantic, pointer, drag/scroll, Unicode and capture/hash effects |
| Source-native Chrome integration baseline | 29 checks; scope separation, effects, capture/hash, stale references and reconnect |
| Exact signed AppImage | 54 native UI/effect/lifecycle checks |
| Exact signed Debian install | 54 native UI/effect/lifecycle checks |
| Signed AppImage replacement | 40 checks; authentication/refusal, exact replacement, automatic relaunch Off and full browser tasks |
| Native screen lock | 10 checks; access revoked, sharing closed, generation rotated and operations refused |
| Reboot/login startup | 8 checks; exact source, background launch, access/sharing Off, preference removal and Quit |
| Ordinary Debian removal | 9 preparation and 7 removal checks; Chrome/user app survive and browser user data remains |
| Common CLI | Local/outside generation parity, independent semantic effects and matching artifact hashes |
| Existing appliance | Claimed live platform smoke passes; ordinary-user desktop remains a separate explicit instance |

Installed acceptance uses native AT-SPI, tray D-Bus, the public socket, visible
portal consent, and independent fixture effects rather than WebView test hooks.
It covers single instance, native denial/approval and pause, expiry, self-interface
refusal, stable-path startup registration/removal, the actual Stop shortcut,
Restart, close/reopen, Quit, and forced operator-loss cleanup while the fixture
survives. The final UI and near-clock tray icon were visually inspected through
independent target-native capture.

Replacement uses an explicitly signed 0.4.8 `update_sender_fixture` from source
`278f2fc` and workflow `36973342785.1`, with a private HTTPS localhost feed and
a disposable copy of the sender. Its purpose and artifact names exclude it from
publication. The final 0.5.0 incoming bytes are authenticated before transfer.
The app refuses modified bytes and a grant armed during download, then installs
the exact valid image. Chrome remains alive, reconnects after native approval,
and performs navigation, click, Unicode and PNG/hash tasks; DevTools remains a
separate scope. This proves the installed updater, not the public Linux route.

Packaging tests exposed AppImage library-prefix leakage and a GTK/AT-SPI callback
deadlock absent from the source-only run. The system Python companion now clears
bundled search paths; Rust operator IPC and lifecycle waits run outside GTK's
event thread. Cold-boot work exposed an upstream unquoted startup path. Linux
now owns an atomic private XDG entry with a fixed positional execv launcher.
Three tests prove opt-in/removal, foreign/symlink preservation, and real native
GIO launches for six reserved-path cases. The final installed reboot test uses
persistent staging and the correctly quoted path containing spaces.

Build dependency installation upgraded this software-rendered VM's Mesa packages.
The next GNOME Wayland startup crashed and fell back to X11. Restoring the
pre-test distribution revision, 25.2.8-0ubuntu0.24.04.2, restored Wayland; read-only
doctor, live smoke and the final app reboot all pass. This is recorded as a
specific testbed dependency observation, not a general compositor diagnosis.

`tests/desktop/linux-installed.py` owns installed UI/effect acceptance,
`linux-updates.py` owns replacement/browser acceptance, and `linux-session.py`
owns the two-phase lock/reboot startup check. Run headed helpers in the active
user's session through the claimed target-native lifecycle; use persistent
staging and read-only doctor after reboot. No outer UI is used.

Portable validation passes eight grant tests, 150 common-client tests, 33 Linux
static tests, 12 unified publication tests and nine website route/proxy tests.
Frontend/build checks, native Linux compile/Clippy, shell syntax and Python
compilation pass. Publication tests require all six architectures and 29 assets,
refuse missing Linux before writing output, and exclude sender fixtures.

ARM64 has native build/package evidence only. Other compositors, physical
hardware, multiple monitors/scaling, suspend/resume, protected login/unlock and
production Linux downloads/updates remain open. Reboot recovery is not an
in-place unlock test. Private target identity, credentials, captures and raw
reports stay outside the public repository.

The canonical stored VM password passes the claimed, pinned secret-transport
hash verifier before and after reboot; its private file remains ready and mode
0600. Owned app/browser profiles, startup/shortcut registration, temporary SSH
verification key, TLS root, sandbox helper and staging were removed. Final
appliance doctor is ready; the VM is restored to its original powered-off state
and the exclusive claim is released. Raw evidence is retained privately.
