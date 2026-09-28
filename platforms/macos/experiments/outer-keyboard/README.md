# Tart outer modifier delivery

**Current (2026-09-28):** A controlled guest-effect comparison on Tart 2.30.5,
with macOS 26.6.2 on host and prepared guest, isolated missing device-dependent
modifier flags in the host sender. No Tart patch, virtual HID device, guest
input provider, or host entitlement change was needed.

## Method and observations

The initial Terminal `read` oracle wrote `AbC!@Z` exactly after adding the
left-Shift bit to the general Shift flag. A separate disposable AppKit guest
fixture then compared four event forms. It records text from its text field
and counts actual menu actions bound to Command–K and Shift–Command–K in a
guest-owned JSON file. The agent prepares and reads this oracle through the
guest command channel; every tested keystroke goes through the outer CLI.
The fixture does not inject input or request Accessibility permission.

| Event form | Requested `AbC!@Z` | Command–K / Shift–Command–K |
| --- | --- | --- |
| Original general flags only | `abc12z` | Literal `kk`, neither action |
| General flags + explicit `flagsChanged` | `abc12z` | Literal `kk`, neither action |
| General + left/right device flags | Exact | One invocation of each action |
| General + device flags + explicit `flagsChanged` | Exact | One invocation of each action |

A first comparison was interrupted because unexpected host typing contaminated
its text. Its cleanup suspended the VM and released the claim. The table uses
the clean rerun after the controller user made the host available.

## Interpretation and adopted form

Apple's [public SDK definitions](https://github.com/apple-oss-distributions/IOHIDFamily/blob/main/IOHIDSystem/IOKit/hidsystem/IOLLEvent.h)
in `IOKit/hidsystem/IOLLEvent.h` define separate
`NX_DEVICELSHIFTKEYMASK` and `NX_DEVICELCMDKEYMASK` bits in addition to the
general masks. The sender had overwritten the complete event flags with only
the general masks. Preserving the matching left-side bits changes the observed
guest effect. This isolates a sufficient sender-side correction; it does not
identify which private Tart/Virtualization.framework routine uses those bits.

The corrected sender uses explicit `flagsChanged` modifier transitions, the
matching device bits throughout the chord, and reverse-order release. The
implementation imports the SDK constants rather than copying provider code.
Shift and Command are the verified scope. Control, Option, and Fn still need
an explicit non-secret diagnostic override; their effect is not inferred from
Shift/Command success. System-reserved shortcuts remain a separate Tart
capture setting.

## Reproduce acceptance

Use a prepared, suspended exact target resolved by private inventory, and an
uninterrupted host desktop:

```bash
python3 platforms/macos/tests/outer-keyboard-live.py --target macos
```

The runner performs common read-only doctor, acquires a disruptive claim,
resumes the VM, installs a disposable guest oracle in a unique scratch
directory, and verifies text, menu effects, releases, refusal without a prefix,
and a public dummy value through `type-secret` into a secure field. The latter
oracle records only a match boolean. The corrected runner selects its dummy through an owner-only temporary target
registry, so the real inventory credential cannot override it. Each fixture
has a unique application identity and reports the active field. Cleanup checks
the recorded PID/executable and observes process exit before removing files,
suspending the VM, and releasing the claim. Captures stay outside Git. The
[tactical record](../../../../docs/tactical/045-macos-tart-outer-keyboard.md)
records the credential-selection and path-alias mistakes found while building
the harness, including cleanup.

**Validation:** Three diagnostic repetitions and the corrected production-CLI
acceptance passed exact text, real menu effects, modifier release, refusal
without a prefix, and dummy secure-field entry. Both modifier orders passed.
The complete Mac smoke suite passed. Final cleanup verified fixture process
exit and file removal; the VM was suspended and the claim released.

This is bootstrap-route evidence on a prepared guest, not a repeated Setup
Assistant or real-account password trial. The input path itself has no guest
agent dependency. Ordinary post-bootstrap control remains target-resident.
