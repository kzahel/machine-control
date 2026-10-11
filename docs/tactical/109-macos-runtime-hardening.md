# 109 — Mac runtime hardening

Status: completed bounded hardening pass.
Owning topic: [runtime and presentation](../../topics/runtime-and-presentation.md).
Parent: [107](107-runtime-and-presentation.md).

## Objective and completion conditions

Before adapting Windows, prove the Mac coordinator remains responsive under
stalled dependencies and concurrent callers. Stop must revoke local authority
promptly; expired or invalidated preflight must not dispatch later effects.
Bound worker, handshake and reply growth, and exercise signed Settings recovery
under host load without replacing the installed application.

## Boundaries

Use deterministic native fault fixtures before headed acceptance. Host live
checks use an isolated candidate, no access grant and no desktop effects.
No public release, notarization, production update installation, protected
setup changes, lock/unlock, VM provisioning or browser takeover. Preserve
installed application, helper, policy and canonical presentation preferences.

## Ordered work

### 1 — audit and reproduce blocking or cancellation gaps

Inspect explicit Resume, helper setup/removal, restart and update paths.
Add meaningful fault cases for combined stalls, Stop and late completion.
Fix reproduced defects in coherent commits while preserving native affinity.

### 2 — exercise bounded concurrency and recovery

Drive actual resident sockets with concurrent discovery, stalled handshakes
and slow readers. Observe main-queue progress, worker admission and resource
recovery. Run appropriate Swift, Rust and native static checks.

### 3 — qualify the signed host candidate and hand off

Build and locally sign exact source. Run bounded concurrent host discovery,
same-runtime Settings recovery and main-thread sampling on an isolated socket.
Restore focus and terminate owned processes; record sanitized evidence and
remaining limits. Provide a native-Windows continuation prompt.

## Validation and result

Runtime source candidate: `9be9f02`, unreleased development version `0.3.0`.
Evidence date: 2026-10-11. No installed-host replacement or public release.

### Deterministic and build checks

- All 170 Swift tests pass. The initial regression reproduced stale preflight
  adopting new authority after Stop; admission-time fencing now refuses it.
  A five-second preflight deadline completes the caller once, retains one
  worker and discards late observations/effects. Its fault case refuses 1,000
  further requests while the slot is occupied.
- Resume uses one asynchronous operator dependency with a three-second caller
  deadline. Tests cover success, timeout, busy admission, Stop, changed pauses
  and grant fencing. Late helper completion cannot clear a newer local pause.
- Eight actual socket clients complete 800 discovery requests while helper,
  session and provider dependencies are blocked. Main ticks continue; native
  Stop removes an actual fixture grant in less than the 250 ms test bound.
- Slow-reader fixtures fill 64 reply slots, refuse 1,000 extra writers, expire
  and recover capacity. Handshakes share that process-wide reply capacity.
- Native static smoke passes, including the 500-case session-probe resource
  fixture. Shared frontend build and 234 portable client tests pass.
- All 10 Rust tests pass, including asynchronous callback ownership. Clippy
  passes for all targets with warnings denied; Rust formatting is clean.
- ARM64 and Intel app bundles build, are locally Developer ID signed and pass
  strict nested signature verification. Intel GUI execution remains absent.

### Signed physical-host load and recovery

The exact signed ARM64 candidate starts with saved appliance/temporary minimal
presentation on an isolated endpoint, no access grant and approval policy.
Settings begins with zero WebViews. Under 96 incomplete-handshake connection
attempts, 87 connect and nine receive expected listen-backlog refusal. Resident
FDs peak at 74 from an eight-FD baseline, consistent with 64 admitted handshakes
plus transient dependency descriptors. Settings opens in 127.6 ms through its
independent endpoint; disconnecting the flood restores ordinary discovery.

Eight clients then complete 22,826 discovery requests during a 90-second
measurement interval plus warmup/recovery: 17,406 accepted and 5,420 bounded
`native_provider_busy` refusals. There are no timeout or unexpected transport
failures in the successful run. Request p99 is 240.3 ms; maximum is 3,550.2 ms.
Five same-runtime Settings recoveries take 10.6–23.3 ms and retain one WebView.
The sampled main thread has no helper/socket wait or audit append path.

Warm resident RSS samples range from 112,288 to 114,192 KiB, settling at
111,520 KiB. Sampled FDs range from 19 to 23, settling at 18. This is a bounded
resident observation, not a strict memory bound, full WebKit-process accounting,
long soak, physical input or protected-session acceptance.

