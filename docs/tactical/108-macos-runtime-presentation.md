# 108 — Mac runtime and presentation acceptance

Status: completed bounded Mac slice.
Owning topic: [runtime and presentation](../../topics/runtime-and-presentation.md).
Parent: [107](107-runtime-and-presentation.md).

## Objective and completion conditions

Deliver the Mac portion of the shared-runtime migration in one existing app.
Personal, minimal and appliance startup, lazy Settings, native approval/notice,
Stop, recovery and saved/temporary configuration must preserve authority.
Prove deterministic failure cases locally, then actual signed installation and
independent fixture effects in a claimed dedicated VM. Finish with bounded
host observations, coherent commits and restoration.

## Boundaries

No public release or host installation replacement. Keep trusted deployment
policy separate; any VM policy used for a candidate is saved and restored.
The standing observer remains independent. No outer VM input, TCC database
edits, secret exposure, privilege expansion or browser-profile takeover.
Windows/Linux native integration and full protected-session recertification
remain separate acceptance campaigns; existing Mac safety fixtures must pass.

## Ordered work

### 1 — isolate runtime waits and native effects

Use bounded background observations and one serial provider slot with private
references/leases. Recheck live authority after preflight, fence cancellation
before cleanup and retain delivery/effect uncertainty for late results. Test
stalled dependencies, expiry, slow readers and worker/backlog bounds.

### 2 — make native safety presentation independent

Reuse one lifecycle/operator boundary. Create/destroy Settings on demand.
Use native approval, notice and Stop with no settings WebView. Inspect actual
WebView count and same-runtime identity across second launch and close/reopen.

### 3 — implement configuration and recovery

Use a versioned owner-only atomic preference beside the socket, personal
fallback, supported local CLI/reset and temporary launch override. Defer live
changes while approval is pending. Keep grants, protected setup and policy
unchanged. Test malformed configuration, unsafe paths and standing-policy Stop.

### 4 — qualify the signed Mac package

Build/sign the exact candidate and verify nested code. Use the independent
standing observer to drive native approvals and deterministic AppKit effects.
Exercise each profile, packaged/local and outside callers, capture/artifacts,
Pause/Stop, settings recovery, restart and update exclusion. Distinguish signed
local installation from notarization or public updater publication. Run bounded
host diagnostics with an isolated socket and restore the original host state.

## Validation and result

Runtime source candidate: `72a2eef`, unreleased development version `0.3.0`.
Evidence date: 2026-10-11. Validation metadata below does not promote a public
package or change the installed host application.

### Deterministic and build evidence

- All 161 Swift tests pass: stalled helper/session observations, main-queue
  Stop, snapshot expiry, late-result refusal, provider cancellation and reply
  bounds, configuration safety and literal Unicode after shortcut modifiers.
- All 9 Rust tests pass, with clippy warnings denied: bounded operator queue,
  update exclusion, endpoint-specific Settings forwarding and restart args.
- All 234 portable client tests and 9 browser source tests pass; the frontend
  builds. Mac static smoke passes, including 500 session-probe resource cases.
- ARM64 and Intel Mac app bundles build and are locally Developer ID signed;
  strict nested signature verification passes. Intel GUI execution is absent.

### Bounded physical host evidence

The exact ARM64 candidate ran on an isolated endpoint with no access grant,
a saved appliance preference and a temporary minimal launch. Settings opened
in 127 ms during a status query. The main-thread sample showed the ordinary
AppKit/CF event loop, without the previously observed helper/socket wait.
Installed executable, helper configuration, root policy and canonical
presentation fingerprints remained unchanged. The candidate terminated, focus
was restored and the host claim released. This is read-only/UI responsiveness
evidence; no physical control or protected-session qualification is inferred.

### Signed VM qualification and restoration

