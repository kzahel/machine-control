# 116 — Desktop 0.6.1 release

Status: active.
Owning topics: [native distribution](../../topics/native-distribution.md) and
[macOS locked use](../../topics/macos-locked-use.md).

## Objective and completion conditions

Commit and publish the Mac covered-startup repair as desktop 0.6.1. Require
meaningful release notes, exact-source checks, authenticated packages for all
six desktop targets, an immutable annotated tag, verified uploaded assets and
working public download/update metadata.

## Boundaries

The source and signed local physical completion evidence are recorded in
[115](115-macos-covered-observation-ordering.md). Publication qualifies package
authentication and delivery; it does not add protected-session, Intel GUI,
expiry, takeover or broader hardware execution evidence. Do not overwrite old
tags/assets or replace the controller's installed test candidate in this step.
Signing credentials and downloaded package evidence remain outside Git.

## Ordered work

### 1 — commit repair and release notes

Review the public diff, preserve the existing validation record, add versioned
notes and run release regression checks. Push clean main matching origin.

### 2 — build and authenticate the release

Use the common release script to create the immutable tag and dispatch the
unified workflow. Require all Mac, Windows and Linux architectures to pass
native publisher signatures, notarization where applicable, signed updater
versions and payload inventories at one source/workflow identity.

### 3 — publish and verify public delivery

Wait through CI, diagnose failures without moving the tag, and authenticate the
complete uploaded public asset set. Verify release notes, package receipts,
download redirects and production update metadata before completion.

## Validation and final result

Pending exact-source release workflow and public verification.
