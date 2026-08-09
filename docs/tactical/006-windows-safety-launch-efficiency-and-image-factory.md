# Tactical 006: Windows Safety, Launch, Efficiency, and Image Factory

Status: complete.

Topics: `windows-resident-control`, `architecture`, and
`capabilities-and-results`.

Precursor:
[`005-windows-clean-appliance-and-real-application-acceptance.md`](005-windows-clean-appliance-and-real-application-acceptance.md).

## Objective

Close the operational and product gaps exposed by the first reproducible
Windows appliance. Make target selection fail closed for mutation, activate
registered and packaged applications without shell typing, broaden sustained
real-application evidence, reduce repeated semantic payloads, and give the
authoritative Windows testbed a secret-safe path from installation media to a
generalized, independently verifiable image.

The result should preserve the already working resident facade. These changes
strengthen its safety, determinism, efficiency, and reproducibility rather than
replace its Cua/native provider composition.

## Completion conditions

- Every mutating testbed operation resolves the configured target's
  provider-native immutable identity, compares it with an ignored explicit
  identity pin, and applies a declared role policy. An absent or stale pin
  fails before mutation.
- Source, candidate, and retained-seal roles have different permitted
  lifecycle operations. Source mutation and persistent seal boot require a
  separately explicit override; deletion remains exact-confirmed and is never
  permitted for a source.
- MachineControl bootstrap can consume the testbed's target assertion rather
  than trusting an SSH alias alone. Bypassing target attestation for physical
  or non-integrated targets requires a conspicuous explicit option.
- The Windows facade has a typed registered-application activation operation.
  It supports package application IDs or registered shell identities, reports
  the activation route and returned process, and confirms a resulting visible
  window instead of treating process creation as sufficient effect.
- Calculator no longer needs Windows Run input. A repeated application corpus
  covers packaged, classic, system, document, semantic mutation, window, and
  cleanup behavior through local and remote placements with independent
  effects.
- Semantic observation supports a compact projection and content digest.
  Repeating an unchanged observation can return an explicit unchanged result
  without resending the element collection. Full fidelity remains available.
- Acceptance records full versus compact versus unchanged bytes, estimated
  tokens, latency, round trips, route, fallback, and effect. Compact and
  unchanged responses demonstrate a material reduction on real applications.
- The authoritative testbed contains a checked-in unattended-install input
  contract, locally rendered secret-bearing answer media, guest bootstrap,
  generalization cleanup, Sysprep shutdown, stopped export, manifest, and
  disposable verification flow. Secrets and private inventory remain ignored.
- Schema, dry-run, and provider tests run without installation media. A live
  image build uses only explicitly selected local media and target inventory;
  if those inputs are unavailable, the exact unexecuted boundary is recorded
  rather than claiming a proven factory.
- All temporary documents, screenshots, installer staging, answer media, and
  disposable candidates created by this tactical are cleaned or moved to a
  recoverable local trash location. Retained outputs remain stopped.

## Boundaries

- Do not mutate the authoritative source appliance or persist a boot of the
  retained seal merely to gain convenient test access. Derive an explicitly
  pinned candidate and delete it only after its replacement is verified.
- Do not put VM names, IDs, addresses, account names, credentials, product
  keys, answer files containing secrets, host keys, bundle paths, or exported
  image identities in Git or command output intended as durable evidence.
- A target assertion is a safety interlock, not an authentication credential.
  SSH, provider authorization, and secret transport remain separate controls.
- Do not weaken UAC, secure-desktop policy, SSH authentication, or the resident
  protected-operation boundary.
- Do not call a clone a generalized or portable image until Sysprep completed,
  Windows shut down, machine-specific material was removed according to the
  declared profile, and a disposable first boot was observed.
- Do not optimize semantics by discarding fidelity silently. Projection,
  omission, digest scope, and unchanged behavior must be explicit in results.
- Do not add broad input fallbacks to make application activation appear
  successful. Activation either produces an independently observed target or
  reports the honest failure.

## Implementation steps

### 1 — make target selection fail closed

Add provider-native identity discovery, an ignored identity pin, explicit
target roles, a machine-readable assertion command, and a role/operation
policy in the Windows testbed. Exercise absent, mismatched, source, candidate,
seal, and exact-delete cases without touching a real target.

### 2 — bind product bootstrap to the asserted target

Teach the MachineControl bootstrap to request and validate a candidate target
assertion from the authoritative testbed. Preserve an explicit unattested mode
for physical hardware and other providers that cannot yet issue the assertion.

### 3 — activate registered Windows applications natively

Add a normalized activation request and a Windows adapter over the registered
shell/package activation APIs. Return the requested identity, native route,
process identity, matching visible windows, elapsed time, and honest effect.
Replace the Calculator Run-dialog path in acceptance.

### 4 — broaden real-application conformance

Exercise at least one packaged application, one classic application, Settings
or another system surface, and a persisted document. Repeat through remote and
target-local callers, observe independent state, and clean all created state.

### 5 — add compact and unchanged semantic observation

Define projection and prior-digest request fields. Normalize provider output,
compute a digest over the declared projection, and suppress an unchanged
element payload only when the caller supplied the matching digest. Measure the
result on the expanded corpus.

### 6 — implement the image-factory contract

In the authoritative testbed, add installation-media validation, unattended
answer-media rendering, VM creation/import boundaries, guest bootstrap,
generalization preparation, Sysprep shutdown, export manifest generation, and
disposable verification. Make secret-bearing outputs ignored and fail closed.

### 7 — prove and close the workstream

