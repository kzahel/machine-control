# Tactical 020: Windows Post-Update and Appliance Certification

Status: complete.

Topics: `windows-resident-control`, `target-lifecycle-and-readiness`, and
`cross-platform-coordinator`.

## Objective

Make the retained Windows development appliance reproducible and cheaply
re-certifiable after Windows or application updates. Add a minimized,
guest-native post-update audit with a bounded idempotent repair path, include
the required development toolchain in the documented bootstrap profile, and
compose those pieces into an occasional end-to-end appliance certification
command without creating another VM lifecycle or clone policy.

## Completion conditions

- `winvm post-update audit` reports automatic-start and running state for the
  QEMU guest agent, hardened key-only OpenSSH, the resident runtime, and any
  installed legacy interactive relay; it also reports firewall, pending-reboot,
  Python, .NET 8 SDK, and full-doctor readiness without exposing target identity
  or private configuration.
- `winvm post-update repair` is explicitly mutating, candidate-authorized, and
  idempotent. It may restore checked-in service, firewall, and SSH policy and
  start installed components, but it may not invent credentials, install an
  absent base component, use outer input, force-stop, or guess an untyped fix.
- Repair prefers key-only SSH. When SSH is unavailable but UTM guest-agent file
  transfer and execution are available, success requires a fresh nonce-bound
  report pulled independently from the guest; the `utmctl exec` result is never
  sufficient evidence.
- Reboot remains an explicit option. A rebooting repair observes a changed boot
  epoch and then re-runs the post-update audit and common doctor.
- The dedicated development bootstrap profile idempotently installs a current
  Python 3 and the .NET 8 SDK through declared package identifiers, verifies
  them, and then deploys and probes the resident runtime. The runtime-only
  profile remains available.
- `winvm appliance-certify` starts the exact candidate, runs post-update audit,
  common doctor, and an explicit reboot cycle, transfers the exact committed
  source with a digest, runs portable and Windows-native checks in the guest,
  removes staging, and cleanly shuts down on success.
- Certification preserves one stateful appliance. It creates no clone,
  workspace, snapshot, seal, or feature-specific VM and does not install or
  repair implicitly.
- Public documentation, results, tests, and commits contain no private target,
  endpoint, account, VM, or deployment identifiers.

## Boundaries

- Do not add libvirt/KVM, another hypervisor provider, generic repair
  abstraction, or generated focused repositories in this tactical.
- Do not fold the legacy WinApp relay into the required resident contract. If
  it is installed, audit it honestly; the MachineControl resident and its
  medium-session helper remain the ordinary interactive route.
- Do not turn the read-only common `doctor` or `target ensure-ready` command
  into a package installer or general repair surface.
- Do not install Windows updates, change update policy, enter credentials,
  weaken UAC or OpenSSH, relax a firewall broadly, or suppress pending-reboot
  evidence.
- Do not claim a healthy appliance from service-manager state alone. Final
  readiness still requires the common semantic, capture, and input probes.
- Do not make every normal check pay the reboot and source-transfer cost.
  Certification is explicit and on demand.
- Do not create or delete a VM during rehearsal. Reuse the exact retained
  candidate and leave it stopped with no named staging artifacts.

## Ordered work

### 1 — define minimized post-update evidence

Implement one guest-native PowerShell script whose audit mode is read-only and
whose repair mode changes only enumerated startup invariants. Give every check
a stable identifier, required/optional status, observed state, and repair
result. Bind guest-agent reports to a caller nonce and omit names, addresses,
accounts, keys, paths, and package-source state.

### 2 — orchestrate inner audit and repair

Expose `winvm post-update audit|repair [--reboot]`. Enforce exact target role
policy before mutation, prefer SSH, and add a guest-agent fallback whose report
is transferred and verified independently. After repair, require SSH and the
full doctor. For reboot, compare Windows boot epochs and fail if the epoch does
not change or readiness does not return.

### 3 — make the development profile reproducible

Add an idempotent guest development-bootstrap script for Python and .NET 8.
Teach the host product bootstrap to select `development` or `runtime` and make
the dedicated-appliance documentation use `development`. Keep the unattended
factory responsible for guest tools and hardened SSH, then use the authenticated
controller bootstrap for public package acquisition and target-attested product
installation.

