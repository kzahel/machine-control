# Installed agent CLI

Topic: `installed-agent-cli`

Status: shipped in public desktop 0.5.3 for all six targets, with authenticated
payload inventories and relocated offline CLI smoke in CI. Mac packages pass
publisher verification and notarization; Windows x64/ARM64 installed catalogs
and Linux x64/ARM64 final packages authenticate. Native Windows ARM64 CI now
executes that architecture's bundled interpreter. Earlier Mac ARM64 appliance,
Linux ARM64 container, and Windows x64 appliance evidence retains its own
scope. Signed Windows and Linux x64 CLI/core control is accepted; Mac installed CLI
replacement to public 0.5.3 is accepted. [Tactical 063](../docs/tactical/063-six-platform-desktop-release.md)
owns exact published package and production delivery verification.

## Contract

**Current:** Agent instructions distinguish harness-supplied claims from
new claims, give the semantic action syntax, and require artifact handles to
be passed unchanged. Mac capture retrieval uses the full `data.artifactPath`.

**Decision:** Python remains the common CLI implementation. Developers run
`bin/machine-control` directly; command changes require no Rust toolchain or
desktop rebuild. Desktop packages bundle the same modules, local host adapters,
claim helpers and a pinned CPython runtime. YA consumes this interface rather
than maintaining a second resident installation for the migrated route.

**Current:** Tauri builds stage `mc-cli` resources using
[`prepare-cli.py`](../desktop/scripts/prepare-cli.py). The terminal entry is
`mc-cli/commands/machine-control` on macOS/Linux and
`mc-cli/commands/machine-control.cmd` on Windows. These names are separate from
the Windows/Linux GUI binary. Mac resources live inside the app bundle;
Windows resources live under the product root. Linux packages put the CLI in
`/usr/share/machine-control/mc-cli`, outside linuxdeploy's ELF rewriting under
`usr/lib`; both Debian and AppImage must retain its exact pinned payload.
The launcher uses isolated Python, suppresses bytecode writes and propagates its runtime to host/claim
subprocesses. No system Python is needed for the CLI; Linux's native GTK/AT-SPI
resident retains its documented system dependencies.

**Current:** `agent identity` returns
[`machine-control-client-identity/v1`](../contracts/client-identity-v1.schema.json)
without contacting a resident. `agent instructions` returns the owned workflow
for doctor, claims, scoped access, semantics, browser control and bounded
artifacts. Reading either grants no authority. Installed defaults expose only
`host`; explicit per-user registries/providers can add other installed adapters.
There is no implicit sibling checkout/private-inventory lookup in a package.

**Decision:** CPython archives are SHA-256 pinned for six desktop targets in
[`python-runtime.lock.json`](../desktop/python-runtime.lock.json). Retain upstream
component license notices. Mac signs nested native libraries before sealing
the script/runtime inventory in the app signature. Windows authenticates the
CLI's complete SHA-256 inventory with its publisher-signed catalog, then checks
every installed byte and refuses unexpected files. Cataloging that inventory
avoids Windows SIP hashing failures for upstream stripped Python DLLs.
Linux final packages
use the existing authenticated package signatures. An unsigned hash receipt is
integrity evidence only, not publisher authority. The packaging
[dossier](../research/providers/python-build-standalone.md) owns licensing.

## Consumer ownership and acceptance

**Decision:** MC owns installed commands, native access/arming, claims,
resident lifecycle and updates. YA owns launch eligibility and advertisement,
optional tool adaptation and media presentation. A session ID is attribution,
not authority; suppressing advertisement cannot contain same-user shell access.
Native sudo remains a separate feature with OS authentication.

**Current:** The CLI does not start a replacement resident when the app is
unavailable. The caller receives the existing typed failure and can ask the
operator to open MC. Mutations and captures retain the shared resident's route,
generation, delivery, effect and uncertainty reporting.

