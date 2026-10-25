# Desktop changelog

## [Unreleased]

- Preserve operator arming when Mac covered startup or a provider fails.
  End the finite task, fence desktop work and recover from fresh locked,
  healthy and quiet conditions. Explicit Stop, original expiry and console changes still
  invalidate consent. Search multiple login windows without choosing an
  ambiguous password field.
- Repair approved but unreachable Mac helpers after app replacement, allow
  bounded cold signature validation and avoid validating the full app twice.
  Keep a missing admission-status sample from disabling an already admitted
  task; retain live guardian, root watchdog and OS permission checks. Drain
  final completion before judging guardian exit, without reviving expired
  heartbeats or blocking on partial covered frames.
- Run root-driven Mac relock through a pinned lock-only helper in the original
  console's GUI session, with independent lock readback. Refuse covered arming
  when that route is unavailable and end active use on fresh root fault evidence.
- Keep the display awake through the bounded covered-startup handoff with a
  kernel-limited display-only assertion; wait for prior root cleanup before
  admitting the next task.
- Keep browser discovery, dialog handling, release and unrelated tabs
  responsive when page work stalls. Cancel expired queued actions, report
  dispatched uncertainty, and protect new routes from stale callbacks.
- Wait boundedly for native file-panel confirmation readiness after path/name
  entry; a disabled or unknown button remains unpressed.
- Add typed browser dialog inspection/handling and sanitized route recovery
  diagnostics. A missing dialog event is reported as unobserved.
- Accept validated bounded COW workspace estimates in scoped tasks while
  continuing to refuse unknown acquisition outcomes.

## [0.6.9]

- Fix the installed Mac app crashing while choosing a browser download or
  upload location. Read keyboard-layout properties on the main thread while
  keeping file-dialog and accessibility work on the provider worker.
- Show when a previous Mac session ended without a clean shutdown, with
  unfinished-operation context and build identity in diagnostics. Add an
  explicit, reviewed OS crash-report export; ordinary exports still exclude
  those reports and nothing is uploaded automatically.
- Keep bounded diagnostics for thirty days on Mac, Windows and Linux.
  Preserve matching Mac executable and native-framework symbols separately
  from the installers.
- Refuse old browser references and queued actions after access ends or
  changes, including native-host reconnection and app restart.
- Require acceptance of the exact signed Mac package before publication,
  including real downloads/uploads, native file dialogs, Settings, Stop,
  forced-exit recovery and diagnostic export.
- Replace the Windows covered-desktop setup file picker with native local
  account password enrollment and update/removal actions. Enrollment does not
  grant ordinary control; browser access while locked remains independent.
  Full signed enrollment/unlock/relock acceptance is still pending.

Targets all six desktop architectures. Mac ARM64 exact-package acceptance is
required for this release. Intel/physical GUI execution and the new Windows
enrollment lifecycle remain separate from build and signature verification.

## [0.6.8]

- Add the default-off **Allow approved browser access while locked** setting
  on Mac, Windows and GNOME Wayland Linux. Existing browser approvals retain
  their expiry; desktop control and broader approvals remain gated. Pause,
  Stop, expiry and session loss still end or suspend access. Scripts and
  DevTools require their separate approval.
- Add `desktop dialog choose --path PATH` on Mac for native Open/Save panels,
  keyboard-layout and modifier-remapping fixes, reliable empty accessibility
  text values, bounded observation identities and exact certificate
  trust-settings prompt recognition.
- Include the candidate persistent Python MCP session with compact trees,
  capture-bound input, explicit activation and owned claim/session cleanup.
  Improve offline help, claim arguments, queued deadlines and provisioning
  journal error reporting.
- Add secret-free Mac covered-unlock diagnostics. The reported physical-Mac
  password-panel discovery failure remains unresolved.
- Fix Linux release verification to require the new locked-browser runtime
  modules, and include nested extension assets such as icons.
- Fix Windows CI coverage of POSIX-only session publication. Windows keeps
  refusing file-based session IDs pending native ACL validation; explicit
  tool/session-environment identities remain available. Report lease-renewal
  failures correctly when they occur before a scoped child starts. Keep Linux
  preference persistence tests on POSIX and test logon identity with a portable
  fixture UID.

