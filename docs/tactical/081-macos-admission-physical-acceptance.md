# Mac admission presentation and consent acceptance

Status: completed for the bounded unlocked physical Mac profile. Protected
resumption and wider platform/distribution acceptance remain separate.

Owning topics: [access admission and pause](../../topics/access-admission-and-pause.md)
and [Mac locked use](../../topics/macos-locked-use.md).

## Objective

Qualify the unlocked physical Mac admission surface without disturbing the
operator's browser or expanding existing OS permissions. Preserve consent and
manual pause through restart, make Stop durable, and end current control cleanly
when the application quits through its ordinary menu.

## Completion conditions and boundaries

- Countdown presentation preserves an independently observed fixture's keyboard
  focus; one accepted native action changes an independent counter exactly once.
- Two connection owners serialize. Manual pause fences both while preserving
  the existing until-stopped consent. Resume clears only its operator reasons.
- Restart restores fresh ordinary authority and manual pause, never old owners
  or queue positions. Stop survives subsequent restart.
- Standard application-menu Quit closes live ownership and performs native
  cleanup before termination. Existing helper consent stays healthy across an
  exact signed candidate update without another Repair or OS approval.
- This slice does not qualify physical takeover, locked quiet resumption,
  closed-lid/sleep, fresh login, Windows native behavior, or distribution.

## Ordered work

### 1 — make the native fixture an independent focus oracle

Report application activation, key-window state and field focus from the
fixture's event loop, independently of action delivery. Refresh those facts even
when text and counters remain unchanged. Require a valid baseline before any
notice, rather than interpreting an old observation as focus loss.

Add the opt-in [live runner](../../tests/macos/admission-live.py), using a
caller-selected private registry, existing exclusive claim, isolated fixture,
bounded waiting and connection cleanup. It neither arms access nor changes
permissions. Pause acceptance uses the native operator surface.

### 2 — qualify the physical presentation and consent lifecycle

Freeze and sign an isolated candidate. Stop the prior resident before replacing
its bundle; retain a rollback copy. Verify existing helper readiness. Enable
only the previously authorized scopes and duration.

Exercise two owners, countdown focus, one AX effect, indefinite operator pause,
normal restart, composed Resume and durable Stop. Preserve private raw evidence
outside the public repository; publish only minimized outcomes.

### 3 — finish native application shutdown

Cover both Tauri exit requests and AppKit's native termination notification,
because standard application-menu termination can bypass the tray's handler.
End volatile grants/control using the existing clean operator-quit path. Allow
background launch on Mac and avoid raising an existing window for that request.

## Validation and result

**Current:** the ARM64 physical unlocked-screen trial observed a nonactivating
countdown with unchanged fixture application/key/field focus. A native AX press
produced an independent counter delta of one. A second owner waited; Pause until
Resume put both owners in manual pause without changing until-stopped consent.
Normal restart preserved that consent and pause and discarded both owners.
Resume cleared manual pause while recent physical activity remained composed.
Stop left access off after a subsequent restart.

The signed update retained a healthy existing privileged helper without a
Repair click or new OS permission. The initial focus-check failure was an
obsolete fixture observation; the repeated trial required a fresh baseline.
The UI automation binding also had to be refreshed after process replacement;
the native Resume action worked with the fresh binding.

Swift contract tests, native fixture compilation, Rust checks and the isolated
Mac smoke suite pass. The guest fixture was deployed to an exactly claimed Mac
VM and its doctor remained ready. Detailed raw observations and installation
paths remain private. The final frozen signed candidate recorded native clean
operator-quit cleanup before termination, and its live owner channel closed.
