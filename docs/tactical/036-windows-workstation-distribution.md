# Windows workstation distribution and appliance compatibility

Status: in progress.

Owning topics: [native distribution](../../topics/native-distribution.md),
[Windows resident control](../../topics/windows-resident-control.md), and
[unified desktop client](../../topics/unified-desktop-client.md).

## Objective

Distribute the real Windows desktop controller as an optional, headless,
ordinary-user component. Preserve existing agent/CLI and dedicated-appliance
workflows while moving both deployments toward a shared desktop implementation
and an explicit user/protected boundary. YepAnywhere consumes the package and
owns its enable/update UI; it does not own a fork of the controller.

## Completion conditions

- An unlocked interactive Windows user can run the packaged resident without
  a service, elevation, source checkout, SDK, or global provider installation.
- The existing service command, default client endpoint, appliance installation,
  request/result vocabulary, and authorized protected behavior remain compatible.
- User and appliance deployments have explicit endpoint selection and separate
  writable state. User mode never selects or retries through the broker.
- Capabilities disclose deployment profile, actual privilege, session limits,
  omissions, and provider availability. Protected requests receive typed refusals.
- An ordinary-user package supports install, launch, stop, upgrade/rollback,
  and removal with a reviewable ownership boundary. Fixtures are separate.
- CI produces self-contained ARM64 and x64 payloads with publisher signatures
  and package authentication. Signed provider bytes have verified provenance;
  exact dependency notices accompany distributed components.
- Candidate acceptance exercises the common desktop contract, independent app
  effects, local/outside parity, stale references, provider failure, and lifecycle.
  Appliance regression includes ordinary and explicitly authorized protected
  control. Native ARM64 and x64 evidence is tracked separately.

## Boundaries

Windows first. No Tauri shell, replacement provider, new remote listener,
arbitrary privileged administration API, or change to target claims and VM
lifecycle. SSH administration remains testbed-owned. No automatic migration of
existing installations. An ordinary-user pipe is an OS-user boundary, not
containment against another unrestricted process belonging to that user.

The initial artifact is an installable versioned directory/archive suitable for
consumer supervision. An MSI and YepAnywhere product UI are subsequent consumer
integration work. Do not publish a public release as an incidental test step.

## Ordered work

### 1 — preserve the appliance contract and introduce user hosting

Record current service/client defaults in regression checks. Add an explicit
ordinary-user resident entry point and client selection without changing those
defaults. Reuse the existing provider router and desktop implementation. Give
the new host an operation allowlist, generation checks, interactive-session and
integrity checks, bounded IPC handling, and user-scoped endpoint ownership.
Keep the broker-managed session host's protected behavior unchanged.

### 2 — isolate state and report the profile honestly

Separate user artifacts/provider state from appliance ProgramData. Keep provider
binaries bundle-relative and verify their provenance. Project capabilities for
the actual host: ordinary mode must not advertise protected workers, login, or
broker retries. Report a locked/unavailable desktop without attempting to switch
to it. Preserve actual provider, delivery, effect, and uncertainty results.

### 3 — package and manage the real payload

Publish both Windows architectures using the existing native dependencies and
pinned Cua provider. Separate product payload from development tooling and
conformance fixtures. Add a consumer-facing lifecycle entry point with explicit
installation identity, versioned staging, validation before activation, recovery
to the previous version, and removal restricted to owned files/processes.
Document launch/IPC/profile/version compatibility and local use.

### 4 — prove the candidate without replacing the accepted runtime

Run doctor before target use and hold an exclusive common CLI claim throughout.
Use SSH/PowerShell for staging and independent evidence; launch desktop processes
through the existing interactive-session machinery. Use a distinct candidate
endpoint and assert its generation/profile. Use an isolated workspace when
service absence or clean installation would otherwise disrupt the accepted VM.
Always release claims/workspaces and restore the appropriate initial power state.

Run the same ordinary conformance against user and appliance modes. Independently
verify fixture/file/window effects. Exercise protected refusals, interrupted IPC,
restart/stale generation, two installations, missing provider, install/upgrade/
rollback/removal, and local/outside parity. Prove runtime-only installation with
no incumbent service masking missing prerequisites. Record native x64 separately
from ARM64; cross-publishing is not native execution evidence.

### 5 — sign CI artifacts and rerun acceptance on final bytes

Reuse the accepted main-only release environment and signing identities. Build,
test, sign, verify publisher/chain/timestamp, package, and authenticate the final
manifest. Audit exact dependency notices and account for Authenticode changing
provider digests without weakening runtime verification. Download the exact
signed artifact and run candidate acceptance again. Hosted compile/sign success
does not substitute for interactive-desktop acceptance.

## Validation

Run portable contract/client tests, Windows source/PowerShell checks,
`dotnet format --verify-no-changes`, and self-contained ARM64/x64 publishes.
Add meaningful tests for endpoint defaults/isolation, privilege refusal,
capability truth, generation fencing, and package lifecycle. Run existing
appliance conformance and the new workstation acceptance on claimed targets.
Minimize public evidence; private target identities, receipts, and captures
remain in ignored local storage. Stop short of claiming completion for any
unexecuted architecture or signed-artifact acceptance cell.

## Final result

In progress. The user host, explicit client/adapter selection, isolated artifact
storage, capability projection, package builder, lifecycle manager, full-file
catalog signing, and preview manifest workflow are implemented.

Initial unsigned ARM64 VM acceptance passed ordinary Medium startup, Cua
semantics/capture, independent fixture counter effect, protected refusals,
stale-generation refusal, common-client selection, running-install refusal,
stop without appliance fallback, and unchanged default appliance client access.
Two-version lifecycle acceptance also passed upgrade, rollback, stale requests,
two-instance isolation and removal. It found and fixed Windows PowerShell's
null-to-empty backup-path conversion in atomic `File.Replace` activation.
An activation lock now covers direct-runtime start versus package mutation.
The native Windows source build/format/PowerShell syntax checks passed. Both
architectures cross-publish; portable/client and release-signature tests pass.

Still required: appliance regression
against the changed service build in isolation, service-absent/runtime-only
acceptance, native x64 execution, and exact signed CI artifact acceptance. Do
not present the initial proof or a signed CI run as completion of these gates.
