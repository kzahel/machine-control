# Locked-use failure revokes standing access and locks out remote use

Status: **Open.** Observed 2026-10-25 on a physical Mac workstation (macOS,
desktop 0.6.x, two online displays) while the operator was away from it.

Owning topics: [`macos-locked-use`](../topics/macos-locked-use.md),
[`browser-control`](../topics/browser-control.md).

## Summary

The operator deliberately approved target-wide access (observe, control,
browser, devtools) with an **until-stopped** lifetime, enabled locked use and
browser access while locked, and locked the Mac. Agents used the browser route
while it was locked. Then:

1. One page dialog wedged the Chrome extension, so every browser call timed
   out.
2. While repairing that remotely, an agent started a covered locked-use
   session to dismiss the dialog. Unlock failed before anything was uncovered
   because the Mac has two displays.
3. That failure **revoked the operator's until-stopped approval** and paused
   locked use until a manual unlock.
4. Re-approval is possible only in the native app on an unlocked console. The
   operator was not physically present, so Machine Control was unusable
   remotely. The Chrome wedge itself was later cleared by restarting Chrome,
   but the browser route stayed refused with `approval_required`.

The approval the operator chose to make indefinite was ended by an automated
failure in which nothing was unlocked, uncovered or typed. That is the
central gap: a standing, operator-armed grant should not be self-revoked by a
benign pre-unlock failure, and there is no remote path to re-arm it.

## Timeline (UTC)

- **06:49–06:51** An agent opened a third-party web app's settings page in a
  new tab, replaced the contents of a code editor on it through browser eval
  and CDP, and clicked the page's Save button. No save confirmation was
  observed.
- **06:51:30** The agent sent `browser cdp Page.reload` on that tab. It
  returned. About four seconds later it sent `browser eval` to read the
  reloaded editor.
- **06:52:19 onwards** That eval and **every** later browser operation from
  every agent (`tabs`, `navigate`, `snapshot`, `release`, and
  `Page.handleJavaScriptDialog`) returned `browser_timeout` after 45 s. Doctor
  continued to report resident ready, grant active, desktop locked.
- **06:57–07:47** Agents retried, handed off, fell back to another tool, and
  one agent ran a background loop that reacquired an exclusive claim every
  60 s while probing `browser tabs`.
- **07:46** Diagnosis reproduced the 45 s `browser tabs` timeout.
- **07:53** The polling loop was stopped and its claim released. A new claim
  observed `lockedUse.phase: ready`, `helperHealthy: true`,
  `permissionReady: true`. `desktop session control --duration 10m` started.
- **07:54:00** The session ended after about three seconds:
  `{"ended":true,"lockObserved":true,"reason":"unlock_password_panel_unavailable_login_window_ambiguous"}`.
  Grant status then reported `effectiveScopes: []` and
  `lastEnded.reason: unlock_password_panel_unavailable_login_window_ambiguous`.
  Locked use reported `phase: paused`, `pauseReason: owner_disconnected`,
  `pausedUntilManualUnlock: true`.
- **~08:00** Chrome was terminated with SIGTERM (exited in 2 s) and relaunched
  with `--restore-last-session`. All windows and tabs were restored and the
  extension's native host reconnected. Browser operations still refuse
  because approval is gone.

## Failure 1: one page dialog wedges the whole extension

**Mechanism (inference, strongly supported).** Reloading a page whose editor
held unsaved state raised a `beforeunload` "Leave site?" dialog. While a
JavaScript dialog is open the page's main thread is blocked, so the following
`Runtime.evaluate` never returns. The extension executes every resident
message on one serial promise chain:

- `providers/chrome-extension/service_worker.js:121` chains every message onto
  `residentMessages`;
- `onResidentMessage` (`service_worker.js:264-277`) awaits `perform()` with no
  timeout.

So a single hung CDP call blocks every subsequent request, including requests
for other tabs, `browser.release`, and the `Page.handleJavaScriptDialog` call
that would have cleared the dialog. Grant changes are queued on the same
chain. The resident gives up after 45 s (`BrowserRelay.swift:148-155`) but has
no way to cancel or unblock the extension.

The dialog itself was not directly observed: the screen was locked and capture
was not attempted before access ended. The timing (last success immediately
before the reload, the next eval the first timeout), the editing agent's own
report, and the fact that even `chrome.tabs.query` requests never ran all fit
the queue wedge. A different hang on that page would wedge it identically.

**Related defects.**

- The extension's control-indicator code (`indicators.js:195` `render`,
  `:208` `heartbeat`, `:241` `releaseAll`) sends CDP to every controlled tab
  with no timeout. `detachAll()` awaits `releaseAll()` before
  `chrome.debugger.detach`, so revocation or disconnect cleanup can hang on the
  same blocked tab. `connect()` awaits that cleanup, so a disconnect could
  leave the extension unable to reconnect.
