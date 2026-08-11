# Physical iPhone Setup

## Controller requirements

- A Mac with full Xcode and the matching iOS platform support.
- Node.js 24 or newer, pnpm 11, and Python 3.10 or newer.
- A paid Apple Developer Program team signed into Xcode for long-lived
  development provisioning.
- An Apple Development certificate with its private key available in the login
  Keychain.

The Mac system Apple Account, the phone's Apple/iCloud account, and the Xcode
developer account are independent. The phone does not need the maintainer's
primary iCloud account.

## Phone preparation

1. Erase or otherwise prepare a dedicated test phone without personal data.
2. Connect it over USB, unlock it, select **Trust This Computer**, and accept
   the Mac pairing prompt.
3. Enable **Settings → Privacy & Security → Developer Mode** and complete the
   required reboot and local confirmation.
4. Open Xcode's device window once so it prepares developer services.
5. Allow Xcode automatic signing to register the phone to the paid team.
6. Enable macOS Developer Tools security once with
   `sudo DevToolsSecurity -enable` if `testmanagerd` attachment is denied.
7. Complete any first XCTest-launch Touch ID or password prompt locally.

Keep the phone on a supported, fully updated iOS release. A device can be
connected to Wi-Fi and still fail developer-certificate verification if its OS
trust state is stale; updating iOS resolved that condition during the initial
spike.

## Testbed configuration

Copy `config.example` to ignored `config.local` and set:

```bash
export IOS_DEVICE_TESTBED_DEVICE=iPhone
export IOS_DEVICE_TESTBED_TEAM_ID=<paid-team-id>
export IOS_DEVICE_TESTBED_RUNNER_BUNDLE_ID=com.example.iosdevicetestbed.runner
```

Use a unique physical-device name. Agent Device 0.20.5 rejected the physical
UDID returned by its own inventory while accepting the unique device name.
Never put a real UDID in committed documentation or examples.

The runner bundle ID must be unique to the developer team and dedicated to this
testbed. It is separate from every application under test.

## Provisioning lifetime

A free Personal Team normally gives short-lived development provisioning. The
validated controller uses a paid team, so weekly reprovisioning is not expected.
Certificates, membership, and Xcode-managed profiles still expire on their
normal longer schedules. Run `doctor` before a campaign and `prepare` after an
Xcode, iOS, Agent Device, certificate, or provisioning change.