Includes the changes from unpublished 0.6.5 through 0.6.7, targeting all six desktop
platform/architecture packages. Source-native VM acceptance covers locked
browser click/text effects and tab capture on Mac, Windows and Ubuntu GNOME
Wayland, plus Windows streamed per-tab DevTools. Mac keyboard, native identity
and Python-session acceptance retain their bounded fixture coverage. Physical
hardware, sleep, Intel Mac execution, other Linux desktops and signed installed
feature acceptance remain separate. The Linux browser fixture used an empty,
explicitly unsandboxed Chrome for Testing profile.

## [0.6.7]

- Add the default-off **Allow approved browser access while locked** setting
  on Mac, Windows and GNOME Wayland Linux. Existing browser approvals retain
  their expiry; desktop control and broader approvals remain gated. Pause,
  Stop, expiry and session loss still end or suspend access. Scripts and
  DevTools require their separate approval.
- Add `desktop dialog choose --path PATH` on Mac for native Open/Save panels,
  keyboard-layout and modifier-remapping fixes, reliable empty accessibility
  text values, bounded observation identities and exact certificate
  trust-settings prompt recognition.
- Include the candidate persistent Python MCP session with compact trees,
  capture-bound input, explicit activation and owned claim/session cleanup.
  Improve offline help, claim arguments, queued deadlines and provisioning
  journal error reporting.
- Add secret-free Mac covered-unlock diagnostics. The reported physical-Mac
  password-panel discovery failure remains unresolved.
- Fix Linux release verification to require the new locked-browser runtime
  modules, and include nested extension assets such as icons.
- Fix Windows CI coverage of POSIX-only session publication. Windows keeps
  refusing file-based session IDs pending native ACL validation; explicit
  tool/session-environment identities remain available. Report lease-renewal
  failures correctly when they occur before a scoped child starts.

Includes the changes from unpublished 0.6.5 and 0.6.6, targeting all six desktop
platform/architecture packages. Source-native VM acceptance covers locked
browser click/text effects and tab capture on Mac, Windows and Ubuntu GNOME
Wayland, plus Windows streamed per-tab DevTools. Mac keyboard, native identity
and Python-session acceptance retain their bounded fixture coverage. Physical
hardware, sleep, Intel Mac execution, other Linux desktops and signed installed
feature acceptance remain separate. The Linux browser fixture used an empty,
explicitly unsandboxed Chrome for Testing profile.

## [0.6.6]

- Add the default-off **Allow approved browser access while locked** setting
  on Mac, Windows and GNOME Wayland Linux. Approve browser access before
  locking, then continue browser work while the computer stays locked,
  without preparing desktop unlock. Browser scripts and DevTools still
  require their separate approval.
- Preserve the existing approval and its expiry while locked. Desktop
  observation/input and new or broader approvals remain gated. Pause, Stop,
  expiry, disabling the option and session loss still end or suspend access.
- Fix Linux browser setup to include nested extension assets such as icons.
- Allow clearing ordinary Mac accessibility text fields and recognize the
  exact system certificate trust-settings authorization prompt while retaining
  requester, window and one-use credential guards.
- Add secret-free Mac covered-unlock diagnostics for password-panel discovery
  failures. The reported physical-Mac unlock failure remains unresolved.

Targets all six desktop platform/architecture packages. Browser work with the
OS locked passes source-native VM acceptance on Mac, Windows and Ubuntu GNOME
Wayland Linux, including independent click/text effects and tab captures.
Windows also passes per-tab streamed DevTools while locked. These tests cover
an awake, existing console; sleep, physical hardware and other Linux desktops
remain separate qualification. The Linux fixture used an empty, explicitly
unsandboxed Chrome for Testing profile; signed installed Settings and
production-browser acceptance remain separate.

## [0.6.5]

- Add `desktop dialog choose --path PATH` on Mac to choose a location in an
  application's native Open or Save panel. It confirms only after the panel
  shows the requested folder and leaves prompts such as Replace to the caller.
- Fix Mac keyboard shortcuts and credential text delivery across supported
  keyboard layouts and modifier remappings. Accept both plus and hyphen chord
  separators, and refuse unsupported input before sending a partial value.
