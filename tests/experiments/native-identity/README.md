# Guest-only native AX identity qualification

This is an owned AppKit fixture and a separate AX client. **Current:** bounded
live qualification passed in a disposable ARM64 macOS guest: ten repeated
reads, twenty identical-presentation replacements, insertion/reorder/removal,
window recreation and process restart. The report observed stable survivor
equality and no cross-incarnation equality in this corpus. A retained stale
proxy still invoked a retired control after window recreation, making current
membership validation necessary. Both fixture processes were reaped. See the
[platform evidence](../../../research/platforms/macos.md#native-efficiency-and-background-effects)
for scope and limits. This is not a production identity or efficiency claim.

The coordinator must use a disposable macOS clone with read-only doctor,
exclusive common-CLI claim, stored credential handoff and finally cleanup.
Carry provisioning/usage journal attribution for this direct-script step.
Never run either native executable against the controller desktop. No guest is
created or selected by these scripts; no YA session is launched. The probe
drives only the exact fixture processes it creates.

## Build without launching UI

From the checkout, on a Mac with Command Line Tools:

```sh
python3 tests/experiments/native-identity/build.py \
  --output /private/tmp/native-identity-build-RUN
python3 -m unittest discover -s tests/experiments/native-identity -p 'test_*.py' -v
```

The build requires a new absolute directory, compiles two original Swift
executables, makes separate ad-hoc signed app bundles, and writes `build.json`
with compiler information, source hashes and signed binary hashes. It never
launches the apps, queries Accessibility or changes consent. Transfer the whole
build directory unchanged into the clone, or build there. Native execution
verifies both binary hashes against the copied build manifest.

## Run only inside the claimed disposable guest

The exact `IdentityProbe.app` needs guest Accessibility consent through the
existing supported consent setup. The probe calls `AXIsProcessTrusted()` without
prompting. A missing grant produces a failed receipt before fixture launch;
do not edit the TCC database or substitute a different executable. Keep the
guest claim held for consent, execution, evidence collection and cleanup.

```sh
/private/tmp/native-identity-build-RUN/IdentityProbe.app/Contents/MacOS/IdentityProbe \
  --disposable-guest \
  --fixture /private/tmp/native-identity-build-RUN/IdentityFixture.app \
  --output /private/tmp/native-identity-receipts-RUN \
  --reads 10 --replacements 20
python3 tests/experiments/native-identity/report.py \
  /private/tmp/native-identity-receipts-RUN \
  > /private/tmp/native-identity-summary-RUN.json
```

`--disposable-guest` is an explicit operator assertion, not VM detection or
authority. Both executables refuse before native operations without it. The
probe requires a new private output directory. Reads are bounded to 2–50 and
replacement cycles to 1–50. The fixture receives an unguessable run nonce and
every oracle read is checked against the probe-owned child PID and process
incarnation. No shell input, pointer event, outer route or other app is used.
If an old PID has become an unowned process, the probe refuses further native
reads/actions against it and leaves an incomplete run, rather than probing it.
The fixture creates visible windows inside the guest. The flag does not make
it safe to run on a personal workstation.

The scripted sequence covers repeated unchanged reads, insertion, reorder,
same-presentation replacement, removal, window destruction/recreation and
process exit/relaunch. Replacements have the same logical AXIdentifier, title,
size and position; a new incarnation exists only in the independent file
oracle. Logical identifiers join one sample to fixture slots; they are never
candidate native identity keys. The report rejects replacement samples whose
oracle frame/label/identifier did not stay equal. Window titles and logical
identifiers are also reused after recreation.

## Receipts and independent effect checks

- `build.json` is embedded in `run.json`, along with OS version, operator
  assertion, corpus sizes, exact child PID/incarnation pairs and cleanup.
- `records.json` is atomically checkpointed after each record. Every snapshot
  contains the fixture oracle, actual AX traversal attributes/order, local
  handles for fresh proxies, all prior-versus-current `CFEqual`/hash results,
  prior-proxy AXRole validity errors, notification registration statuses and
  observed process/window epochs. Missing or duplicate joins fail the run.
- `notifications.json` records real AX destruction callbacks, their hashes,
  matching retained proxy handles and monotonic receipt times. The fixture
  never posts artificial destruction notifications. Oracle creation/removal,
  NSButton deinitialization and target/action effects are independent events.
- `process-*/state.json`, `command.json` and `fixture.log` retain independent
  oracle state and setup/error evidence. Keep all runtime files private.
- Actions include current-control presses plus intentional old-proxy presses
  after replacement/removal/window/process boundaries. The probe records API
  error and independent per-incarnation effect deltas separately. These raw
  experiments bypass production guards only for owned fixture controls;
  accepted stale actions are evidence, not a refusal success.

The probe reaps every process it creates in cleanup, including failures, and
reports forced termination. It removes its AX observer run-loop sources. The
coordinator must verify the cleanup receipt, then release the claim/workspace;
an external kill of the probe cannot run its cleanup. Resolve any remaining
exact fixture processes from the private receipts before guest disposal.

## Interpret the result before choosing a policy

The report fails closed for incomplete coverage, inconsistent receipts,
non-identical replacement presentation, missing cleanup or bad oracle joins.
It distinguishes survivor inequality, same-scope cross-incarnation equality,
cross-epoch equality, raw stale-action effects, validity and notification
support/errors. Current actions require exactly the intended callback effect.
No match is inferred from a hash, logical identifier, label, position or index.

`bounded_candidate_observed` proposes only a process/window-incarnation scope
with native equality and a fresh complete membership check before each action;
uncertain reads, ambiguity or epoch changes must invalidate. It does not enable
production identity or prove that an AX token can never be reused. A raw
stale-proxy effect can make current membership essential even when equality
measurements pass. Review the raw findings, especially effects and callback
coverage, before adopting any bounded policy. Notifications are collected in
bounded intervals; absence is not a guarantee, and preflight cannot eliminate
every mutation race before dispatch. PID reuse is not qualified merely by one
process restart. Process/window incarnations in these receipts are oracle
fields, not a resident epoch implementation; deriving those boundaries from
trustworthy process/window evidence remains a separate implementation gate.
Generalize only after additional real app/provider evidence.

This experiment measures identity/lifetime and callback effects. It makes no
native latency, API-count, tokenizer, model-cost or task-efficiency claim.
