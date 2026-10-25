# Preserve remote arming and recover stalled browser control

Owning topics: [Mac locked use](../../topics/macos-locked-use.md),
[browser control](../../topics/browser-control.md),
[access admission and pause](../../topics/access-admission-and-pause.md),
[Mac resident control](../../topics/macos-resident-control.md).

Status: complete; unreleased implementation and bounded VM qualification.

## Objective

Repair the [remote lockout incident](../../gaps/2026-10-25-locked-use-self-revocation.md).
Operator arming survives ordinary task/provider failures. Protected cleanup
remains mandatory, and a stalled browser page cannot block recovery commands
or unrelated tabs.

## Completion conditions

- Ordinary faults preserve operator consent; Stop, expiry and console identity
  changes retain their authority semantics.
- Covered failure verifies cleanup without erasing unrelated authorization.
  The helper recovers from fresh safe conditions, without routine manual unlock.
  Transient admission observations cannot disable an admitted task, while a
  hung root is detected by a bounded positive-status liveness requirement.
  A root-only fault cell stops both user-session control processes and requires
  independent IOKit lock within ten seconds of the root's fault marker, using
  CLOCK_MONOTONIC_RAW and the effective GUI-session lock-only route.
- Multiple login windows are searched for an unambiguous ready field.
- Browser requests have bounded scheduling, request-local authority and
  cancellation. Recovery messages bypass stalled ordinary work.
- Dialog inspection/handling and honest unknown outcomes are exposed. Indicator
  cleanup cannot prevent debugger detach or reconnection.
- Regressions and a claimed signed packaged Mac VM campaign establish
  independent effects, lock state, consent retention, Stop and cleanup.

## Boundaries

No publication, workstation app replacement, personal browser automation,
retained appliance, credential changes or outer VM input. An explicitly
claimed isolated COW workspace may qualify helper registration and locked
endings without modifying the accepted source's service registration.
The Mac VM is the primary
acceptance platform. Physical multi-display execution remains separate from
synthetic discovery coverage. Raw evidence and reviewer metadata stay private.
Review uses the requested independently configured agent through YepAnywhere.
Independent read-only Claude Opus 5.5 high reviews covered the implementation,
harness, final evidence and corpus. The reviewer did not control the test
target. Session, account-pool and deployment metadata remain private.

## Ordered work

### 1 — preserve arming across covered failures

Separate consent invalidation from transient grant/session failure. Fence
unsafe desktop dispatch, preserve permitted locked browser use, and make root
recovery depend on fresh same-console lock/health evidence. Exercise discovery
failures and multiple-window metadata without secrets.

### 2 — recover browser control despite a stalled page

Introduce bounded per-tab request ownership and an independent recovery path.
Fence canceled and stale continuations, bound indicators and detach, expose
dialogs, and distinguish unknown dispatched effects from refused queued work.

### 3 — qualify the signed Mac application

Extend existing acceptance with composed locked-use and browser faults. Run
doctor, acquire/renew an exclusive claim, use Chrome for Testing, verify
independent effects and safety, and restore state in finally cleanup. Review
each slice and final evidence, then reconcile the gap and owning corpus.

Use read-only generation refreshes within the status observation budget;
startup can hold the main queue for twelve seconds. Never replay an action.
Root-only evidence uses narrow broker-message predicates and a precomputed
line set, keeping collection bounded after the independent lock measurement.
Compare OS crash-report basenames across active and Retired directories, and
repeat the user/root/helper check after an eight-second settle before restoring
the original app. These are development-assembly tests, ineligible as release
acceptance evidence.

## Validation and final result

**Current (2026-10-25), unreleased:** the final signed ARM64 development
assembly passes the composed campaign in an exclusively claimed, disposable
COW Mac workspace. macOS 26.6.2, SIP disabled, one awake display and Chrome for
Testing 155 qualify this route. Extension 0.8.1 is bundled. The successful
result's executable and native-framework hashes match the frozen candidate;
raw evidence remains private.

