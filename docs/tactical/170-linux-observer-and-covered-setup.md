# Linux observer polling and covered-access setup

Owning topics are [Linux desktop](../../topics/linux-desktop.md),
[Linux locked use](../../topics/linux-locked-use.md), and
[Desktop access experience](../../topics/desktop-access-experience.md).

## Objective

Resolve the [idle resident retry loop](../../gaps/2026-11-27-linux-activity-observer-spin.md)
and the [covered-access setup feedback gaps](../../gaps/2026-11-27-linux-covered-access-setup-feedback.md)
in the Ubuntu GNOME desktop app.

## Completion conditions

- Keep idle CPU and status traffic low with the observer absent. Recover
  readiness after installation and preserve the fresh post-offer sample
  required for admission.
- From Permissions, expand Access → More options and focus the covered-access
  heading. Show the setup blocker beside the control while either surface
  has live access. Show native refusals there if a request races that state.

## Boundaries and implementation

1. Sample activity on a 250 ms coordinator timer. Publish on observed changes
   and the existing periodic refresh. Keep the observer-health and fresh
   post-offer requirements for admission.
2. Separate the notification helper's periodic heartbeat from immediate
   reports of changes in notice visibility or availability.
3. Reveal the covered-access heading and show the Linux resident's live
   access prerequisite beside setup, password update, and removal controls.
   The resident continues to enforce eligibility at execution time.

The evdev observer and GTK notification protocol are Linux-specific. The
Permissions shortcut and the requirement to turn both surfaces off before
enrollment belong to the GNOME setup route.

## Validation

The released x86_64 0.7.5 Debian package reproduced the issue on an Ubuntu
26.04.1 GNOME Wayland VM. With the observer absent, the idle resident used
98% of one logical core and issued about 3,050 writes per second. With an
unsigned development Debian build installed in the same guest, the idle
resident used 1.4% of a core and issued about 90 writes per second.
In a second workspace, the released package with the three patched Python
modules averaged 1.4% CPU and 89 writes per second with GNOME locked and the
observer absent.

The Linux Python suite passed, including the missing-observer retry,
recovery, deliberate input, and post-offer sample checks. The desktop build
and browser tests passed, including the 640-by-440 Settings layout, both
surface blockers, and a native refusal shown beside setup.

The installed development build passed the shortcut, focus, inline blocker,
and setup re-enable checks on GNOME 50. The running resident recognized the
newly installed observer and reported it healthy without a restart.
