# Linux Resident Control

Topic: `linux-resident-control`

Status: accepted Ubuntu GNOME Wayland logged-in appliance; other compositors,
protected login planes, and physical Linux hardware remain research-stage.

**Current:** Retained UTM appliances can explicitly select
`LINUXVM_ADMIN_TRANSPORT=ssh` after guest-agent host-key pinning. Root
administration and transfer then use pinned key-only SSH and appliance sudo;
UTM retains exact identity, lifecycle and address discovery. There is no
implicit transport fallback. The resident and its desktop contract stay the
same. See [Tactical 090](../docs/tactical/090-retained-desktop-appliance-rebuild.md)
for the fresh retained-appliance acceptance status.

## Current state

The authoritative [`platforms/linux`](../platforms/linux/README.md) now
provides an accepted Ubuntu 24.04 GNOME 46 Wayland logged-in software-testing
surface. A persistent active-user resident exposes the same
`machine-control/v0` Unix-socket contract to guest-local and outside callers.
It owns compact AT-SPI semantics, GNOME display and active-window capture,
argv-only user-systemd application lifecycle, generation-bound references,
and a bounded root appliance input broker available only to the active user.

The guarded corpus covers GNOME Shell, dock, top bar, notifications, Files,
Settings, a file chooser, Polkit detection/cancellation, GTK, Qt/XWayland,
Chromium, and custom-rendered visual fallback. It verifies independent
application or OS effects and fails closed on every outer UTM-window capture
or input operation. A full reboot restores both resident services and rejects
pre-reboot references as stale.

**Current:** Tactical 018 re-proved the retained appliance without cloning or
outer input. Its static device-activated QEMU guest-agent, GNOME auto-login,
resident, semantics, capture, and input all returned after a boot-ID-changing
reboot while outer UI remained prohibited. The same exact candidate reached a
clean stopped promotion handoff and passed a disposable-marker outcome. A live
restart also exposed and fixed the bounded provider race in which guest
execution preceded UTM's first IPv4 result.

**Current:** Tactical 021 added and live-proved a Linux-native maintenance
surface around that accepted shape. A nonce-bound minimized audit checks dpkg
consistency, pending
reboot, declared runtime/development packages, QEMU/SPICE support, the GNOME
Wayland session, resident, input broker, and target-native status before the
common doctor. Its exact-candidate repair changes only installed systemd
startup invariants and keeps a missing guest agent as an explicit recovery
boundary. On-demand certification audits without repair, uses the provider's
changed-boot-ID reboot proof, runs an archive of exact committed source inside
Ubuntu, cleans staging, and stops only after success. Dependency-light policy
fixtures cover the current contract. The retained candidate passed an
idempotent development-profile bootstrap, healthy audit and no-reboot repair,
exact-source portable and Linux-native certification after a changed-boot-ID
reboot, and a final outer-prohibited resident smoke cycle. No clone or
workspace was used, and the appliance was left stopped.

**Current:**
[`Tactical 028`](../docs/tactical/028-linux-libvirt-controller-host.md) built a
separate native x86_64 Ubuntu 24.04 GNOME Wayland appliance under Linux
libvirt/QEMU/KVM. The same resident, AT-SPI, capture, input, fixture,
maintenance, exact-source certification, and local/outside contracts passed
without ordinary host-console access. A receipt-bound QCOW2 workspace proved
discard semantics, and the accepted base was left stopped and claim-free.

**Current:** The ARM64 UTM factory now runs unattended through UTM scripting
alone, without reading UTM's sandbox container, and was proved end to end on a
macOS controller whose own screen was locked: create, NoCloud first boot,
cloud-init, resident bootstrap, seed detachment, restart, doctor, and two
common conformance passes. The seed is a bundle-contained VirtIO disk; the EFI
variable store is normalized by export and re-import; the seed disables idle
lock and first-login setup. Doctor now reports a locked GNOME session, and
clipboard text waits for selection ownership instead of racing the paste. See
the [Linux problem record](../platforms/linux/docs/problems.md).

**Current:** The Mac UTM factory now has a read-only precreation report for
cloud-image shape, exact key-only NoCloud seed content, host tools, responsive
UTM scripting, and unused destination. The claimed UTM candidate report now
observes guest-agent and NoCloud completion, requires explicit completion
attestation before stopped seed removal, and checks resident readiness and
final stop. A fresh official ARM64 candidate passed stage-driven creation,
bootstrap, two platform smoke runs around seed removal, and exact-source
development-profile certification after a changed-boot-ID reboot. The final
report marked it complete and stopped; the claim was released. UTM's silent
cloud-init command is handled through read-only runtime records, including the
disabled marker on later boots. See
[tactical 042](../docs/tactical/042-macos-utm-ubuntu-candidate-stages.md).

