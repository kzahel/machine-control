# 114 — Desktop 0.6.0 release

Status: complete; published on 2026-10-12.
Owning topics: [native distribution](../../topics/native-distribution.md) and
[runtime and presentation](../../topics/runtime-and-presentation.md).

## Objective and completion conditions

Publish the runtime/presentation refactor as one desktop release for Mac
Apple silicon/Intel, Windows x64/ARM64 and Linux x64/ARM64. Require meaningful
notes, passing source checks, authenticated six-target candidates, immutable
publication and verified public downloads and production update metadata.

## Boundaries

Promote exact successful unified candidate bytes without rebuilding. Preserve
all existing tags and assets. Prior native qualification remains tied to the
revisions and environments recorded in [113](113-arm64-runtime-presentation-qualification.md).
Publication establishes production package authentication, not new installed
GUI, updater replacement, protected-session, physical or soak acceptance.
Do not install or update the controller or accepted appliances for this release.

## Ordered work

### 1 — prepare notes and check source

Version the configurable profiles, UI responsiveness, independent safety and
CLI recovery changes. Run release regression checks and exact-source hosted
checks; retain explicit native execution limits.

### 2 — authenticate all six candidates

Build at one main revision and workflow attempt. Require native publisher
signing, Mac notarization/staples, updater signatures and signed versions,
payload inventories, CLI relocation and tamper rejection.

### 3 — publish and verify delivery

Create an annotated immutable tag and promote the verified candidate. Verify
uploaded GitHub digests before publication, independently authenticate public
assets, and check downloads and production update responses.

## Validation and final result

**Current:** [Public desktop 0.6.0](https://github.com/kzahel/machine-control/releases/tag/desktop-v0.6.0)
uses source `c5839c828d2e515ce7d9fcfea99ea29f9e0e25b1`.
[Candidate 38293625475](https://github.com/kzahel/machine-control/actions/runs/38293625475),
attempt 1, builds and authenticates all six targets.
[Promotion 38297493792](https://github.com/kzahel/machine-control/actions/runs/38297493792)
publishes those exact bytes without rebuilding.
[Exact-source cross-platform checks](https://github.com/kzahel/machine-control/actions/runs/38293617507)
pass on macOS, Windows and Linux.

All 29 independently downloaded public assets match GitHub SHA-256 digests
and sizes. All package receipts bind version, source, candidate run and
attempt. Windows/Linux updater signatures, signed versions and payload
inventories pass; Mac nested publisher signatures, Gatekeeper, notarization
and staples pass. Modified packages are refused. Hosted installed CLI
relocation passes for every target, including native Windows ARM64. Hosted
Windows builds verify installed publisher signatures and payload catalogs.
This establishes production package authentication, not installed GUI or
versioned replacement acceptance for the refactored runtime.

The public manifest has exactly six signed updater entries and the required
changelog. The download page and all eight redirects select 0.6.0. All 24
production responses across the website proxy and shared service match the
manifest for 0.5.8 clients and return HTTP 204 for 0.6.0 clients.

Release regression tests pass (75 tests, one platform-specific skip). Native
Swift, Rust, frontend, format/lint, Windows contracts and native publishes
pass in hosted qualification. The prior VM profile/safety/recovery effects
retain the exact sources and limits recorded in Tactical 113. Intel GUI,
native Windows ARM browser/GPU, broader compositor/hardware, protected-session
recertification and longer fault/load soak remain separate work.

No controller or accepted appliance installation is changed. Downloaded
packages are authenticated in isolated staging and never launched as residents.

### Qualification repairs

The first candidate built and signed Linux ARM64 containers, then correctly
rejected five runtime/presentation modules absent from the older strict payload
requirements. `c5839c8` makes version 0.6.0 require coordinator, notice, one-shot,
presentation and work modules. Regression fixtures accept both complete
architectures and reject each omitted module independently; historical
release inventories retain their original requirements. The failed candidate
([38292312876](https://github.com/kzahel/machine-control/actions/runs/38292312876))
is cancelled before any tag or publication. Redundant automatic Mac checks
are cancelled to free the unified workflow's check slot.
