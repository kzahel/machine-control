# macOS screen-lock investigation

Historical investigation: [Tactical 034](../../../docs/tactical/034-macos-session-state-and-unlock.md)
subsequently implemented the shared lock observer, input guards, and explicit
resident unlock provider. Statements below describe the investigated revision,
not the current resident's reporting behavior.

Status: **Current**, bounded native-provider `live-tested` evidence from
2026-09-10. This is an investigation, not protected-plane acceptance.
Source reviewed: Machine Control `bc29dae`.

Follow-up: [Tactical 032](../../../docs/tactical/032-macos-authorization-unlock-investigation.md)
records a separate disposable-VM prototype that achieved password-free unlock
through an owned authorization plug-in. The ordinary-resident findings below
remain unchanged; screen covering was explicitly deferred for that prototype.
[Tactical 033](../../../docs/tactical/033-macos-sip-authorization-unlock.md)
subsequently proved the plug-in with SIP, authenticated-root protection, and
Gatekeeper enabled, using normal guest consent and no outer desktop control.

## Scope and method

The user requested a VM experiment to understand a Mac controlling its own
locked session, with an explicitly disposable account credential retained for
handoff. The selected Tart guest ran macOS 26.6.2 (25G83), with native
Accessibility and Screen Recording consent, SIP disabled, FileVault off,
and passwordless test-appliance sudo. Cua was unavailable in this session;
previous Cua acceptance does not imply its presence on every configured VM.
No Codex authorization plug-in was installed or tested in the guest.

Read-only doctor resolved the target, then an exclusive common-CLI claim
covered lifecycle, administration, and resident operations. Outer UI remained
prohibited. The experiment resumed the suspended guest, deployed the existing
AppKit fixture, and compared unlocked, locked with an active display, locked
with no active display, and unlocked-again observations. Local CLI and outside
callers reached the same resident. No worker agent was required in the guest.
The host frontmost application was unchanged, but its cursor position changed
between the before/after samples. Outer UI was prohibited and never invoked;
the endpoint samples alone do not prove zero host interference during the
whole interval, so this run is not labeled conformance-tested.

Independent observations used the guest's `IOConsoleLocked` value, fixture
file oracle, process and file operations, and visually inspected guest-created
captures. `IOConsoleLocked` is an observed OS signal, not a newly adopted
cross-version lock API contract. The existing public dummy password was
verified once and retained in a private machine manifest linked from ignored
local configuration. No password or account-policy change was needed.

## Results

| Operation | Observed while locked |
| --- | --- |
| Guest commands, file write/read/delete, and sudo | Continued working. The test administrator still obtained UID 0. |
| Resident and local/outside CLI | Remained reachable with the same process and generation. Both placements reproduced the missing fixture button. |
| Application inventory and launch | Inventory remained available; TextEdit launched as a new process. Launch is not proof of usable foreground UI. |
| Fixture window inventory | Still returned the window, including `onScreen: true`, although the lock screen covered it. |
| Fixture AX inspection | A filtered Increment query returned an accepted empty result. A full bounded tree retained application/menu remnants, but no usable fixture window controls. |
| Previously acquired fixture AX reference | Press failed with `delivery_failed`, AX error `-25202`; the fixture counter did not change. There was no explicit lock-transition invalidation. |
| Full-display capture, active display | Returned the login/lock screen. |
| Exact fixture-window capture | Still returned readable fixture pixels underneath the lock screen. This proves retained visibility, not continuous rendering freshness. |
| Targeted keyboard input, active display | A key requested for the fixture instead appeared as a masked character in the login password field. The fixture recorded no key or text change. |
| Targeted pointer input, active display | Accepted with delivery confirmed, but the fixture's counter and event oracle did not change. The coordinates addressed the lock screen covering the fixture. |
| Loginwindow AX | Exposed the login window, focused-user description, and password-field identifier. Visibility alone is not a complete credential-provider contract. |
| Normal account unlock | One correct dummy-password submission using guest-native key events unlocked the session, independently confirmed by the OS signal. No host-window input or authentication plug-in was involved. |
| After unlock | A fresh fixture AX press changed its counter, and a keyboard event changed its text and key-event oracle. The resident did not restart. |

An exploratory TextEdit AppleScript request timed out without a pre-lock
AppleScript baseline. It is inconclusive and is not evidence that all
application scripting stops under lock. The owned application was cleaned up.

### Display availability is a separate axis

During the locked interval, the provider later reported no active main display.
Full-display capture returned `display_not_found`, and coordinate input was
refused because no active display contained the point. Guest administration
and the resident continued responding. A bounded guest `caffeinate -dimu`
assertion restored capture of the lock screen while `IOConsoleLocked` remained
true. No persistent power settings were changed.

Do not equate this display-off observation with full system sleep. Nor should
an image returned for an individual window imply that the display is active,
the application is interactable, or the image is freshly rendered.

## Confirmed contract gaps

The checked-in resident hard-codes `desktopState: unlocked`. Doctor infers
`unlocked` from ownership of `/dev/console`, then derives input readiness from
semantic permission state. The console remained owned by the logged-in user
through screen lock, so doctor returned `ready: true` and unlocked/ready
capabilities while fixture semantics and input were unusable.

The native input path attempts application activation, ignores that result,
and posts global HID events. Under lock the password field received a key
whose request named an ordinary application. Its result still reported
`focusConsequence: target_application_activated`. The effect was correctly
left unverifiable, but the claimed target/focus consequence was misleading.

These observations require separate lock/session state, display availability,
permission, route readiness, and target-effect reporting. Application-targeted
global input needs a fail-closed check before posting when the target cannot
own the intended desktop. An explicitly selected login operation needs its
own typed authority and credential channel. References and authorization
leases also need a session/desktop transition boundary in addition to resident
process generation. This investigation does not implement those changes.

## What transfers to a physical Mac

**Inference:** A logged-in resident using the same macOS APIs can remain alive
under lock while ordinary application interaction degrades. The local/outside
parity result supports treating transport as independent of that OS boundary.
It does not establish a personal-Mac security profile: this guest had SIP
disabled, existing TCC grants, no FileVault, and appliance-level administration.

**Open:** Repeat on SIP-enabled physical hardware, with display sleep and
full system sleep measured separately. Also test fresh login, logout, fast
user switching, multiple displays, FileVault preboot, and provider-specific
background input/capture. A suspended VM is not evidence about physical
sleep/wake or a MacBook with its lid closed. No physical host was locked in
this investigation.

### Codex Computer Use comparison

**Upstream-claimed:** OpenAI documents an opt-in macOS “Locked use” mode that
installs an Apple authorization plug-in. A trusted active Computer Use turn
can temporarily unlock the session while covering every display and blocking
local use; local keyboard or pointer activity triggers relock and pauses
automatic unlock until manual unlock. This is a dedicated integration, not a
promise that ordinary AX/global input works through lock, and not a general
unlock facility available to Machine Control.

Sources: [OpenAI Computer Use, Locked use](https://learn.chatgpt.com/docs/computer-use#locked-use)
and [Apple authorization plug-ins](https://developer.apple.com/documentation/security/extending-authorization-services-with-plug-ins).
The feature was documentation-reviewed, not exercised in this VM.

## Evidence handling and restoration

Raw requests, responses, screenshots, and private identity observations stay
outside the public checkout. This report contains only portable findings.
The dummy credential is retained in the controller-local machine manifest;
ignored configuration records its locator for the next operator. The fixture
application installation was retained, its test process and the newly launched
TextEdit were closed, transient captures and the bounded wake assertion were
removed, and the guest was returned to suspension before releasing the claim.
