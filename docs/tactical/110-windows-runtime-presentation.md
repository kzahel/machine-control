# 110 — Windows runtime and presentation

Status: Windows implementation complete; bounded development-signed x64
qualification passes. ARM64 desktop and publisher qualification remain open.
Owning topic: [runtime and presentation](../../topics/runtime-and-presentation.md).
Parent: [107](107-runtime-and-presentation.md).

## Objective and completion conditions

Keep the Windows operator responsive under companion/provider faults. Reuse
the .NET resident and its authorization boundaries for personal, minimal and
appliance presentation. Settings is disposable; approvals, notices and Stop
work independently. Support persistent configuration, launch overrides and
same-runtime recovery through the local CLI.

## Boundaries

No public release or replacement of the operator's installed application.
Presentation never grants access or selects a protected provider. Use native
builds and isolated candidates; effects and protected trials use claimed
dedicated targets. Keep raw evidence, infrastructure and deployment state
outside Git. Restore target installation, policy and initial power in cleanup.

## Ordered work

### 1 — bound companion work and fence cancellation

Move IPC and lifecycle waits off the Tauri event thread. Bound admission and
retain capacity for late workers. Keep native Stop independent of stalled
providers and reject work admitted before authority changes.

### 2 — make presentation optional and recoverable

Add native approvals/notices, lazy Settings, atomic preferences, local CLI
status/set/reset, temporary overrides and existing-runtime Settings recovery.
Keep configuration distinct from workstation/appliance authority.

### 3 — qualify native and signed candidates

Run fault/load contracts, frontend/client checks, format verification and
x64/ARM64 builds. Exercise all profiles, native fixture effects, owner loss,
Pause/Stop, restart, recovery, browser without Settings and update exclusion.
Distinguish unsigned/source evidence, signed bytes and native execution.

## Validation and final result

The starting checkout was `7a32778`, already pulled by the operator. All Git
operations used WSL on the current branch. Implementation stages are
`b38747a`, `73a9d6e`, `4c05939`, `ad2e3f3` and `0875e39`; the final functional
candidate is `0875e39f0d666b4f78bb1a521e1f591e8dd6eb38`. Subsequent evidence
and actor changes do not alter the executable implementation.

### Runtime, safety and configuration

**Current:** Windows companion calls and lifecycle waits run away from the
Tauri event thread. Admission is bounded; polls coalesce and a timed-out
physical provider worker retains its single slot until completion. Native Stop
posts independently to a process-bound resident HWND. Quit terminates the owned
job. Generation/cancellation fences prevent old preflight from borrowing new
consent. Protected policy, session and guardian observations now occur outside
the consent lock, with fresh authority checks before dispatch.

The existing .NET resident owns separate native approval and notice windows,
including narrowing, Pause and Stop. Settings is lazy and disposable in all
three profiles. Owner-only, bounded, versioned preferences use atomic writes
and a cross-process lock. Local status/set/reset, launch overrides, same-runtime
Settings recovery and restart reuse existing authorization. Presentation never
arms protected control or grants access. Appliance presentation is an idle
visibility choice, distinct from privileged appliance deployment.

A live run found a configuration transport defect: disconnecting with unread
reply bytes broke the CLI. A bounded acknowledgement now completes the exchange;
a busy live pipe cannot be mistaken for absence and edited offline. Later
review moved protected preflight out of the consent lock and bounded operator
admission. Runner corrections use actual cursor readback and exact UIA Settings
title absence; idempotent pointer motion and Process.MainWindowHandle were
inadequate effect/window oracles. Failed attempts remain in private evidence.

### Exact signed x64 execution

**Current:** A temporary local development certificate signed the exact GUI,
.NET resident and native fixture. The isolated x64 target authenticated these
bytes through Windows trust. This is development signing, not production
publisher or complete-package acceptance. Pinned upstream Cua bytes were
preserved; the Python/provider inventory has no signed package catalog.

| Executable | SHA-256 |
| --- | --- |
| x64 GUI | `f91fadee699eabc95a2ee640423775701684d3c4a87b5ccfd059f96aa1e923f5` |
| x64 resident | `1c487537db1740ee8fd6f313dbee9b6cb4c08ad0b718c5f191fd5dac7af38792` |
| ARM64 resident | `6a45383cff2fd9135745f64f60ec3412111a86b85a51567e027a87ebf2441e15` |

`runtime-presentation-live.py` passes 57 checks on the exact x64 candidate:
personal/minimal/appliance startup, native approvals/notices with Settings
absent, pending-approval preference deferral, independent native pointer effect,
owner disconnect/replacement, stale ownership, Pause/Resume, running-drag Stop
and observed button release, same-runtime recovery and restart. Restart expires
the temporary profile override, revokes volatile authority and reaps its old
resident. Pointer delivery remains distinct from effect uncertainty; the
fixture independently observes the effect.

Six discovery clients complete 60 requests: measured maximum 1,078 ms and p95
969 ms. With six incomplete public handshakes plus an owner occupying seven
slots, independent Settings/configuration recovery retains the resident PID
and completes in 2,516 ms. These end-to-end measurements include process/UIA
startup and are bounded trials, not pure IPC latency or a long soak.

