# 112 — Runtime and presentation acceptance review

Status: completed bounded review; release qualification remains open.
Owning topic: [runtime and presentation](../../topics/runtime-and-presentation.md).
Parent: [107](107-runtime-and-presentation.md).

## Objective and completion conditions

Continue after the Linux implementation by comparing the actual Mac, Windows
and Linux candidate records. Establish which parts of the reusable runtime and
three presentation profiles are implemented, built, authenticated and executed.
Check the combined source on the Mac development host, correct stale acceptance
guidance and give the next campaign a concrete order.

## Boundaries

No publication, installation, updater replacement, target startup, claim
acquisition or live desktop effects. Review the recorded native campaigns;
do not represent them as newly replayed or independently reauthenticated here.
Use deterministic source suites and unsigned development builds. Keep logs and
generated packages private; commit only minimized findings and reusable fixes.

## Ordered work

### 1 — compare exact candidate scope

Inspect checkout state, topic, platform reports, migration tacticals and
acceptance matrix. Separate platform-native runtime changes from shared
Tauri/frontend changes and historical released-package evidence.

### 2 — check combined Mac source

Run portable checks, Swift/Rust tests, frontend build, Rust formatting/Clippy,
Mac native static checks and both Mac app builds. Investigate actual failures;
never turn compilation into native-effect or production-authentication evidence.

### 3 — reconcile guidance and select the next campaign

Update current topic and acceptance indexes without rewriting completed
platform execution records. Order remaining package, architecture, installed,
protected-session and physical qualification work; keep publication separate.

## Validation and final result

### Candidate comparison

**Current, record/source review:** the starting checkout is clean at
`fc4ad9dc39c5adc9c54159df2b9c0bf08e03e5be`, containing both later native ports.
The [acceptance matrix](../desktop-acceptance.md#runtime-and-presentation-candidate-acceptance)
indexes the distinct functional revisions:

- Mac profile/effect campaign: `72a2eef`; signed ARM64 Tart execution.
- Mac hardening: `9be9f02`; signed ARM64 physical-host discovery/recovery and
  deterministic faults, with no new full VM/protected campaign.
- Windows: `0875e39`; development-signed x64 execution. ARM64 .NET publish is
  build/static-authentication evidence; full ARM64 Tauri tooling is missing.
- Linux: `35ee5ec`; development-authenticated x64 debug Debian candidate,
  extracted rather than installed. All 214 recorded native checks pass.

The Mac Swift runtime and bridge are unchanged after hardening. Linux work
preserves the Windows .NET runtime and Windows-specific Rust adapter. Shared
Tauri startup/window/lifecycle, argument handling and frontend changed across
the ports. No record establishes native/installed acceptance of one common
source revision across all six release targets. Older ARM64 or production
acceptance cannot fill that gap.

**Current:** the initial matrix omitted Mac hardening and both native ports.
The parent tactical still called Linux integration open. Those summaries now
describe completed implementation and bounded platform campaigns while keeping
combined-source release qualification open. Completed tacticals 108–111 retain
their original candidate identities, procedures and limits.

### Combined-source checks on Mac

**Current, `built`:** all 170 Swift and 10 Rust tests pass. TypeScript/Vite
build, Rust formatting, all-target Clippy with warnings denied and Mac native
static checks pass, including the 500-case session-probe resource fixture.
Existing AppKit activation deprecation diagnostics remain; these checks do not
claim warning-free Swift or all-path native responsiveness.

Unsigned ARM64 and Intel Tauri app builds pass. Embedded `MCSourceRevision`
records `fc4ad9d` for ARM64 and `2eb2ba9` for Intel. The latter commit changes
only the cancellation test described below; executable implementation is the
same. These are development builds, with no publisher/notarization or fresh
GUI execution evidence. No Windows/Linux native build or target campaign was
run from this Mac review.

Portable `bin/check --portable` passes after the fixture correction, including
236 client tests and the desktop cancellation/configuration/work fixtures.
Platform-specific skips remain explicit. Logs and generated apps stay local.

### Cancellation fixture correction

The first portable run failed the queued CLI cancellation test on Python 3.14:
an import-time SyntaxWarning made stderr readable before the CLI installed its
signal handler. SIGTERM then terminated the interpreter directly instead of
testing queued cancellation. This is a readiness-oracle defect, not evidence
of a resident or cancellation implementation failure.

`2eb2ba9` waits for the explicit `machine-control-run/v0` waiting record, then
sends SIGTERM. It injects an early startup diagnostic on every Python version
to preserve coverage of this distinction. All ten claim-session tests pass;
the cancelled child never starts and the existing owner's claim remains active.
The complete portable suite also passes. CLI/runtime behavior is unchanged.

## Next campaign order

**Decision:** keep the existing runtimes and one package stream. Further
ordinary-profile implementation is not the next milestone. Qualify the
combined implementation at an explicitly pinned candidate revision:

1. **Close build gaps.** Use native Windows/CI with ARM64 MSVC/clang tooling
   for the full GUI; use supported native Linux ARM64/CI dependencies for
   release-mode Debian/AppImage. Verify all six packages share the selected
   source, version and inventories. Prefer native build placement over slow
   emulated VM builds.
2. **Authenticate candidate bytes.** Use the existing candidate workflow and
   package verification for publisher, nested payload, installer/updater and
   tamper checks. Preserve candidate-only status; signing does not authorize
   publication or establish native execution.
3. **Run ordinary native acceptance.** On claimed dedicated targets, exercise
   all three profiles, Settings absent during approvals/notices/browser work,
   independent effects, local/outside parity, stale authority, Pause/Stop,
   provider faults, same-runtime recovery, restart and override expiry. Repeat
   Mac ARM64 effects after hardening and the shared changes. Execute Windows
   and Linux ARM64; qualify Intel Mac GUI separately from its build.
4. **Prove installation and replacement.** Test fresh install, startup/session
   transitions, preference retention/reset, permissions, access-off restart,
   browser continuity and actual updater/package-manager replacement on test
   targets. Update exclusion alone is not installed-update evidence. Preserve
   the operator's installed app and restore each target's prior state.
5. **Qualify protected and broader environments.** Keep Mac helper
   setup/repair/removal, covered startup and fresh protected effects, Windows
   UAC/locked-use and independent cleanup in their dedicated bounded campaigns.
   Physical hardware, monitors/scaling, suspend/resume and longer soak establish
   additional support scope. State omissions explicitly if release scope is
   narrower; a stuck native worker retaining capacity is not a universal hard
   latency guarantee.

The first ordinary acceptance campaigns need not wait for broader hardware
coverage, but cannot claim protected or physical qualification they omit.
Publication is an independent, explicitly authorized final step after the
chosen release scope meets its gates. Nothing was published, installed or
changed on a test target by this review.
