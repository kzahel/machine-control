# Tactical 031: iOS Diagnostic and Lifecycle Operation Parity

Status: proposed.

Topics: `ios-device-control`, `capabilities-and-results`, and
`android-family-control`.

## Objective

Give an agent driving the accepted physical iPhone the diagnostic and
lifecycle operations it already has on the Android family, using CoreDevice
and the pinned Agent Device provider rather than a new control model. After
this slice an agent can open a URL into an installed app, capture bounded
application logs, list and uninstall applications, and copy files into and out
of a developer-installed app's data container, all through typed operations
with the common result vocabulary.

The gap this closes is recorded in the
[topic](../../topics/ios-device-control.md#operation-coverage-gap-against-the-android-family);
route candidates are compared in the
[platform report](../../research/platforms/ios.md#route-comparison-for-uncovered-operations).

## Completion conditions

- The wrapper exposes typed `open-url`, `logs` capture, `uninstall`, `apps`,
  `processes`, and `copy` operations that route through CoreDevice or the
  pinned Agent Device and return `machine-control/v0` results with actual
  route, delivery, independently observed effect where available, uncertainty,
  and retry safety.
- URL open reports whether it launched the named bundle with a payload URL or
  observed system routing through a link press, and never claims the latter
  from the former.
- Log capture writes a bounded artifact to a caller-chosen path outside the
  repository, matching the Android `logcat OUTPUT` contract, and returns its
  path plus line count rather than inline device output.
- The common `ios` family allowlists each new operation only after its live
  acceptance on the accepted passcode-free phone.
- Unit tests cover argument allowlisting, URL and path validation, result
  sanitization, and refusal paths for unknown bundles and unsupported domains.
- The capability matrix, wrapper README, setup, and topic documents describe
  the result without exposing controller or device identity.

## Boundaries

- Do not add an arbitrary shell, provider dispatch, or filesystem-wide
  operation. Stock iOS offers no shell, and the project exposes typed
  capabilities only. Record the absence as a boundary in capability output.
- Do not add a jailbreak, developer disk image, or supervision requirement.
- Do not add a second iOS provider dependency in this slice. Evaluate a system
  `os_log` route separately if app-scoped console capture proves insufficient.
- Do not transport passcodes, biometrics, or account credentials. A URL can
  carry an embedded token; treat URL arguments as potentially sensitive, keep
  them out of logs and results, and never commit a captured log artifact.
- Do not automate the simulator. Physical-device identity and simulator
  identity remain a separate open question.
- Do not restore a passcode on the accepted phone for coverage.

## Implementation steps

### 1 — open a URL into an installed application

Add a wrapper operation that opens a custom-scheme or `https` URL into a named
bundle through Agent Device `open`, which uses CoreDevice
`process launch --payload-url`. Require the bundle identifier explicitly rather
than depending on session state. Return the CoreDevice launch result as
delivery and a following foreground snapshot as separate effect evidence.
Document that this exercises the application's URL handling, not iOS's
system-routing choice, and that routing is observed by pressing a link in
another application and snapshotting the foreground.

### 2 — capture bounded application logs

Expose a `logs` operation that uses Agent Device `logs clear --restart` and
`logs path` so the session app is relaunched under CoreDevice `--console` and
its stdout and stderr are captured to a file. Copy or reference that file at a
caller-chosen path outside the repository, bound its size, and return path,
byte count, and truncation state. Record in capability output that this is
application-scoped and that system daemon and SpringBoard lines are not
captured.

### 3 — list applications and processes, and uninstall

Wrap CoreDevice `info apps`, `info processes`, and `uninstall app`. Sanitize
device identity and controller paths from the JSON output. Make uninstall
refuse bundles that the adapter did not install or that match Apple system
bundle prefixes, and require the exact bundle identifier.

### 4 — copy files to and from an application data container

Wrap CoreDevice `copy to` and `copy from` restricted to
`--domain-type appDataContainer` for an explicit bundle identifier. Reject
other domain types, relative destinations, and paths outside the caller's
declared source or destination. Record that this works only for
development-installed applications.

### 5 — expose the operations through the common facade

Extend the iOS adapter request allowlist and the common client's `ios` family
with the accepted operations, keeping the family explicitly iOS. Update
`IOS_CONTROL_OPERATIONS`, the capability declaration, and result validation
tests. Include the arbitrary-shell and wake/keyguard non-parity as declared
boundaries in `capabilities` output.

### 6 — validate on the accepted phone and record the matrix

Live-test each operation with a development-installed application: open a
custom-scheme URL, open an `https` universal link, capture logs across a
reproduced action, list apps and processes, copy a file in and out, and
uninstall. Move each proven row into the capability matrix, and leave
unproven rows under "Not yet proven".

## Validation plan

- `cd platforms/ios && pnpm check`
- `python3 -m unittest discover -s platforms/ios/tests -v`
- `python3 -m unittest discover -s tests/client -v`
- `python3 bin/check --portable`
- live common `ios` URL open, log capture, app and process listing, container
  copy, and uninstall on the accepted passcode-free phone
- `git diff --check`, JSON/schema validation, and public-data review of every
  document and test fixture

## Result

Not started.
