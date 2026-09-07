# libimobiledevice

Upstream: [libimobiledevice/libimobiledevice](https://github.com/libimobiledevice/libimobiledevice)

Declared license:
[LGPL-2.1-or-later](https://github.com/libimobiledevice/libimobiledevice/blob/master/COPYING.LESSER)
for the repository.

Last corpus review: 2026-09-07.

## Evidence by platform

| Platform | Level | Evidence and limit |
| --- | --- | --- |
| Physical iOS on macOS | `adopted` | Stable Homebrew 1.4.0 `idevicesyslog` connected to the accepted paired phone, streamed `os_trace_relay`, and passed bounded transactional collection plus abandoned-stream cleanup |
| Other Apple devices and hosts | `upstream-claimed` | Upstream supports multiple Apple device services and macOS/Linux/Windows hosts; this project has not tested those combinations |

## Architecture and depth

libimobiledevice is a native protocol library and CLI suite for communicating
with Apple devices without linking Apple's private frameworks. The adopted
surface is intentionally one command: `idevicesyslog`. In 1.4.0 it uses
`os_trace_relay` by default, supports exact UDID selection, process and text
filters, and logarchive retrieval; `--syslog-relay` selects the older service.

The CLI emits a high-volume text stream rather than structured records. The
iOS adapter therefore keeps it behind the device lease, spools only the newest
16 MiB in private state, returns no log text inline, and materializes a bounded
create-only artifact when collection stops. Session cleanup stops and discards
an abandoned capture.

libimobiledevice also offers application, crash-report, file, pairing, and
diagnostic operations. Machine Control does not adopt those duplicates where
CoreDevice already supplies a live-tested native route. In particular, crash
inventory and collection stay on CoreDevice's `systemCrashLogs` domain.

## North Star fit

The library fills a narrow gap in the authoritative device-host provider while
preserving exact physical-device selection and the common capability/result
surface. It does not run on the phone, provide semantic UI control, replace
CoreDevice/XCTest, or create an arbitrary shell.

## Current disposition

**Decision:** Adopt stable libimobiledevice only for physical-iOS system-log
capture. Prefer the Homebrew bottle on macOS and require version 1.4.0 or newer,
where `os_trace_relay` is present.

**Decision:** Do not add pymobiledevice3 for the same operation. Its structured
stream and broader service coverage are useful, but they add a Python runtime
and optional modern developer-tunnel surface that this accepted USB logging
route does not require. Reconsider it only for a future capability that
CoreDevice and libimobiledevice cannot reasonably provide.

**Open:** Add process/text filtering or bounded logarchive capture only when a
real debugging workflow needs it. The accepted first surface is a bounded raw
transactional window.