### 4 — compose on-demand certification

Add a candidate-only certification script that starts the appliance, audits
without repairing, reboots explicitly, proves full doctor readiness, transfers
an archive of the exact committed tree with its digest, runs portable and
Windows-native checks, removes its unique staging directory, and shuts down.
Leave a failed target running for diagnosis unless shutdown itself was reached
after every acceptance check.

### 5 — test policy and failure boundaries

Cover command parsing, candidate authorization, minimized schemas, audit versus
repair behavior, nonce mismatch, false-success guest execution, explicit reboot,
profile selection, cleanup, and no-clone/no-outer behavior with fixtures. Run
PowerShell static checks and both Windows publishes.

### 6 — run one bounded live rehearsal

On the existing exact Windows candidate, run audit, idempotent repair without a
reboot, then certification once. Record only minimized outcomes, verify that
staging is absent, and leave the persistent candidate stopped. Do not create a
workspace or clone for the rehearsal.

### 7 — close current guidance

Update Windows bootstrap/factory guidance and the owning topics with the proven
contract, route limits, and remaining gaps. Audit the public diff, commit in
coherent stages, push, and verify hosted CI.

## Validation

- `python3 bin/check --portable`
- `python3 bin/check --native`
- `platforms/windows/tests/smoke.sh`
- Windows PowerShell static and contract suites
- `dotnet format --verify-no-changes`
- Windows ARM64 and x64 publishes
- live minimized audit and idempotent repair on the retained candidate
- one live changed-boot-epoch certification with exact-source guest checks
- stopped target and absent named guest/host staging at handoff

## Result

Completed on 2026-08-11 without creating, cloning, snapshotting, deriving, or
deleting a VM. The existing private-inventory candidate remained the only
stateful Windows appliance and was left cleanly stopped. No workspace receipt
was acquired.

The published resident now carries a guest-native
`machine-control-windows-post-update/v0` script. Its minimized development
audit independently passed automatic QEMU guest agent and OpenSSH service
state, key-only SSH options and configuration validation, restricted key
material, the exact TCP/22 firewall rule, automatic LocalSystem resident
service, the Medium interactive probe, Python 3, .NET 8, clear pending-reboot
state, and the optional installed WinApp relay. The host orchestration adds the
full common doctor, refuses to start a stopped target for audit, restricts
repair to an exact candidate, and keeps reboot explicit.

The live healthy candidate passed one no-reboot idempotent repair through
key-only SSH with no required failure and a ready final doctor. Fixture
acceptance separately proved the guest-agent fallback when the simulated
`utmctl exec` status disagreed with the nonce-bound report, rejected a nonce
mismatch, and verified that SSH plus full doctor readiness remain required.
Repair installs no missing component, reads no credential, invokes no outer
input, and never clears pending-reboot evidence.

`scripts/bootstrap-windows.sh` now defaults to a `development` profile that
idempotently verifies or installs the declared Python 3 and .NET 8 SDK WinGet
packages before resident installation; `runtime` remains explicit. The live
candidate already had both packages, and transactional ARM64 deployment
verified the resident and provider digests, automatic LocalSystem service,
Medium helper, Cua/native provider inventory, and staging removal. The
unattended first-logon factory also now makes the installed QEMU guest agent
automatic; network package acquisition remains in the authenticated,
target-attested controller bootstrap rather than one-use answer media.

The final certification accepted exact commit `9f3dd01`: its archive matched
SHA-256 inside Windows, a changed boot epoch returned all post-update and full
doctor checks with a new resident generation, portable and Windows-native
checks passed, guest staging was removed, and the candidate cleanly shut down.
Earlier fail-closed attempts exposed and fixed the need for a per-process
PowerShell bypass, PowerShell 5.1 empty-collection binding, typed safe failure
projection, and isolation of normal native stderr from PowerShell error-record
semantics. Failed attempts left the candidate running and reported zero stale
certification staging. The final runner also bounds each supervised portable
or native guest process with a configurable 20-minute default and kills only
that process tree on timeout.

Portable checks, Windows provider smoke and target-safety fixtures, macOS
native checks, Windows ARM64/x64 publishes, .NET formatting, and hosted CI
complete the final validation record. Public results contain no concrete
target name, identity, endpoint, account, or private inventory path.
