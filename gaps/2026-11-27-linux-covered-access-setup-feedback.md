# Linux covered-access setup hides the section and the reason setup is blocked

**Fixed in source.** Observed on 2026-11-27 with Machine Control desktop
0.7.5 on Ubuntu 26.04.1, GNOME 50 Wayland, using the physical desktop over
VNC. [Tactical 170](../docs/tactical/170-linux-observer-and-covered-setup.md)
records the fix and verification.

Owning topics: [Linux locked use](../topics/linux-locked-use.md) and
[Desktop access experience](../topics/desktop-access-experience.md).

## 1. Permissions opens Access with the relevant section collapsed

From **Permissions → Covered desktop while locked**, the operator clicked
**Open access settings**. The app switched to the **Access** tab and left
**More options** collapsed, so the covered-desktop controls remained hidden.

In the 0.7.5 source, the shortcut calls `navigate("access")` in
[`main.tsx`](../desktop/src/main.tsx). The destination is inside a separate
`<details>` element in [`surface-access.tsx`](../desktop/src/surface-access.tsx).
The navigation carries no request to open that element or reveal the control.

**Proposed repair.** Expand **More options** and bring **Covered desktop while
locked** into view when the operator follows that shortcut. Verify the
destination is visible in the default-size Settings window when the section
starts collapsed.

## 2. Enrollment looks actionable while Agent access blocks it

After expanding **More options**, the operator clicked **Set up covered
desktop access** and saw no password dialog or clear explanation at the button.
At diagnosis the resident was reachable, the GNOME console was unlocked,
Desktop access was **Automatic**, and `lockedUse.setupState` was `idle`.

The button's disabled state in
[`surface-access.tsx`](../desktop/src/surface-access.tsx) does not check for
active surface access. The Linux resident's `require_settings()` guard in
[`locked_use.py`](../desktop/native/linux/locked_use.py) rejects setup before
launching the dialog if any surface has live access. The frontend routes the
rejection to a page-level alert at the top of Access, which may be out of view
while the operator is at the bottom of **More options**.

**Proposed repair.** Show the current blocker beside the setup button, with
an explicit instruction to turn **Agent access** off. Keep refused attempts
visible at that control if access changes between rendering and clicking.
Verify the message when Desktop or Browser access is on, then verify that
turning access off on the unlocked console makes setup available.
