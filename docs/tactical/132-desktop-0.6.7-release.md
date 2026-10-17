# 132 — Desktop 0.6.7 release recovery

Owning topic: [native distribution](../../topics/native-distribution.md).

Status: in progress.

## Objective and completion conditions

Repair the failed 0.6.6 release, publish a new immutable 0.6.7 release and
verify successful CI publication with all six platform/architecture packages.
Keep 0.6.5 and 0.6.6 tags unchanged. Installation and new native feature
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

### 2 — validate source and publish

Run portable checks and focused regressions. Prepare cumulative 0.6.7 notes
because 0.6.5 and 0.6.6 never published. Commit/push main and dispatch the
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
Release preflight and whitespace validation pass. Hosted execution and
publication remain pending.
