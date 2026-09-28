# Mac Tart Outer Keyboard Delivery

Topics: [macos-resident-control](../../topics/macos-resident-control.md),
[operational-workflow-automation](../../topics/operational-workflow-automation.md)

Status: complete for diagnosis, guarded input, and independently verified
outer Shift/Command delivery. Control, Option, and Fn remain guarded.

## Objective and completion conditions

Measure shifted text and modifier chords against a guest-owned effect, test
plausible host event routes, and prevent outer input from silently changing a
bootstrap password or shortcut. A safe result must reject unsupported input
before sending any prefix, keep secret bytes out of output, and preserve
unshifted bootstrap input.

## Boundaries

This slice changes only the explicit host Tart recovery route and its guide.
The ordinary target-resident keyboard route remains the application-testing
path. It does not change host privacy permissions, install a virtual keyboard
driver, weaken guest consent, or place credentials in the repository.

## Ordered work and validation

1. **Measure guest text.** Use a Terminal `read` script with a guest file
   oracle to compare the requested string with the received bytes.
2. **Locate the loss.** Observe the host event stream and compare Quartz event
   tap locations, event sources, modifier event types, process targeting, and
   an independent computer input route.
3. **Guard outer input.** Refuse shifted text and modifier chords by default;
   keep an explicit diagnostic override for non-secret trials. Check the
   actual focused Tart VM window before reading a secret.
4. **Verify effects.** Prove a refused mixed-case string, modifier chord, and
   shifted secret insert no bytes, while plain text and a plain test secret
   still reach the guest.

## Initial guarded result

On the tested prepared Tart VM, `type 'AbC!@Z'` produced guest bytes
`abc12z`. A host event tap observed Shift flags on the generated events, but
session, annotated, HID-source, flags-changed, and process-targeted Quartz
variants still produced lowercase `a`. Unicode events used the base keycode;
the legacy AX post call reported success without a guest effect. An
independent computer input route also altered the requested text. A host
virtual HID device was unavailable without its entitlement. This evidence
narrows the problem to a boundary after the host event stream, without proving
the exact Tart or Virtualization.framework mechanism.

The initial safeguard rejected modified input before sending a prefix.
The diagnostic override is explicit and does not apply to `type-secret`.
The latter uses the Tart application's actual focused-window accessibility
attribute, so a small Tart overlay cannot falsely block a correctly focused
VM. Live guest-file checks proved refusal left the next read intact and plain
text and an owner-only plain test secret still reached the guest. The normal
resident route remains the supported path for modified input after bootstrap.
The explicit diagnostic override still reproduced the altered guest bytes,
and the full Mac smoke suite passed.

## Follow-up — correct modifier delivery

The continuation requested a reliable outer Shift/Command route before the
guest agent exists, proved by an independent guest effect, with safeguards
preserved until a route passed. The controlled
[platform experiment](../../platforms/macos/experiments/outer-keyboard/README.md)
compared the original sender, explicit `flagsChanged` alone, device-dependent
flags alone, and both changes. Only variants with the matching left-side
device flags produced exact text and actual Command/Shift–Command menu actions.
This establishes a sufficient sender correction without asserting a private
Tart or Virtualization.framework implementation detail.

The corrected implementation sends explicit modifier transitions with both
general and device-dependent flags, keeps them on base-key events, and releases
in reverse order. Three repeated diagnostic trials passed mixed text, shifted
punctuation, both menu actions, and unmodified typing afterward. The default
CLI now enables Shift and Command while preserving refusal for unverified
Control/Option/Fn. Whole-string ASCII validation and exact focused-window
credential checks remain.

A reusable AppKit oracle and live runner cover the production CLI without the
diagnostic override. The fixture records field text and actual menu effects;
its secure field records only whether a public dummy matched. Private inventory
and captures stay outside Git. The runner owns a disruptive claim, renews it,
removes its guest fixture, suspends the VM, and releases the claim in cleanup.

One secure-field harness run exposed that inventory environment overrides a
process-level dummy credential path. It sent the inventory-selected value into
the disposable secure field; only a false match boolean was retained, with no
value logging. A separate cleanup bug matched `/tmp` while LaunchServices used
`/private/tmp`, leaving old fixture windows alive and contaminating a later
focus assertion. Subsequent captures could therefore show the masked field;
those task-generated captures were removed. The stale processes were
explicitly removed under a new disruptive claim. The corrected runner selects
the dummy file through an owner-only temporary target registry, uses a unique
application identity and canonical scratch path, verifies active field state,
and verifies its recorded PID/executable before termination and file cleanup.

The first full smoke invocation lacked the private direct-platform target
configuration and stopped at status. The live smoke tail now restores required
claim enforcement after its isolated fixtures; it must run with the private
selected configuration and the existing disruptive claim. That complete run
passed and returned the VM to suspended with its claim released.

Final production-CLI acceptance passed without the diagnostic override:
all ASCII letters and shifted punctuation, Command and Shift–Command menu
callbacks, both modifier orders, plain input after release, unsupported-input
refusal without a prefix, and the explicitly selected dummy secure field.
The oracle also verified active application/window/field state. Cleanup
independently observed the fixture process exit and removed its files.

This acceptance uses a prepared guest as the observer. It does not repeat
Setup Assistant, create an account, change a password, or weaken host/guest
privacy permissions. Ordinary post-bootstrap input remains target-resident.
