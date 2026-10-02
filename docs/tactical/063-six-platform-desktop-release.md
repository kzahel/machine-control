# 063 — Six-platform desktop 0.5.1 release

Status: in progress.

Owning topics: [native distribution](../../topics/native-distribution.md),
[installed agent CLI](../../topics/installed-agent-cli.md), and
[native sudo](../../topics/native-sudo.md).

## Objective and completion conditions

Release a new version on every packaged platform, as requested. Publish desktop
0.5.1 for Mac Apple silicon/Intel, Windows x64/ARM64, and Linux x64/ARM64.
Include native update discovery, the bundled Python CLI, and Mac sudo helpers.

- Require meaningful notes and one exact main source across all six targets.
- Pass source checks and native CI tests, authenticate final packages and CLI
  payloads, and retain honest GUI execution and physical-hardware gaps.
- Publish one immutable annotated tag and complete verified asset set.
- Verify public receipts, all six updater entries, eight download redirects,
  and production metadata for older and current clients.

## Boundaries

No workstation-component release, appliance replacement, credential rotation,
permission expansion, or physical-host input. Preserve unrelated working edits.
Existing native acceptance belongs to tacticals 060–062; package verification
alone does not establish a new GUI execution result.

## Ordered work

### 1 — prepare the complete patch

Version the unreleased notes and add installed CLI and Mac sudo changes. Run
portable checks, release tests, the desktop build, and site release tests.
Commit and push main without including unrelated working edits.

### 2 — build and authenticate every platform

Dispatch the unified release workflow from the exact main source. Require both
Mac, Windows, and Linux targets, native tests, signatures, installed inventories,
relocated CLI smoke, provenance, and tamper rejection before publication.

### 3 — verify public delivery

Use the common release script and its verified-draft publication flow. Check
published assets and receipts, signed updater metadata, production update
responses, and every download route. Record exact source and workflow identity,
restore working edits, and keep execution gaps explicit.

## Validation and final result

Pending hosted builds and public delivery verification.
