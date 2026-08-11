# Tactical 023: ChromeOS Common Readiness and Maintenance

Status: active.

Topics: `target-lifecycle-and-readiness`, `cross-platform-coordinator`, and
`unified-desktop-client`.

## Objective

Bring the existing physical ChromeOS developer-device implementation into the
common target doctor and maintenance namespaces without pretending it is a VM
appliance. Preserve the proven target-native SSH, desktop, capture, input, and
post-update routes while making current-boot SSH persistence, profile-session
readiness, pending updates, and explicit recovery boundaries visible through
portable minimized results.

## Completion conditions

- `machine-control --target TARGET target status|doctor|capabilities` accepts a
  declared ChromeOS native target and returns the common doctor projection.
- Common doctor distinguishes reachability, administration, current-boot SSH
  persistence, profile lock state, target-native client readiness, semantics,
  capture, input, and prohibited ordinary outer UI without exposing the
  endpoint, account, boot ID, release, paths, or device identity.
- Doctor and status never start SSH, log in a profile, deploy client files,
  repair configuration, reboot, or invoke VT2/host input.
- Maintenance capability discovery declares only the ChromeOS runtime profile,
  exposes audit and repair, truthfully marks exact-source certification
  unavailable, and never invokes the adapter.
- Common maintenance audit reuses the platform-owned focused audit, validates
  a ChromeOS orchestration schema, and minimizes update, rootfs, stateful
  fallback, SSH autostart/current-boot evidence, prepared-release, and
  DevTools checks.
- Common repair is explicit and selected-target only. It may perform the
  existing bounded active-image repair when the current root image is writable
  and no update is waiting, and may run the existing proof reboot only with
  `--reboot`.
- Pending-update and read-only-rootfs recovery returns a typed guided-recovery
  boundary without changing boot state. The existing VT2 flow remains the
  authoritative explicit escape because SSH may disappear across that repair.
- A healthy reboot result requires a changed boot ID, automatic current-boot
  startup evidence, a healthy post-update audit, and returned SSH. It does not
  require the ChromeOS profile to be unlocked after reboot.
- Dependency-free common and ChromeOS fixtures cover projection, partial
  capabilities, unsupported certification, stopped/unreachable observation,
  safe repair, guided-recovery refusal, explicit reboot, and private-field
  minimization.
- One live rehearsal uses the existing authorized device, performs no update,
  rootfs-verification change, login, or outer UI action, and runs at most one
  proof reboot after a healthy read-only preflight.

## Boundaries

- Do not add a hypervisor, workspace, candidate, image-certification, sealing,
  or clone abstraction to a physical Chromebook.
- Do not guarantee that physical hardware powers itself on after loss of
  external power. Report whether ChromeOS is reachable and whether SSH started
  automatically during the current observed boot.
- Do not make common readiness silently repair SSH, unlock the ChromeOS
  profile, approve ADB, deploy code, wake the display, or manipulate the
  controller desktop.
- Do not weaken the hidden one-shot profile credential path or place a PIN in
  JSON, arguments, environment, logs, fixtures, or evidence.
- Do not automatically disable rootfs verification or consume a pending A/B
  update from the common command. Those transitions retain the existing
  guided, physical-recovery-aware workflow.
- Do not expose raw legacy doctor/audit output through the common projection.
  It contains controller-local host labels and target-specific observations.
- Do not normalize the full ChromeOS desktop command vocabulary in this slice.
  Existing native commands remain available through `testbed --` while their
  measured behavior informs a later shared desktop projection.
- Do not add ChromeOS lifecycle verbs merely because other native devices
  expose reboot. Capability output must report the actual empty common
  lifecycle set.

## Ordered work

### 1 — allow honest partial maintenance capabilities

Move profiles, supported operations, interface eligibility, exact-candidate
requirements, and doctor-readiness rules into the public platform maintenance
declaration. Reject an unavailable operation before adapter execution and keep
the existing three appliance declarations unchanged.

### 2 — project ChromeOS common readiness

Add a platform-owned common doctor that consumes existing read-only checks in
memory and emits only normalized state and stable check IDs. Teach the common
client that the ChromeOS native adapter has a common doctor while retaining an
empty common lifecycle set and the explicit platform escape.

### 3 — compose ChromeOS maintenance results

Add a structured wrapper around the existing focused post-update audit,
bounded active-image repair, and proof reboot. Validate preconditions before
mutation, bind the runtime profile, preserve unhealthy JSON and exit status,
and return the common doctor separately from maintenance health so a normal
post-reboot locked profile does not invalidate SSH persistence evidence.

### 4 — prove refusal and minimization policy

Extend common mock-adapter tests for native ChromeOS doctor, runtime-only
partial capabilities, audit/repair dispatch, unavailable certification, and
minimization. Add POSIX fake-SSH fixtures for locked/unlocked doctor states,
unreachable observation, safe no-op repair, guided-recovery refusal, and a
changed-boot automatic-start proof without a real device.

### 5 — document and rehearse the physical-device boundary

Update common and ChromeOS guidance with the new entry points and the
difference between OS boot persistence and physical automatic power-on. Run a
read-only live preflight; only if it is healthy, run one explicit proof reboot
and verify returned SSH/current-boot evidence. Record minimized outcomes only.

### 6 — close and publish

Run portable and native host checks, public-diff review, and hosted macOS,
Linux, and Windows CI. Mark this tactical complete, update continuing topics,
commit coherent stages, and push.

## Validation

- `python3 bin/check --portable`
- `python3 bin/check --native`
- `python3 -m unittest discover -s platforms/chromeos/tests -v`
- tracked Bash syntax and JSON schema validation
- common client fixtures for native doctor and partial maintenance operations
- live common doctor and read-only maintenance audit
- one live `maintenance repair --profile runtime --reboot` only after healthy
  preflight
- returned SSH, automatic current-boot startup evidence, and locked-profile
  state reported independently

## Result

Pending implementation and live evidence.
