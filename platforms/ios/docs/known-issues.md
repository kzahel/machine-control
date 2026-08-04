# Known Issues

These observations apply to Agent Device 0.20.5 unless stated otherwise.

## Signing environment is daemon-start state

The Agent Device daemon inherits the Apple team and bundle configuration when
it starts. A daemon first launched without the testbed environment reused
upstream placeholder signing values and failed every later runner build until
it was stopped.

The wrapper prevents this by using a dedicated state directory, always setting
the signing environment, and cleaning its own daemon at transactional-session
exit. Do not invoke bare `agent-device` against testbed state.

The 0.20.5 Apple compilation cache remains user-wide at
`~/.agent-device/apple-runner/derived`; it is not controlled by
`AGENT_DEVICE_STATE_DIR`. Its signing/build inputs participate in the cache
key. Recovery deliberately leaves those reusable build products intact.

## Device selection

`doctor` background warming selected an unavailable Vision Pro simulator when
the physical phone was the only connected booted target. The version also
rejected the UDID returned by its own device inventory while accepting the
unique device name. The wrapper performs its own CoreDevice selection and
passes an explicit physical name.

## First device registration

`prepare ios-runner` passes `-allowProvisioningUpdates` but not
`-allowProvisioningDeviceRegistration`. A newly attached phone may need Xcode
to register it first. The initial spike required one device-specific Xcode
build with registration allowed; later prepares reused the resulting profile.

## Keychain prompts

A newly created signing private key may prompt once per concurrent `codesign`
process. Grant `/usr/bin/codesign` **Always Allow** only after verifying the
request and selected key. Do not disable Keychain protections globally.

## Automation presentation

The physical display may remain on Apple's **Automation Running** presentation
while commands execute. Runner snapshots and screenshots still show the real
underlying target UI. End the session and use `normal-launch` when a human needs
the normal on-device presentation.

## Keyboard dismissal

iOS does not have a safe app-agnostic keyboard blur action. `keyboard dismiss`
can report unsupported when no Done-like native control exists. Do not tap an
arbitrary heading to hide it: the heading may belong to a tappable parent.
Scroll the intended control into view or activate it semantically through the
keyboard when safe.

## Snapshot latency

Physical snapshots sometimes take several seconds. Prefer compact interactive
snapshots, small scopes, settled diffs, and assertions. Do not poll at video
rates. Investigate sustained latency before layering retries on top.

## Version sensitivity

The runner uses Xcode/XCTest behavior that changes across Xcode and iOS
versions. Pin Agent Device and rerun the physical capability matrix after any
upgrade. Keep an Appium/WebDriverAgent fallback and experimental CoreDevice
screen/HID work provider-neutral rather than embedding them into project tests.