Installed executable, helper configuration, trusted policy and canonical
presentation fingerprints are unchanged. The installed resident PID is retained.
The candidate terminates, its owned endpoint/preferences are removed, focus is
restored and the host claim is released; final claim state is available. Raw
samples/logs and exact private target details remain outside Git. No VM was used.

### Findings and runner corrections

Live load exposed a real discovery hot path: delegation status was treated as
an unknown action and wrote/pruned audit segments on the main thread. Concurrent
discovery timed out, and an independent main-thread sample caught the writer.
The already public same-user query is now classified as discovery and leaves
durable and in-memory action audit unchanged. A 1,000-poll regression preserves
audit bytes, while subsequent grant requests still persist intent. The exact
signed replay above passes after this fix.

Earlier runner attempts also mistook listen-backlog refusal for a crash and
half-closed an already answered socket. The corrected runner counts overload
refusal only while the candidate is alive and uses the newline framing contract.
Failed runs terminated their candidate and released their host claim. The
pre-fix audit-pressure sample remains in private evidence.

`runtime-host-load.py` is the reusable bounded runner; the caller owns doctor
and claim lifecycle. It preserves the installed app and uses an isolated socket.

## Lifecycle audit

**Current, source-reviewed:** normal display polling uses bounded observations;
native effects use one serial provider slot; Resume now waits asynchronously.
Stop fences local authority and does not wait for helper acknowledgement.
Restart prepares native revocation and spawns an OS handoff; waiting for the
predecessor occurs in that helper process.

**Open:** helper registration/preparation/removal still includes synchronous
ServiceManagement calls and fresh session/helper checks, including the
already-installed helper's automatic repair path. Covered-control startup
includes native guardian/input readiness waits. Logs, consent and some
preferences still perform synchronous file work. Actual update replacement
runs on the main thread behind the native lifecycle gate. These paths need
separate fault injection and protected/update acceptance; this campaign does
not install a helper, replace a bundle through the updater or lock the host.

The original installed helper delay and exact displayed error remain unknown.

## Native Windows handoff prompt

Continue the runtime/presentation migration in this checkout on a native
Windows development host. The user wants end-to-end Windows implementation,
verification and coherent commits, then Linux on a native supported host.
Stay on the current branch; use Git through WSL. Do not publish a release or
replace the operator's installed app as part of this implementation campaign.

Read `AGENTS.md`, `topics/runtime-and-presentation.md`, tacticals 107–109,
`topics/windows-desktop.md`, `topics/windows-resident-control.md`, the Windows
platform report and applicable platform instructions. Create a bounded Windows
child tactical under the existing `runtime-and-presentation` topic.

Reuse the existing .NET resident, providers, workstation/appliance deployment
boundaries, grants, owner sessions and protected helpers. Implement personal,
minimal and appliance as presentation settings in one package/release stream;
presentation must never grant authority or choose a privileged fallback.

First remove Tauri-main-thread companion waits in
`desktop/src-tauri/src/windows.rs` and `main.rs`. Keep operator Stop independent
of stuck work, bound concurrency and deadlines, and fence preflight/completion
against Stop, owner loss, timeout, pause and grant/session generation changes.
Preserve accurate delivery/effect uncertainty for already dispatched calls.

Then implement lazy Settings creation/destruction, approvals/notices/Stop with
Settings absent, safe persistent profile storage, selector and local CLI
status/set/reset, temporary launch overrides that expire on Restart, and
second-launch recovery in the existing endpoint's runtime. Adapt Windows-native
interfaces rather than copying Swift or rewriting the common contract.

Build on the native host. Run meaningful fault/load tests, shared frontend and
client checks, `dotnet format --verify-no-changes`, contract tests and x64/ARM64
publishes. Qualify exact signed candidates on suitable claimed targets: all
three profiles, native approval and independent fixture effects, local/outside
CLI parity, stale references, Pause/Stop, owner loss, restart, browser without
Settings and update exclusion. Use separately identified test browsers.
Protected/UAC/lock tests belong on dedicated appliances, with target-native
control and independent cleanup. Read doctor, acquire/renew/release claims and
restore initial power/installation/policy; keep private evidence out of Git.

Commit coherent stages with `Topic: runtime-and-presentation`, update the
topic/platform/tactical evidence honestly, and finish with Windows results,
remaining limits and a Linux continuation prompt. Do not claim Mac tests
qualify Windows or compilation qualifies installed behavior.