Run static and mocked safety tests, build both Windows architectures, perform
the full suite on an explicitly pinned disposable candidate, and exercise as
much of the image factory as available local installation media permits.
Update the testbed runbook, Windows topic, tactical index, and this record with
measurements, deviations, and the exact remaining boundary.

## Validation record

Completed 2026-08-10.

### Target safety and bootstrap binding

The authoritative testbed now pins UTM's immutable target UUID in ignored
state, classifies `source`, `candidate`, and `seal` roles, and checks each
operation against that role before dispatch. Source deletion is never allowed;
source mutation and persistent seal boot require separate overrides. Product
bootstrap consumes the testbed's machine-readable candidate assertion and
requires `--allow-unattested-target` when no integrated testbed can attest a
physical or alternate-provider target.

Live cleanup exposed an important second-process configuration bug: the CLI's
selected target name could be replaced by `config.local` while its UUID and
role survived. The testbed now preserves the resolved selection across child
processes, gives explicit environment values precedence over file defaults,
and addresses all pinned UTM lifecycle, clone, export, guest-agent, and
recovery-input operations by UUID. Mocked regressions prove double-source
layering and UUID-addressed deletion.

### Native application and window behavior

`app.activate` uses Windows `IApplicationActivationManager` for registered or
packaged application identities. It reports the returned process, activation
route, matching visible HWNDs, and independently confirmed effect. Packaged
frame association uses the window AppUserModelID property, including existing
Settings frames hosted by `ApplicationFrameHost`.

The final acceptance rerun caught intermittent `ShowWindowAsync` no-effects
on Calculator. Window lifecycle now uses native UI Automation `WindowPattern`
as the primary maximize, restore, minimize, and close route, retains Win32 as
a disclosed fallback, and reads back semantic plus HWND state. The suite
requires all four transitions rather than merely recording partial success.

Both authenticated-remote and target-local Medium-user placements passed 51
facade calls over the same four-application workflow:

- Calculator: registered activation, four native UIA actions, independent
  display value, exact-window capture, four confirmed state transitions, and
  close;
- Settings: registered activation, system-scope UIA semantics, and preservation
  of a pre-existing window;
- Character Map: classic executable launch, matching process/window effect,
  native UIA semantics, and close; and
- Notepad: visible launch, two semantic edits, two exact filesystem saves,
  reopen/readback, exact-window capture, close, and document cleanup.

Both placements reported all owned windows, documents, and captures cleaned.

### Compact and unchanged observations

Snapshots now accept explicit `full` or `compact` projection and return a
digest whose scope excludes generation-scoped references. Suppression occurs
only when the caller supplies a matching prior digest; an unchanged response
states `unchanged: true` and omits the element collection. Full fidelity
remains available.

Final real-application payloads were:

| Surface | Full | Compact | Unchanged | Compact/full | Unchanged/compact |
| --- | ---: | ---: | ---: | ---: | ---: |
| Calculator | 9,971 B / ~2,493 tokens | 6,577 B / ~1,644 | 1,165 B / ~291 | 0.660 | 0.177 |
| Settings | 4,971 B / ~1,243 tokens | 3,843 B / ~961 | 986 B / ~246 | 0.773 | 0.257 |

The local and remote runs produced the same sizes on the final application
state. Results still report the actual Cua or native UIA route, latency,
fallback, delivery, effect, focus, and cursor consequences.

### Image factory

The Windows testbed now owns:

- a secret-safe unattended answer-file renderer and ignored answer-media ISO;
- explicit local Windows-media validation and a parsed ARM64 UTM creation
  recipe;
- first-logon OpenSSH/public-key bootstrap;
- candidate-only preflight, BitLocker decryption, and exact AppX
  reconciliation;
- detached LocalSystem preparation, auto-logon/LSA cleanup, SSH host-identity
  removal, and Sysprep `/generalize /oobe /shutdown /mode:vm`;
- stopped UTM export plus an atomic private manifest; and
- disposable OOBE verification without persisting the first boot.

Live preflight found two real blockers rather than hiding them: the OS volume
was fully encrypted with protection off, and six removable per-user AppX
packages were absent from image provisioning. Explicit preparation reached
`FullyDecrypted` and reconciled the exact reported packages. Sysprep then
completed, UTM independently observed shutdown, a roughly 53-GiB private
bundle was exported, and a disposable boot visibly reached the Windows
country/region OOBE page. The adjacent mode-0600 manifest records the declared
same-controller UTM profile and confirmed disposable OOBE without a persistent
first boot.

The retained pre-generalization recovery clone passed a disposable `doctor`
run and is stopped. The generalized export is stopped. Temporary host keys,
answer media, acceptance artifacts, and screenshots were removed and were not
committed.

### Validation commands and remaining boundary

- Both `win-arm64` and `win-x64` runtime builds completed with no warnings or
  errors.
- `tests/windows/bootstrap-target-safety.sh` passed.
- The testbed's `tests/image-factory.sh` and `tests/smoke.sh` passed, including
  target-role, configuration-layering, UUID-deletion, renderer, manifest, and
  mocked provider checks.
- The UTM factory AppleScript parsed against the installed UTM dictionary.

No compatible licensed Windows installation ISO was present locally. The
ISO-to-new-base lane therefore stops honestly at: explicit media validation,
`factory-create`, Setup/image-index and driver compatibility, first-logon SSH
bootstrap, answer-media removal, and product installation on that newly
created target. The renderer and provider boundary are implemented and tested,
but this lane is not called live-proven until such media is supplied. See the
authoritative testbed's
[`image-factory.md`](../../../winvm-testbed/docs/image-factory.md).
