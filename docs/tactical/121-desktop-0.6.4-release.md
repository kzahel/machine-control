# 121 — Desktop 0.6.4 release

Status: complete; published on 2026-10-14.
Owning topics: [native distribution](../../topics/native-distribution.md),
[host control](../../topics/host-control.md),
[browser control](../../topics/browser-control.md) and
[operational workflow automation](../../topics/operational-workflow-automation.md).

## Objective and completion conditions

Publish the requested next Machine Control desktop version as 0.6.4. Include
cross-platform person-armed access retention, Chrome extension side panel and
store-origin support, and installed CLI help and private usage notes. Require exact-source
checks, authenticated packages for all six targets, an immutable annotated
tag, verified uploaded assets and working public downloads/update metadata.

## Boundaries

[120](120-person-armed-access.md) owns the cross-platform retention work;
this release includes all three platform implementations, with exact
production-package installed acceptance remaining separate. [117](117-chrome-web-store-extension.md)
owns store review and installed store-copy acceptance. Publication establishes
package authentication and delivery, not new installed GUI, protected-session,
lock/restart, Intel or physical-hardware effects. Preserve existing releases
and keep signing material and downloaded evidence outside Git.

## Ordered work

### 1 — prepare notes and validate source

Review changes since 0.6.1, write versioned notes, run portable and release
checks and the Mac resident tests. Commit and push clean main.

### 2 — build and authenticate six targets

Pin the clean main source with the common annotated-tag release script, then
let the unified workflow build, authenticate and publish only after all gates
pass. Require exact source,
native publisher signatures, Mac notarization/staples, signed updater versions,
payload inventories and tamper rejection across all six targets.

### 3 — verify publication and public delivery

Wait for workflow completion, verify uploaded assets and independently
authenticate public packages. Check release notes, receipts, all download
redirects and both production update metadata routes. Record actual evidence
and its execution limits before completion.

## Validation and final result

**Current:** [Public desktop 0.6.4](https://github.com/kzahel/machine-control/releases/tag/desktop-v0.6.4)
uses immutable annotated tag `desktop-v0.6.4` at source
`48b87b7e779f295b25f384b5438d73469b4ed5fb`.
[Unified release 38524756135](https://github.com/kzahel/machine-control/actions/runs/38524756135),
attempt 1, builds, authenticates and publishes all six targets.
[Exact-source cross-platform checks](https://github.com/kzahel/machine-control/actions/runs/38524749192)
pass on all three platforms. The release passes Mac Swift/static/Rust checks,
frontend builds, Windows native contracts and `dotnet format`, native
ARM64/x64 publishes, installed CLI relocation and publisher/catalog checks.

All 29 independently downloaded public assets match GitHub SHA-256 digests
and sizes. Six receipts bind version, source and workflow identity. Both Mac
candidates passed independent local updater signatures, signed versions,
nested publisher signatures, Gatekeeper, notarization/staples and tamper
rejection before publication; their public packages and receipts are
byte-identical to those authenticated candidates. Public Windows/Linux
updater signatures, signed versions, payload inventories and tamper rejection
also pass. Packages are authenticated in isolated staging without launching
residents or installing the public release.

The manifest contains exactly six signed updater entries and the required
changelog. The download page and all eight redirects select 0.6.4. All 24
production responses across the website proxy and shared service match the
manifest for 0.6.1 clients and return HTTP 204 for 0.6.4 clients. A default
Python user-agent received HTTP 403 during one redirect probe;
curl and the identified release-verification user-agent verify the route.

Local validation passes 77 release regression tests (one platform skip), five
claim-channel tests, 14 Linux grant tests and 178 Mac resident tests. The
revised channel fixtures pass in both Windows release jobs. Bounded installed
Mac and signed ARM64 Windows/Linux retention evidence remains tied to the
sources and limits in [120](120-person-armed-access.md), including Windows's
remaining owner-session fixture work. Publication does not establish new
exact-production GUI, protected-session, lock/restart, Intel or broader
physical-hardware acceptance.

The failed 0.6.2 tag remains intact; neither cancelled 0.6.3 candidate was
tagged or published. The final standard tagged workflow pins its source
before building, so concurrent later main commits cannot invalidate it.
Earlier standalone qualification builds delayed its platform slots; a
redundant automatic Mac check was cancelled. Candidate rebuilds and those
queue waits made this release substantially slower than the prior release.

### Qualification repair

The first tagged attempt for 0.6.2 at source
`a412b58136b3efb09a786864394a6afbfc863f5c`
([38518358573](https://github.com/kzahel/machine-control/actions/runs/38518358573))
built and signed Linux ARM64 packages, then correctly rejected seven side-panel
and icon resources missing from the strict inventory requirements. No draft
or public release was created. The remaining jobs were cancelled.

The repair requires all seven resources for versions 0.6.2 and later;
regressions authenticate complete x64/ARM64 fixture inventories and reject
omission of each resource. Historical inventory requirements stay unchanged.
The immutable failed 0.6.2 tag remains intact. The next attempt used 0.6.3
from the repaired source as an untagged candidate.

The first 0.6.3 candidate
([38519495134](https://github.com/kzahel/machine-control/actions/runs/38519495134))
at `de253841f10c9df1da457dc5cd4780d20c9bfd68` passed both Mac and Linux
package jobs. It was cancelled during Windows packaging after concurrent
work advanced main with installed Mac evidence and a bundled CLI bytecode
repair. The next candidate included that completed work at exact main.
No 0.6.3 tag or release was created from the cancelled candidate.

The repaired-source cross-platform checks
([38519495376](https://github.com/kzahel/machine-control/actions/runs/38519495376))
passed after retrying the Windows coordinator job. Its first attempt found one
claim winner but a losing process reported a lock error instead of the expected
claim conflict. This unchanged concurrency test failure remains a separate
diagnostic observation; the retry does not establish its cause or repair it.

The next 0.6.3 candidate
([38522635339](https://github.com/kzahel/machine-control/actions/runs/38522635339))
at `d65645e7afd819b2718f761d3a4690892e8f64ea` passed Linux packages and
exact-source cross-platform checks, but Windows x64 portable checks failed
in two claim-channel fixtures. Its remaining jobs were cancelled. Separately,
main advanced with Windows/Linux retention and 0.6.4 notes. Neither 0.6.3
candidate produced a tag or public release.

The channel fixtures previously spent their two-second claim during process
startup; non-expiry tests now allow ten seconds. Expiry/renewal tests shorten
the lease after the first independent fixture effect, preserving the expiry
and renewal assertions. Oversized writes may observe early pipe closure only
when the guardian reports `control_frame_too_large` and no fixture effect.
EOF diagnostics now include the guardian's stderr. The original failing logs
did not retain that stderr, so the exact original child-exit cause remains
unknown; this is a fixture robustness repair, not a claimed runtime repair.

All changes since public 0.6.1 were consolidated into 0.6.4. The standard
tagged workflow kept its source pinned through publication.
