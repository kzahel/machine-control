# Desktop 0.7.0 release

Topics: `native-distribution`, `shared-resident-core`, `access-admission-and-pause`

Status: **In progress**; committed refactor pushed, source CI and exact signed
candidate acceptance required before publication.

## Objective and motivation

The user requested pushing all current work, making CI green, then releasing
the unified permissions and named-profile experience. Include the retained
Python client's negotiated automatic renewal, while preserving finite owner
watchdogs, consent ceilings, Stop and claim validation.

## Completion conditions

- Commit all intended changes and meaningful 0.7.0 notes; source CI is green.
- Build the unified signed six-target candidate at the exact clean main source.
- Execute the required packaged Mac acceptance against those authenticated
  bytes, with coverage matching the new surface contract and verified cleanup.
- Invoke the release script once with the candidate and qualifying receipt.
  Report queued publication; hosted CI owns signing/package verification and
  publication. No personal installation or post-publication monitoring.

## Boundaries

Preserve unrelated personal installations and private inventory. Use a clean
controller checkout where release validation requires it. Native effects run
on claimed dedicated targets, never through the controller's desktop.
Disposable reliability workspaces are sequential, journaled and cleaned up;
credential locators remain controller-private. Raw evidence is never committed.
Do not weaken the acceptance gate to accommodate removed legacy grants.

## Ordered work

### 1 — prepare and validate the release source

Commit the complete requested workspace, release notes and any demonstrated
CI fixes. Check all applicable source workflows at the final source.

### 2 — accept the exact signed candidate

Build all six targets, authenticate the Mac ARM64 archive and execute the
packaged reliability campaign with original consent ceilings, native effects,
crash/restart Off, saved choices, expiry/renewal and protected cleanup.

### 3 — queue publication

Promote the accepted candidate bytes through `desktop/scripts/release.sh`.
Record source/candidate and the workflow link without private evidence or
infrastructure identities. Finish after successful dispatch.

## Validation and result

All previously uncommitted client changes are included in `24b1b9f`; all 95
client/session tests pass. CI exposes POSIX-only Linux fixtures on Windows;
`db1fa68` declares their actual requirements while preserving pure event tests.
The next Windows run reaches the extension test and exposes its LF-only source
extractor. `10ae897` accepts actual LF/CRLF delimiters and refuses missing code;
the real worker lifecycle passes with both original and CRLF source bytes.

The legacy release harness expects grant restoration after crash and old scope
checkboxes. Its v2 path now uses real Settings, named enabled profiles and the
shipped Python SDK, retaining exact owners and finite watchdogs. Clean exit,
crash and boot must restore no authority. Native models, file dialogs, expiry,
renewal, guardian/root faults and disposal remain required. Active protected
Stop runs in the fresh sequential reboot workspace, followed by an observed
normal boot to regain the prepared auto-login session before visible choice
checks. No locked-console permission is silently rearmed.

The published extension 0.8.4 predates profile negotiation. Prepare 0.9.0 and
submit it through the existing tag/OIDC workflow before the desktop candidate,
so the bundled worker and store rollout have honest versions. New workers keep
older residents compatible; the new resident refuses old unprofiled workers.
Google review/publication remains distinct from successful submission.

Candidate construction and native qualification of the updated harness are
pending. The native adoption evidence in Tacticals 153–155 remains separate.

The first updated-source real-browser CI gate finds stale controlled-tab UI
after Stop. A deterministic real-panel test holds old tab metadata, delivers
a newer cleared state, then releases the old result; the stale render restores
old tabs. A presentation generation now fences both asynchronous tab and
activity commits. This changes panel rendering only, not control authority.

Mac CI also exposes a model fixture reading the runner's real console during
native preflight. The resulting session-generation refusal is correct, but
cannot qualify the simulated action. Admission-channel tests now bind both
coordinator and worker observations to their same modeled console. All 17
admission-channel cases pass. Real console/session behavior remains a native
candidate gate; it is not inferred from this fixture.

A subsequent Mac run reaches a renewal assertion comparing a real shared-child
lease view to exactly 120 seconds. The observed 119.999 seconds is elapsed
monotonic time, not a shortened requested lease. The test now requires the
renewed view in (119, 120] while retaining same-session and Stop/refusal checks.
All 17 admission-channel cases pass again; production timing is unchanged.

All four source workflows pass at `da4762a`. Extension `extension-v0.9.0`
submits successfully for Google review. Unified candidate `41974918896` then
finds a Windows release-only ordering bug: native shared-policy contracts run
before installing their Node dependencies. The failed composition cannot
qualify publication; its remaining builds are canceled before VM acceptance.
Install shared dependencies before native/portable checks in both Windows
release jobs. Mac source paths and its pure fixture test invocation now include
the shared runtime and all Mac acceptance helpers. Extension bytes are unchanged;
its immutable submission is not repeated when rebuilding the desktop candidate.

The replacement source again passes all source workflows. Candidate
`41977322135` clears Windows native contracts, then its Windows-only Rust
Clippy gate rejects a side-effect-only `map_err`. Use `inspect_err` while
preserving the diagnostic and original error. Add the unsigned Windows desktop
check to main/PR source CI; signed jobs remain dispatch-only on main. This
moves Windows Rust verification ahead of candidate construction. The failed
candidate is canceled before appliance acceptance; no VM has been created.

Controller review also catches a temporary-directory lifetime bug: the final
boot validator reads the extracted app's surface-contract marker after its
directory has been removed. Capture that marker while the verified archive is
still extracted; cleanup then cannot misclassify the current app as legacy.
No candidate or appliance execution is needed to reproduce this path error.
