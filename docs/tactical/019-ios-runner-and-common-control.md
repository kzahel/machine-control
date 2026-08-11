# Tactical 019: iOS Runner and Common Control

Status: complete with physical-fixture gaps recorded.

Topics: `ios-device-control`, `capabilities-and-results`, and
`target-lifecycle-and-readiness`.

## Objective

Make the adopted physical-iOS provider usable for ordinary application and
semantic work through the common target-selecting client, while preserving
iOS-specific XCTest semantics. Make runner signing lifetime and preparation
truthful for both Apple Developer Program and free Personal Team profiles, and
strengthen the passcode-protected state sequence without placing a credential
back on the accepted passcode-free phone.

## Completion conditions

- `machine-control --target <ios-target> ios ...` exposes a bounded,
  explicitly iOS command family for capabilities, runner preparation,
  application launch/termination, semantic snapshot/press/fill, and Home.
- The iOS adapter accepts a typed request and returns the common result
  vocabulary with actual CoreDevice or XCTest route, delivery, independently
  observed effect where available, uncertainty, retry safety, and sanitized
  upstream data.
- Doctor reports the declared signing profile separately from observed runner
  provisioning lifetime and warns before a short-lived profile expires.
- Personal Team preparation refreshes only this configuration's matching
  runner build cache when its installed build profile is near expiry or when
  refresh is explicitly requested.
- Unit tests cover command allowlisting, result validation, upstream-error
  sanitization, signing-profile configuration, profile-expiry observation,
  bounded cache refresh, and passcoded before/after-first-unlock states.
- The current passcode-free phone proves runner preparation and representative
  common launch, snapshot, semantic action, and Home operations. Missing
  Personal Team or second passcoded-fixture acceptance remains explicit.
- Current platform, provider, topic, capability, setup, and recovery documents
  describe the result without exposing controller or device identity.

## Boundaries

- Do not create a generic mobile or desktop abstraction. The public command
  family is explicitly `ios`; its operations and capability declarations may
  differ from Android and Quest.
- Do not automate or transport iOS passcodes, biometrics, Trust confirmation,
  Apple Account login, signing-team selection, or protected authorization.
- Do not restore a passcode on the accepted passcode-free phone solely for
  coverage. Use deterministic state-sequence tests until a separate fixture is
  available.
- Do not claim a Personal Team live result from the current long-lived
  Developer Program profile. Apple-account enrollment and team choice remain
  one-time Xcode operator actions.
- Do not delete provisioning profiles, signing identities, account state, or
  unrelated Agent Device caches. Refresh may remove only matching derived
  runner products that are safe to rebuild.
- Do not expose arbitrary Agent Device dispatch through the common client;
  retain `testbed -- agent --` as the explicit provider escape hatch.

## Implementation steps

### 1 — model signing lifetime and bounded refresh

Add an explicit signing-profile declaration, inspect only the matching cached
runner's embedded provisioning lifetime, and project sanitized expiry state
into doctor. Keep account class declared and profile duration observed. On
Personal Team, rebuild matching products before their seven-day profile
expires; support an explicit refresh for recovery and testing.

### 2 — add typed iOS adapter operations

Define a narrow JSON request/result boundary in the iOS adapter. Translate the
owned operations to CoreDevice or pinned Agent Device commands, preserve the
provider's structured semantic data, strip device identity and diagnostic
paths, and distinguish observation, delivery, effect, and uncertainty.

### 3 — expose the iOS common client family

Add ergonomic client parsing and strict result validation for the adopted
operation subset. Require an iOS target, dispatch only through its
authoritative adapter, and include logical-target/client transport metadata.
Reject other device families and unrecognized operations without invoking an
adapter.

### 4 — strengthen authentication-state conformance

Exercise passcode-free readiness, passcode-protected post-reboot gating,
passcode-protected post-first-unlock readiness, unavailable lock observation,
and reboot delivery independently. Keep credential entry outside every
request, fixture, log, and test.

### 5 — validate the accepted physical route

Run platform and common checks, inspect identifier-free doctor/capabilities,
prepare the current runner, and perform a representative common Settings
launch, snapshot, semantic action, and Home sequence. Review all tracked
changes for public-data safety before committing.

