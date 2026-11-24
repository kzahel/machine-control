# Restore indefinite access at startup

Owning topics are [access admission](../../topics/access-admission-and-pause.md)
and [desktop access](../../topics/desktop-access-experience.md).

## Objective

Let an operator leave a desktop available to agents after a restart. The
operator can opt in and independently choose Desktop and Browser access,
including the exact browser profiles. A fresh installation starts Off. Turning
a surface Off or using Stop clears the corresponding saved consent.

The app starts after OS sign-in. The existing operating system startup settings,
locked-session preparation and per-task admission govern the resulting route.
Timed grants and any previous approval, task, owner or reference end with the
previous runtime.

## 1 — persist indefinite consent

The shared resident saves opted-in choices in a private per-instance file from
the trusted native operator channel. A fresh process reads those choices as
pending. A normal Stop clears them. Quit and update termination revoke live
access while retaining the saved choices for a subsequent launch.

## 2 — rebind after sign-in

The desktop shell asks the resident to apply only the pending surfaces.
Each native adapter verifies the current local session and configures a new
consent instance. Existing route readiness governs locked Desktop work, and a
Browser choice waits for its exact profile. OS login and keyring management are
outside this slice.

## Validation and result

The shared policy process test covers opt-in, indefinite and timed access,
exact profiles, process restart, explicit Stop and corrupt state. Native
adapter coverage includes Linux's inherited policy transport, macOS's shared
policy fixture and the Windows locked-session readiness contract.

The portable suite, desktop Settings tests, Linux adapter tests, focused
Windows surface-policy contracts and Windows x64 and ARM64 publishes passed.
The broader Windows desktop suite hit the same audit-rotation failure as the
unmodified source when run on Linux. The macOS fixture and packaged post-reboot
acceptance on all three platforms remain open.
