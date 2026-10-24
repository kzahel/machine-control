# Desktop crash hardening

Owning topics: [desktop audit and diagnostics](../../topics/desktop-audit-and-diagnostics.md),
[native distribution](../../topics/native-distribution.md),
[runtime and presentation](../../topics/runtime-and-presentation.md),
[browser control](../../topics/browser-control.md).

Status: complete; bounded locally signed Mac packaged qualification passes.

## Objective

Following the reproduced installed Mac keyboard-layout crash and its fix,
make future failures diagnosable and qualify the actual embedded runtime.
Add a repeatable packaged campaign rather than extending source-only evidence
to the installed product.

## Completion conditions

- Gate new publication on acceptance bound to exact signed candidate bytes.
- Retain thirty days of bounded diagnostics and explicit unclean-exit context.
- Offer operator-reviewed OS-report export without automatic collection/upload.
- Retain nonempty executable and embedded-framework symbols with final UUIDs.
- Audit short thread-affine native reads and exercise packaged recovery faults.
- Restore the claimed VM, release its claim and keep raw evidence private.

## Boundaries

No release, push, controller workstation app replacement, new VM, credential
change, raw stderr retention, automatic OS-report upload, or outer VM input.
Mac is the packaged crash-hardening vertical slice; Windows/Linux receive the
shared thirty-day diagnostic retention change. Their OS-report and unclean-exit
implementations remain open. Intel compilation does not establish GUI execution.

## Ordered work

### 1 — record unclean termination and review crash context

The Mac journal creates a private marker after serving begins. Actual clean
termination removes only its own runtime marker; an older instance cannot clear
a replacement's marker. A stable per-instance file lock makes replacement and
ownership-checked removal atomic across processes; contention fails tracking
without waiting on the coordinator or disabling audit. A subsequent start
records bounded unfinished operation names and validated build/image identity with unknown effect and limited-history
semantics. Marker failure is visible without disabling Stop or ordinary audit.

Standard exports still exclude OS reports. A separate operator preview reads at
most three matching user-owned regular reports, each at most 2 MiB, from the
fixed OS directory. It rejects links, unrelated applications and invalid data.
Save consumes an expiring one-use snapshot, so it exports the reviewed bytes
even if the source changes. File scanning/export work uses the existing bounded
operator worker; OS-report reads do not hold the audit lock.

### 2 — preserve matching usable symbols

CI builds Rust and Swift line information with source path remapping. Swift's
completed dSYM is moved outside the shipped framework before temporary object
files disappear. The collector checks both image UUIDs, dwarf hashes and actual
compile units: an empty dSYM with the correct UUID is refused. Product debug maps
are stripped before signing; final signed UUIDs are verified again. Separate
ninety-day symbol artifacts never enter the public installer asset set.

### 3 — fence native and browser work across authority changes

`NativeUIThread` wraps only short main-thread reads. Keyboard input-source
properties use it; AppKit window enumeration asserts its main-thread placement.
SDK-declared thread-safe process/workspace reads remain on workers, as do AX,
process/socket waits and whole provider operations. Regression checks cover
worker/main execution, returning to the worker, and error propagation.

The browser audit found a second defect: numeric references survived grant
replacement, and queued ordinary requests could adopt new approval. References
now include a random authority epoch, and ordinary work binds authority at native
message arrival. CDP awaits and navigation effects recheck it. A held-geometry
fixture proves a revoked click never presses after its late reply; queued old
text never reaches Chrome. Already-delivered effects are not rolled back.

### 4 — exercise the installed app and gate exact-byte promotion

The controller harness authenticates final packages, installs the actual app on
a claimed VirtualMac with a stricter workstation policy, and uses independent
target-native AX to approve and operate Settings. Chrome for Testing has its own
temporary profile/process group. Seeded filenames include spaces and Unicode;
HTTP bodies and file bytes verify effects independently. Operation timelines
exclude request fields and response payloads.

Faults terminate only the test browser's proven-owned native host, stop access
during a held HTTP navigation, and forcibly terminate the installed resident.
The planned restart is explicit; other reply generations/PIDs must stay stable.
Recovery requires access Off, an unclean-exit breadcrumb, new approval, old-ref
refusal and a fresh independently observed browser effect. Operator UI checks
cover the unclean notice, ordinary export exclusion and reviewed crash export.

From 0.6.9 the main-only publication path requires a successful unified candidate
and minimized controller receipt. It checks exact source/version/run attempt and
Mac ARM64 archive hash, required coverage, bounded counts and successful cleanup.
Development/dirty runs cannot qualify. There is no prepared-VM CI controller;
the receipt is maintainer attestation, not hardware attestation or a claim that
hosted CI executed the GUI. Publication still promotes those exact bytes.

## Validation and result

**Current (2026-10-24):** the first locally Developer ID signed full application
passes 47 packaged checks and nine download/upload cycles with seed 3407,
Settings recreation, native-host recovery, blocked-provider Stop, planned app
termination/restart, old-reference refusal and unclean-exit context. The original
app byte/mode manifest, root policy, LaunchAgent and operator files are restored;
the VM returns suspended and the exclusive claim is released. No unexpected
resident restart or new OS report is observed. Raw evidence remains private.

The following full candidate passes 53 checks and ten download/upload cycles
with seed 8911. Its actual installed Activity UI shows the unclean-exit notice,
omits OS reports from ordinary export, and exports the exact explicitly reviewed
report after the source changes. The blocked-provider Stop reply takes 44 ms in
this run. Its 290-row private timeline contains only operation, monotonic time,
duration, acceptance and error code. Cleanup is independently verified and the
VM returns suspended with its claim released. Matching native symbols resolve
the keyboard-layout function to `KeyboardInput.swift` through `atos`.

The final marker-lock/health-synchronization package passes another 32 checks
and three cycles, including every recovery fault and real operator export.
Native tests total 230, including nonblocking lock contention and marker
ownership. Rust's eleven tests, seventeen browser tests, seven Linux journal
tests, release validation (82 tests; one Windows-registry-only skip), TypeScript,
clippy/format and Mac static checks pass. The static probe corpus includes 500
successes plus error/deadline/cancellation/reaping cases without descriptor
growth. Intel native compilation and Windows contract/format checks plus
ARM64/x64 self-contained publishes pass. The portable suite passes; raw logs
and symbol archives remain private. The final VM is restored and suspended and
its exclusive claim released.

This local development campaign cannot issue a release acceptance
receipt; the future signed/notarized CI candidate must run the same gate at its
exact clean source. Windows/Linux browser execution, Intel/physical execution,
long-duration soak, updater replacement and production crash capture remain
separate evidence gaps.