Outside CLI discovery through target-native administration reports the same
ordinary resident route and generation; an unapproved effect is refused before
dispatch. Local retained-channel fixture work separately proves owned effects.
`browser-cdp-live.py` passes 29 checks with Settings absent: real page reads,
events, correlation, independent HTTP effects, pending-command progress,
scope/token/Origin refusal, Pause/Resume, owner loss, native-host reconnection
and Stop. Its HTTP oracle observes exactly the first, resumed and reconnected
effects. Registration is restored and app/browser/server are reaped. Optional
Playwright/Puppeteer browser-root clients were not included in this campaign.

`runtime-lifecycle-live.py` passes 11 checks through the inherited native
operator bridge: active consent excludes replacement, access-off admits update
exclusion, exclusion refuses new consent, cancellation releases it, and native
exit revokes authority and closes endpoints. It dispatches no installer or
replacement and does not qualify installed updating.

### Build and fault evidence

**Current:** TypeScript/Vite build, Rust formatting and warning-free clippy,
10 Rust tests, .NET format verification, Windows desktop/unlock and access
admission contracts pass. Python client tests pass 235 cases with nine platform
skips; focused Windows presentation CLI tests pass. Final .NET self-contained
x64 and ARM64 publishes pass. A symlink test is skipped where privilege is
unavailable. Fault contracts cover actual silent-child read timeout and kernel
reaping, native Stop independent of the companion lock, bounded admission and
queueing, cancellation, late completion and authority changes. They do not
claim every OS/provider failure has a hard latency bound.

The native x64 Tauri candidate builds. Full ARM64 Tauri compilation was
attempted and fails because ARM64 MSVC C++/clang tooling is unavailable. The
host installer cannot add it unattended without elevation. The ARM64 .NET PE
has ARM64 machine type and authenticates statically on the x64 target; it was
not executed on ARM64.

### Remaining qualification and cleanup

**Open:** Full ARM64 desktop build and native execution, production publisher
signing, complete-package/installer/updater authentication, installed
replacement, fresh protected UAC/lock/covered-control qualification, physical
hardware and longer fault/load soak. Existing protected authorization is
retained; older protected acceptance does not qualify these new bytes. Native
approval-loop faults, helper installation/repair, filesystem stalls and broader
OS/session transitions require separate bounded campaigns.

No public release or operator installed-app replacement occurred. All native
effects used a claimed dedicated target and a separately identified test
browser. Raw reports, trust material, infrastructure details and failed-run
logs remain ignored/private. Independent cleanup confirms no owned test processes remain, browser
registration is restored, owned scheduled tasks are removed, and temporary
guest trust plus the host signing certificate/private key are removed. The
canonical stored login credential is verified. The initial installed-app
presence is unchanged. Automatic approval review rejected combined recursive
cleanup as blocked by policy; the inert, uninstalled staging directory is
retained as a private artifact. Graceful shutdown succeeds in 32.1 seconds through the target's declared
bounded scheduler assistance. Final power is off, restoring the initial state;
the disruptive restoration claim is released and claim state is available.
No credential rotation, helper installation or policy weakening occurred.

## Native Linux handoff prompt

Continue Machine Control's runtime/presentation migration on a native supported
Linux host. Read `AGENTS.md`, `topics/runtime-and-presentation.md`, tacticals
107�110, `topics/linux-desktop.md`, `topics/linux-resident-control.md`, the Linux
platform report and applicable platform instructions. Stay on the current
branch and commit coherent stages with `Topic: runtime-and-presentation`.
Do not publish a release or replace the operator's installed app.

Reuse the existing Python/AT-SPI resident, provider adapters and authorization.
Keep ordinary compositor RemoteDesktop/ScreenCast consent separate from the
explicitly authorized root virtual-HID appliance route. Start on the supported
Ubuntu/GNOME Wayland target and report actual compositor/session capability.
Move companion/provider waits away from the GTK/Tauri event thread; bound
admission, work and deadlines, retain capacity for late workers, fence dispatch
and completion against Stop/owner loss/pause/generation changes, and preserve
uncertain already-dispatched effects.

Implement personal/minimal/appliance presentation within the existing package,
lazy Settings, native approvals/notices/Stop without Settings, atomic persistent
configuration, local status/set/reset, temporary overrides expiring on Restart
and existing-runtime Settings recovery. Presentation grants no authority and
must not select a privileged fallback.

Run native fault/load/cancellation tests, all three profiles, independent
fixture effects, local/outside CLI parity, stale references, ownership loss,
restart, browser without Settings and lifecycle exclusion. Build x64/ARM64
where supported and qualify exact signed candidates with honest distinctions
between build, authentication, execution and installed acceptance. Use doctor,
exclusive claims, separately identified browsers and target-native control;
restore original installation/policy/power and release claims. Keep private
infrastructure and evidence outside Git. Finish with Linux results and remaining
limits; Windows ARM64, publisher and protected gates above remain independent.
