# Desktop control reliability and saved access choices

Owning topics: [host control](../../topics/host-control.md),
[Mac locked use](../../topics/macos-locked-use.md),
[Mac resident control](../../topics/macos-resident-control.md),
[access admission and pause](../../topics/access-admission-and-pause.md),
[desktop diagnostics](../../topics/desktop-audit-and-diagnostics.md).

Status: **complete** for the shared preference repair and documented Mac VM
implementation/qualification scope. Child tacticals own execution and remaining
physical/real-use evidence limits. No release or primary-host replacement.

## Objective

Make ordinary authorized desktop tasks reliable without repeated manual mouse
checks, settings re-entry, or control-session cycling. Separate five concerns
so each can be implemented and reviewed independently: saved choices,
guardian failures, input/observation consistency, automated acceptance, and
control-owner duration.

The motivating reports describe different symptoms, not one established root
cause. The [covered-control gap record](../../gaps/2026-10-29-covered-observations-and-duration.md)
owns the sanitized observations and existing source findings. The
[Mac platform report](../../research/platforms/macos.md) owns platform evidence;
[Tactical 138](138-remote-arming-recovery.md) owns the earlier bounded repair
campaign. Their results do not establish that the current failures are fixed.

## Completion conditions

- Last-selected scopes and duration survive Settings recreation and app
  restart. Remembered choices, effective grants, and control owners have
  distinct persistence and UI behavior.
- An exact packaged Mac app passes clean quit/relaunch and crash/relaunch
  checks under the documented same-console authorization policy. Stop remains
  off. Logout and reboot behavior is tested and described separately.
- Guardian termination identifies the failed safety condition and the timing
  context without changing fail-closed behavior or retaining UI/secret data.
- Independent application, AX, and rendered-state evidence explains and
  verifies a repair for delayed/absent edits. Uncertain writes are not replayed.
- A repeatable unattended Tart campaign covers normal operation, faults,
  real-duration expiry, restart, and presentation. Physical-only omissions
  remain explicit; a manual takeover cell is not an unattended pass.
- The duration-policy work reaches an explicit decision. If renewable owners
  are selected, all enforcing layers and loss-of-authority paths are qualified
  before claiming long-running task support.

Each workstream can complete separately. The parent remains open until every
condition has a recorded result or an explicit scope decision; a passing
short session is not closure for sustained reliability.

## Boundaries

- Start with macOS and the shared desktop UI. Preserve Windows/Linux policy
  distinctions; remembering choices does not authorize cross-platform grant
  restoration. Broader native ports need their own acceptance.
- Do not weaken lock, cover, takeover, credential, or watchdog protections.
  Preserve explicit Stop and Pause, generation fencing, and task-end cleanup.
- Persisting a UI preference never grants access. Do not restore dead owners,
  pending actions, queue positions, or expired authorization.
- Use owned native/browser fixtures and a separately identified test browser.
  Personal store dashboards are not the regression fixture.
- Use claimed dedicated targets and private evidence. Fresh workspaces follow
  provisioning-journal and credential-handoff rules. Release claims and restore
  owned state in cleanup, recording incomplete recovery honestly.
- No routine host pointer/focus manipulation to drive a VM. Any independent
  outer presentation/input test needs its explicit route authorization and
  non-interference assessment; keep it out of ordinary application control.
- The authorized implementation installs development candidates only inside
  claimed disposable test workspaces. Primary-host app replacement,
  physical-host interruption, release and publication remain outside this work.

## Workstreams

### 1 — remember access choices and restore valid consent

**Current at planning, source-reviewed:** the shared form initialized scopes to observe/
control and duration to 900 seconds. These editable choices are not hydrated
from durable selections. A live grant supplies displayed scopes while active,
so the form reset alone does not explain every reported loss of active access.
Mac consent storage and same-console restoration already exist.

Reproduce Settings close/reopen, clean app quit/relaunch, process death,
Stop/relaunch, timed expiry, logout, and reboot as separate cases. Distinguish
forgotten selections from failed consent restoration and temporarily unavailable
scopes. Include browser/DevTools and indefinite duration, not only desktop
defaults. A temporarily restricted live grant must not overwrite saved choices.