- Improve Mac accessibility reliability: non-finite values no longer crash
  replies, and bounded observation identities preserve unchanged controls
  across reads. Actions still require fresh snapshot references and recheck
  process and ancestor membership before dispatch.
- Include a candidate persistent Python MCP session through
  `machine-control mcp`, with compact tree observations, capture-bound input,
  explicit application activation and owned claim/session cleanup. This
  interface has bounded source acceptance on Mac; installed-package, remote
  and broader platform qualification remain open.
- Improve offline claim/workspace help and claim renewal/release arguments,
  use a shared Mac clock for queued admission deadlines, and preserve failed
  provisioning-journal persistence errors in the CLI exit status.

Targets all six desktop platform/architecture packages. Mac keyboard candidate
acceptance covers six layout/remapping combinations with AppKit, WebKit,
Terminal, Electron and real administrator authorization; browser shortcuts
also pass a focused Chrome for Testing smoke. Native identity and persistent
session acceptance are bounded by their documented fixtures and agent trials.
GUI execution for these changes is ARM64 Mac; Intel execution, broader
hardware/layouts and exact signed production-package acceptance remain separate.

## [0.6.4]

- Preserve access enabled by the person on Mac, Windows and Linux when an
  agent calls `grant revoke`. Grant status reports whether access came from
  the person or an approved agent request. Revoking a request grant still
  ends it; access the person enabled returns when that grant ends or expires.
  On Mac, request cleanup preserves saved personal consent. The person's
  Stop still ends all access and clears saved consent.
- Add Chrome extension icons and a side panel showing connection, access,
  controlled tabs and recent operation activity without recording typed text
  or page content. Native browser hosts on all three platforms accept the
  Chrome Web Store extension as well as the existing unpacked copy. Store
  review and installed store-copy acceptance remain separate.
- Add offline `--help` for desktop, browser, grant and audit commands, clearer
  argument and claim-ID errors, and guidance for until-stopped access. Keep
  the built-in local host available alongside private inventory targets.
- Add private `usage note|show` records for control friction and correlate
  retained command history with the agent's published session reference.
- Prevent the installed CLI entry point from writing Python bytecode into
  the signed application bundle, preserving its code signature.

Includes all six desktop platform/architecture packages. Grant-retention
regressions pass on all three platforms; installed Windows and Linux
retention remains separate qualification. Mac broker, consent and socket
regression tests pass. A locally signed source build also verifies installed
grant retention and capture; lock/unlock, Stop,
and exact production-package GUI effects remain separate qualification.

## [0.6.1]

- Fix Mac covered locked-use startup that could immediately relock the screen
  and end approved access after the helper had verified unlock. Older cached
  or in-flight session polls no longer overwrite newer native observations;
  activation uses the guardian's verified original-console observation.

The repaired source passed a single-display physical ARM64 completion test:
covered unlock, native actions/input, filtered capture, automatic relock and
retention of the original approval. Expiry, physical takeover, successive
tasks, multiple displays and Intel execution remain separate qualification.
Existing opt-in, native permissions, finite ownership and watchdog protections
remain required. Includes all six desktop platform/architecture packages.

## [0.6.0]

- Add personal, minimal and appliance presentation profiles to the same
  desktop app on Mac, Windows and Linux. Settings opens on demand; native
  approvals, notices, Pause and Stop remain available without Settings.
- Add a Settings profile selector and local `machine-control presentation
  status|set PROFILE|reset` recovery commands. Temporary launch overrides
  expire on Restart. Presentation changes do not grant access, install a
  protected helper or replace administrator-provisioned appliance policy.
- Keep slow helper, companion and provider work away from the UI event loop,
  with bounded capacity, deadlines and cancellation. Stop fences new actions
  independently; late replies cannot revive access or reuse stale references.
- Improve restart and recovery after companion loss, preserve Mac update
  status through asynchronous replies, and restore Mac log-folder opening.

Includes Mac Apple silicon/Intel, Windows x64/ARM64 and Linux x64/ARM64
packages. Bounded VM qualification covers all three profiles on Mac ARM64
and both Windows/Linux architectures at their recorded source revisions;
Linux ARM64 additionally covers installed Debian and AppImage launchers.
Signed publication is separate from those development-candidate campaigns.
Intel Mac GUI execution, native Windows ARM browser/GPU, broader hardware,
protected-session recertification and longer load/soak coverage remain open.
Ordinary desktop control still requires a supported graphical session and
OS permissions; appliance presentation alone does not enable unattended access.

