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
