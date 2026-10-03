# Package the Python CLI for desktop consumers

Owning topics: [Installed agent CLI](../../topics/installed-agent-cli.md),
[Native distribution](../../topics/native-distribution.md).

Status: complete, 2026-10-03. Packaging and accepted consumer cutover are
recorded below; continuing contracts and further platform cells live in topics.

## Objective

The maintainer requested end-to-end implementation of YA's desktop-consumer
migration while retaining Python for fast command iteration. Ship the common
client, its local adapters and its runtime with the desktop product; expose
offline identity and agent instructions. YA's
[Tactical 142](../../../yepanywhere/docs/tactical/142-machine-control-desktop-consumer.md)
owns consumer migration and legacy retirement gates.

## Completion conditions and boundaries

Source-independent installed CLI use, authenticated package closure, real
desktop/browser effects and actual YA advertisement must pass before claiming
consumer acceptance. Keep writable state external, local/remote targets honest,
claims separate from access and native sudo separate from desktop arming.
Preserve direct Python development and existing appliance providers. No native
provider rewrite or GUI focus for ordinary CLI commands.

## Ordered work

### 1 — package the Python client and local dependencies

Pin six standalone runtime archives, include local adapters/claim helpers,
stage a relocatable command directory and authenticate complete product bytes.

### 2 — publish identity and agent instructions

Define a versioned offline identity and owned instructions. Test calls without
a checkout, system Python or ambient Python configuration. Expose only installed
default adapters and preserve explicit controller configuration.

### 3 — prove installed control through YA

Build the product, validate in a claimed dedicated appliance, and prove local
semantics, browser operations, artifacts and refusal. Integrate YA discovery
through the same installation. Verify publisher trust before executing probes.

## Validation and result

Mac ARM64 staging, CLI identity, portable packaging negatives, common client
tests, desktop frontend build and Rust tests pass locally. A Developer ID signed
Mac assembly passes deep verification and YA authentication, closure checks and
launch-context composition. Physical CLI relocation and guest execution with
ambient Python disabled pass. The signed ARM64 candidate passes bounded native
control through the installed CLI under workstation approval: denial, narrowed
observe-only access, independent AppKit counter effect, exact-window capture
and artifact PNG bytes, self/protected refusal, prompt pause and Stop/revocation.
Separate controller and guest-local claims are released by the harness.

The broader tray/updater run did not establish acceptance on the local 0.3.0
assembly: the second tray opening did not expose `Check for Updates…` to AX.
The new `--control-only` run passes its declared control slice; it leaves
updater/tray acceptance open rather than treating the broad run as passing. Notarization/publication and Windows/Linux desktop acceptance remain separate
gates. Browser acceptance passes 21 checks with the signed embedded native host and
extension, Chrome for Testing, an independent HTTP/Chrome oracle, and the
installed CLI. It exercises enumeration, semantics/click effects, PNG capture
and bounded artifact retrieval, release/marker cleanup, debugger cancellation,
worker restart/reconnect and resumed control. The separate test browser is
reaped, its temporary profile removed, the native access grant revoked and the
guest-local claim released. A real YA local Codex provider turn reads installed instructions/identity and
invokes its native image viewer on the retained browser fixture PNG, correctly
reporting the visible page button. A controller model also confirms fixture
contents and managed tab-strip presentation. Subsequent YA full-app media
acceptance is recorded below; provider-driven control remains open.

The original appliance policy and socket are restored, resident doctor is
ready, owned candidate/browser/fixture processes are stopped, test files
removed, and guest shutdown is independently observed. Guest and controller
claims are released. The canonical login credential remains ready and
owner-only; no credential changes. Windows/Linux execution and legacy YA
retirement remain open. Windows was initially unavailable from the selected
controller; a subsequent declared alternate controller supports the Windows
execution recorded below. No private infrastructure or credential locators are
recorded here.

Linux ARM64 offline CLI execution passes in an isolated native Ubuntu container
using the bundled interpreter and physically relocated payload. Network and
source checkout are absent; the installed payload is read-only. The run caught
unused terminfo aliases that collide on case-insensitive build filesystems.
Staging now omits that data before extraction, with a regression fixture; all
57 release tests pass. Platform workflows now run the relocation smoke,
including actual Windows installer bytes. These checks do not establish native
Linux approval or capture acceptance.