## [0.5.8]

- Fix Mac locked-use helper setup when another product, such as Codex
  Computer Use, already has a lock screen plug-in. Setup and removal now
  change only Machine Control's entry in the shared unlock rule, and
  Permissions lists the other plug-ins. Helper setup failures show their
  specific reason instead of `helper_setup_failed`.

## [0.5.7]

- Add native Windows pointer move, bounded left/right drag and signed vertical
  and horizontal wheel input. Live control ownership and operator protections
  apply; interrupted drags release their attempted button without replay.

- Automatically pause Windows desktop control for human keyboard/mouse
  activity while retaining approval. Agents wait for quiet and accept a fresh
  session; injected agent input does not trigger takeover. Covered takeover
  relocks and waits for locked quiet, while owner-unlocked local use stays
  paused until relock plus quiet or Resume. Manual Pause remains independent,
  and interrupted actions are never replayed automatically.

- Add explicit Windows locked-screen preparation with a separately approved
  controller, one-shot password delivery and a finite task owner. An opaque
  single-display cover preserves underlying native capture and injected input.
  An independent guardian requests relock on locked-origin task end,
  Pause, Stop, expiry, takeover or heartbeat loss; no password is cached.
  Tasks that start unlocked finish without requesting lock on Windows and Mac.

- Add Windows browser file uploads through the Chrome extension, using named
  target-local files and current page references. Browser-only access can
  attach files without the OS picker; live ownership, Pause/Stop and file-path
  checks remain enforced. Attachment delivery does not imply website success.

- Add owner-bound Windows streaming CDP and shared browser-level target
  discovery with flattened sessions for Playwright and Puppeteer. DevTools
  approval and live ownership remain required; Pause, Stop and owner loss
  invalidate endpoints. Add background navigation for unfocused new tabs.

- Add an optional Windows administrator-installed UAC helper with per-run
  opt-in, native grants and live ownership. Approved tasks can observe English
  stock consent prompts, approve/cancel them and control elevated apps. Pause,
  Stop and owner loss still fence effects. UAC credential prompts and cold login
  remain unavailable; UAC and secure-desktop policy stay enabled.

This release includes Mac Apple silicon/Intel, Windows x64/ARM64, and Linux
x64/ARM64 Debian/AppImage packages. New Windows features have focused unsigned
x64 VM acceptance; signed installed feature, ARM64 and physical execution
remain separate coverage gaps. Protected helpers require explicit setup and
approval. Reload the unpacked Chrome extension after updating.

## [0.5.5]

- Redesign the Access tab around an on/off switch with Pause and Resume
  beside it, so turning access on no longer requires scrolling. Permissions,
  duration and **Also while the screen is locked** sit in one section; the
  locked-screen helper can be set up from there. Disabled controls say why.
- Move the takeover policy and notice countdown to Settings.
- On Mac, replace the YepAnywhere trust checkbox with an experimental **Only
  the YepAnywhere app** option that lists its current limits.
- Explain why **Install and restart** is disabled and offer **Go to Access**
  when access must be stopped first.
- On Windows, require live connection ownership for desktop and browser
  operations and keep one owner across interactive CLI control streams.
- Add Windows scan-code keyboard input, including bounded overlapping and
  tap-then-hold key timelines that always release held keys.
- Keep CLI control-session ownership after a delivered action whose effect
  cannot be independently verified, and preserve interruption details in
  client errors.

## [0.5.4]

- Offer **Until I turn it off** when manually enabling access on Windows and
  Linux, matching Mac. Indefinite access has no countdown and retains selected
  scopes, Stop, platform availability checks and update-install exclusion.
  Agent approval requests remain timed. This change adds no new reboot or
  restart persistence behavior.
- Include Windows main-executable CLI discovery and startup, desktop audit
  history and diagnostics, and resumable Windows operator pause controls.
- Include the intervening Mac caller-authorization, consent and control-session
  work, with capability-specific acceptance limits retained in the repository.

One tagged release includes Mac Apple silicon/Intel, Windows x64/ARM64, and
Linux x64/ARM64 Debian/AppImage packages. Native feature acceptance and package
verification are recorded separately in the desktop acceptance matrix.

