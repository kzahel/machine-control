# 060 — Native desktop update discovery

Status: complete

Owning topic: [native distribution](../../topics/native-distribution.md).

## Objective and completion conditions

Implement the requested Desktop Release Kit discovery pattern, then commit and
push. Native code schedules silent checks after five seconds and every 24 hours;
Settings, tray, and CLI share discovery state. Checks must not focus the app,
download/install, restart, or change access. Retain explicit installation and
the native access/approval replacement gate.

- Test scheduling, wake catch-up, concurrency, failure visibility, retained
  candidates, and mutual exclusion with installation.
- Exercise metadata-only queues through existing Mac/Windows/Linux transports.
- Prove native Mac discovery with the settings window closed and no focus or
  access change, restoring the claimed VM and its original policy/power.
- Build applicable source/packages and Windows ARM64/x64 runtimes, keep signed
  update acceptance distinct, and commit only this work.

## Boundaries

No release, physical-host input, automatic package installation, new transport,
channel adoption, endpoint changes, or permission/policy expansion. Existing
packages retain their shipped behavior. Reuse product-specific keys, routing,
replacement ownership, and Linux package-manager policy.

## Ordered work

### 1 — share discovery in the native controller

Own scheduling, deduplication, available metadata, errors, and install exclusion
in Rust. Preserve an offered update across failures and empty responses.
Automatic failures stay quiet; manual callers joining startup get visible
results. An overdue daily check runs once after wake.

### 2 — connect Settings, tray, and common CLI

Use existing private native operator channels to synchronize discovery metadata
and consume coalesced public requests. Mac's socket, Windows' desktop pipe, and
Linux's desktop socket expose only `update.check|status`. Queue acceptance and
completed network discovery stay separate. Only the local operator installs,
through the final access/approval check.

### 3 — validate without controller desktop input

Run Rust state/schedule tests, native mailbox/transport tests, frontend and Mac
package builds, Windows contracts and both runtime publishes. Exercise an
isolated Mac development app through claimed target-native control with its
settings window closed. Restore the original app/policy/power and release the
claim. Keep raw/private deployment evidence outside this repository.

## Validation and result

**Current:** Native Rust owns discovery and installation exclusion. Settings,
tray, and the three existing resident transports share that state. Public
discovery stays available with access off and cannot authorize control or
replacement. A consumed CLI request remains visibly busy until the next native
snapshot, preventing premature completion polling.

Validation passed:

- Four Rust scheduling/state tests, strict Clippy, and Rust formatting.
- Frontend production build, native Mac debug application bundle, 51 Swift
  tests including socket-level access isolation, and the portable check suite.
  Mac static smoke also passed, with existing AppKit deprecation warnings.
- Windows desktop contracts and ARM64/x64 runtime publishes. Local
  `dotnet format --verify-no-changes` returned success but warned that Windows
  workspace references did not fully load on macOS; Windows CI retains the
  authoritative semantic formatting check.
- Linux mailbox ownership/coalescing tests and common CLI routing, argument,
  and claim checks for all three desktop transports.
- A claimed macOS VM ran an isolated-identity, ad-hoc-signed development app.
  Both real startup discovery and a CLI request completed with Settings closed,
  unchanged foreground, available metadata, and access off. The original
  resident, policy, and suspended power state were restored and the claim
  released. Private logs remain outside the public repository.

This is source integration. Windows/Linux desktop execution, signed old-to-new
update acceptance, and physical-Mac execution of this change remain untested.
No release was published or physical-Mac package replaced by this tactical.