**Current:** Mac installed-client acceptance includes an explicitly absent
socket and isolated claim store. Doctor reports `resident: unavailable`, and
desktop enumeration/read-only grant status refuse with the existing
`machine-control-client-error/v0` / `adapter_failed` result and resident
unavailability diagnosis on stderr. The endpoint stays absent and the claim
returns to available in cleanup. Run `tests/desktop/cli-installed.py --client
INSTALLED_COMMAND --unavailable-resident` on Mac to reproduce this negative
cell. The flag refuses on other platforms; it does not establish their native
resident recovery or any successful control route.

**Current:** `tests/desktop/cli-lifecycle.py --client INSTALLED_COMMAND` passes
inside the claimed Mac appliance with the signed assembly and standing policy.
It starts only its own isolated resident/socket, proves exclusive and concurrent
claim behavior, real one-minute expiry and superseded-claim fencing, then stops
that owned resident. Offline identity stays available, target operations refuse
and the CLI creates no replacement. An explicit harness restart has a fresh
resident generation while preserving the still-live target-use claim. The
original appliance resident stays ready; owned processes/state are removed,
the controller claim is released and initial power-off is restored. This is
claim/resident recovery evidence, not app replacement, native grant expiry,
YA session-close/crash behavior or Windows/Linux lifecycle parity.

