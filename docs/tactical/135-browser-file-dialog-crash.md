# Browser file-dialog crash investigation

Owning topics: [Mac resident control](../../topics/macos-resident-control.md),
[desktop audit and diagnostics](../../topics/desktop-audit-and-diagnostics.md).

Status: complete; released packaged crash reproduced and fix validated.

## Objective

Investigate reports that the desktop app exited during browser tasks,
possibly when choosing a download location. Assess retained crash evidence,
exercise real browser/file-dialog workflows on dedicated appliances, and
correct any evidenced native failure without broadening logging to payloads.

## Completion conditions

- Identify what the existing audit and diagnostics can establish and what
  requires a separate OS report.
- Address the evidenced failing code path with a regression check.
- Exercise real browser effects and file dialogs; detect resident restarts
  rather than accepting a recovered connection as uninterrupted success.
- Restore target lifecycle, release claims, and preserve raw evidence privately.

## Boundaries

No controller workstation app replacement, release, OS crash upload, raw
stderr capture, new credential, outer guest input, or VM rebuild. The packaged
campaign temporarily replaces the dedicated VM's app and uses a stricter
workstation policy, with original app/policy/operator state backed up and
restored. A clean bounded run does not prove every reported crash has the
same cause.

## Ordered work

### 1 — correlate operation history and the OS crash

**Current:** a macOS desktop 0.6.8 report contains an `EXC_BREAKPOINT`/`SIGTRAP`
dispatch assertion. Its faulting stack runs through HIToolbox input-source
property lookup, `KeyboardLayoutSnapshot.current`, `ResidentService.sendKey`
and `PanelChooser.navigate`. A retained `dialog.choose` intent at the same
timestamp has no result. The raw report and operation history remain private.

The application audit identifies the interrupted operation, while the OS
report supplies the faulting stack. Diagnostic export includes neither OS
reports nor full native/Rust/webview crash coverage. Diagnostics retain seven
days and audit thirty days, with independent byte caps. Updated operator
guidance describes private collection and these limits.

### 2 — keep keyboard-layout properties on the main queue

The native provider executes operations on its serial worker. Copy the
selected input source, keyboard layout data, source identifiers and keyboard
type on the main queue; return an immutable layout snapshot to the worker.
Keep AX operations, panel waits, key planning and delivery on the worker.
Existing per-request acquisition and layout-change refusal remain intact.
An XCTest now calls the real layout lookup and verification from a worker,
including the chord used to open Go to Folder.

### 3 — exercise browser downloads and native panels

Added [a guest-only runner](../../tests/macos/browser-file-dialogs.py) using
Chrome for Testing, the owned extension, a disposable profile and a loopback
HTTP fixture. It exercises extension click, Unicode typing and PNG capture;
real downloads and upload Open panels; cancellation after unconfirmed
navigation; an unanswered overwrite prompt; Save Page As; and no-panel refusal.
File bytes and HTTP request bodies independently verify effects. Every reply
must retain one resident generation, with final PID and OS-report checks.
Cleanup releases the tab, reaps the browser process group, removes its profile
and stops its server. The controller owns staging, deployment, power and claims.

### 4 — distinguish the initial standalone evidence

**Current (2026-10-24), bounded `live-tested`:** macOS 26.6.2 ARM64 with
Chrome for Testing 155.0.8059.79 passes ten checks on the existing source
appliance and eighteen checks on the repaired source appliance. The repaired
run includes five independent download/upload cycles. Both preserve resident
PID/generation and produce no new resident OS report. This initial standalone
campaign did not reproduce the crash; the packaged campaign below does.

All 223 resident Swift tests, the Mac static smoke suite, and ARM64/x86_64
source-native app builds pass. The x86_64 result is build evidence only.
The existing live keyboard matrix also passes all six U.S./Dvorak/hybrid
layout and default/remapped-modifier cells (210 resident checks), followed by
real Chrome for Testing navigation, Unicode typing, clipboard and new/close
tab effects. Temporary guest settings are restored; passive controller cursor
and frontmost-app samples are unchanged and outer input is forbidden.