| Surface | Result |
| --- | --- |
| Consent and native regression tests | 253 Swift tests pass; includes operational retention, multi-window discovery, late guardian startup, root liveness and restoration before the root fault marker |
| Root policy and protocol | Native quiet/fault recovery, bounded socket inbox, completion/EOF ordering and console-lock identity checks pass |
| Portable and native checks | Repository portable checks and Mac native static checks pass; optimized ARM64 signed app and Intel build pass |
| Shared Windows transport | Format verification, contract tests and self-contained ARM64/x64 publishes pass; follow-up ARM64 source-native browser smoke passes ten checks |
| Shared Linux transport | Focused relay deadline/cancellation tests and portable checks pass; follow-up ARM64 GNOME Wayland browser smoke passes ten checks |
| Composed signed Mac campaign | 81 checks pass, three download/upload cycles, two planned app restarts, native Settings/Permissions/Stop, file-panel cancellation/overwrite and independent HTTP/native fixture effects |
| Locked browser recovery | Observed beforeunload handling preserves its recoverable attachment; release, stale IDs, queued refusal, dispatched uncertainty and unrelated-tab progress pass under unchanged until-stopped consent |
| Covered faults | Late pre-arm cancellation, repeated guardian death, guardian stall, root stall and armed resident death pass; browser remains independent and desktop dispatch remains refused during protected recovery |
| Root-only relock | Both resident and guardian SIGSTOP: lock observed 4.858 seconds after injection, 0.156 seconds after root fault detection, on CLOCK_MONOTONIC_RAW; new dispatch, child exit and root IOKit readback logs agree |
| Guardian stall | Lock observed 5.225 seconds after injection, 0.325 seconds after root fault detection; the resident's 30-second silence fallback cannot account for this cell |
| Recovery and Stop | Fault cooldown grows from 30 to 60 seconds, clean completion resets it, root-resume/restart cooldowns use exact root timestamps, saved consent is unchanged, and native Stop revokes access and independently relocks |
| Crash and capture readback | No new resident/guardian or root-helper OS reports after an eight-second settle; old reports moving to Retired are not new crashes. Private PNG visually shows fixture count/text beneath excluded covers |

The investigation also corrected a provider-placement defect: the private
lock primitive had no observed effect from the system bootstrap within five
seconds, while a console-user GUI-bootstrap probe locked in about 0.10
seconds. Root now launches the pinned, signed, non-setuid lock-only runner in
that original GUI bootstrap. Only root IOKit readback ends cleanup. Historical
composed relock evidence in Tactical 064 did not isolate root independence.

The app, policy, LaunchAgent and operator files were restored inside the
clone. Its helper registration is deliberately not claimed as restored;
the exact workspace receipt was released and the clone discarded. The accepted
source retains its prior native app, standing policy and absent helper and was
returned to its initial suspended power state. Testing required a shutdown and
boot, so its original suspended memory image was not preserved. All task-owned
claims were released. The canonical owner-only credential remained ready and
unchanged. No workstation installation or publication occurred.

Physical multiple-display execution, SIP-enabled fault recovery, Intel live
execution, other OS/browser versions and Chrome Web Store/mixed-version rollout
remain separate. Startup's bounded main-queue wait remains documented in the
locked-use guide. This development assembly is not a clean-source release
acceptance receipt.

## Cross-platform release smoke

**Current (2026-10-25), unreleased:** the requested small Windows/Linux check
found a Windows integration omission: `browser.dialog` was advertised but had
no `DesktopGrants.ScopeFor` mapping. The retained control channel refused it
before dispatch. Map it to the existing browser scope, matching Linux and Mac;
raw CDP remains DevTools-only. Contracts now require every advertised browser
operation to have a scope and explicitly permit typed dialogs under a browser
grant. Format verification and both Windows architecture publishes pass.

The [short native relay fixture](../../tests/browser/README.md) passes ten
checks on Windows 11 ARM64 with x64-emulated Chrome for Testing 155 and ten on
Ubuntu 24.04 GNOME 46 Wayland ARM64 with native Chrome for Testing 156. Both
exercise extension 0.8.1, independent HTTP click and hashed PNG effects,
observed dialog handling, dispatched timeout uncertainty, confirmed release
and fresh evaluation, and Stop. Windows proves control-status responsiveness
during a pending action; its owner channel intentionally serializes actions.
Linux separately proves browser discovery progresses during stalled work.

These are source-native fixtures using inherited operator arming, not signed
installed Settings or protected-desktop acceptance. Linux's empty browser
fixture explicitly disables its namespace sandbox without changing OS policy.
The independent Opus review accepts the scope repair and fixture contracts.
Fixture startup failures were corrected rather than counted as native passes.
Original native registration is restored, owned processes and staging are
removed, both initially-off VMs are routinely shut down, and claims released.
The interrupted initial hypervisor operation retains unknown journal coverage;
its journal closes without inventing that missing result. Raw evidence stays
private. No release is dispatched by this smoke campaign.
