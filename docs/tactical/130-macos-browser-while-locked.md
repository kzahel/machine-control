# 130 — macOS browser access while locked

Owning topics: [browser control](../../topics/browser-control.md),
[macOS locked use](../../topics/macos-locked-use.md).

Status: complete; bounded source-native workstation acceptance passes.

## Objective and completion conditions

The controller user requested a setting that lets approved browser work continue
behind the macOS lock screen, then asked for implementation and a commit.
Add a default-off local preference without requiring covered unlock, preserve
existing browser authority and its expiry, keep desktop and new approvals gated,
and validate independent browser effects while the OS remains locked.

## Boundaries

- macOS workstation source and its shared Settings UI only; no release or
  physical-host preference change.
- Existing awake console and Chrome extension route. No unlock, root policy
  changes, sleep prevention, new credential handling or desktop fallback.
- Browser scripts require their existing separate DevTools approval.
- Standing appliance behavior and covered desktop control retain their
  separate authority; browser-only owners never activate covered unlock.

## Ordered work

### 1 — establish browser-only feasibility

The [platform report](../../research/platforms/macos.md#browser-control-with-the-console-locked)
records the standing-appliance experiment and its independent HTTP and IOKit
oracles. It establishes feasibility, not workstation authorization.

### 2 — retain approved browser access

Settings persists the local choice through an in-process operator command.
Enabling requires the current user's unlocked console; the agent socket cannot
change it. Grants retain their ID, scopes and deadline, with an explicit
browser-only availability restriction while locked. Desktop scopes return on
unlock within the same grant's lifetime. Status distinguishes approved scopes
from effective scopes. Browser-only admission skips covered unlock.

### 3 — validate the authority boundary

Socket tests cover default-off revocation, preference persistence without
authority, mixed scopes, separate DevTools, unavailable new approval, Pause,
expiry, Stop, disabling, unknown/replaced console and invalid locked-origin
grant binding. Build the desktop UI/native app and both native architectures.
Use the [guest probe](../../tests/browser/locked-macos-live.py) with a
[source-native workstation fixture](../../tests/macos/build-browser-locked-fixture.py)
for real native approval, independent page effects, locked browser-owner
admission and desktop refusals. The fixture's narrow operator input cannot
answer approval. An independent claimed appliance presses the native dialog.
Raw evidence and exact resource identity stay private.

## Validation and final result

- 222 Swift tests pass, including seven new socket-based authority tests.
- TypeScript checking, the unsigned ARM64 desktop app build, ARM64/x86_64
  source-native fixture builds, the Mac static smoke suite and portable
  repository checks pass.
- The source-native workstation probe passes 26 checks on macOS 26.6.2 and
  Chrome for Testing 155. Independent HTTP effects and IOKit lock readback
  establish browser operation while actually locked; the PNG is visually
  checked. The [platform report](../../research/platforms/macos.md#browser-control-with-the-console-locked)
  owns the evidence boundaries.
- Fixture preferences, runtime, browser and guest staging are removed; the
  separate experiment VM returns to its initial powered-off state and its
  claim is released. No installed host app or root guest policy changes.

Signed installed Settings/native approval, physical Macs, streaming DevTools
and other platforms remain distinct follow-up work. Source-native evidence
does not imply their acceptance. The clearest next slice is signed installed
Settings plus per-tab/browser-root streaming through lock, unlock, Pause and
expiry, followed by an explicitly opted-in physical-Mac task.
