# Recovery

## Start with observation

```bash
bin/ios-device probe
bin/ios-device status
bin/ios-device doctor
```

These commands do not start, install, unlock, repair, or otherwise mutate the
phone. Resolve cable, pairing, unlock, Developer Mode, Xcode, certificate, and
configuration failures before retrying automation.

If Apple's Developer Mode inventory sees the exact configured phone but normal
CoreDevice discovery has not converged, use the explicit bootstrap operation:

```bash
bin/ios-device pair
```

`pair` holds the device lease and attempts only CoreDevice pairing for that
exact selector. Confirm Trust on the phone. A passcode-protected phone also
requires its passcode locally; a passcode-free phone does not. The wrapper
never receives the credential or prints the device identifier.

## After a full reboot

`reboot` separately observes delivery, disappearance, and return of the same
physical phone. Its successful exit means the phone rebooted and reconnected,
not necessarily that XCTest is authorized:

- On a passcode-free dedicated phone with wired accessories allowed, doctor
  should return `interaction: unlocked` and `interactionGate: none_observed`.
  Run `prepare` if the cached runner still needs a health-check.
- On a passcode-protected phone, doctor can return connection ready while
  reporting `interaction: protected` and
  `interactionGate: manual_first_unlock_required`. Unlock once locally, then
  rerun doctor or prepare. Do not treat this expected state as reconnect
  failure and do not retry a credential.
- If connection returns but lock-state observation is temporarily unavailable,
  doctor preserves connection and reports an unverified interaction gate. Wait
  or diagnose CoreDevice rather than pretending the phone is disconnected.

## Interrupted testbed session

A transactional session records a private controller-local `lease.json` and
cleans the named Agent Device session and dedicated daemon on ordinary exit.
If the controlling process dies, the next session may recover a dead lease from
the same controller. Explicit recovery is:

```bash
bin/ios-device recover
```

Recovery stops only the daemon in this testbed's isolated state directory and
removes its stale lease. It does not uninstall apps, erase data, change phone
settings, revoke pairing, delete certificates, or remove profiles.

If the recorded owner PID is still alive or the journal belongs to another
controller, recovery refuses. Inspect that owner first. Use `recover --force`
only after confirming no live automation owns the phone.

## Runner does not connect

1. If doctor reports a manual gate, unlock the phone locally.
2. Confirm `probe` is `connected` and `doctor` sees Developer Mode.
3. Run `recover` to stop stale testbed-owned processes.
4. Run `prepare` to rebuild or health-check the signed runner.
5. Complete any local Touch ID, password, trust, or developer-certificate
   prompt.

After an Xcode or Agent Device upgrade, stale derived products should not be
reused across incompatible versions. Agent Device normally detects and rebuilds
bad exact-cache artifacts. If it cannot, move the testbed state aside for
inspection. Agent Device 0.20.5 stores Apple build products separately under
`~/.agent-device/apple-runner/derived`; inspect and move only the exact failing
`ios-device` cache entry if upstream diagnostics specifically identify it.
Never delete broad user directories.

## Signing failure

- Verify the paid developer account is still signed into Xcode.
- Verify a valid Apple Development identity and private key exist in Keychain.
- Verify the phone remains registered to the team and the managed profile has
  not expired.
- Verify `config.local` selects the correct team and unique runner bundle ID.
- If this is a new phone, register it through Xcode before retrying `prepare`.

Never copy certificates, private keys, profiles, account credentials, or signed
runner products into this repository.

## Human handoff

Unlock, Touch ID, Face ID, passcodes, account recovery, Apple Pay, CAPTCHAs, and
security-warning bypasses are local human actions. Stop and request handoff
instead of retrying coordinates or changing OS security settings.
