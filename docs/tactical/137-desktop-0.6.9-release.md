# Desktop 0.6.9 release

Owning topics: [native distribution](../../topics/native-distribution.md),
[desktop audit and diagnostics](../../topics/desktop-audit-and-diagnostics.md).

Status: complete; public 0.6.9 published with green candidate/publication CI.

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

**Current (2026-10-24):** [desktop 0.6.9](https://github.com/kzahel/machine-control/releases/tag/desktop-v0.6.9)
is public at source `799044d244712ab9b67a3840d47c38df8ec2cc2b`.
[Candidate 40133355870](https://github.com/kzahel/machine-control/actions/runs/40133355870)
passes every six-target build, signature/inventory check, installed CLI smoke,
symbol verification and final asset staging. The normal cross-platform and Mac
source workflows also pass at that source.

The exact signed/notarized ARM64 Mac archive passes 173 checks with fifty real
download/upload cycles, seed 3407 and a five-minute soak. Coverage includes
native panels, Settings recreation, cancellation/overwrite, native-host loss,
blocked-provider Stop, forced-exit recovery with access Off and unclean-exit
context, stale-reference refusal and real Settings diagnostic export. The
receipt binds source, candidate attempt, archive hash and successful cleanup.
The original app/policy/LaunchAgent/operator state is restored, the target is
suspended and its exclusive claim released. Raw evidence remains private.

[Publication 40135808548](https://github.com/kzahel/machine-control/actions/runs/40135808548)
promotes those exact candidate bytes and passes. All 29 public asset names,
sizes and GitHub SHA-256 digests verify independently against the authenticated
candidate set. An unauthenticated public Mac archive download matches the
VM-accepted archive hash. Public update metadata covers all six architectures,
and all six production updater routes return 0.6.9. The generated manifest's
publication timestamp legitimately differs between private staging and final
publication; all other fields match. Matching nonempty Mac symbols are retained
as separate CI artifacts, and actual ARM64 symbols resolve the repaired
keyboard-layout function to its source line.

Earlier development evidence belongs to [135](135-browser-file-dialog-crash.md)
and [136](136-desktop-crash-hardening.md); it did not qualify this release
receipt. Intel/physical GUI execution, Windows native enrollment lifecycle,
Linux new-feature GUI qualification and installed Chrome Web Store connection
retain their separate gates. The browser campaign uses the bundled unpacked
provider in Chrome for Testing. No controller workstation app is replaced.

### Validation repairs

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

The corrected fixture first passes 170 checks and 49 cycles against the earlier
signed package in an explicitly nonqualifying development run. The final exact
candidate then passes the complete 173-check gate described above. No source or
tag replacement, reduced soak, or substituted receipt is used.
