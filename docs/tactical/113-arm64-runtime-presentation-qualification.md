# 113 — ARM64 runtime and presentation qualification

Status: active.
Owning topic: [runtime and presentation](../../topics/runtime-and-presentation.md).
Parent: [112](112-runtime-presentation-acceptance-review.md).

## Objective and completion conditions

Close the Windows and Linux ARM64 build/native-execution gaps using the
existing local VMs, then repeat hardened Mac ARM64 effects in Tart. Qualify
one pinned implementation through all three profiles, independent safety UI,
CLI recovery, native/browser effects, cancellation and restart. Distinguish
development authentication from production publisher and installed-update
evidence. Record exact source and artifact identity, fixes and remaining gates.

## Boundaries

No public release or replacement of the operator's installed host app.
Use claimed dedicated targets and target-native administration/control;
preserve appliance policy and the separate ordinary-user product boundary.
Use separately identified test browsers. Keep credentials, target identity,
captures, signing material and raw evidence private. Preserve existing guest
installations or explicitly back them up for bounded install/update trials.
Restore initial power and promptly release claims in cleanup. No forced
shutdown, VM deletion, reversion or outer-input fallback is authorized.

## Ordered work

### 1 — prepare and qualify Windows ARM64

Doctor and claim the existing target. Inspect tooling and resources; provision
missing native development dependencies within this dedicated appliance.
Stage exact source, build the full ARM64 Tauri/.NET package, run meaningful
contracts, authenticate the candidate and execute the existing native profile,
browser and lifecycle runners. Restore owned deployment/trust state and power.

### 2 — prepare and qualify Linux ARM64

Use the supported Ubuntu/GNOME Wayland target. Build release-mode Debian and
AppImage with bounded build parallelism, authenticate exact bytes and exercise
native profiles, portal/browser effects, fault/cancellation, recovery and
restart. Qualify installed replacement where a reversible dedicated-target
fixture is available. Preserve the root appliance route as a separate profile.

### 3 — repeat Mac ARM64 regression and reconcile evidence

Build and locally sign the same implementation source. Use a claimed Tart
target, persistent staging and restoration backups to repeat profile/safety,
native/browser effects, CLI recovery and restart after hardening. Keep broader
protected/physical and Intel GUI scope explicit. Update topic/platform/matrix
evidence and commit coherent fixes and final results.

## Validation and execution

Starting implementation source: `38750bd`; the pending queue/test edits from
the review are now committed and the controller worktree is clean. Subsequent
documentation commits do not alter executable implementation. If qualification
finds a product defect, record the replacement source and rerun affected gates.

The selected Windows and Linux targets are configured ARM64 hardware-accelerated
guests. Both start powered off, with canonical credential files ready. Concrete
identity, claims, journals, tool inventories and raw reports remain private.

### Windows ARM64 result

The combined implementation was built from
`221f6d48b09a404ea7eddeb1590cf068ddb73871` (executable code unchanged
from `38750bd`). Native ARM64 Windows 11 build `10.0.26300.9457`
produced the optimized Tauri GUI, .NET resident/fixture and NSIS installer.
Frontend, Rust formatting, all-target Clippy with warnings denied, ten Rust
tests, .NET formatting/build/contracts and independent ARM64 PE checks pass.
The dedicated guest retains its provisioned native development toolchain.

A disposable non-exportable development certificate authenticated the staged
GUI, resident and fixture; changed bytes refuse. The NSIS installation trial
used an unsigned developer installer. Neither establishes production publisher
trust or versioned updater replacement. Private transfer hashes were verified
for the preserved candidate, installer and minimized report archive.

| Native campaign | Result |
| --- | --- |
| Runtime, profiles, independent safety and recovery | 57 checks |
| Lifecycle exclusion | 11 checks |
| Native pointer effects | 36 checks |
| Streaming/browser roots, including 11 Playwright/Puppeteer client checks | 52 checks |
| Outside/local owner SDK and bundled CLI effects | 39 checks |
| Isolated NSIS install, repeated repair, PATH opt-out and uninstall | Pass, including nested CLI discovery |

Both native and browser counter effects were independently observed; owner
cleanup reported no errors. Browser qualification uses x64-emulated Chrome
for Testing with explicitly selected software rendering. Default rendering
timed out; native ARM browser and accelerated GPU behavior remain open.
Fixture fix `e0cc39f` adds explicit rendering selection, waits for native
consent, selects browser scopes after recreated Settings and preserves failure
diagnostics. Fixture fix `2e82a7c` compares installed files by identity across
short/long TEMP aliases and waits boundedly for uninstaller removal. Neither
changes product executable code. Failed attempts remain in private evidence.