The Windows attempt could resolve exact identity after loading the UTM
library, but a successful start response was followed by independently
observed power Off. The readiness monitor was cancelled after confirming that
state; no Windows browser execution is claimed. Its claim was released and
the appliance remains Off. Linux received read-only preflight only. Private
usage notes retain startup/selection friction and session references.
The Mac appliance returns to its initial suspended state, with all scoped
claims released and temporary browser/fixture staging removed.

### 5 — reproduce the released packaged app crash

The controller user clarified that the installed app is their ordinary route
and explicitly requested reproduction and repair there. Use the same signed
0.6.8 app as that installed product, copied read-only from the controller.
Verify its expected Developer ID, strict nested signatures, version/source
identity and Gatekeeper acceptance before staging. The baseline is the
unchanged released bundle from source `fa776a6`.

Run it through the actual per-user installer in the dedicated VM, on the
canonical native-host socket and under trusted workstation policy. A separate
standing observer presses the real native approval; the test uses the app's
own bundled extension and native-messaging executable. Root appliance policy,
original app bytes/modes/symlinks, LaunchAgent, operator files and preferences
are preserved for restoration. There is no public approval bypass or TCC edit.

**Current, packaged `live-tested`:** two independent fresh 0.6.8 launches
crash at the first download-location `dialog.choose`, after extension click,
Unicode typing and browser PNG capture pass. Both new OS reports show
`EXC_BREAKPOINT`/`SIGTRAP` at `_dispatch_assert_queue_fail`, through
`TSMGetInputSourceProperty`, `KeyboardLayoutSnapshot.current`, `sendKey` and
`PanelChooser.navigate`. This matches the original reported stack. The
LaunchAgent brings back a resident after the fatal exit; the failed connection
and OS report must not be hidden by a later successful status request.

### 6 — qualify the repaired embedded framework

Keep the released Rust shell, frontend and extension, rebuild its unchanged
native sources plus the main-queue keyboard fix as `MCResident.framework`,
then locally Developer ID sign and strictly verify the complete candidate.
This isolates the native repair while exercising the real packaged process.
The locally modified package is not a new notarized or published release;
private receipts identify its framework digest rather than treating the
released source stamp as an identity for the modification.

The first complete packaged candidate run passes 29 checks, including ten
download/upload cycles with exact file/HTTP bytes, U.S./Dvorak/hybrid layout
changes, unconfirmed cancellation, unanswered overwrite, Save Page As and
missing-panel refusal. PID/generation remain stable and no new OS report
appears.

Two additional complete candidate runs pass eighteen Settings-lifecycle checks
with three download/upload cycles, then fifteen checks with another three
cycles after a fresh app launch. Settings is recreated and closed three times
in the same runtime. The fresh launch independently reports `physical_activity`
and clears through the ordinary quiet window before browser operations begin.
Across the three successful packaged runs, 62 checks and sixteen download/upload
cycles pass with stable within-run PID/generation and no new crash reports.
The fixed executable satisfies the released executable's designated
requirement; Accessibility and Screen Recording are ready without new grants.

Follow-up fixture work separates ordinary refusal from a crash. A fresh
process can conservatively pause for recent HID activity from the prior
trial; the runner now logs blocking reasons and observes its normal bounded
quiet window without disabling or resuming the safety guard. Settings close
discovery now requests full native fields, because compact snapshots omit the
subrole used to identify `AXCloseButton`. The existing presentation runner
receives the same projection correction. A local argument-name collision in
the expanded runner was also corrected before the actual reproduced action.
Failed attempts and restoration receipts remain private.

Final restoration verifies the original app byte/mode/symlink manifest, root
policy bytes and ownership, LaunchAgent bytes, and operator-file bytes/modes/
presence; saved preferences are imported through the supported defaults tool.
The separate observer and test-browser processes are stopped and owned staging
is removed. The Mac returns to its initial suspended state and scoped claims
are released. Raw crash reports, signed candidate identities, failed-attempt
logs and successful reports remain private. The controller's installed app and
canonical VM credentials are unchanged.

## Final result

The packaged released app now reproduces one concrete reported crash path.
The shared native source confines keyboard-layout property access to the main
queue, and the repaired framework passes the corresponding packaged browser
workflow. The original standalone pass alone was insufficient evidence.
The fix is unreleased. OS crash-report collection, explicit unexpected-exit
diagnostics, notarized replacement/update acceptance of the fixed release,
broader platform coverage and sustained dependency-fault/load testing remain
open.
