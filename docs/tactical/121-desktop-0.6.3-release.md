# 121 — Desktop 0.6.3 release

Status: active.
Owning topics: [native distribution](../../topics/native-distribution.md),
[host control](../../topics/host-control.md),
[browser control](../../topics/browser-control.md) and
[operational workflow automation](../../topics/operational-workflow-automation.md).

## Objective and completion conditions

Publish the requested next Machine Control desktop version as 0.6.3. Include
Mac person-armed access retention, Chrome extension side panel and store-origin
support, and installed CLI help and private usage notes. Require exact-source
checks, authenticated packages for all six targets, an immutable annotated
tag, verified uploaded assets and working public downloads/update metadata.

## Boundaries

[120](120-person-armed-access.md) owns the cross-platform retention work;
this release includes its Mac implementation only. [117](117-chrome-web-store-extension.md)
owns store review and installed store-copy acceptance. Publication establishes
package authentication and delivery, not new installed GUI, protected-session,
lock/restart, Intel or physical-hardware effects. Preserve existing releases
and keep signing material and downloaded evidence outside Git.

## Ordered work

### 1 — prepare notes and validate source

Review changes since 0.6.1, write versioned notes, run portable and release
checks and the Mac resident tests. Commit and push clean main.

### 2 — build and authenticate six targets

Build a unified candidate before tagging, then promote its exact signed bytes
with the common release script. Require exact source,
native publisher signatures, Mac notarization/staples, signed updater versions,
payload inventories and tamper rejection across all six targets.

### 3 — verify publication and public delivery

Wait for workflow completion, verify uploaded assets and independently
authenticate public packages. Check release notes, receipts, all download
redirects and both production update metadata routes. Record actual evidence
and its execution limits before completion.

## Validation and final result

Pending.

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
The immutable failed 0.6.2 tag remains intact. Use 0.6.3 from the repaired
source and authenticate the complete candidate before creating another tag.
