# 132 — Desktop 0.6.8 release recovery

Owning topic: [native distribution](../../topics/native-distribution.md).

Status: complete; published on 2026-10-17.

## Objective and completion conditions

Repair the failed 0.6.6 release, publish a new immutable 0.6.8 release and
verify successful CI publication with all six platform/architecture packages.
Keep 0.6.5, 0.6.6 and 0.6.7 tags unchanged. Installation and new native feature
acceptance are outside this recovery.

## Ordered work

### 1 — diagnose and repair release gates

The [failed 0.6.6 run](https://github.com/kzahel/machine-control/actions/runs/39031823850)
rejected Linux's newly packaged `browser_preference.py` and `session.py`.
Require both from 0.6.6 onward and test omission of each on both architectures.
Windows exercised POSIX mode-0600 publication tests even though that route
cannot validate Windows ACLs. Retain explicit refusal before reading a file,
test it on every host, and run POSIX publication cases only on POSIX.
Explicit tool/environment session identities retain their existing route.

One Windows x64 scoped-run test exposed a prelaunch renewal failure reported
as setup failure. Classify it as renewal failure and cover cleanup and refusal
to start the child with a deterministic test.

Windows CI for source `ef60f19` then reached the desktop suite and exposed
Linux preference persistence and logon-identity tests using unavailable Unix
APIs. Run preference file-mode checks on POSIX and use an explicit fixture UID
for the pure session-identity test on every platform. The 0.6.7 release run
was canceled before publication; its tag remains unchanged.

### 2 — validate source and publish

Run portable checks and focused regressions. Prepare cumulative 0.6.8 notes
because 0.6.5 through 0.6.7 never published. Commit/push main and dispatch the
standard release script once.

### 3 — verify publication

Monitor the release workflow through signed builds and authenticated draft
publication. Verify the public release identity, complete assets and six-target
updater metadata. Record exact source and workflow identities below.

## Validation and final result

Local portable checks pass. All 79 release regression tests pass (one native
platform skip), including required Linux module omission cases for both
architectures. Focused MCP (12) and scoped-run (22) tests pass; Windows
publication refusal and deterministic prelaunch renewal cleanup are covered.
Release preflight and whitespace validation pass.
The revised desktop suite passes 25 tests (one skip). Its four locked-browser
tests also pass with `getuid` and `fchmod` removed to emulate missing Windows
APIs, skipping only native preference persistence.


**Current:** [Public desktop 0.6.8](https://github.com/kzahel/machine-control/releases/tag/desktop-v0.6.8)
uses immutable annotated tag `desktop-v0.6.8` at source
`fa776a64fde531464c9b9e0c2ea5f5033f4a22b9`.
[Unified release 39037695500](https://github.com/kzahel/machine-control/actions/runs/39037695500),
attempt 1, passed all six signed package jobs, Windows authentication and
final draft authentication/publication. Both
[source checks](https://github.com/kzahel/machine-control/actions/runs/39037689795)
and [tag checks](https://github.com/kzahel/machine-control/actions/runs/39037695739)
passed all six coordinator/native jobs across Mac, Windows and Linux.

All 29 independently downloaded public assets match GitHub SHA-256 digests
and sizes. Six build receipts bind the exact version, source and workflow
attempt. Eight package updater signatures and their signed versions verify
against the configured product key. The updater manifest contains exactly
six targets, matching public package URLs and signatures, and the release
body/manifest notes match the versioned changelog. All eight website download
redirects select 0.6.8.

After the shared service's cached 0.6.4 selection refreshed, all 24 production
update responses across the shared service and website proxy pass: 0.6.4
clients receive the exact 0.6.8 package URLs/signatures for all six targets,
and 0.6.8 clients receive HTTP 204. This required no service or site deployment.

Publication verifies package authenticity and delivery; this recovery does
not add installed GUI, protected-session, physical-hardware or sleep coverage.
The changelog preserves the existing feature acceptance limits. No published
assets or existing release tags were replaced. The 0.6.7 run was canceled
before publication when its source check exposed the remaining Linux fixture
portability errors.
