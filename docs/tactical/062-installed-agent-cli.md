# Package the Python CLI for desktop consumers

Owning topics: [Installed agent CLI](../../topics/installed-agent-cli.md),
[Native distribution](../../topics/native-distribution.md).

Status: in progress, 2026-10-02.

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