**Current:** YA's separate full-app lifecycle probe now also passes in the
source-independent Mac staging. Real Codex offline instructions/identity turns,
verified Supervisor session close, full app disposal/fresh restart and an abrupt
owned YA process crash preserve the independently started MC resident's exact
PID, generation and held claim. The orphaned Codex group is checked, reaped and
observed gone; original resident readiness, initial power-off and released
claims are confirmed. [YA's tactical result](../../yepanywhere/docs/tactical/142-machine-control-desktop-consumer.md#full-ya-app-close-restart-and-crash-result)
owns this probe. Windows/Linux lifecycle parity remains separate.

**Current:** `tests/macos/cli-grant-expiry.py` passes through the installed signed
Mac client with separate controller/host claims. A candidate loads workstation
approval policy while the independent appliance observer retains standing
policy; the trusted policy file is restored before the probe. Native visible
approval issues an observe-only 60-second grant. Fixture observation succeeds,
then actual elapsed-time expiry reports `expired` and refuses observation with
`approval_required` while the same candidate process stays alive. No clock or
grant-state mutation is used. Cleanup disarms access, reaps the owned candidate
and fixture, removes staging, restores initial power-off and releases claims.
This closes Mac native grant expiry, separately from signed app replacement.

**Current:** Mac installed replacement from an owned signed 0.5.2 fixture to
exact public 0.5.3 passes through the installed CLI. Active access disables
installation; Stop allows automatic signed replacement/relaunch with access
off, retained permissions and a fresh generation. The CLI identity follows
the replaced app, its held host claim remains valid, stale UI references refuse
and YA reauthenticates the replacement. [Tactical 062](../docs/tactical/062-installed-agent-cli.md#published-mac-installed-cli-replacement)
owns the fixture distinction, exact source and cleanup evidence.

**Current:** The Mac ARM64 0.5.3 candidate from source `698550b` passes exact
updater signature/version and source verification, complete CLI closure,
Developer ID verification, Gatekeeper, stapling and archive-tamper refusal.
Relocated offline CLI and unavailable-resident checks pass. YA's actual consumer
also accepts identity, instructions, launch context and a relocated copy, and
refuses wrong publisher, changed script and missing interpreter. The two Mac
jobs passed within failed workflow 37054647423; this is notarized candidate
evidence, not publication or Windows/Linux acceptance. Earlier native/browser,
model and lifecycle evidence used the local signed assembly. [YA's record](../../yepanywhere/docs/tactical/142-machine-control-desktop-consumer.md#exact-notarized-mac-candidate-discovery-result)
owns the consumer probe and its notarized-fixture construction correction.

[`cli-installed.py`](../tests/desktop/cli-installed.py) tests offline discovery,
isolated runtime use and bundled claim dependencies from an unrelated directory.
Archive traversal, external links, unused terminal-data aliases,
modified/missing files and unexpected files have portable negative tests.
Linux ARM64 passes the same relocation smoke in an isolated native container.
The Mac and Linux workflows execute this smoke after staging; Windows executes
it against the actual signed installer payload before recording provenance. The signed Mac ARM64 assembly passes bounded
workstation approval/refusal/revocation, an independent AppKit counter effect,
exact-window capture and artifact retrieval through the installed CLI. This is
claimed-appliance evidence, not physical-workstation acceptance. Chrome for Testing browser acceptance also passes 21 checks through the
installed CLI with independent page/Chrome effects, browser PNG retrieval,
release, worker restart and reconnect. A real YA local Codex provider launch
reads installed instructions/identity and observes the retained browser fixture
PNG through its native image viewer. YA also passes full-app HTTP media and
real desktop/phone image-viewer acceptance: live output serves exact native PNG
bytes, and a fresh app/media store reconstructs them from the actual transcript
after provider shutdown. Preservation stays off and the fixture source remains
available until cleanup. This media-view cell is separate from provider-driven control. Windows/Linux
per-platform evidence remains required before
retiring any legacy YA component. [Tactical 062](../docs/tactical/062-installed-agent-cli.md)
records implementation; [YA's migration plan](../../yepanywhere/docs/tactical/142-machine-control-desktop-consumer.md)
owns consumer cutover.

**Current:** A source-independent YA Codex provider inside the claimed Mac
appliance uses the signed installed CLI for a single semantic fixture increment,
an exact-window capture and built-in agent image consumption. The independent
fixture count and reported image count agree. This uses the appliance's
standing policy, distinct from the earlier workstation approval slice.
The generated native PNG also passes YA's separate full-app live/reloaded
HTTP and desktop/phone viewer route. A separate browser model also uses the
installed CLI to increment an independent HTTP fixture once and consume its
new tab capture; the headed browser harness passes all 23 checks. Signed
Windows/Linux native acceptance and lifecycle parity remain open.

**Current:** Public desktop 0.5.3 Windows x64 from source `d5aa271` passes
ordinary interactive installed-CLI acceptance in a claimed Windows 11 appliance.
YA's real consumer authenticates the published product, complete client and
relocated copy, including wrong-publisher, changed-script and missing-interpreter
negatives. With no checkout or system Python in the payload, the installed
command refuses control with access off. Visible native approval permits one
Cua semantic counter increment independently confirmed by fixture state;
capture/artifact bytes match their SHA-256, capture invalidates the old reference,
and native Stop revokes access. `tests/windows/desktop-cli.ps1` supplies the
control assertions. Its owned actor uses per-process PowerShell execution policy
without changing the machine's policy. Temporary installation and staging are
removed, the pre-existing custom-install registry restored, original power-off
confirmed, and local and controller claims released. Windows provider-driven
model control/media, browser and lifecycle parity remain separate gates.

**Current:** Public 0.5.3 Linux x64 Debian bytes, source `d5aa271`, pass
production YA receipt/full-client/identity/context verification and relocated,
changed-script and missing-interpreter negatives. A claimed Ubuntu 24.04 GNOME
46 Wayland appliance passes 46 bounded checks through the installed CLI:
Off/refusal, native arming/Stop/approval/denial, expiry, visible portal consent,
capture/artifact hash, independent GTK semantic/pointer/Unicode effects,
restart revocation and sharing closure, tray/close/Quit and operator loss.
`tests/desktop/linux-installed.py` optionally consumes a caller-owned local host
claim and installed command. The actor's state is isolated; temporary package,
units and staging are removed, original power-off confirmed, and all claims
released. The broader harness's Stop-shortcut checkbox did not become checked
in this configuration; the accepted slice excludes startup/shortcut settings
and does not establish their 0.5.3 parity. Linux model/browser and additional
lifecycle cells remain separate from this CLI/core desktop evidence.
