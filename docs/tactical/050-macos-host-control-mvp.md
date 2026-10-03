# Tactical 050: macOS Host Control MVP

Status: active, 2026-09-30. Steps 1–6 complete; step 7 needs the person at
the development Mac.
Topics: `host-control`, `browser-control`, `macos-resident-control`.

## Objective and completion conditions

The user wants Machine Control to control their own Mac directly, not only
Tart guests, and to feel safe installing it on a main workstation. It should
be off by default and armed on demand or approved per request from a menu bar
application. They also want it to control their local browser, because
assistant-coupled browser extensions did not work from YepAnywhere sessions.
The MVP need not have final security, but it must put enforcement in the
right place so later hardening does not redesign it.

The slice is complete when:

- a Tart guest and the physical host run the same application bundle,
  differing only in the policy file, and existing guest acceptance still passes
  under the `appliance` preset;
- a workstation installation with no policy file refuses every desktop
  operation until a person approves a grant in the menu bar prompt;
- approval, denial, timeout, expiry, Stop, and resident restart behave as
  specified, and a direct socket caller cannot bypass a missing, expired, or
  revoked grant;
- a local agent on the host controls the desktop through `bin/machine-control`
  with the same vocabulary it uses for a Tart guest; and
- the unpacked extension lets that agent list tabs, snapshot, and act in the
  user's running Chrome under a `browser` grant.

## Boundaries and non-goals

- Local callers only. Remote callers of a physical host are later work.
- Click approval only. Touch ID, out-of-band approval, and connection-bound
  grants are later work.
- The `unattended` preset is parsed and unit-tested; acceptance on physical
  hardware is not claimed.
- No unlock, away mode, curtain, presence guard, or closed-lid work. The
  workstation preset registers no protected operation, and the host
  installation installs no root helper.
- Development builds are ad-hoc signed with a pinned designated requirement.
  Developer ID signing, notarization, and Sparkle need release credentials
  that are not on the development machine and belong to a later CI slice.
- Guests keep the existing testbed identity until the shared application is
  proven, then move to it in one step; no guest runs a mixture of the two.
- `SECURITY.md` and the personal-machine support statement change only after
  this slice is proven; until then the host build is a developer preview.
- No Windows work and no Web Store publication.

## Ordered work

### 1 — share the resident package

Move `platforms/macos/guests/macos/ui/macui.swift` into a SwiftPM package with
a core library, the existing `macui` executable, and tests. Split files only
where the grant broker and policy loader need seams; do not refactor
providers. Keep the in-guest build working with Command Line Tools only, and
assemble application bundles with a script rather than an Xcode project.
Record in the step whether `swift build` is available on prepared guests or
whether the guest build must stay `swiftc` over the package sources.

### 2 — add policy and the grant broker