**Current, `conformance-tested`, signed ARM64 Tart candidate:** all three
profiles pass healthy trusted workstation-policy loading at startup and
restart. Native denial/view-only/full approval, deferred preference edits,
actual WebView create/destroy, second-launch same-runtime recovery, live
selector/reset, Pause/Resume, notice without Settings, Stop, self/protected
refusal, local/outside independent AppKit effects, PNG bytes and native
keyboard/text/pointer effects pass. Restart retains TCC, restores no grant and
rejects old references. The one-launch override expires without changing the
saved preference. Update discovery and disabled installation during active
access pass; no production update was installed.

Minimal also passes the 21-check Chrome for Testing 154 corpus with Settings
absent and native browser/DevTools approval: independent page/icon changes,
packaged CLI PNG retrieval, marker lifecycle, worker restart and native-host
reconnect. This is the existing indicator/browser corpus, not a YA model probe
or browser-root streaming qualification. The separately provisioned standing
policy passes independent effect, Stop/Resume, stale-reference refusal and
reset to personal presentation without changing policy.

A persistent staged candidate and temporary LaunchAgent also pass an actual
normal shutdown/cold startup: saved appliance presentation has zero Settings
WebViews, signed permissions stay ready, a native action changes the independent
fixture once and explicit Settings recovery stays in the same runtime.

The original installed resident and trusted standing policy are healthy after
cleanup, helper configuration remains absent as before, temporary launch
registration and staged processes/files are removed, the fixture is stopped,
and the VM is returned to its original powered-off state. The VM and host claims
are released; the canonical controller-local login credential remains ready and
unchanged. Restoration is subject to the backup-loss limit below. Exact private
paths, credentials, samples, logs and captures stay outside Git.

### Findings and limits

Live qualification required fixes for last-Settings-window exit, split runtime
generations, endpoint-specific recovery, temporary override replay on Restart,
and inherited shortcut flags on literal text. The latter reproduced through
the independent original observer and was a pre-existing native input defect.

The harness now binds the actual Settings close button rather than the first
AX window (which can be a tray help tag), reads native static-text values,
uses the canonical executable path required by the updater and clears fixture
state through its Reset control. Bundled Python uses `-B`; deployment replaces
only the owned staged app cleanly before verifying its sealed resources.

The initial temporary workstation-policy copy retained non-root ownership.
The runtime correctly diagnosed it and used approval-required fallback.
Root ownership was repaired; minimal and personal were repeated with strict
healthy trusted-file assertions, including a second browser run. Appliance
and standing-policy runs also assert healthy loading. Fallback runs remain
separate evidence.

The extra cold-boot driver initially staged its app and restoration backups in
`/tmp`, which macOS cleared on startup. The original installed app and already
restored root policy survived. The original LaunchAgent was regenerated from
the installed bundle's template through the supported user installer; the
originally absent presentation preference was removed. Existing delegated
caller identity/scopes were retained with delegation suspended and no saved
operator consent. The lost preference backup prevents claiming byte-for-byte
restoration of its original contents. The recovered baseline was then backed
up on both controller and persistent guest storage; the repeated cold-boot
trial passed and cleanup verified that baseline. This was a test-driver error,
not evidence of product configuration loss across boot.

The Mac common adapter does not support `target reboot`; its shutdown
`sudo -v` preflight also refused despite passwordless command authorization.
Normal guest administration through `sudo -n shutdown` worked; independent
power readback established shutdown before common lifecycle startup. No
password, permission change, force-stop or outer input was used. These adapter
gaps are recorded rather than folded into the runtime refactor.

The original helper latency and exact displayed error remain unexplained.
Explicit protected setup/resume and update installation retain their native
lifecycle paths, including some synchronous calls; this work does not prove
that every OS call is nonblocking. Already dispatched native calls cannot
always be interrupted. Existing protected safety fixtures pass, but full
protected/hardware/lock-session recertification is outside this slice.
No notarization, public release, production replacement, Intel GUI execution
or Windows/Linux native qualification was performed. Same-user operator and
configuration surfaces do not contain an agent with a same-user shell.
