# Physical iPhone Setup

## Controller requirements

- A Mac with full Xcode and the matching iOS platform support.
- Node.js 24 or newer, pnpm 11, and Python 3.10 or newer.
- An Apple development team signed into Xcode. The validated long-lived setup
  uses an Apple Developer Program team. A free Personal Team is supported as a
  distinct short-lived signing profile, but remains to be physically accepted
  with a separate free account/team.
- An Apple Development certificate with its private key available in the login
  Keychain.

The Mac system Apple Account, the phone's Apple/iCloud account, and the Xcode
developer account are independent. The phone does not need the maintainer's
primary iCloud account.

## Phone preparation

1. Erase or otherwise prepare a dedicated test phone without personal data.
2. Configure `IOS_DEVICE_TESTBED_DEVICE` with one exact private device name,
   connect it over USB, unlock it, and run `bin/ios-device pair`. Select
   **Trust This Computer** and, when the phone has a passcode, enter it locally.
3. Enable **Settings → Privacy & Security → Developer Mode** and complete the
   required reboot and local confirmation.
4. Open Xcode's device window once so it prepares developer services.
5. Allow Xcode automatic signing to register the phone to the configured team.
6. Enable macOS Developer Tools security once with
   `sudo DevToolsSecurity -enable` if `testmanagerd` attachment is denied.
7. Choose one of the passcode profiles below, then run `prepare`. Complete any
   first XCTest-launch Touch ID or password prompt locally.

Keep the phone on a supported, fully updated iOS release. A device can be
connected to Wi-Fi and still fail developer-certificate verification if its OS
trust state is stale; updating iOS resolved that condition during the initial
spike.

## Passcode profiles

Both profiles use the same provider and common target surface:

- **Passcode-free dedicated device:** Remove Touch ID or Face ID enrollment,
  turn off the passcode, and set **Settings → Privacy & Security → Wired
  Accessories → Always Allow**. On an Apple-silicon Mac laptop, approve the
  phone and choose an appropriate **Privacy & Security → Accessories** policy;
  a dedicated controller can use **Always Allow**, while a general-purpose Mac
  should prefer **Automatically Allow When Unlocked**. Run `pair` again if the
  Trust flow does not converge after the passcode change. This profile is
  live-proven through remote full reboot and post-reboot XCTest preparation.
- **Passcode-protected device:** Keep the passcode and biometrics enabled.
  Ordinary automation works after the phone has been unlocked locally since
  boot. After every full reboot, doctor reports a protected interaction and
  `manual_first_unlock_required` until that local action occurs. The provider
  does not request, transport, store, or enter the passcode.

Apple's `devmodectl` supports passcode-free Developer Mode automation. The
wrapper uses that inventory only for discovery; it does not silently change
Developer Mode. Apple Configurator supervision is optional for repeatable lab
provisioning and does not require MDM, but preparing an already activated phone
for supervision erases it. It was not needed for the current passcode-free
acceptance.

## Testbed configuration

Copy `config.example` to ignored `config.local` and set:

```bash
export IOS_DEVICE_TESTBED_DEVICE=iPhone
export IOS_DEVICE_TESTBED_TEAM_ID=<apple-team-id>
export IOS_DEVICE_TESTBED_RUNNER_BUNDLE_ID=com.example.iosdevicetestbed.runner
export IOS_DEVICE_TESTBED_SIGNING_PROFILE=developer_program
```

Use `personal_team` for a free Xcode Personal Team. The declaration controls
renewal policy only; the adapter deliberately does not infer account class from
the team identifier. Xcode account sign-in and team selection remain manual.

Use a unique physical-device name. Agent Device 0.20.5 rejected the physical
UDID returned by its own inventory while accepting the unique device name.
Never put a real UDID in committed documentation or examples.

The runner bundle ID must be unique to the developer team and dedicated to this
testbed. It is separate from every application under test.

## Provisioning lifetime

Apple's [developer-account
documentation](https://developer.apple.com/help/account/basics/about-your-developer-account)
states that a free Personal Team permits on-device Xcode testing but limits it
to ten App IDs, three devices, and three installed apps per device; its App
IDs, device registrations, and install profiles expire after seven days.
XCTest runner products consume the same finite signing resources, so reserve
capacity for both the runner and applications under test.

Doctor reports the configured account policy separately from the embedded
profile's observed lifetime and expiration. A matching expired runner cache is
not ready. With `personal_team`, `prepare` removes only this team/bundle's
matching derived products and rebuilds when no more than 48 hours remain:

```bash
bin/ios-device doctor
bin/ios-device prepare
bin/ios-device prepare --refresh  # explicit recovery/reprovisioning
```

The current physical acceptance uses a long-lived Developer Program profile,
so weekly reprovisioning is not expected. Certificates, membership, and
Xcode-managed profiles still expire on their normal schedules. Run `doctor`
before a campaign and `prepare` after an Xcode, iOS, Agent Device, certificate,
or provisioning change.
