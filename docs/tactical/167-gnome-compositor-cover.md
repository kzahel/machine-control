# 167 — GNOME compositor cover

Topic: [Linux locked use](../../topics/linux-locked-use.md).

Status: GNOME Shell 50 appliance prototype.

## Objective and completion

Keep the active Ubuntu GNOME Wayland console covered during native GDM
reauthentication and a task in the existing session. Verify the lock,
covered unlock, an independent application effect, and native relock.
Run the proof under an exact appliance claim. The installed Desktop
owner, credential enrollment, and the ordinary portal capture and input
routes require their own acceptance before this becomes an app feature.

## Cover the same console

Install the test extension in the dedicated guest. GNOME Shell places an
opaque actor over the complete monitor layout and reports the current views
it has painted. The extension owns no unlock or password operation. Its
cover is tied to a private D-Bus connection and renewed with a short lease.
The lease closes on local input, an explicit end, owner disconnect, an
expired heartbeat, or a change to the monitor layout. Shell keeps the cover
while it requests and waits for its own ScreenShield to lock.

The cover paints normally for the display. It excludes itself only from the
exact offscreen framebuffer allocated for an authorized capture. A single
covered click uses a compositor virtual pointer. The compositor filter
adopts only the queued events for that pointer and the active lease. The
existing root activity observer supplies a separate opaque movement token.
The cover client keeps its lease only while both the movement and deliberate
input tokens are unchanged and the observer covers the same console.

The client checks the already-bound console again before native GDM
reauthentication. The claimed appliance probe sends the canonical password
over its existing one-shot transport only after the cover and GDM prompt
events. GNOME Shell and logind both report the resulting lock
state. An independent fixture counter verifies the semantic press and
the covered pointer click. The physical compositor image contains only
the cover before authentication and after capture and input. The private
offscreen capture contains the known GTK canvas.

## Validation

Package the two files in `platforms/linux/guests/ubuntu/ui/gnome-cover/`
at the root of a ZIP. Install and enable the extension as the guest's
graphical desktop user. For a fresh extension, log back in once so GNOME
Shell discovers its files. Run the following from an unlocked, claimed
GNOME 50 appliance with the canonical password handoff complete.

Run the appliance observer fixture in a transient root unit, with
`RuntimeDirectory=machine-control-cover-test` and mode `0755`. Stage
`tests/desktop/linux-cover-activity-fixture.py` with `activityd.py` and
`activity_events.py` from `desktop/native/linux` in a root-owned directory.
The fixture additionally observes the exact test HID. The workstation
observer excludes virtual devices. The probe sends movement through that
test HID and checks the lock through GNOME and logind.

```bash
bin/machine-control --target linux run \
  --reason 'Verify the GNOME compositor cover' \
  --claimant-authority local-test --claimant-id gnome-cover-test \
  -- python3 tests/desktop/linux-gnome-unlock-live.py --covered-effect
```

Use `--covered-stop`, `--covered-expiry`, `--covered-owner-loss`, or
`--covered-crash` to exercise the other lease endings. The crash test kills
only the selected fixture worker and reads the relock from a second process.
Stop the transient observer, remove its staged files and the extension,
and return the claimed VM to its original power state.

## Results

Stock Ubuntu 26.04.1 x64, GNOME Shell 50.1 passed same-session covered
unlock, AT-SPI, offscreen capture, an independently observed pointer click,
and relock after simulated local mouse motion. GDM also refused an incorrect
password. The actor follows monitor rectangles because the Shell stage
resizes during authentication. The independent kernel observer catches
movement that the compositor does not report after the virtual pointer
operates. The test covers one VM display at scale 1 and a simulated input
device.

Explicit Stop, lease expiry, and a deliberate SIGKILL of the covered
fixture worker passed the same capture and click sequence. A separate
observer found the original session locked after SIGKILL. The test
extension and transient activity service were removed. The stored guest
credential remained valid and the VM was shut down with its claim released.

The normal Linux desktop companion still needs local enrollment and binding
to its authorized task channel. Hotplug, physical hardware and input beyond
the qualified click require further acceptance.