**Current:** The native x86_64 KVM factory now has read-only precreation and
claimed candidate stages for QCOW2/NoCloud inputs, exact destination,
guest-agent and cloud-init readiness, resident bootstrap, seed removal, and
clean stop. A fresh candidate passed the Linux smoke suite and changed-boot
exact-source certification with portable and native checks, then stopped
cleanly and released its claim.

**Current:** [Tactical 048](../docs/tactical/048-linux-rebuild-credential-handoff.md)
recreates and promotes a disposable x86_64 appliance with an explicit stored
password handoff. The key-only seed remains bootstrap-only; promotion verifies
the canonical password against the guest and registers its private locator.
Portable checks, native smoke, seed detachment, restart and final readiness pass;
the retained VM is off and claim-free after consuming product tests. A separate
RTC-scheduled suspend-to-idle experiment failed to return; guarded forced-stop
and readiness recover it, without qualifying native sleep/wake. GUI password
submission remains a distinct provider gap.

**Current:** [Tactical 049](../docs/tactical/049-linux-credential-promotion-gate.md)
adds a private credential verifier and a required factory/promotion handoff.
Password verification uses pinned setup SSH stdin and guest shadow-hash
comparison; explicitly password-free profiles instead prove a locked entry.
Both factory routes require current exact-target evidence before reporting
promotion complete, and common promotion preparation verifies before shutdown
and rechecks the receipt afterward. Operational readiness remains independent.
Deterministic regression coverage is recorded in the tactical. The live command
verifies the canonical stored password on an x64 appliance before and after
reboot in [Tactical 056](../docs/tactical/056-linux-desktop.md); full factory
promotion remains a separate acceptance case. This is not a GUI unlock
implementation.

## Current goal

**Decision:** Keep this accepted GNOME Wayland profile stable while extending
Linux through separate compositor and authority profiles. The target selector
may change, but guest-local and outside callers should retain the same facade,
capability, result, and reference vocabulary.

## Decisions

- Always discover the canonical stored appliance credential through private
  inventory before declaring login/unlock a human gate. The controller-local
  secret file is the source of truth; public guides contain only generic
  locator rules. See the [credential contract](../docs/target-registry.md#credentials-and-private-data).
  Stored disposable-VM credentials may be used unattended. Linux currently
  lacks a dedicated secret-safe password submission operation; distinguish
  that provider gap from missing credential metadata or a human-only step.

- Treat GNOME Wayland as a concrete platform profile, not generic “Linux.”
  Capability reports name the desktop session, compositor, XWayland use,
  portal state, and actual capture/input route.
- Reuse the owned facade and result concepts proven on Windows and macOS while
  keeping AT-SPI, D-Bus, PipeWire, portals, EIS/libei, and any dedicated
  appliance privilege explicit.
- Use the owned native resident as the default for this profile. It is deeper
  for measured Qt semantics and reliable Unicode input and does not require an
  interactive portal for dedicated-appliance input.
- Keep Cua 0.17.0 as an optional composed provider for its rich Chromium
  combined tree/image and GNOME Shell helper's arbitrary target-window
  capture. The measured gaps do not justify a fork.
- Report the input broker honestly as `root_test_appliance`. It is deliberate
  dedicated-appliance authority, not same-user containment or a generic
  workstation route.
- Treat GNOME Settings' labelled but zero-bounds GTK 4 controls as a visual
  fallback: fixed display capture, target-local HID, and an independent
  `gsettings` effect. Do not invent semantic coordinates.
- A private or nested compositor may later be a valuable isolated test target,
  but it is not a prerequisite for proving the existing logged-in GNOME
  appliance.
- GDM, lock screen, encrypted preboot, and absent-user-session control are
  separate authority domains. They are not part of the first logged-in slice.

## Known gaps and next work

The native capture route supports the display and exact active window, not an
arbitrary hidden window. Cua can supply arbitrary target-window capture when
its GNOME Shell helper is deliberately installed. Portal/libei input is a
viable bounded workstation route. The separate ordinary-user
[Linux desktop profile](linux-desktop.md) now has signed x64 GNOME consent,
sharing-lifetime, effect and lifecycle acceptance; it never selects the
appliance input broker.

GDM, lock screen, encrypted preboot, absent-user sessions, other compositors,
and physical hardware remain separate authority and compatibility profiles.
The completed execution record is
[`Tactical 012`](../docs/tactical/012-linux-gnome-wayland-resident-control.md),
the maintenance execution record is
[`Tactical 021`](../docs/tactical/021-linux-post-update-and-appliance-certification.md),
and exact differential evidence lives in the
[Linux findings](../../machine-control-spike/docs/linux-findings.md).
