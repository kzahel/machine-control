# iOS Device Testbed Agent Guide

This platform directory is the canonical public source. Do not make
implementation changes in the legacy `ios-device-testbed` checkout.

This repository owns project-neutral control of a physical iPhone through
Xcode, CoreDevice, and a pinned Agent Device XCTest runner. Consuming projects
own application builds, fixtures, and product-specific assertions.

Start with `bin/ios-device probe` and `bin/ios-device doctor`. Run mutating or
multi-step work through `bin/ios-device session -- COMMAND` so the physical
device has one owner and runner cleanup happens on exit. Use the wrapper rather
than invoking `agent-device` directly; it supplies the signing environment,
explicit device selection, isolated state directory, and session policy.

Never select the first arbitrary Apple device or simulator. Refuse ambiguous
device names. Never commit a device UDID, Apple account, certificate, private
key, provisioning profile, signed product, local path, session log, or captured
private UI. Keep controller settings in ignored `config.local`.

Do not attempt to automate passcodes, biometrics, Apple Pay, CAPTCHAs, account
recovery, or security-warning bypasses. Report these as human gates. Do not
weaken Developer Mode, pairing, signing, Keychain, or macOS privacy controls to
make automation more convenient.

`probe`, `status`, and `doctor` must remain read-only with respect to the phone.
`prepare`, `install`, Agent Device actions, and `session` may mutate only the
explicitly selected testbed device. Recovery may stop only this repository's
dedicated Agent Device daemon and lease.

Before committing behavior changes, run:

```bash
pnpm check
bin/ios-device probe
bin/ios-device doctor
```

When signing, device selection, runner lifecycle, or recovery changes, also run
`bin/ios-device prepare` and one transactional physical-device session.
