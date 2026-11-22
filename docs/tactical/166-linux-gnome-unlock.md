# 166 — Native Ubuntu GNOME session unlock

Status: GNOME 46 authentication proof on both VM architectures. The x64
Desktop sequence passes with the upstream accessibility fix loaded and
on stock Ubuntu 26.04.1 with GNOME 50.1. Workstation integration remains
open.

Topics: [Linux locked use](../../topics/linux-locked-use.md),
[Linux resident control](../../topics/linux-resident-control.md).

## Objective and boundaries

Unlock the same already-logged-in local Ubuntu GNOME Wayland session using
the user's native GDM authentication. Require separate native observations
of lock, unlock and relock. Use the retained Linux appliances under their
exact target claims. Cold login, user switching and other compositors are
outside this slice.

## Ordered work

### 1 — bind to the session and verify native authentication

Resolve one local Wayland graphical session and reject concurrent graphical
sessions for the same UID. Bind the lock observation to the GNOME Shell
process and its ScreenShield D-Bus owner. The public ScreenSaver name on
GNOME 46 is a separate GJS proxy. Recheck the same session before beginning
GDM verification, before reading a password and before dispatching it.
Only answer the expected English `gdm-password` prompt once. Treat GDM
verification and the observed unlock as separate results.

### 2 — exercise the claimed appliances

Use an existing password-profile appliance with a canonical private
credential file and the pinned setup SSH route. The probe runs in the
logged-in user's systemd manager so GDM resolves the native graphical
session. The controller reads the canonical file only after the guest
reports a recognized GDM prompt. It sends the password over SSH stdin and
closes the stream. The temporary guest worker disables dumps and exits on
a bounded deadline. The probe observes the original unlocked session for
eight seconds, relocks and confirms that one incorrect password attempt
leaves it locked.

```sh
bin/machine-control --target linux run \
  --reason 'Verify native GNOME session reauthentication' \
  --claimant-authority local-test --claimant-id gnome-lock-test \
  -- python3 tests/desktop/linux-gnome-unlock-live.py
```

Append `--desktop-effect` to exercise a GTK fixture through AT-SPI after
the same-session readback. Start from a booted, unlocked appliance before
using this diagnostic. A failed run can leave the appliance at GDM.

### 3 — record workstation requirements

On Ubuntu 26.04 x64 with GNOME Shell 50.1, a read-only compatibility check
found the GDM bindings, exact local Wayland session and live compositor
lock state. Platform source review also confirms the ScreenShield owner's
interface remains present in GNOME 50. Workstation enrollment, covered
activation and physical relock qualification remain open in the owning
topic.

## Results

Native lock, GDM authentication, original-session unlock and relock passed
on Ubuntu 24.04 GNOME 46, on ARM64 UTM and x64 KVM. No outer console or
input was used. The unit suite exercises wrong or duplicated prompts,
unsupported sessions, changed ScreenShield ownership and conflicting
native lock observations.

On KVM, in one run after eight seconds of positive same-console observations,
a native dialog launched, relock completed and GDM refused a bad password.
The corresponding ARM64 attempt lost the Shell connection. A separate
prestarted GTK fixture also lost the GNOME session on each architecture
during the AT-SPI effect check. The KVM system journal confirmed a Shell
SIGSEGV after an earlier application-launch attempt. The same semantic
button increment passed on x64 after a normal boot. The final authentication
probe passed the eight-second hold, relock and bad-password refusal on both
architectures. The eight-second window is an observation bound for the test.

### Accessibility crash and corrected x64 sequence

The x64 crash dump shows GNOME Shell dying in the ATK bridge while
dispatching an accessibility D-Bus message. The frames pass through
`g_object_ref` and `g_hash_table_foreach`. They match the dangling
accessibility cache reference fixed by GNOME upstream. The VM ran
Ubuntu Noble's `libatk-bridge2.0-0t64` 2.52.0-1build1.
[GNOME fix](https://github.com/GNOME/at-spi2-core/commit/d442ee182ec8fa095c6bc5298a17663cfc70cf9a)

Built the 2.52.0 bridge with that patch and mount-bound the one rebuilt
library in the claimed VM for the test. Verified that the restarted GNOME
session loaded it. The complete `--desktop-effect` sequence passed on x64
KVM. GDM unlocked the original session, the resident invoked the GTK
fixture button, the independent fixture counter advanced, and the console
relocked. An incorrect password was then rejected with the console still
locked. The fixture's optional canvas reported a missing Cairo binding.
The semantic button and its independent counter completed.

After the test, rebooted the VM and verified that the temporary mount and
build directory were gone and the stock package passed `dpkg -V`. The VM
was shut down and its claim released.

The Ubuntu 26.04 GNOME 50.1 physical target has Ubuntu's AT-SPI 2.60.4
package, whose upstream tag includes the cache fix. Evidence on that
target remains read-only. The corrected ARM64 application-effect sequence
and packaged workstation route remain open.

### Stock Ubuntu 26.04.1 VM

A separate amd64 libvirt candidate cold-booted from its own disk after the
NoCloud seed was detached. Ubuntu reports 26.04.1. GNOME Shell
`50.1-0ubuntu1.5`, GDM `50.1-0ubuntu0.1` and AT-SPI
`2.60.4-0ubuntu0.1` match the physical reference. The stock candidate
passed native same-session lock, GDM reauthentication, a GTK button
press verified by the fixture counter, relock and bad-password refusal.

Provisioning on this release required two compatibility fixes. The
credential tool now reads an exact shadow entry through guest-local NSS
because the guest's Python 3.14 lacks `spwd`. The input broker and CLI
fallback now query logind for the active seat session instead of relying
on the human-readable session table. The stored credential was verified
after the disk-only boot. Both the factory credential-handoff and promotion
stages passed.

The ordinary smoke suite stopped at display capture. On GNOME 50,
`gnome-screenshot` 41 could not use the GNOME Shell screenshot interface.
Its X11 fallback produced no screenshot in the active Wayland session.
A second run with the two capture checks omitted verified app launch and
termination, an AT-SPI button press, pointer click, Unicode text entry,
and scroll. The fixture did not record the expected drag release.