Persist operator choices independently of authority. Restore valid Mac consent
under the existing console/permission policy; make any broader reboot or login
persistence a separate explicit policy decision. Timed access must not restart
its countdown on relaunch. Stopping access should preserve editable choices
while leaving authorization off.

**Done when:** regression evidence checks both the visible controls and native
grant state across the restart matrix, including a subsequent ordinary task.
This work can proceed independently of the covered-control fault investigation.

### 2 — identify and repair guardian failures

Add bounded private diagnostics for console identity matching, lock observation,
cover health, input-guard health, lid state, parent/helper liveness, and the
component ending control. Record monotonic start/deadline/end times, remaining
duration, sample freshness, and transition generations. Use closed subreason
codes; do not retain raw identities, UI contents, or secrets.

Keep the external failure semantics and immediate safety cleanup. Record all
relevant failed predicates when health and expiry coincide so check ordering
does not masquerade as a root cause. Inject each condition deterministically,
then reproduce the live symptom before choosing a repair.

**Done when:** each injected fault has attributable diagnostics and independent
relock evidence; the reported failure has a supported explanation and bounded
regression, or remains explicitly unresolved. Healthy status after a fault and
a short successful retry do not establish a fix.

### 3 — make input and observations agree

Compare an owned native text fixture and an owned browser form outside and
inside covered control. Include form-model change events, save, and full reload;
an AX value write alone does not prove a browser application accepted an edit.
Measure independent input/application events, AX values, rendered frames, and
persisted values after a single known mutation and across clean re-admission.
Bind observations to the current application, owner, and coordinate generation.

Separate delayed input processing, stale AX/presentation, application event
semantics, and caller targeting mistakes. Test hover and pointer delivery as
well as keyboard/text effects. Do not use repeated writes or session cycling
as the success oracle; a duplicate after retry is a failure to investigate.

**Done when:** independent effects and fresh observations agree in repeated
ordinary and covered fixture trials without per-edit owner cycling. If a route
cannot establish an effect, it reports uncertainty rather than success.

### 4 — automate covered-control acceptance in Tart

Extend the existing packaged and covered-recovery runners rather than creating
a parallel control stack. Inventory existing cells and their exact package,
OS, SIP/security profile, display configuration, and execution evidence first.
Tart evidence must not inherit physical coverage or a different image's policy.

The campaign should include:

- Fresh and successive covered tasks with independent native/browser effects,
  synthetic hover, pointer, keyboard, text, and capture checks.
- Independent unfiltered display/compositor evidence that covers conceal the
  application, alongside the agent capture that intentionally excludes covers.
  Self-reported cover counts alone do not qualify visible concealment.
- Completion, disconnect, actual configured-duration expiry, resident/guardian/
  helper failures, recovery, retained consent, and fresh-generation refusal.
- Full-duration active work and waiting, plus rapid clean completion/re-admission
  to expose status races. A five-minute run does not qualify a fifteen-minute
  deadline; any later renewal design needs execution across that boundary.
- Workstream 1's packaged restart matrix and workstreams 2/3's regressions.

Investigate a command-driven independent virtual input route for mouse movement,
keys, and takeover. First verify how the guest classifies its events and that
they exercise the production guard. Spoofing event-origin metadata or calling
an internal interruption function is deterministic coverage, not native HID
conformance. If an independent safe VM route is unavailable, record that gap;
do not turn the existing wait-for-a-person test into an automated-pass claim.

Keep a small separate physical matrix for actual mouse/keyboard takeover,
display configurations, and lid/wake behavior. Automate instrumentation and
result collection there so any human step is precisely bounded. Report gaps
per capability; a VM cannot certify a physical setup it did not exercise.

**Done when:** the supported VM cells run unattended against exact packaged
bytes, produce independent effects and cleanup evidence, and list remaining
physical-only/manual cells. Integrate the relevant cells into the acceptance
gate for releases changing these surfaces; record the execution route honestly.

### 5 — decide and implement long-running control ownership

