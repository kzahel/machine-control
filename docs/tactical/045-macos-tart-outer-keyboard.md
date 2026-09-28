# Mac Tart Outer Keyboard Delivery

Topics: [macos-resident-control](../../topics/macos-resident-control.md),
[operational-workflow-automation](../../topics/operational-workflow-automation.md)

Status: complete for diagnosis and fail-closed bootstrap input; reliable
synthetic modifiers through the Tart window remain open.

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

## Result

On the tested prepared Tart VM, `type 'AbC!@Z'` produced guest bytes
`abc12z`. A host event tap observed Shift flags on the generated events, but
session, annotated, HID-source, flags-changed, and process-targeted Quartz
variants still produced lowercase `a`. Unicode events used the base keycode;
the legacy AX post call reported success without a guest effect. An
independent computer input route also altered the requested text. A host
virtual HID device was unavailable without its entitlement. This evidence
narrows the problem to a boundary after the host event stream, without proving
the exact Tart or Virtualization.framework mechanism.

The outer CLI now rejects modified input by default before sending a prefix.
The diagnostic override is explicit and does not apply to `type-secret`.
The latter uses the Tart application's actual focused-window accessibility
attribute, so a small Tart overlay cannot falsely block a correctly focused
VM. Live guest-file checks proved refusal left the next read intact and plain
text and an owner-only plain test secret still reached the guest. The normal
resident route remains the supported path for modified input after bootstrap.
The explicit diagnostic override still reproduced the altered guest bytes,
and the full Mac smoke suite passed.