## [0.5.3]

- Check for updates silently five seconds after startup and daily while the
  desktop app runs, independently of its settings window. Show available
  updates in Settings and the tray.
- Add `machine-control update check|status` through existing resident transports.
  Discovery never downloads, installs, restarts, or focuses the app. Installation
  stays explicit and refuses active access or approval.
- Bundle the Machine Control CLI and its Python runtime on all six desktop
  targets. Agents can read offline identity and instructions and use the
  installed CLI without a source checkout or system Python.
- On Mac, include signed `mc-sudo` helpers for one-command administrator
  authentication through a native password dialog.

This release includes Mac Apple silicon/Intel, Windows x64/ARM64, and Linux
x64/ARM64 Debian/AppImage packages. CLI relocation and offline execution have
Mac ARM64, Windows x64, and Linux ARM64 evidence; native installed control has
Mac ARM64 appliance evidence. Full signed Windows/Linux CLI desktop acceptance,
Intel/Windows ARM64/Linux ARM64 GUI execution, and physical-host acceptance
remain separate coverage gaps. Updates install only after explicit approval.

## [0.5.0]

- Add a Linux desktop preview for Ubuntu GNOME Wayland, with the shared settings
  and tray, native access approval, timed scopes, Stop, and startup preferences.
- Use visible portal consent for screen capture and input without the dedicated
  test appliance's privileged input service. Close access when sharing or the
  unlocked desktop session ends.
- Add Linux Chrome integration and Debian/AppImage downloads for x64 and ARM64.
  Include Linux in the single desktop release and signed AppImage update path.

Linux desktop execution is accepted on an Ubuntu 24.04 GNOME 46 Wayland x64
VM. ARM64 packages are built natively and authenticated; ARM64 desktop execution,
other desktops and physical hardware remain untested. Screen and input sharing
requires visible portal consent. AppImage supports signed in-app replacement;
Debian updates use the package manager. Protected login/unlock, multiple shared
screens and file upload are outside this preview. Browser setup is optional.

Mac and Windows include the improvements from 0.4.9 and 0.4.10. Reload the
unpacked Chrome extension after updating.

## [0.4.10]

- Show a pointer badge on the favicon of each controlled browser tab.
- Put new agent-created tabs in a blue **Machine Control** group, preserving
  existing user groups.
- Restore site icons and owned grouping when browser control is released,
  access ends, or the connection closes. Preserve later site-icon and user
  group edits; markers also expire if the extension loses its debugger.

This patch includes Mac Apple silicon/Intel and Windows x64/ARM64 packages.
Browser marker execution is checked in an Apple silicon macOS VM with Chrome
for Testing. Other architecture execution and Linux publication remain separate
coverage gates. Reload the unpacked Chrome extension after updating.

## [0.4.9]

- On Mac, add **Until I turn it off** when manually enabling access for the
  selected scopes. The active-access status shows this lifetime without a timer.
- Stop access, screen lock/session loss, Quit, and Restart still end access.
  Access starts off after restarting the app or Mac.
- Agent-requested approvals remain time-limited. Windows retains timed access.

This patch includes signed Mac Apple silicon/Intel and Windows x64/ARM64
packages. Linux packages remain planned for 0.5.0. Full physical-Mac product
acceptance and Intel/Windows ARM64 execution remain separate coverage gaps.

## [0.4.8]

- First public Windows desktop preview for x64 and ARM64, alongside Mac.
- Shared settings and tray controls with scoped approvals, expiry, and Stop.
- Windows Chrome extension setup and separately approved browser scripts.
- Signed Windows updates and uninstall while Chrome remains open.
- One tagged release script, changelog, and update manifest for all packages.
- Latest download links for Mac and Windows on the download page.

Windows x64 passes installed VM testing. Windows ARM64 packages are signed and
verified; native ARM64 execution remains untested. Mac native acceptance covers
Apple silicon Tart; physical Mac and Intel execution remain open. Grants apply
to callers running as your user. Protected Windows desktops, file upload, and
raw CDP WebSockets are outside this Windows preview. Linux desktop packaging
is not available yet.

When updating Mac 0.3.3 or 0.3.4, reopen Machine Control if it closes after
installation. Later versions support automatic relaunch.

