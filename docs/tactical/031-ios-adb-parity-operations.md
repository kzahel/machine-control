# Tactical 031: iOS Debugging and Diagnostic Operations

Status: complete.

Topics: `ios-device-control`, `capabilities-and-results`, and
`android-family-control`.

## Objective

Make an agent materially better at diagnosing and manipulating applications on
the accepted physical iPhone. Explore the useful application-management,
diagnostic, and file-exchange facilities already available through CoreDevice
and the pinned Agent Device XCTest provider; retain the routes that prove
reliable and useful; and expose the adopted subset as typed iOS operations with
the common result vocabulary.

Android's ADB surface is a source of debugging use cases, not a parity
checklist. The iOS surface should use the strongest reasonable native route for
each operation and preserve its actual scope and limitations rather than force
an Android-shaped abstraction.

The resulting surface is recorded in the
[topic](../../topics/ios-device-control.md#diagnostic-operation-coverage);
route candidates are compared in the
[platform report](../../research/platforms/ios.md#route-comparison-for-diagnostic-operations).

## Intended outcome

An agent testing an iOS application should be able to do more than launch it
and operate its visible UI. The accepted surface should cover as much of this
workflow as the live provider evidence supports:

- invoke an installed application with a test URL or deep link;
- inspect installed development applications and relevant running processes;
- collect useful, bounded application diagnostics;
- install, verify, terminate, and safely remove a disposable development app;
- exchange fixtures, databases, exports, or other bounded files with an
  application's data container; and
- use those observations as evidence alongside XCTest snapshots and actions.

TomConnect, maintained in the private `tomfit-app` repository, is the primary
acceptance application because it is expected to be the main near-term iOS
system under test. Use a development or QA build and private local test data.
Do not record its private controller configuration, signing material, member
account data, captured logs, machine-link payloads, or device identity here.

## Completion conditions

- The accepted physical-iOS testbed has materially better support for
  diagnosing and manipulating development and QA applications.
- Every adopted operation has a typed wrapper request, a bounded normalized
  result, an actual provider route, honest delivery/effect/uncertainty fields,
  and focused refusal tests.
- An operation enters the common `ios` family only after the platform wrapper
  proves its route and result shape on the accepted phone. Common-facade
  acceptance then repeats the useful workflow.
- TomConnect exercises the adopted operations that its available development
  build supports. A smaller disposable fixture may cover destructive or
  deterministic behavior that should not be imposed on TomConnect.
- Candidate operations that are unreliable, excessively broad, redundant, or
  not useful are recorded as limited, rejected, or deferred rather than being
  forced into the common facade.
- The capability matrix, wrapper README, setup guidance where needed, provider
  and platform research, and owning topic describe the resulting surface
  without exposing private infrastructure or captured application data.

## Boundaries

- Do not add an arbitrary shell, arbitrary provider dispatch, or
  filesystem-wide operation. Stock iOS has no general shell, and the project
  exposes typed capabilities.
- Do not add a jailbreak, a separately managed developer disk image,
  supervision, or a second iOS provider merely to complete a checklist.
- Do not automate passcodes, biometrics, account credentials, protected
  confirmations, or payment surfaces. TomConnect test URLs and test accounts
  are application data: use them only in private live validation and do not
  commit or echo them in durable evidence.
- Restrict file exchange to an explicit application data-container domain and
  bounded caller-selected files. Do not generalize it into device filesystem
  access.
- Perform uninstall acceptance only on an explicitly selected removable
  development build. Report that uninstall removes its application container,
  and independently confirm the intended bundle is absent. The installed
  TomConnect development build is explicitly authorized for this run.
- Keep generated logs, copied data, screenshots, and other application
  artifacts outside the repository and remove them after acceptance.
- Do not automate the simulator in this slice. Physical-device and simulator
  identity remain a separate open question.
- Do not restore a passcode on the accepted phone for coverage.

## Candidate capabilities

These are investigation candidates, not mandatory one-to-one deliverables:

| Debugging need | Preferred first probe | Adoption question |
| --- | --- | --- |
| URL or deep-link delivery | Agent Device `open` or direct CoreDevice `process launch --payload-url` | Can the route target an explicit bundle, avoid stale session dependence, and distinguish direct payload delivery from iOS system routing? |
| Application logs | Agent Device session logs backed by CoreDevice `process launch --console` | Can an agent delimit a useful action window, stop capture reliably, and collect a bounded artifact without leaving provider state running? |
| Development-app inventory | CoreDevice `device info apps` | Which stable, privacy-minimized fields are useful for selection, install verification, and cleanup? |
| Relevant process inventory | CoreDevice `device info processes` | Is a bounded standalone projection useful, or should process evidence attach only to lifecycle results? |
| Safe uninstall | CoreDevice `device uninstall app` plus inventory readback | Can the wrapper prove the exact disposable/development bundle is eligible and confirm its absence afterward? |
| App-container file exchange | CoreDevice `device copy to|from` with `appDataContainer` | Which source/destination path rules, size bounds, overwrite behavior, and readback evidence are reliable on the accepted build? |

The first pass treated system `os_log` and crash-report collection as possible
follow-up work. The required extension below brought both into this tactical
after the near-term TomConnect debugging workflow established the concrete
need. Notifications, richer gestures, and other facilities remain outside the
slice.

## Adaptive implementation approach

### 1 — establish the live application baseline

Run the iOS wrapper's read-only probe and doctor. Identify the installed
TomConnect development or QA build and its current CoreDevice/XCTest behavior
without writing private identifiers into this repository. If a current signed
device build is available locally, use the existing typed installer; otherwise
begin with the installed build and record which destructive tests require a
separate fixture.

Run mutating and multi-step experiments through one transactional
`bin/ios-device session -- COMMAND` so the physical device has one owner and
the Agent Device session and daemon are cleaned up.

### 2 — probe each native route before fixing its contract

Exercise the candidate CoreDevice and Agent Device commands through the
authoritative wrapper or a bounded development spike. Inspect their structured
output, timing, state lifetime, failure behavior, privacy exposure, and value in
a real TomConnect debugging workflow.

Prefer CoreDevice for operations it directly owns. Reuse Agent Device where it
adds useful session, application-resolution, or XCTest integration. Do not
preserve a proposed provider choice when the live route shows a simpler or more
truthful implementation.

### 3 — adopt useful platform operations incrementally

For each successful candidate:

1. define the smallest typed request and normalized result that serves the
   observed debugging need;
2. validate exact bundle, URL, path, direction, bounds, and overwrite inputs as
   applicable;
3. keep raw CoreDevice documents and captured application output out of the
   normalized result unless a minimized field is deliberately adopted;
4. distinguish observation, delivery, independently observed effect, and
   unknown outcome;
5. add unit tests for accepted arguments, refusal paths, sanitization, retry
   safety, and cleanup; and
6. live-test the platform operation again on the accepted phone.

Combine operations when the evidence shows that a standalone surface would be
noisy or misleading. Split stateful operations, such as log collection, when a
single command cannot honestly represent the workflow.

### 4 — expose the proven subset through the common facade

Extend `IOS_CONTROL_OPERATIONS`, the capability declaration, and the common
client only for operations accepted through the platform wrapper. Keep the
family explicitly iOS. Add common request-construction and result-validation
tests, then repeat live acceptance through `bin/machine-control --target ios
ios ...` inside the transactional device session.

Capability output must retain meaningful omissions and limits, including the
absence of arbitrary shell, filesystem-wide access, protected authentication,
and Android-style wake/keyguard operations.

### 5 — prove realistic debugging workflows

Use TomConnect for the non-destructive workflows its available build supports:

- direct URL payload delivery followed by a foreground semantic observation;
- application and relevant process observation;
- log collection around a reproducible application action; and
- bounded container exchange when its signed build permits it and a harmless
  test file is available.

Do not describe direct payload delivery into a named bundle as proof of iOS
universal-link association or system routing. Observe genuine system routing
separately by activating a link from another application when the installed
TomConnect build and associated-domain environment make that test meaningful.

Use TomConnect for uninstall in this acceptance run. A disposable development
fixture remains preferable for deterministic stdout, container, deep-link, or
intentional-crash behavior that TomConnect does not expose safely. Restore or
reinstall only when the consuming project needs that state.

### 6 — record the resulting surface

Move each candidate into one of these outcome classes:

- **accepted/common** — useful, typed, live-tested, and exposed through the
  common iOS family;
- **accepted/platform** — useful and live-tested, but intentionally remains a
  platform operation;
- **limited** — usable with a material scope or fidelity limitation;
- **rejected** — tested but unreliable, unsafe, or not useful; or
- **deferred** — needs another provider, fixture, product change, or concrete
  debugging requirement.

Update the capability matrix and current research/topic truth from those
results. The final tactical result records what was actually adopted rather
than restating the original candidate list as completed.

## Validation

- `cd platforms/ios && pnpm check`
- `python3 -m unittest discover -s platforms/ios/tests -v`
- `python3 -m unittest discover -s tests/client -v`
- `python3 bin/check --portable`
- `platforms/ios/bin/ios-device probe`
- `platforms/ios/bin/ios-device doctor`
- one transactional physical-device workflow covering every adopted operation
  through the platform wrapper
- one transactional physical-device workflow covering every operation promoted
  to the common `ios` family
- `git diff --check`, JSON/schema validation, artifact cleanup, and a
  public-data review of every changed document and fixture

## Result

### Initial diagnostic slice

This table records the first pass. Its uninstall and system-log deferrals were
subsequently resolved by the required extension below.

The tactical produced a deliberately iOS-native diagnostic surface rather than
a literal ADB clone:

| Candidate | Outcome | Result |
| --- | --- | --- |
| Development-app inventory | **accepted/common** | `application list` returns at most 256 developer-built, non-default applications using six stable fields; it omits CoreDevice paths and the internal runner |
| URL or deep-link delivery | **accepted/common** | `application open-url APP URL` confirms direct CoreDevice payload delivery to an exact installed development bundle and reports the application effect as unverifiable; it does not claim iOS system routing |
| Application logs | **accepted/common** | Transactional `logs start` and `logs collect OUTPUT` delimit application stdout/stderr capture and write a create-only bounded artifact outside the repository; the default is 1 MiB and maximum is 16 MiB |
| App-container file exchange | **accepted/common** | `copy-to` and `copy-from` transfer one file of at most 16 MiB in `appDataContainer`; copy-to performs a hash readback and copy-from creates rather than replaces the host artifact |
| Process inventory | **limited/not exposed** | CoreDevice returned hundreds of executable/PID rows without bundle identity. Launch deltas were useful during investigation, but a standalone common projection would be noisy and weakly attributable |
| Uninstall | **deferred** | The CoreDevice route exists, but the installed TomConnect build had no matching signed device artifact available for safe restoration. A disposable reinstallable fixture is required before adoption |
| System logs and genuine URL routing | **deferred** | App console capture does not include `os_log`; direct payload delivery bypasses iOS's system routing decision. Neither justified a new provider or broader operation without a concrete debugging case |

The initial wrapper and common client validated bundle identifiers, URLs, byte
bounds, remote container paths, transactional log lifetime, create-only local
artifacts, and development-app eligibility. At that point, capability output
declared route, scope, limits, omissions, and the unsupported shell,
filesystem-wide, protected-authentication, wake/keyguard, and system-log
surfaces.

The installed TomConnect development build exercised inventory, an HTTPS
payload, an application-console window around an XCTest observation, and a
file round trip. Platform-wrapper and common-facade transactional workflows
both passed. The copied bytes matched in both directions, the temporary host
artifacts were removed, and the temporary device payload was cleared. No
TomConnect bundle suffix, phone identity, signing identity, log content, or
captured application artifact was added to the repository.

Validation completed with 47 iOS tests, 84 common-client tests, the full
portable repository check, final probe and doctor readiness, whitespace and
tracked-JSON checks, and public-data review. The portable check was run with
private VM target-file discovery disabled so ignored local inventory could not
change isolation-test expectations.

## Required extension

The initial slice established useful application-scoped diagnostics, but the
near-term TomConnect workflow also requires lifecycle cleanup and evidence
outside application stdout/stderr. This extension is required before the
tactical returns to complete:

- add typed uninstall for an exact removable development application, with
  installed-app preflight and absence readback;
- select and adopt the most reasonable maintained physical-iOS system-log
  provider, then expose bounded transactional `os_log` collection without
  returning log content inline;
- expose bounded crash-report inventory and collection with enough metadata to
  select relevant application crashes while keeping reports outside the public
  repository; and
- live-test all three routes on the accepted phone, using TomConnect for
  uninstall as explicitly authorized and using generated diagnostic artifacts
  only outside this repository.

Process inventory remains deferred unless the investigation finds a stable
bundle-attributed route. Its presence is not a completion condition.

### Extension approach

1. Source-review current CoreDevice, Agent Device, libimobiledevice, and
   pymobiledevice3 routes. Prefer an already-installed Apple facility when it
   provides the needed evidence; otherwise choose the smallest maintained
   dependency that works with the accepted modern physical-iOS connection.
2. Probe system logs and crash reports read-only before fixing their request
   and result contracts. Record pairing/tunnel requirements, scope, bounds,
   cancellation behavior, and artifact format.
3. Add typed platform operations, focused refusal and cleanup tests, capability
   declarations, and common-client commands only for live-proven routes.
4. Uninstall the exact installed TomConnect development bundle, then confirm
   its absence through independent CoreDevice inventory. No reinstall is
   required for this acceptance run.
5. Repeat platform and common-facade acceptance, update current topic/provider
   evidence, run the portable suite, and return this tactical to complete with
   the actual provider choice and remaining limitations.

### Extension result

The extension completed the remaining high-value diagnostic surface:

| Capability | Outcome | Result |
| --- | --- | --- |
| Safe uninstall | **accepted/common** | `application uninstall APP` requires an exact installed application reported as developer-built, non-default, and removable; CoreDevice performs the uninstall and a fresh inventory confirms absence. The authorized TomConnect development build was removed during live acceptance and was not reinstalled |
| System `os_log` | **accepted/common** | Transactional `system-logs start` and `system-logs collect OUTPUT` use libimobiledevice 1.4.0's `os_trace_relay` stream. A private worker retains only the newest 16 MiB, collection writes a create-only artifact bounded to 16 MiB with a 1 MiB default, and session cleanup stops and discards abandoned streams |
| Crash-report inventory | **accepted/common** | `crashes list [--match TEXT]` projects at most 512 readable `.ips`, `.log`, and `.txt` records from CoreDevice's native `systemCrashLogs` domain using relative path, name, size, modification time, and format |
| Crash-report collection | **accepted/common** | `crashes collect SOURCE OUTPUT` preflights one exact inventory path, copies at most 16 MiB to a create-only host artifact, hashes it, and leaves the report on the phone |
| Process inventory | **limited/not exposed** | CoreDevice still supplies only a large PID/executable projection without stable application-bundle attribution. Lifecycle-specific observations remain more truthful than a noisy standalone inventory |

libimobiledevice was selected only for the system-log gap. Its stable 1.4.0
CLI is a small packaged dependency, works with the phone's existing pairing,
and reaches `os_trace_relay` without a developer tunnel. CoreDevice remains the
native route for uninstall and crash reports. pymobiledevice3 was investigated
but not added: its structured syslog and broader services are potentially
useful, while its Python and optional tunnel surface add no benefit to the
accepted USB logging workflow.

Live common-facade acceptance captured a 524,142-byte bounded system-log tail
containing 3,413 lines, listed 53 crash reports, and copied an existing
20,510-byte `.ips` report without removing it from the phone. Transaction exit
left no system-log worker or private spool state. A deliberately induced new
TomConnect crash was not attempted because the authorized uninstall had
already removed the build; collection of an existing device report proves the
transport and artifact contract, while deterministic crash generation remains
fixture work rather than a dependency of this capability.

The focused iOS and common-client suites pass 53 and 87 tests respectively.
The wrapper probe and doctor, live platform/common workflows, portable checks,
diff validation, artifact cleanup, and public-data review completed without
committing device identity or captured diagnostics.
