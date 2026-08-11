# Tactical 022: Common Maintenance and macOS Certification

Status: active.

Topics: `target-lifecycle-and-readiness`, `cross-platform-coordinator`, and
`macos-resident-control`.

## Objective

Give agents one discoverable maintenance namespace over platform-owned
Windows, Linux, and macOS appliance operations, then bring the retained macOS
Tart development appliance to the same bounded post-update and exact-source
certification standard already proven on Windows and Linux. Keep common code
limited to selection, validation, dispatch, and minimized results; launchd,
TCC, systemd, and Windows service policy remain platform-owned.

## Completion conditions

- `machine-control --target TARGET maintenance capabilities` reports an
  explicit, minimized contract for audit, repair, reboot, certification, and
  supported runtime/development profiles without invoking the adapter.
- `maintenance audit|repair|certify` validates its options, dispatches only a
  declared platform command, validates that platform's result schema, wraps
  it in one common result envelope, and preserves nonzero unhealthy outcomes.
- Native targets or future desktop targets without the declared appliance
  surface receive a typed refusal before adapter execution.
- `target ensure-ready` remains limited to its existing start transition. A
  running unhealthy target may recommend the explicit maintenance audit, but
  the command never audits, repairs, reboots, or certifies implicitly.
- `macvm post-update audit` is read-only, refuses a stopped target before
  guest execution, and reports minimized launchd, Aqua, stable resident/TCC
  identity, target-native control, and declared profile-tool checks.
- `macvm post-update repair` is exact-candidate only and changes only
  enumerated, already-installed launchd services or the checked-in resident
  deployment. It never edits TCC, installs a missing system package, handles
  a credential, changes login policy, uses outer UI, or suppresses an update
  or reboot requirement.
- Reboot is opt-in and accepted only after a changed macOS boot epoch plus a
  healthy post-update audit and common doctor observation.
- `macvm bootstrap --profile development|runtime` idempotently deploys the
  checked-in resident and post-update support, checks the declared native
  tool profile, and reports any missing OS/Xcode component rather than
  launching an interactive installer or Homebrew.
- `macvm appliance-certify` requires a clean committed tree and exact retained
  candidate, audits without repair, observes a real reboot, transfers a
  digest-bound archive, runs portable and macOS-native checks in an isolated
  guest home with bounded timeouts, removes staging, and cleanly shuts down
  only after success.
- One minimal live rehearsal reuses the retained macOS candidate, creates no
  VM or workspace, leaves no named staging, and leaves the candidate stopped.

## Boundaries

- Do not add libvirt/KVM, another hypervisor, a direct resident transport,
  unattended macOS installation, image sealing, or generated repositories.
- Do not create, clone, snapshot, derive, compact, rename, or delete a VM.
- Do not define a generic repair vocabulary for platform services. The common
  layer validates the complete platform result as input but projects only
  stable, minimized platform-owned evidence.
- Do not make maintenance support an inventory property. It is an owned
  platform-adapter capability keyed by the selected platform and interface,
  so private inventory continues to contain only routes and concrete target
  selection.
- Do not make capability discovery boot or inspect a target. Adapter
  availability and maintenance support are distinct facts.
- Do not broaden macOS consent. Audit reports TCC-dependent effects, repair
  may redeploy the same stable identity, and unsupported consent repair stays
  an explicit manual boundary.
- Do not run `softwareupdate`, install Homebrew, Xcode Command Line Tools, or
  framework runtimes as a side effect of audit or repair. Development profile
  acquisition remains deliberate and separately documented.
- Do not expose concrete target identity, endpoint, account, VM name, boot
  epoch, TCC rows, installed paths, archive paths, or captured UI in public
  common results or committed evidence.
- Do not shut down a failed certification target; leave it running for bounded
  diagnosis after removing staging.

## Ordered work

### 1 — define common maintenance projection

Add dependency-light validators and result projection for capabilities,
audit, repair, and certification. Declare the exact platform adapter schemas
and command spellings in public coordinator code, not in private inventory.
Keep platform evidence nested and validate only stable orchestration fields
that the common layer needs to interpret.

### 2 — dispatch explicit maintenance operations

Expose `maintenance capabilities|audit|repair|certify` for the three desktop
appliance adapters. Parse `--profile development|runtime`, permit `--reboot`
only with repair, preserve an adapter's valid JSON failure, and refuse every
unsupported platform/interface before dispatch. Add a non-mutating
maintenance recommendation to failed `ensure-ready` results.

### 3 — define macOS minimized guest evidence

Implement a target-local support script with nonce-bound read-only audit and
bounded repair modes. Check the guest-agent daemon and interactive agent,
logged-in Aqua session, stable resident application and CLI, Accessibility,
capture/input semantics, and runtime/development tools without publishing
identifying observations.

### 4 — compose macOS audit, repair, and profiles

Add host orchestration that refuses stopped audit before guest execution,
guards repair as an exact candidate, validates the guest nonce and profile,
and requires the existing full doctor. Add an idempotent profile bootstrap
that deploys exact checked-in support and resident sources without attempting
interactive package or consent acquisition.

### 5 — compose exact-source macOS certification

Audit without repair, reboot through target-native administration, prove a
changed `kern.boottime`, transfer and verify a Git archive, execute portable
and macOS-native checks under bounded timeouts and isolated state, remove all
staging, then cleanly shut down the healthy candidate.

### 6 — prove policy and failure boundaries

Add common mock-adapter coverage for discovery, dispatch, schema validation,
nonzero projection, unsupported refusal, and ensure-ready non-mutation. Add
macOS shell fixtures for stopped audit, candidate-only repair, nonce/profile
validation, bounded changes, explicit reboot, clean-source requirements,
digest checks, timeouts, cleanup, and success-only shutdown.

### 7 — run one bounded live rehearsal

On the existing retained candidate, deploy the development profile, run a
read-only audit, run one healthy idempotent repair without reboot, then run
exact-source certification once. Record only minimized outcomes, confirm no
workspace or unique staging remains, and leave the candidate stopped.

### 8 — close current guidance

Update common lifecycle/coordinator guidance and macOS bootstrap/platform
documentation with the proven contract and its consent/recovery limits. Run
portable, macOS-native, platform fixture, public-diff, and hosted CI checks;
commit coherent stages and push.

## Validation

- `python3 bin/check --portable`
- `python3 bin/check --native`
- `platforms/macos/tests/smoke.sh --static`
- common client fixtures for every maintenance operation and refusal
- macOS fixture coverage for audit/repair/bootstrap/certification policy
- live minimized audit and healthy no-reboot repair on the retained candidate
- one live changed-boot-epoch certification with exact-source guest checks
- stopped candidate and absent guest/host staging at handoff

## Result

Pending implementation and live evidence.
