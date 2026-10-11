# 108 — Mac runtime and presentation acceptance

Status: active.
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

**Current:** Source checks include Swift runtime/configuration/safety tests,
Rust queue/update/restart tests, frontend compilation, portable client tests
and the native Mac static smoke. Signed VM and bounded host acceptance are in
progress. Exact private paths, credentials and captures remain outside Git.
