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
contents and managed tab-strip presentation. Provider-driven control and
live/reloaded YA views remain open; do not infer their acceptance from this
bounded launcher/image smoke.

The original appliance policy and socket are restored, resident doctor is
ready, owned candidate/browser/fixture processes are stopped, test files
removed, and guest shutdown is independently observed. Guest and controller
claims are released. The canonical login credential remains ready and
owner-only; no credential changes. Windows/Linux execution and legacy YA
retirement remain open. The configured Windows appliance is unavailable; no
private infrastructure or credential locators are recorded here.

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