Canonical stored password verification passed. Owned task, candidate/browser/
fixture staging, certificate trust and private key were removed; registry,
PATH and startup state were restored. Graceful shutdown restored initial off
power and the claim was released. One interrupted stream command lacks an
automatic journal result, so the journal closed as interrupted rather than
claiming complete coverage; later acceptance and cleanup evidence establish
final state independently. No publication or host-app replacement occurred.

### Linux ARM64 result

The same source `221f6d4` builds natively on Ubuntu 24.04.5/GNOME 46
Wayland ARM64. Node 24.21.0, pnpm 10.33.0 and Rust 1.99.0 produced
optimized Debian and AppImage packages with one build job. Frontend, Python
unit/static checks, Rust formatting, warning-denied Clippy and nine native
Rust tests pass. A transient DNS failure interrupted pinned Python staging;
the independently digest-verified archive was transferred into the existing
build cache. Dependency pins and product bytes were unchanged.

Both containers independently pass ARM64 compiled identity, exact source,
bundled CLI relocation and complete runtime/CLI inventory checks. Product
resources match across formats. Their SHA-256 identities are:

- Debian: `e7c35eeaa4ec3a60ff0c1b28d75fb6a1e260e4179aea4c177c12a1b4a146faa8`.
- AppImage: `4807ea6e769043ad8d683da340f7c6214a116dcac188173699beec540ef3d3ff`.

Disposable development-key detached signatures authenticate both final files;
changed bytes refuse. The private key was removed. This is development
authentication, not production publisher or updater signing.

| Native ARM64 campaign | Result |
| --- | --- |
| Companion, portal capture/input/Unicode and cancellation | 57 checks |
| Three GUI profiles, independent safety, recovery and restart | 92 checks |
| Provider/session-owner/safety faults and late completion | 30 checks |
| Native ARM64 Chrome for Testing browser effects and reconnect | 29 checks |
| Outside/local bundled CLI generation and independent effects | 6 checks |
| Actual installed Debian native/operator/lifecycle behavior | 52 checks |
| Actual AppImage launcher native/operator/lifecycle behavior | 54 checks |

The first five campaigns repeat the 214-check runtime scope on ARM64. The
additional 106 package checks exercise startup registration, real shortcut
Stop, native approvals/expiry, portal capture and independent semantic, pointer
and Unicode effects, restart Off, tray recovery, Quit and owner loss.
Debian was installed with dpkg over the backed-up existing package; AppImage
was launched through its actual container. This adds release-mode and local
installed/replacement evidence, not a production updater campaign.

The portal offered two screens. Fixture-only `c71b166` adds a caller-selected
exact accessible screen name; the primary screen at the origin was selected
and returned capture/input effects verified. This does not qualify arbitrary
monitor layouts or scaling. Native ARM64 Chrome for Testing 155.0.8059.39
uses the existing runner's explicit software rendering and the supplied
setuid sandbox helper via its supported locator. No sandbox or AppArmor
weakening was needed; accelerated GPU presentation remains open.

Fixture-only `e95b01b` waits for actual native readiness, preserves an enabled
shortcut, observes active Stop after effects and finalizes reports after
cleanup. Installed testing must share GNOME's actual dconf database: an
isolated XDG config directory otherwise reads a different database from the
settings daemon's writes. Failed attempts remain privately preserved. The
first attempt touched the owned shortcut before its canonical snapshot, so
byte-for-byte pre-trial shortcut preference restoration is not established.
Later trials restore and verify the captured state; unrelated bindings are
preserved. GTK/AT-SPI/GLib diagnostics remain in private logs, including native
hash-table warnings; passing bounded effects do not prove warning-free
libraries or unrestricted event-loop/provider latency.

The original Debian installation was preserved as a restoration package and
separate file archive, transferred and hash-verified before the install trial.
Reinstallation restores its original version and a root-relative archive
comparison verifies original file bytes/metadata. Both package files and
minimized final/failure reports are privately preserved with verified transfer
hashes. The canonical stored password verifies through the supported helper.
The separate root appliance smoke and final read-only doctor pass without
outer UI. Owned candidate/browser/fixture processes and sockets are absent;
owned staging is removed, the sandbox helper disarmed and private signing key
absent. System build dependencies remain installed. Graceful shutdown restores initial
off power; the exclusive claim is released. No publication occurred.
