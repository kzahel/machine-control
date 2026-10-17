# 131 — Windows and Linux browser access while locked

Owning topics: [browser control](../../topics/browser-control.md),
[Windows desktop](../../topics/windows-desktop.md),
[Linux desktop](../../topics/linux-desktop.md).

Status: complete; bounded source-native VM acceptance passes on both platforms.

## Objective and completion conditions

The controller user requested the Mac browser-while-locked option on both
Windows and Linux, implemented end to end and committed. Provide the same
local, default-off choice, retain existing browser approval and its deadline,
refuse desktop operations and new approvals while locked, and demonstrate
independent browser effects without unlocking either test appliance.

## Boundaries

- Existing awake, logged-in console, Chrome extension/native messaging and
  separate DevTools authority; no new unlock helper or protected provider.
- Windows ordinary-user desktop and Ubuntu GNOME Wayland desktop. Other Linux
  compositors, X11, sleep, cold login and browser authentication prompts need
  separate evidence.
- Source-native operator fixtures exercise the actual native brokers, Windows
  native approval and Linux person-armed access. Shared Settings is type checked;
  signed installed UI, physical hardware and release publication remain
  separate work.

## Ordered work

### 1 — retain approval on the same console

Persist only the local preference, never consent. Enabling requires an
unlocked console and cannot be requested through the agent endpoint. Bind
Windows grants to the WTS console session and logon timestamp; bind Linux
grants to the active logind graphical session, monotonic creation timestamp
and GNOME screensaver bus owner. Missing, stale or changed identity revokes.
Keep grant identity and remaining lifetime, rotate observation generations at
lock transitions, and admit only existing browser/DevTools scopes while locked.

### 2 — preserve desktop and operator boundaries

Keep desktop observation/input unavailable, maintain separate DevTools scope,
and refuse new or expanded locked approval. Pause, Resume, Stop, expiry and
disable remain effective. Browser-only Windows owners skip covered unlock;
Linux closes its desktop portal without revoking the retained browser grant.
Status distinguishes approved and effective scopes.

### 3 — prove native browser effects

Run Windows grant/admission/persistence contracts, Linux grant/preference/session
unit tests, shared TypeScript checking, both Windows architecture publishes,
platform static smoke suites and portable repository checks. Use
[the Windows actor](../../tests/windows/browser-locked-live.py) and
[the Linux actor](../../tests/desktop/linux-browser.py) with separate Chrome for
Testing profiles, independent HTTP effects and independent OS lock readback.
Preserve operator registrations/preferences, reap owned browsers and restore
initial VM power state. Raw evidence and target identity stay private.

## Validation and final result

- Windows grant/admission/persistence contracts, Linux grant and desktop unit
  tests, shared TypeScript checking, both Windows architecture publishes,
  formatting, platform static smoke suites and portable checks pass.
- Linux source-native ARM64 acceptance passes 37 checks with Chrome for
  Testing 156. The [platform report](../../research/platforms/linux.md#browser-control-with-the-console-locked)
  owns route, effects and sandbox limitations. The locked PNG is visually
  checked. Earlier uncertain observations revoke conservatively; those failed
  attempts are retained privately rather than counted as acceptance.
- Linux native host setup previously copied only top-level extension files;
  recursive copying now includes required extension 0.8.0 icon assets.
- Linux fixture preferences/registrations and owned staging are removed, its
  browser/resident are reaped, normal shutdown restores initial off power and
  its claim is released.
- Windows ARM64 source-native acceptance passes 18 checks with x64-emulated
  Chrome for Testing 155 and real native approval. Independent WTS lock and
  HTTP effects, tab PNG and per-tab streamed DevTools pass. The
  [platform report](../../research/platforms/windows.md) owns evidence limits.
  The raw-CDP fixture client now handles Chrome's query-free browser endpoint,
  case-insensitive HTTP headers, cold-start latency and in-progress port files.
- Windows native host registration and preference restoration are independently
  verified; no staged process remains. The locked PNG is visually checked.
  Owned staging is removed, normal shutdown restores initial off power and
  the claim is released. The repaired supported UI relay remains installed as
  appliance infrastructure.

The next bounded slice is signed installed Settings/native approval acceptance
through lock, unlock, expiry and browser-root streaming. Then qualify physical
hardware and additional Linux compositors independently. No release is part
of this change.
