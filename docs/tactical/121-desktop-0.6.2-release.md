# 121 — Desktop 0.6.2 release

Status: active.
Owning topics: [native distribution](../../topics/native-distribution.md),
[host control](../../topics/host-control.md),
[browser control](../../topics/browser-control.md) and
[operational workflow automation](../../topics/operational-workflow-automation.md).

## Objective and completion conditions

Publish the requested next Machine Control desktop version as 0.6.2. Include
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

Use the common release script and unified workflow. Require exact source,
native publisher signatures, Mac notarization/staples, signed updater versions,
payload inventories and tamper rejection across all six targets.

### 3 — verify publication and public delivery

Wait for workflow completion, verify uploaded assets and independently
authenticate public packages. Check release notes, receipts, all download
redirects and both production update metadata routes. Record actual evidence
and its execution limits before completion.

## Validation and final result

Pending.
