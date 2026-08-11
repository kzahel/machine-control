# Three-Desktop Common-Entry Evidence

Date: 2026-08-11.

Status: current live evidence for the accepted Windows, macOS, and Linux
desktop appliances.

## Scope

[`Tactical 013`](../tactical/013-unified-desktop-entry-and-conformance.md)
exercised one target-selecting client against all three authoritative testbed
adapters. Every run enabled the testbed's outer-UI prohibition before checking
readiness. Ordinary status, capabilities, application launch, semantic
snapshot/action, input, target-native capture, and bounded artifact retrieval
went through [`bin/machine-control`](../../bin/machine-control).

Fixture deployment/reset, independent state reads, and cleanup used the
client's explicit `testbed` or `os` escape hatches. They were effect oracles,
not alternate desktop-control routes.

## Accepted results

| Profile | Status route | Semantic route | Capture route | Independent press effect | Unicode effect |
| --- | --- | --- | --- | --- | --- |
| Windows 11 desktop | `windows.user_session/input_desktop` | Cua exact-window semantics/action | Cua exact-window capture | confirmed | not present in the shared fixture |
| macOS Aqua Tart | `guest.user/macos.resident` | native Accessibility | native Quartz | confirmed | confirmed |
| Ubuntu GNOME Wayland | `guest.user/linux.atspi` | native AT-SPI | target-native GNOME screenshot | confirmed | confirmed |

For every profile:

- `doctor` reported ready with `states.outer: prohibited`;
- outside and guest-local status returned the same resident generation;
- accepted resident results reported `hostInterference: none`;
- the semantic action changed independently read application state;
- capture returned a target-created handle and bounded retrieval produced a
  nonempty PNG; and
- cleanup completed before a common `target shutdown`, after which common
  `target status` reported `powerState: off`.

The Windows shared fixture has no editable text element, so this one corpus
does not repeat its Unicode-input proof. Windows Unicode delivery remains
accepted by the deeper Windows platform conformance suite; the shared result
reports the fixture omission rather than pretending it was tested here.

## Efficiency sample

These are single-run transport observations, useful as a baseline rather than
a performance guarantee:

| Profile | Doctor | Snapshot result | Snapshot transport | Action transport | Capture transport | PNG |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Windows | 35,789 ms | 1,211 B | 10,213 ms | 8,561 ms | 18,636 ms | 14,445 B |
| macOS | 7,291 ms | 1,014 B | 3,574 ms | 3,830 ms | 3,669 ms | 87,753 B |
| Linux | 19,365 ms | 736 B | 6,215 ms | 4,968 ms | 6,220 ms | 20,014 B |

The retained Windows image predates the mandatory `hostInterference` field.
The common client applied and disclosed its narrowly scoped compatibility
projection. Newly published Windows runtimes emit the field directly.

No raw logs, target identifiers, addresses, user names, guest paths,
credentials, generations, or artifact handles are retained in this evidence.
