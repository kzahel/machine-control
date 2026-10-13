# 116 — Desktop 0.6.1 release

Status: complete; published on 2026-10-13.
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

**Current:** [Public desktop 0.6.1](https://github.com/kzahel/machine-control/releases/tag/desktop-v0.6.1)
uses immutable annotated tag `desktop-v0.6.1` at source
`d0da170e9cb5e0c29b688abd856d611336defc21`.
[Unified release 38455544883](https://github.com/kzahel/machine-control/actions/runs/38455544883),
attempt 1, builds, authenticates and publishes all six targets.
[Exact-source cross-platform checks](https://github.com/kzahel/machine-control/actions/runs/38454945028)
pass; a Mac coordinator job required retry after hosted runner acquisition
failed before any steps ran. The redundant push-triggered Mac check is
cancelled to free the release workflow's check slot.

All 29 independently downloaded public assets match GitHub SHA-256 digests
and sizes. Six package receipts bind version, source, workflow run and attempt.
Windows/Linux updater signatures, signed versions and payload inventories
pass with tamper rejection. Both Mac packages pass nested publisher signatures,
Gatekeeper, notarization/staples and updater signatures, including tamper
rejection. Hosted builds verify native Windows installed publisher signatures
and catalogs, Linux container inventories and installed CLI relocation for
all six targets. Local public verification authenticates packages in isolated
staging without launching residents or replacing the installed test candidate.

The public manifest contains exactly six signed updater entries and the
required changelog. The download page and all eight redirects select 0.6.1.
All 24 production responses across the website proxy and shared service match
the manifest for 0.6.0 clients and return HTTP 204 for 0.6.1 clients.

Local release/changelog regression tests pass (20 tests), as do portable
checks. The release workflow passes Mac Swift tests, native static smoke,
Rust/frontend format, lint and build checks, Windows contracts and native
publishes. The repair's 175 Swift tests and 16-check physical completion
retain the precise source/candidate limits in [115](115-macos-covered-observation-ordering.md).
Publication does not establish new installed production-package effects or
broader expiry, takeover, successive-task, Intel or multiple-display evidence.