Windows x64 also passes the relocated smoke in a claimed Windows 11 appliance.
The existing desktop harness now accepts the installed CLI instead of a source
checkout for control and artifacts. Native PowerShell syntax passes. The conflicting/missing selection run was
blocked by the guest's script execution policy; it is not counted as passing. Upload through the command's stdin
timed out; the owned carrier processes were terminated, and SFTP through the
claimed MC transport delivered the bounded payload successfully. Test payload
and harness files are removed. This unsigned staging run proves runtime/client
execution, not the signed desktop package or native approval route.
The appliance was ready and unlocked before cleanup; clean guest shutdown is
confirmed and the target-use claim released. Its canonical login credential
remains ready and owner-only. No installed product or standing policy was
replaced by this offline client test.

YA now passes real-provider live/reloaded media acceptance through its production
app, HTTP routes and browser client on desktop and phone. The model queries the
signed installed CLI and views the retained native browser fixture PNG. Live
media bytes match exactly; after provider shutdown and full app/media-store
replacement, the native transcript reconstructs another exact PNG handle.
Preservation remains off and the fixture source remains available until cleanup.
The probe reaps its provider/browser and closes owned services/sockets/listeners,
then removes its temporary owner-only provider profile, authentication/config,
fixture and YA data. Nonpersonal captures are presented from ignored artifact
storage. [YA's current topic](../../../yepanywhere/topics/optional-computer-control.md#installed-launch-and-media-boundary-acceptance)
owns the repeatable command and details. This closes the fixture media-view gate,
not provider-driven desktop/browser control, signed Windows/Linux native control,
installed replacement or legacy retirement.

Mac absent-resident acceptance also passes through physically relocated signed
client bytes, isolated Python configuration and a temporary claim store. Doctor
reports the missing resident; desktop windows and read-only grant status refuse
with the existing client-error schema/adapter-failed code and an unavailable
resident diagnosis. The endpoint remains absent, the local claim is released
and its state returns to available. The reusable CLI smoke adds an explicit
Mac-only `--unavailable-resident` cell; other platforms refuse that option.

Target-local provider prerequisites were inspected in a claimed Mac appliance:
Node and pnpm are available, while Codex was not found on the inspected login
PATH. No provider installation or model control task was performed. The
passwordless shutdown command refused; guest-native System Events shutdown
then succeeded. Power-off is independently confirmed, the controller claim is
released and the canonical login credential remains ready. This inspection is
preparation for provider-driven control, not its acceptance.

A target-local YA provider attempt subsequently used the signed CLI, changed
the AppKit count once and opened its new exact-window capture. It reached the
bounded deadline before reporting the visible count, so the full probe did not
pass. Its trace motivates clearer instructions: reuse a harness-supplied claim,
show semantic press syntax, and retrieve the unchanged artifact path rather
than guessing a capture id. The six CLI packaging checks pass. Provider-driven
acceptance remains open pending the corrected run.

The corrected target-local YA native probe passes with the updated Python
instructions and a re-signed local app assembly; no Rust rebuild was needed
for that command-workflow change. A complete Codex runtime and bundled YA probe
run without source checkouts, use the supplied exact claim, perform one
semantic fixture increment, fetch the native window artifact and consume it
through the agent's built-in image tool. Independent count and reported visible
count agree. The appliance's standing policy is explicit, not workstation
approval evidence. Matching native artifacts and staged app/profile/runtime
are removed, claims released and initial power-off independently confirmed.
The same fixture capture passes YA's live/reloaded HTTP and desktop/phone
media-view acceptance. Provider-driven browser control, signed Windows/Linux
native use, lifecycle parity and YA legacy retirement remain open.

The browser model cell also passes from the source-independent Mac staging
with Chrome for Testing 145. The existing headed harness adds an optional
bounded YA probe and a server-owned counter fixture. Its 21 installed-client
indicator/worker checks and two new agent/effect checks pass: actual CLI
instructions/identity, tabs/snapshot, a single semantic click, tab capture,
unchanged artifact retrieval and built-in image consumption. Counter and
visible image agree. The first staged attempt carried an older harness and
refused the new arguments before browser/model startup; it is not passing
evidence. The corrected handoff verifies the harness hash before execution.
Eight extension unit checks and Python compilation also pass.

Owned Chrome/profile, native artifacts, staged auth/runtime and candidate are
cleaned; the canonical native-host socket is restored, claims released and
initial power-off confirmed. Standing appliance authority remains explicit.
The generated tab PNG passes YA's separate full-app live/reloaded HTTP and
desktop/phone viewer checks. Signed Windows/Linux control, lifecycle parity,
public consumer selection and YA legacy retirement remain open.

## Installed Mac claim and resident lifecycle result

The new `tests/desktop/cli-lifecycle.py` passes against the signed, staged Mac
assembly without a source checkout. The controller holds a fresh exact
appliance claim; the helper owns a separate host claim store, socket and
resident. Claim-free target observations refuse, a second claimant cannot
acquire held access, and three concurrent claimed discovery calls report the
same native generation. The actual one-minute minimum lease expires without
changing policy or its stored clock; expired and superseded claim IDs refuse.

Stopping only the helper's resident makes doctor unavailable and target
operations refuse. Offline identity still works and the CLI leaves the socket
absent. Explicitly restarting the same signed binary restores readiness with
a different resident generation and the still-live host claim. The helper
releases its claim, reaps its process and removes temporary state. The original
appliance resident remains ready; the controller restores initial power-off
and releases its claim. This closes the Mac installed claim/fencing and owned
resident recovery cell. It does not prove app replacement, native grant expiry,
YA session close/crash or Windows/Linux lifecycle parity.

YA's subsequent full-app lifecycle probe closes the Mac close/restart/crash
isolation cell. Two real local Codex turns read only installed instructions and
identity through the signed assembly. Verified Supervisor abort, full app
disposal/fresh restart and abrupt loss of a separate YA process each preserve
the independent MC PID, native generation and held host claim. Codex's separate
owned group is checked, killed and observed gone. The original appliance
resident stays ready; temporary app/runtime/auth/data are removed, initial
power-off restored and claims released. [YA's execution record](../../../yepanywhere/docs/tactical/142-machine-control-desktop-consumer.md#full-ya-app-close-restart-and-crash-result)
owns the dependency staging and failed-attempt details. Native grant expiry,
signed replacement, Windows/Linux parity and legacy retirement remain open.

## Installed Mac native grant expiry result

The new `tests/macos/cli-grant-expiry.py` passes against the source-independent
signed Mac assembly. The controller owns the exact appliance claim and stages
the app; the guest owns a separate local-host claim. An independent standing
observer drives the candidate's visible native approval. The candidate loads a
temporarily stricter workstation policy, and the trusted file is restored before
the probe begins. An observe-only request through the installed CLI receives a
timed 60-second grant and can observe the deployed AppKit fixture.

The probe waits for the real deadline without changing the clock or grant
state. Native status reports the grant ended as `expired`; another installed
CLI observation refuses with `approval_required`. The candidate PID remains
unchanged. Finally, the probe resolves pending approval and revokes access;
the controller reaps owned candidate/fixture processes, removes staging,
confirms original resident readiness, restores initial power-off and releases
claims. No installed application or credential is replaced.

The first attempt failed on harness assumptions: the Tauri approval label is
`Allow access`, and successful native actions may omit `data`. Its cleanup
restored power-off and released the controller claim. The corrected fresh run
passes. Python syntax checks and all 61 release tests pass. This closes the Mac
native grant expiry cell; signed app replacement, Windows/Linux acceptance,
public picker approval and legacy retirement remain open.

## Exact notarized Mac candidate verification result

The Mac ARM64 0.5.3 artifacts from successful signing job in workflow
37054647423 authenticate source `698550b`. Windows/Linux failed that workflow,
so it has not published a release. The package verifier accepts updater
signature/version, signed source, complete CLI closure, native publisher
signatures, Gatekeeper and stapling, and refuses modified archive bytes.
Physically relocated offline execution and unavailable-resident refusal also
pass. YA's actual installed consumer and its source-independent bundle both
pass identity, instructions, launch context, relocated-copy verification and
wrong-publisher, changed-script and missing-interpreter negatives.

YA corrected the negative fixture construction after macOS App Management
refused a write in a copied notarized app. Invalid fixture bytes are now built
before Info.plist is copied; production verification and OS permissions remain
unchanged. [YA's execution record](../../../yepanywhere/docs/tactical/142-machine-control-desktop-consumer.md#exact-notarized-mac-candidate-discovery-result)
owns its full checks and failed-attempt details. This is exact candidate
discovery evidence; earlier control/model/lifecycle cells used the local signed
assembly. Signed replacement, publication, other platforms and legacy cutover
remain separate gates.

## Published Mac installed CLI replacement

**Current (2026-10-02):** `tests/macos/tauri-update.py` optionally uses the exact
installed client with a caller-owned host claim, in addition to the existing
independent controller claim/observer. Discovery verifies native update
metadata plus the visible disabled install button instead of depending on one
exact accessibility static-text rendering. Publisher and signed-version
verification remain enforced.

The sender is an owned Developer-ID-signed 0.5.2 fixture with a private loopback
feed, not a published 0.5.2 release. The receiver is the untouched public Mac
ARM64 desktop 0.5.3 archive/signature from source
`d5aa271ca93d890325a12b0906432b762a4aaec4`. Full package verification, including
source, updater signature/version, CLI inventory, Gatekeeper, native signatures,
stapling and archive tamper refusal, passes before use.

Through the installed CLI, native discovery reports 0.5.3 and the visible
Install and restart action is disabled with active access. Stop enables it.
Actual replacement and automatic relaunch retain semantic/capture permission,
start with access off, change resident generation and refuse an old reference.
Offline CLI identity changes from 0.5.2 to 0.5.3; the existing host claim still
authorizes native status. Actual YA discovery, launch-context composition and
publisher/script/interpreter negatives pass before and after replacement.
Post-replacement source identity and signatures/staple match public 0.5.3.

Cleanup restores original trusted policy bytes/metadata, disarms/reaps only the
owned candidate/feed/fixture and removes staging. An independent staged CLI
releases the host claim and verifies availability even after app replacement.
The original resident stays ready. Initial power-off and controller claim
availability are independently confirmed; canonical credentials are unchanged.
Portable release tests (61) and Python syntax checking pass. Signed Windows/
Linux native acceptance and YA legacy retirement remain open.

### Public Windows x64 installed CLI acceptance

**Current (2026-10-03):** Exact public desktop 0.5.3, source `d5aa271`, passes
YA's production authentication/closure/identity/instructions/context probe,
including relocation and the three integrity/publisher negatives, in an ordinary
interactive Windows 11 x64 session. The installer was authenticated first with
the pinned updater key and signed version, then its valid timestamped native
signature supplied the publisher for the test. No public trust key was changed.

The existing `tests/windows/desktop-cli.ps1` runs from the installed command,
without a checkout in the payload. Access-off refusal passes. An independent
ordinary-user actor approves the visible request; the packaged Cua route performs
one independently observed counter increment, captures only the fixture, verifies
artifact bytes by SHA-256 and refuses the capture-superseded semantic reference.
Native Stop revokes the grant. No system Python or developer toolchain executes
these operations. PowerShell bypass is scoped to the owned test process.

NSIS initially restored a previous test's custom installation path. The accepted
run instead pins the normal product path and backs up/restores the pre-existing
uninstall registry. Temporary installation and staging are removed, original
power-off is independently confirmed, and both local CLI claims and the controller
claim are released. Provider-driven Windows control/media, browser, lifecycle,
Linux GUI acceptance and YA legacy retirement remain open.

### Public Linux x64 installed CLI core acceptance

**Current (2026-10-03):** Public 0.5.3 Debian x64, source `d5aa271`, is
independently authenticated with the pinned updater key and signed version.
YA's production consumer passes receipt signature, complete client dependency
hashes, identity, instructions, launch context, relocation, changed-script and
missing-interpreter negatives in an ordinary GNOME 46 Wayland session.

The installed native harness now optionally routes requests through the exact
bundled client with a caller-owned host claim, including artifact retrieval.
The bounded slice passes 46 checks: Off/refusal, native arming and Stop,
approval/denial and expiry, explicit portal consent, capture/artifact hashes,
independent GTK semantic/pointer/Unicode effects, restart revocation and sharing
closure, tray/close/Quit, and operator loss while the fixture survives. There is
no checkout in the test payload, and the client uses its bundled interpreter.

The full run first stopped at the Stop-shortcut checkbox, which did not become
checked under isolated product state. The accepted slice excludes startup and
shortcut settings rather than counting the broader run as passing. Native
resource discovery uses the package's actual `Machine Control` resource directory.
Product/source behavior is not changed to match guessed resource paths.

The initially absent package is removed, owned units collected/stopped, all
staging removed, original power-off confirmed, and host/controller claims released.
The canonical stored credential remains ready and unchanged. Linux provider
model/browser and further lifecycle cells, Windows model/browser/media and
legacy migration remain explicit remaining work.

**Current (2026-10-03):** A real ordinary-user Windows YA Codex 0.159.0
provider turn now passes with the exact public 0.5.3 installed CLI: instructions,
identity, claimed window enumeration/native JSON snapshot, one semantic
invocation, exact-window capture, artifact retrieval and built-in image viewing.
Independent fixture process/count and model-reported visible count match. YA
reauthenticates the live runtime through its signed catalog using a bounded copy,
because PowerShell cannot hash the active executable directly. Provider close
leaves MC usable; native Stop revokes access before owned cleanup. Original
installation registry/power are restored and all claims released. Windows browser,
full-app media and further lifecycle gates remain open.

## Windows installed browser result

Exact public desktop 0.5.3 x64 passes the existing Windows installed-browser
harness using bundled Python and Chrome for Testing 145.0.7632.117 in an owned
profile. Native grant/deny, independent semantic click/text effects, PNG/hash,
browser-only evaluation refusal, Stop/stale references, DevTools/CDP and
operator restart/reconnection pass. An actual YA Codex 0.159.0 turn through
the verified custom product directory performs one independent fixture click
and consumes its new matching image. No primary browser or source checkout
is used. The original native-host registry/manifest and uninstall registry
are restored, owned processes/product/profile/staging removed, original
power-off confirmed and local/controller claims released.

YA's [execution record](../../../yepanywhere/docs/tactical/142-machine-control-desktop-consumer.md#windows-browser-and-custom-location-result)
owns model and media/lifecycle cutover gates. This result does not infer those
remaining gates or Linux browser/model parity.

## Final installed consumer result

Public 0.5.3 ships the authenticated complete Python runtime/client for all six
desktop targets, with relocated offline execution. Mac/Windows actual YA
Codex native/browser turns, capture consumption, full-app live/reloaded media
and close/restart/crash isolation are accepted. Windows built-client desktop
and phone media serve the exact native PNG; independent MC PID/generation and
claim survive actual YA lifecycle operations. Linux x64 core desktop/portal
control is accepted within its bounded 46-check slice. Cleanup restores owned
processes, installations/state, original power and released claims.

YA's old component installer/updater, resident supervisor, grant UI and deferred
tool are retired after these gates. Its bounded compatibility/cleanup boundary
is owned by [YA Tactical 142](../../../yepanywhere/docs/tactical/142-machine-control-desktop-consumer.md#windows-lifecycle-and-consumer-cutover-result).
YA advertisement does not grant or revoke MC access: native Stop, expiry or
MC restart owns revocation. Headless workstation and protected appliance
profiles remain independent. Python development still runs directly from the
checkout without Rust; installed users receive commands through MC releases.

Linux model/browser and further lifecycle cells, actual Claude use, other GUI
architectures and remote/sandbox delivery remain separate from this accepted
slice. Windows high-level app snapshot resolution and Linux startup/Stop-
shortcut settings are not established. Existing experimental failure records
above retain their historical scope rather than claiming broad runs passed.
