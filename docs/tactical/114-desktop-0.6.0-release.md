# 114 — Desktop 0.6.0 release

Status: in progress.
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

Pending candidate and public delivery verification.

### Qualification repairs

The first candidate built and signed Linux ARM64 containers, then correctly
rejected five runtime/presentation modules absent from the older strict payload
requirements. Version 0.6.0 now requires coordinator, notice, one-shot,
presentation and work modules. Regression fixtures accept both complete
architectures and reject each omitted module independently; historical
release inventories retain their original requirements. The failed candidate
is cancelled before any tag or publication.
