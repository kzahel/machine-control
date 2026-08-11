# Validated Capabilities

Last physical-device validation: 2026-08-04.

Validated combination:

- iPhone SE (3rd generation), iOS 26.6.
- Apple-silicon macOS controller, Xcode 26.6.
- Paid Apple Developer Program team and Xcode-managed development profile.
- Agent Device 0.20.5.

## Proven

| Capability | Evidence |
| --- | --- |
| Runner preparation | XCTest host/runner built, signed, installed, started, and health-checked over USB |
| Provider lifecycle | Pinned wrapper probe, doctor, prepare, exclusive session lease, semantic snapshot/assertion, screenshot, Home action, daemon stop, and lease cleanup passed end-to-end |
| App installation | The wrapper installed a development-signed JSTorrent `.app` through CoreDevice |
| Ordinary app snapshot | Settings and JSTorrent returned roles, labels, values, state, frames, and refs |
| Semantic navigation | Ref/selector actions opened Settings, returned Back, and navigated SwiftUI sheets |
| Text entry | A 524-character canonical magnet link filled into a physical SwiftUI text field |
| Keyboard-obscured controls | Small semantic scroll exposed and activated Add while the keyboard remained visible |
| Coordinate input | Resolved actions emitted physical coordinate taps; raw point input is available |
| Gestures | Physical scrolling is proven; swipe and long-press are exposed by the runner |
| SpringBoard | A 77-node tree exposed widgets, icons, folders, pages, and the Dock |
| System launch | A semantic Safari Dock ref launched Safari on the real phone |
| Home navigation | The runner returned from Safari to physical SpringBoard |
| Evidence | Physical screenshots captured Safari, Home Screen, and JSTorrent underneath the automation presentation |
| Product state assertion | Big Buck Bunny progressed from Fetching Metadata to 100% Seeding |
| Reboot/update reuse | The cached signed runner worked after reboot and an iOS update, with a first-launch local-authentication gate |

Healthy initial snapshots measured 313–569 ms. The later JSTorrent run reported
approximately 4.4-second p95 snapshots while the runner/device was under load.
Track both latency and cause instead of treating one number as a stable SLA.

## Not yet proven

- An ordinary system permission alert on the physical device.
- USB disconnect/reconnect with automatic runner recovery.
- App switcher behavior on the physical phone.
- Multi-touch, pinch, rotate, and complex drag paths.
- Protected or intentionally obscured screen capture.
- Long-duration session stability and lease interruption recovery.
- Multiple simultaneously connected physical iOS devices.

## Expected boundaries

Accessibility-first automation is the primary path. Screenshots and coordinates
are valid fallbacks for canvas, custom-drawn, or poorly labeled UI, but they are
less stable across layout, orientation, text size, and OS changes.

Passcodes, biometrics, Apple Pay, CAPTCHAs, account recovery, and protected
security confirmations require a human. A screenshot or accessibility tree may
omit, obscure, or refuse protected content. Treat that as a boundary, not as a
reason to weaken the device.