## [0.4.7]

- Finish ordinary Windows uninstall with Chrome open by stopping the operator
  before unregistering the browser host and waiting for its image to close.
- Refuse incomplete browser cleanup before removing the rest of the payload;
  preserve Chrome, independent user apps, and separate appliance services.

This internal Windows candidate fixes a live 0.4.6 uninstall race. Public
Windows downloads and the production update feed remain separate gates.

## [0.4.6]

- Let Windows updates finish while Chrome remains open by pausing only the
  owning native-host registration during replacement and restoring it afterward.
- Recover interrupted browser-registration maintenance when the app starts.
- Remove owned browser registration during uninstall without requiring an
  interactive desktop or changing another installation's host.

This internal Windows candidate fixes a live 0.4.4 browser-open updater blocker.
Public Windows downloads and the production update feed remain separate gates.

## [0.4.5]

- Add installed-browser update checks for registration and startup retention,
  Chrome survival/reconnect, access revocation, and stale references.
- Confirm browser effects after replacement and startup recovery after sign-in.

This internal Windows candidate exercises an actual 0.4.4 to 0.4.5 update.
Public Windows downloads and the production update feed remain separate gates.

## [0.4.4]

- Add Windows Chrome extension setup and scoped browser control.
- Rebuild self-contained Windows packages and reject missing native runtime
  companions or extension files before candidate acceptance.
- Keep browser scripts and raw DevTools behind a separate approval scope.
- Refuse stale browser references after grant or provider changes and report
  uncertain delivery when a browser request times out.
- Preserve startup and browser registration during updater replacement; remove
  only the owning installation's browser registration on ordinary uninstall.

Windows browser support uses the bundled unpacked extension. File upload,
raw CDP WebSockets, and browser-level attachment are not available on this
Windows candidate. Public Windows publication remains a separate gate.

## [0.4.3]

- Refuse Cua stale-element errors even when its CLI exits successfully.
- Keep capture-superseded actions from reporting accepted delivery on Windows.

Windows signed preview acceptance requires independent application effects.

## [0.4.2]

- Verify installed Windows files using paths relative to the product root,
  including controllers whose temporary directory uses a Windows short alias.
- Reject incomplete, duplicate, or unsafe installed payload inventories.

This candidate continues the signed Windows VM acceptance work. Publication
remains a separate gate.

## [0.4.1]

- Guard Windows taskbar and tray controls owned by Explorer.
- Refuse operator clicks through transparent provider cursor overlays.
- Report Windows local host grant state through the common CLI.

This Windows acceptance candidate also exercises the signed upgrade from 0.4.0.
Windows publication remains gated by installed acceptance.

## [0.4.0]

- Windows desktop preview with shared settings and tray controls.
- Native scoped approvals, expiry, Stop, and session revocation on Windows.
- Bundled ordinary-user runtime with signed installers and update packages.
- Windows startup preference and supervised resident lifecycle.

Windows signed candidates precede public release. Grants apply to all callers
running as the same user. Protected desktops and browser integration are outside
the Windows preview; architecture-specific acceptance is recorded separately.

## [0.3.5]

- Reliable Restart and relaunch after signed updates.

When updating from 0.3.3 or 0.3.4, reopen Machine Control if it closes after
installation. Those versions can install the update but miss automatic relaunch.

## [0.3.4]

- Settings and Check for Updates in the menu bar.
- Production update checks and signed installation with access off.
- Bounded update checks with concise status and retry messages.

Grants apply to all callers running as the same user. Native acceptance covers
ARM64 Tart; physical Mac and Intel runtime acceptance remain open.
Windows and Linux desktop apps are not available yet.

## [0.3.3]

- First public Mac desktop preview for Apple silicon and Intel.
- Compact Access, Permissions, Activity, and Settings tabs.
- Visible approval, scope and duration controls, and Stop access.
- Developer ID signing, notarization, and authenticated update packages.
- Tagged releases with required changelogs and latest Mac download links.

Grants apply to all callers running as the same user. Live native acceptance
covers ARM64 Tart; physical Mac and Intel runtime acceptance remain open.
Windows and Linux desktop apps are not available yet. The in-app update feed
is not deployed; install new versions from the download page.