## Validation plan

- `cd platforms/ios && pnpm check`
- `python3 -m unittest discover -s tests/client -v`
- `python3 bin/check --portable`
- common iOS doctor, capabilities, runner prepare, Settings launch, snapshot,
  semantic action, and Home on the accepted passcode-free phone
- `git diff --check`, JSON/schema validation, and public-data review

## Result

Completed 2026-08-11.

The common client now exposes an explicitly iOS command family rather than a
generic mobile abstraction. Its allowlist covers capabilities, runner prepare,
application install/launch/termination, semantic snapshot/press/fill, and Home.
Requests cross the common-client/adapter boundary over standard input. The
adapter maps them to CoreDevice or pinned Agent Device, sanitizes device and
controller identity, and returns `machine-control/v0` with actual route,
delivery, effect, uncertainty, retry safety, and provider attempts. Semantic
payloads retain Agent Device's snapshot-scoped `refsGeneration`; target
generation remains honestly unavailable.

Signing policy now declares `developer_program`, `personal_team`, or
`unspecified` independently of the team identifier. Doctor inspects the exact
matching cached runner's embedded profile lifetime and marks a fully observed
expired cache unavailable. A declared Personal Team automatically refreshes
within 48 hours of expiry. Explicit `prepare --refresh` removes only matching
Agent Device version/team/bundle derived products; tests prove unrelated caches
remain intact. Apple-account login, team choice, identities, and profiles are
never removed or automated.

Passcode-state conformance now covers protected post-reboot state, ready state
after local first unlock, passcode-free readiness, unavailable lock-state
observation, and reboot delivery without carrying a credential. The accepted
passcode-free phone's security policy was not changed and it was not rebooted
again for this slice.

### Validation record

- The iOS dependency-free suite passed 38 tests. New coverage includes signing
  declaration validation, short-lived near-expiry refresh, expired cache state,
  cache deletion scope, provider-result sanitization, settled action effects,
  and the passcoded first-unlock transition.
- The common client passed 49 tests. New cases prove iOS target gating,
  allowlisted requests over standard input, fill text absent from adapter
  arguments, strict result validation, and logical-target projection.
- The complete `python3 bin/check --portable` gate passed common client, shared
  ADB, workspace receipts, Android, ChromeOS, iOS, Quest, Steam Deck, tracked
  JSON, Bash syntax, and whitespace checks.
- Live common doctor remained ready with connection and interaction ready, no
  observed gate, and a valid long-lived cached runner profile. The new signing
  policy is not yet declared in private inventory, so doctor truthfully warns
  `unspecified` while reporting the observed lifetime separately.
- Live common capabilities returned all nine owned operations without the
  provider device descriptor. Runner prepare returned confirmed XCTest health.
  Settings launch, Home, an interactive SpringBoard snapshot, semantic Settings
  press, a separate 17-node Settings foreground snapshot, termination, and
  owned-daemon recovery all succeeded.
- The Settings press's own settled diff was empty, so its effect correctly
  remained `unverifiable`; the following foreground snapshot is independent
  evidence. No screenshot, UI content, controller path, device identifier,
  team identifier, signing asset, or local result was added to Git.

### Remaining acceptance gaps

- Free Personal Team limits and seven-day expiry are first-party documented;
  initial runner provisioning and near-expiry automatic renewal are implemented
  and unit-tested but require a separate free Xcode account/team for live
  acceptance. The current runner uses a long-lived Developer Program profile.
- A separate passcode-protected fixture is still needed to live-exercise the
  normalized post-reboot/manual-first-unlock and post-unlock sequence. Do not
  restore a passcode on the accepted passcode-free phone merely for coverage.
- The new common install path has CoreDevice inventory readback and unit-level
  contract coverage; this slice reused prior native install evidence rather
  than reinstalling a product solely to exercise the facade.
- Common `ios fill` transport is appropriate only for non-secret application
  text. Agent Device's downstream CLI has no one-shot protected secret channel,
  so passcodes and other protected credentials remain unsupported and human.