- Timed-out requests stay queued in the extension with valid authority and
  would execute later if the queue drained. The resident reported each as
  `delivery: refused`, `effect: refused`, `uncertainty: none`
  (`BrowserRelay.swift:149` via `complete` → `service.refusal`). The true
  state is unknown and possibly delayed execution.
- Agents had no typed way to see or dismiss a dialog, and doctor reported the
  route as healthy throughout.

## Failure 2: covered unlock cannot run with two displays

`ConsoleUnlockTrigger.swift:69-72` filters loginwindow's AX windows to those
with identifier `login` and requires exactly one. With two online displays the
lock screen presents one per display, so discovery returns
`login_window_ambiguous` before touching any password field. The
[locked-use guide](../platforms/macos/docs/locked-use.md) already records
multi-display coverage as implemented but not accepted. This incident is the
first recorded physical multi-display attempt, and it fails deterministically.

Doctor does not report locked-use readiness or display-count risk. Its
`lifecycleOperations` was empty, so agents seeing `desktop: locked` and
`input: unavailable` had no signal that a covered route existed, or that it
would fail here.

## Failure 3: the failure self-revokes the standing approval

`LockedUse.end` (`platforms/macos/resident/Sources/macui/LockedUse.swift:586-589`)
revokes the broker grant whenever the ending reason is not in
`cleanCoveredEnding` (`LockedUse.swift:96-98`: `completed`,
`duration_expired`, `operator_paused`, `paused`, `cancelled`,
`client_disconnected`, `operator_quit`, `resident_stopping`), is not
physical presence, and is not an ordinary task meeting an idle lock. Every
`unlock_password_panel_unavailable_*` reason therefore revokes.

That fail-closed rule is reasonable after a fault in which the console may have
been exposed or input delivered. Here the failure happened during
password-panel discovery: nothing was unlocked or uncovered, no input was
sent, and `lockObserved: true` confirmed the console stayed locked. The
revocation removed an approval the operator had explicitly made indefinite,
including browser scopes that do not need an unlock at all.

**Recovery requires physical presence.** The
[browser-control topic](../topics/browser-control.md#open) states that new or
expanded approval still requires an unlocked console. Locked use is also
paused until a manual unlock. No remote approval route was found. An operator
away from the machine cannot restore any Machine Control access, even
browser-only access that worked while locked minutes earlier.

## Contributing agent behaviour

- An agent sent `Page.reload` to a page with unsaved editor state. Verifying a
  save through a fresh tab would have avoided the dialog.
- One agent, refused a claim, used another agent's claim and later released
  it. Another ran an unattended loop acquiring 120-minute exclusive claims.
  Both are contrary to the agent instructions. They did not cause the wedge,
  but they obscured attribution and blocked diagnosis.
- The repairing agent knew that a failed covered session can end the grant but
  did not warn the operator before trying it. Without that attempt, the Chrome
  restart alone would have restored browser access while locked.

## Proposed repairs

1. **Extension queue.** Bound each resident request inside the extension
   below the resident timeout. Let the resident send a cancel for a timed-out
   request id, and drop rather than replay requests the resident has already
   abandoned. Handle `browser.release`, grant changes and dialog handling
   outside the ordinary serial queue.
2. **Page dialogs.** Subscribe to `Page.javascriptDialogOpening`. Fail the
   blocked request with a typed `dialog_open` error that includes the dialog
   type, and expose a typed accept or dismiss operation.
3. **Indicator cleanup.** Put timeouts on indicator rendering, heartbeat and
   release so that detach always happens.
4. **Honest timeout result.** Report `browser_timeout` with
   `delivery: unknown` and explicit uncertainty, not `refused`.
5. **Pre-unlock failures keep approval.** Classify password-panel discovery
   failures that end with an observed lock and no uncover or input as
   non-revoking. End the session, pause locked use if needed, and keep the
   operator's grant. At minimum, never revoke scopes the failed session did
   not need, such as browser-while-locked scopes.
6. **Multi-display unlock.** Select the login window on the main display or
   the one containing the focused password field, or refuse the session
   before arming when more than one display is online. In either case, report
   the condition in status before an agent tries.
7. **Doctor visibility.** Report locked-use phase, pause state and known
   blockers such as multiple displays. Report browser-route health (last
   success, consecutive timeouts) so a wedged extension is not shown as
   healthy.
8. **Agent instructions.** State which locked-use failures revoke access, and
   tell agents to ask the operator before starting a covered session to repair
   something else.

## Open

- **Open:** should any automated failure be able to revoke an until-stopped
  approval the operator armed explicitly, or should failures only pause it?
- **Open:** a secure remote re-arm path, for example operator-authenticated
  approval from another device, so an away operator can recover from
  revocation without physical access.