**Current at planning:** 900 seconds was an enforced owner bound independent
of renewable target claims. [Tactical 144](144-renewable-control-owners.md) now
owns the decision and source implementation for renewable finite ownership
under the original operator-selected authorization lifetime. Its packaged
acceptance passes in the documented VM profile; the tactical owns its limits.

Specify authorization lifetime, owner heartbeat/watchdog, lease renewal, and
task deadline independently. Decide who may extend a live owner, the total
limit and UI wording, idle behavior, pause behavior, and how grant expiry or
revocation wins a renewal race. A surviving SDK heartbeat alone must not grant
unlimited work beyond the selected policy.

If adopted, implement typed owner-bound renewal through every enforcing layer,
including the privileged broker, with observable deadlines. Renew only a live
authorized owner; never silently reopen an ended session or replay an action.
Keep finite failure watchdogs and prompt completion/disconnect cleanup. Do not
substitute claim renewal or a larger client-side constant for this contract.

**Done when:** the policy decision is recorded in the owning topic. Any adopted
implementation has contract tests and exact-package acceptance across multiple
lease intervals, including Stop, Pause, takeover, grant expiry, connection loss,
helper loss, and late-renewal refusal. Longer ownership is not a repair for
workstreams 2 or 3.

## Ordered phases and dependencies

| Phase | Work | Exit criterion |
| --- | --- | --- |
| 1 — establish regressions | Start saved-choice repair and guardian diagnostics independently; inventory and extend the existing VM harness | Reproducible restart cases, attributable fault diagnostics, explicit coverage inventory |
| 2 — repair ordinary covered work | Investigate guardian reliability and input/observation behavior using the growing harness | Independent effects, fresh readback, fault cleanup, and sustained runs; unresolved causes remain visible |
| 3 — settle duration policy | Draft policy can proceed earlier; implement an adopted renewal contract after diagnostics and baseline acceptance exist | Separate clocks and authority semantics, all-layer enforcement, multi-interval acceptance |
| 4 — qualify the packaged result | Compose completed repairs into the exact-package VM gate and the bounded physical matrix | Published coverage and omissions, complete cleanup, and explicit release eligibility |

Workstream 4 supplies infrastructure throughout, rather than waiting until the
end. Saved-choice work need not wait for a duration decision. Keep fixes and
their relevant fixtures in focused changes; do not bundle all five streams into
one runtime patch. Create child tacticals when an implementation slice is
selected, linking back here and using its owning topic's existing trailer.

## Validation and result

Run checks appropriate to each changed surface and record source/build/package
identity. Deterministic tests prove contract cases; claimed live VM tests prove
OS effects; physical cells qualify only their observed configuration. Keep raw
timings, screenshots, and target metadata private and promote minimized results
to the platform report and owning topics.

**Current result:** [142](142-saved-access-choices.md) owns saved choices;
[143](143-covered-control-diagnostics-and-acceptance.md) owns guardian diagnosis,
input/observations and automated acceptance; [144](144-renewable-control-owners.md)
owns the renewal decision and implementation. The exact locally signed
development bundle passes the 200-check VM campaign, 19 browser cycles, five
planned restarts, actual 900-second expiry and 960-second same-owner renewal.
An additional disposable workspace verifies visible Stop/relaunch choices and
actual reboot, including the locked-browser preference, with access off.
Completed common-run receipts verify both claims/workspaces released.

The first reboot recording left an unpaired shutdown-transport intent; its
journal remains honestly failed. One-shot guest launchd submission fixes that
recording path, and a development-only recovery revalidates the completed
campaign before repeating the same archived app's reboot phase. The rerun
finishes ready with zero unpaired commands. Recovery cannot emit a release
receipt; exact clean CI-candidate acceptance remains required before release.

All 268 native tests, portable/native static checks, the pinned headless UI
regression, strict typed-client checks, 87 release/harness tests and ARM64/Intel
builds pass. Physical takeover, lid/wake, multiple displays and SIP-enabled
qualification remain outside the executed VM profile. The original intermittent
physical guardian fault and isolated ordinary shortcut refusal remain open with
diagnostics; the new cover/input regressions do not explain every real-site
symptom. The controller's desktop/application were not operated or replaced.
