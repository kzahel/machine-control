# Physical Windows x64 evidence

Status: current minimized validation record; temporary artifacts are cleaned
and the runtime remains installed for continued appliance testing.

This is a minimized public summary. Raw JSON, screenshots, process/window IDs,
account and machine names, paths, addresses, and host keys remain target-local
and must be deleted during cleanup.

## Environment and baseline

- Physical x64 Windows, build `10.0.26200.8457`.
- Runtime absent before the test: no service, install root, or artifact root.
- UAC enabled (`EnableLUA=1`).
- Administrator consent prompting enabled
  (`ConsentPromptBehaviorAdmin=5`).
- Secure-desktop prompting enabled (`PromptOnSecureDesktop=1`).
- No VM host, hypervisor input, or hardware KVM route was available to the
  acceptance caller.

## Completed cases

| Case | Result | Important evidence |
| --- | --- | --- |
| x64 self-contained publish and service install | pass | Automatic LocalSystem service; active x64 process architecture |
| Cua/native provider composition | pass | Digest-pinned Cua ran only in the Medium helper; owned native UIA/Win32 retained shell, state, fallback, session, and protected routes |
| Ordinary Medium plane | pass | Integrity RID 8192, `Default`, not LocalSystem |
| Local/remote parity | pass | Target-local Medium workflow and SSH carrier used the same operations, pipe, provider routes, result vocabulary, and fixture oracle |
| Provider timeout and revocation | pass | One-millisecond Cua observation deadline disclosed native UIA fallback; stale generation was rejected and helper recreated |
| Start and Start menu | pass | Bounded UIA projection and semantic toggle |
| Search | pass with explicit fallback | Taskbar configuration had no Search element; target-local `Win+S` opened a compact semantic Search surface |
| Quick Settings | pass with explicit fallback | Target-local capture/input; zero matching UIA elements reported honestly |
| Notification overflow | pass | Bounded UIA projection and semantic action |
| Notification Center | pass with explicit fallback | Target-local capture/input |
| Settings and Explorer | pass | Bounded UIA projections |
| Desktop context menu | pass | Target-local input plus bounded UIA effect |
| Window lifecycle and exact capture | pass | Minimize, maximize, restore, close effects confirmed; `PrintWindow` route |
| Revocation and stale references | pass | Helper recreation and stale-generation refusal |
| UAC cancel | pass | Genuine Medium request, `Winlogon`, secure-desktop capture, semantic cancel, return to `Default` |
| UAC approve and High application | pass | Semantic approval, High fixture semantics, independent counter effect |
| Lock | pass | WTS lock flag, protected route, target-local capture; modern lock UI remained on `Default` |
| Logout/no user | pass with result fix | Active session changed, no interactive user, protected `Winlogon` capture and compact sign-in semantics |
| PIN login | pass | Stock PIN field discovered semantically before one hidden one-shot submission; independent WTS, `Default`, and Medium-helper effect |
| Password login | pass | Stock Sign-in options and Password provider invoked semantically before one hidden one-shot submission; independent WTS, `Default`, and Medium-helper effect |
| Windows boot recovery | pass | After explicitly selecting Windows again, SSH, the automatic service, a new generation, and the Medium helper returned |

The composed provider acceptance reran ordinary shell and UAC cases after the
earlier full-control validation. It did not rerun PIN or password submission
because no change crossed that separately guarded secret path. The complete
execution decision is in
[`Tactical 004`](../tactical/004-windows-provider-composition-and-agent-ergonomics.md).

## Compact observation measurements

Measurements are result payload sizes and provider-local latency from the
passing physical run.

| Surface | Elements | Visited | Bytes | Est. tokens | Latency ms |
| --- | ---: | ---: | ---: | ---: | ---: |
| Start | 1 | 46 | 288 | 72 | 127 |
| Start menu | 2 | 7 | 599 | 149 | 13 |
| Search surface | 5 | 7 | 1,456 | 364 | 31 |
| Notification overflow | 1 | 105 | 229 | 57 | 319 |
| Settings | 22 | 164 | 6,797 | 1,699 | 314 |
| Explorer | 2 | 135 | 521 | 130 | 711 |
| Desktop context menu | 9 | 200 | 2,661 | 665 | 604 |

## Findings

The target-native runtime is not coupled to the ARM64 VM: ordinary semantics,
native shell fallback, Cua exact capture and background semantic action,
secure-desktop UAC control, elevated application control, and lifecycle routing
all ran on physical x64 Windows.

Logout exposed a race in its effect oracle. Windows switched to a new active
session while the old WTS record still reported a user, causing the operation
to return `unverifiable`. The implementation now treats an authoritative
active-session change as a confirmed logout, reports whether the new active
session has an interactive user, and gives Windows a bounded 25-second
transition window. Independent follow-up confirmed the no-user `Winlogon`
state, protected capture, and compact sign-in semantics.

The laptop is dual-boot and Windows had been selected through one-shot EFI
`BootNext`. A generic reboot therefore returned to the default Linux entry and
did not constitute a Windows restart test. The initially suspected Windows SSH
identity failure was actually the Linux SSH service. After Windows was
explicitly selected again, Windows SSH authenticated, the runtime service had
a new generation, and it attached a Medium helper. The authoritative physical
testbed must model one-shot boot selection explicitly rather than treating a
generic reboot as a same-OS restart.

PIN and password login both passed through the dedicated non-JSON credential
channel. The resident worker first discovered the requested stock Credential
Provider controls through UI Automation, then read the secret and used
target-local Unicode `SendInput` for characters and submission. No screenshot
was taken during entry. The independent oracle observed a logged-in user,
`Default`, and a fresh integrity-RID-8192 helper after each case. The target did
not require Secure Attention Sequence generation to expose sign-in controls.

## Remaining work

- Add localized and policy-varied Credential Provider fixtures before claiming
  general Windows-version resilience.
- Exercise the facade on additional physical Windows hardware and session
  configurations.
- Temporary screenshots, user-profile evidence, and deployment staging files
  are removed; the adopted runtime intentionally remains installed.
