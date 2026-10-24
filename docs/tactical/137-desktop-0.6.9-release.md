# Desktop 0.6.9 release

Owning topics: [native distribution](../../topics/native-distribution.md),
[desktop audit and diagnostics](../../topics/desktop-audit-and-diagnostics.md).

Status: active.

## Objective

Publish the packaged Mac crash fix and subsequent hardening across the six
desktop architectures. The user requests monitored validation, repair of bugs
found during that process, green CI and a completed public release.

## Completion conditions

- Versioned release notes and exact committed source on main.
- Green source and six-target candidate CI, including matching Mac symbols.
- Claimed VM acceptance of the exact authenticated Mac ARM64 package with a
  qualifying minimized receipt and verified target restoration.
- Publication of those same candidate bytes, with complete signatures,
  inventories, update metadata and uploaded digest verification.
- Honest recorded execution gaps; raw VM evidence remains private.

## Boundaries

No controller workstation app replacement, new VM, credential change or outer
VM input. Existing package validation and the claimed Mac installed-app harness
are the ordinary routes. Intel/physical GUI execution and Windows/Linux new
feature GUI acceptance remain separate from package authentication.

## Ordered work

### 1 — prepare release identity

Add the 0.6.9 changelog, commit and push main, then dispatch the unified
candidate workflow. Keep the candidate source fixed through exact-byte
acceptance and publication; defects require a new source/candidate, not a
replacement tag or an unqualified receipt.

### 2 — validate CI and the installed package

Monitor all checks and signed architecture builds. Diagnose failures from their
actual logs, fix evidenced defects, run relevant checks and repeat affected
validation. Authenticate the Mac ARM64 candidate before the claimed seeded
browser/dialog/recovery/export campaign; restore the target in cleanup.

### 3 — promote and authenticate the public release

Use the release script with the successful unified candidate and its exact
acceptance receipt. Monitor publication through green CI, then verify public
asset completeness and identity without changing the controller's installed app.

## Validation and final result

Pending monitored candidate validation and publication. Earlier development
evidence belongs to [135](135-browser-file-dialog-crash.md) and
[136](136-desktop-crash-hardening.md); it cannot qualify this release receipt.

The first candidate was cancelled before promotion to correct shared Mac CI
concurrency: a push and a reusable release workflow could replace each other's
pending check. Include the caller workflow in the group while retaining serial
runs within each caller/ref. Complete the notes for the pre-existing Windows
native enrollment changes, keeping their incomplete signed lifecycle gate
explicit. No release tag was created for the cancelled candidate.

The next exact Mac package campaign passed seventeen complete download/upload
cycles, then failed its upload-panel lookup. Private diagnostics reproduced a
1,000-element truncated AX read while the Open window remained present; a
shallower read found Cancel. The harness had mistaken omission from a partial
tree for absence. Bound panel reads to their shallow controls, retain the same
element cap and soak requirement, reject missing controls on truncated reads,
and preserve private failure context. This is a fixture correction, not an
observed app crash. Both failed campaigns restored the VM and released claims;
neither produced a qualifying receipt.