Load the root-owned policy file and fall back to `workstation` as specified in
[`host-control`](../../topics/host-control.md#decisions). Register operations
by operation set. Add the grant broker with `observe`, `control`, and
`browser` scopes; `standing` and `approval` modes; and an approver interface.
Check grants in dispatch before any provider runs. Invalidate grants and
element references on revocation, expiry, restart, and session or desktop
transitions. Report preset, grant mode, and live grant in `status` and
`capabilities`. Keep a bounded in-memory audit ring of operation, scope,
caller peer, and claim ID.

Update `deploy-ui.sh` to write the `appliance` policy with the guest's
existing `sudo` before it installs the new resident, then rerun the macOS
static smoke and a live guest ordinary-control conformance pass.

### 3 — build the menu bar application

Assemble one application bundle that contains the resident, the menu bar UI,
and the browser native host, with a stable bundle identifier used on both
guests and hosts. Under a standing preset the menu shows that access is always
allowed and offers no approval prompt. Follow lid-awake's AppKit status item, login item,
setup/repair, and uninstall patterns. Include:

- guided Accessibility and Screen Recording consent, with status that states
  when consent is missing;
- Off/Active indication, time remaining, scope, and recent actions;
- Stop in the menu and a global hotkey;
- the approval prompt with reason, unverified caller chain, and narrower
  scope and duration choices; and
- refusal of synthetic input while a prompt is visible and of actions targeting
  the application's own windows.

### 4 — add the local host target

Add a local-socket transport and a `host` target kind to the common client and
registry schema, with generic examples only; concrete host inventory stays
private. Add `machine-control host request --scope … --duration … --reason …`
that blocks for a bounded time, and map `approval_required` into the common
result vocabulary. (Implemented as `grant request|status|revoke`, which also
works against guests.) Keep doctor and target-use claims unchanged for the host.
Add a host skill that tells agents to request a grant before control and to
treat denial as final.

### 5 — add the unpacked browser extension

Create an MV3 extension under `providers/chrome-extension/` with a fixed
manifest key, `chrome.debugger`, `chrome.tabs`, and `nativeMessaging`. Add the
native host, a per-user registration command, and the resident's peer
code-identity check for the browser-provider role. Port page-level
accessibility snapshot and node actions from `platforms/chromeos/cdp.py`.
Expose `machine-control browser tabs|navigate|snapshot|click|type|capture`
under the `browser` scope.

### 6 — move guests onto the shared application

Change guest deployment and bootstrap to install the shared bundle with the
`appliance` policy, retire the testbed-identity bundle and LaunchAgent, and
renew Accessibility and Screen Recording consent through the existing guest
consent bootstrap. Update doctor, maintenance audit/repair, and the drive-macvm
skill for the new identity. Re-run guest ordinary-control conformance.

### 7 — prove refusals, then use the host

Write broker unit tests with an injected approver that exists only in the test
target. Cover a missing, malformed, non-root, or writable policy file; each
refusal path; expiry during a request; Stop mid-sequence; restart; direct
socket calls; and self-targeted input. Install the workstation build in a
disposable Tart guest first and have a person approve through guest Screen
Sharing. Then install it on the development host and complete a realistic
desktop and browser task from a local agent under an approved grant.

## Validation

- `python3 bin/check --portable` and `bash platforms/macos/tests/smoke.sh
  --static`.
- Package unit tests, including broker and policy refusal tests.
- Live Tart guest ordinary-control conformance under `appliance`.
- Workstation acceptance in a disposable guest, then on the development host,
  recording refusal and approval evidence without committing private
  screenshots, names, or identifiers.
- `codesign --verify` on assembled bundles; release signing is not claimed.

## Result

Steps 1–6 were completed and committed on 2026-09-30 against the Tart
appliance under an exclusive claim, with outer UI prohibited.

- **Shared package.** The resident is a SwiftPM package. Guests no longer
  compile it: `deploy-ui` builds `Machine Control.app` on the controller for
  the guest architecture, so guests and hosts run identical bundles.
- **Policy and grants.** 31 unit and socket-level tests cover policy trust and
  fallback, operation classes, expiry, revocation, narrowing, prompt-time
  pausing, direct-socket refusal, self-targeting, and the browser relay. Live,
  a missing or user-owned policy file turned the guest into a workstation.
- **Menu bar app.** A workstation instance ran beside the appliance resident.
  Its prompt, Allow, Deny, manual arming, Stop hotkey, revocation, and refusal
  of a click on its own status item behaved as designed. The appliance
  resident could press those controls through Accessibility, confirming the
  documented same-user gap that Touch ID approval is meant to close.
- **Host target.** The `host` target, `machost` adapter, `grant` commands,
  remediation hint, and skill are in place. The adapter's doctor validated in
  the guest; it has not run against a resident on the development Mac.
- **Browser.** Chrome for Testing in the guest loaded the unpacked extension,
  which connected and passed the code-identity check; a Python peer was
  refused. Typing, clicking, navigation, capture, `file:` refusal, and
  revocation were observed. Chrome for Testing showed no debugger info bar.
- **Guest migration.** The old testbed resident granted the new identity
  Accessibility and Screen Recording through the guest's own System Settings,
  then was retired. Doctor was ready, the maintenance audit was healthy, and
  a repeat deploy was a no-op.

Deviations and limits:

- `conformance.sh` stops at raw text input because Cua is absent from this
  guest; the previous build stops at the same step. With that one cell
  removed, the suite passed for both placements.
- The `grant` command replaces the planned `host request` name.
- Development signing is ad-hoc with an identifier-only requirement, so any
  ad-hoc app claiming `org.machine-control.app` would satisfy the macOS
  consent and browser-provider checks. Release signing remains open.
- The controller's private registry sets `includeDefaults: false`, so it must
  list `host` before the default host target is selectable there.

Step 7 remains: install on the development Mac with `install-user.sh`, have
the person grant Accessibility and Screen Recording and approve the login
item, register and load the extension in their Chrome, then complete a
realistic desktop and browser task from a local agent under an approved grant.
