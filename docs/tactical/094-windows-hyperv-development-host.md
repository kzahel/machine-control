# 094 — Windows development host and Hyper-V test loop

Status: native builds and two Windows build/deploy/test cycles passed on a
Windows Home x64 host. The VirtualBox follow-up qualified a Windows lifecycle
compatibility profile and promoted a protected stopped base, with an accepted
independent full-copy development VM. Linux resident/cold-boot evidence also
exists. Complete factory and isolated-workspace integration remain open;
Hyper-V is unimplemented and QEMU/WHPX Windows 11 TPM support remains blocked.

Owning topics: [VM workspaces](../../topics/vm-workspaces-and-storage-policy.md),
[cross-platform coordinator](../../topics/cross-platform-coordinator.md),
[target lifecycle](../../topics/target-lifecycle-and-readiness.md), and
[Windows resident control](../../topics/windows-resident-control.md).

## Objective

Use the operator's fast Windows machine for native builds and orchestration,
with Hyper-V Windows guests for installation and disruptive acceptance. Keep
the checkout, toolchains and reusable build caches on the host rather than
making a small VM the main compiler. Establish this loop before continuing
Windows desktop feature parity work.

**Decision:** prioritize the Windows-host provider now because it serves both
the immediate development workflow and the existing cross-platform hosting
direction. Host builds can start before the provider is complete. An agent
may run on the Windows host, but neither YA delegation nor a second agent
inside the guest is required. Ordinary guest control stays target-native.

## Starting point

**Decision (2026-10-04):** the operator does not want Windows Pro to become a
hosting prerequisite and authorized a bounded QEMU/WHPX experiment after
read-only inspection found Windows Home. Evaluate that route before the
Hyper-V-specific implementation steps below. Any host reboot requires explicit
operator approval. This changes provider qualification order; it does not
authorize declaring a supported provider from low-level smoke tests.

**Current:** the coordinator and local Windows desktop adapter exist. Windows
VM hosting is implemented for UTM on macOS and libvirt/KVM on Linux; there is
no implemented Hyper-V provider. See the [host matrix](../../README.md#controller-host-support)
and the [Linux provider precedent](028-linux-libvirt-controller-host.md).

**Current:** the desktop product contains a React/TypeScript UI, Rust/Tauri
shell and supervised C#/.NET Windows engine. Python supplies the shared CLI,
coordination and packaging tools. Signed 0.5.4 Windows packages were built in
CI and installed on the ARM64 VM for acceptance; that is not evidence of a
complete local Windows-host build loop.

**Current:** UAC approve/cancel, elevated applications and lock/login already
exist in the protected appliance runtime. The separately armed workstation
unlock component preserves an existing console session. These are distinct
from the ordinary desktop profile. Do not reimplement them or silently grant
their authority to desktop callers as part of this provider work.

**Current:** private inventory and read-only inspection resolved the x64 Home
development host and baseline resources/toolchains. No host was selected by
the original planning commit; the initial experiment below records the later
inspection. **Open:** qualify a reproducible Windows Home hosting profile and
prove the installed toolchains through actual builds.

## Boundaries

- First acceptance is one Windows guest on the selected Windows host's native
  architecture. Record the exact supported host/guest configuration. Do not
  import the ARM64 UTM disk into an incompatible host or use emulation as an
  implicit fallback. Linux guests are a later extension, not this gate.
- Public provider code belongs here; private identities, switches, storage,
  endpoints, media locators and credentials remain in private inventory/state.
  Preserve unrelated edits. Use Git through WSL on Windows, as required by
  project instructions; run Windows compilers and Hyper-V management natively.
- Keep the development host out of guest installer, UAC, lock, logout and
  destructive lifecycle tests. Native development does not authorize replacing
  the host's installed desktop app or changing its standing control grants.
- Use Hyper-V management interfaces for lifecycle. PowerShell Direct is a
  candidate bootstrap/recovery route; validate its actual requirements before
  adopting it. Ordinary administration and UI control use the guest's existing
  authenticated transport and resident facade. VMConnect is not the test loop.
- Retain Windows Secure Boot, TPM, UAC, secure-desktop and credential policies.
  Never turn generic host administration into an arbitrary SYSTEM guest API.
- Do not add desktop feature parity changes, reboot-persistent consent, Linux
  guest acceptance, remote provider hosting or a new release to this slice.
  Keep signing credentials in the existing release system. Local development
  binaries do not establish signed-install/update acceptance.

## Ordered work

### 1 — select and inspect the Windows development host

Resolve the intended machine through private inventory; ask for its logical
selection only if ambiguous. Inspect architecture, edition, virtualization
readiness, Hyper-V management access, WSL/Git, native toolchains, existing VMs,
networking and storage capacity. Check current Microsoft prerequisites rather
than assuming one Windows edition or CPU architecture supports the plan.
Record a private baseline and any required feature activation/reboot. Establish
the actual host interruption window before a disruptive host transition.
Do not modify unrelated VMs, switches or management permissions.

Choose a host-local checkout and cache layout accessible to native tools and
WSL Git without maintaining two independently edited copies. Verify path,
quoting, executable and line-ending behavior. Keep concrete paths private.

### 2 — prove native host builds before VM provisioning

Use [Windows desktop CI](../../.github/workflows/windows-desktop.yml),
[component packaging](../../release/windows-package.py) and repository locks
as the dependency/build source. Install or reuse the required .NET SDK,
Rust/MSVC toolchain, C++ Build Tools/Windows SDK, Node, pnpm and Python; record
actual versions and architecture. Do not assume the source checkout's static
package version is the release version; use the existing version/staging tools.

Build and test the Windows engine, frontend, Rust shell and a complete local
development package. Provide repeatable commands for engine-only, frontend
and full-shell changes. Reuse verified component staging rather than rebuilding
unrelated layers on every edit. Bind deployed artifacts to source revision and
digests. Record one cold build and representative warm rebuild timings; do not
claim an iteration-speed improvement without measuring it.

### 3 — add the Hyper-V provider and common adapter

**Proposal:** place reusable Windows-host management under
`providers/hyperv-windows/` with a thin Windows target integration under
`platforms/windows/providers/hyperv-windows/`. Keep provider-specific commands
behind the existing common CLI; do not add a parallel VM command vocabulary.

Implement read-only capabilities/doctor and exact VM-ID resolution first,
then guarded start, clean shutdown, reboot, explicit recovery and storage
inspection. Re-read identity, role and capability before mutation. Register
Windows controller eligibility and truthful unsupported capabilities.

Integrate the existing claim authority, command audit and provisioning journal.
Refuse missing, expired or mismatched claims on accepted-target operations;
use the existing explicit factory boundary before a newly created VM can be
pinned and claimed. Serialize conflicting management/workspace mutations.
Claims coordinate use and are not authentication or desktop authorization.

Test management parsing and refusal paths with deterministic fixtures before
live mutation. In particular, cover missing/renamed/replaced VMs, non-owned
resources, unavailable permissions, unsupported hosts and interrupted commands.
Never auto-adopt a same-named VM or hide uncertain completion with a retry.

### 4 — provision and recover one Windows appliance

Begin a [private provisioning journal](../provisioning-journals.md). Adapt the
existing Windows factory/bootstrap to the verified Hyper-V guest configuration
and official native-architecture media. Reuse Windows guest setup and resident
code; replace only hypervisor-specific provisioning and transport assumptions.

Store every assigned login password immediately in the controller's canonical
untracked secret store, with mode 0600 where meaningful and equivalent private
Windows ACL protection. Rotate the same locator atomically and verify the
canonical password before promotion. Answer files, chat and auto-login are not
credential handoff. Keep secrets out of arguments, ordinary JSON and logs.

Pin the created VM's exact identity privately. Doctor and claim it before
meaningful accepted-target use. Establish authenticated administration, native
app launch and the existing resident service independently of a visible host
console. Inspect credentials through `inventory credentials` for unlock/login;
use the supported secret transport rather than asking for passwords in chat.

Prove reboot and guest-transport recovery with fresh runtime/session identity.
Qualify a bounded recovery route when ordinary transport is unavailable;
report console capture/input unavailable unless actually implemented and tested.
Any necessary outer UI recovery must remain explicit and must not become the
normal install/test path. Keep the privileged appliance management runtime
separate from the ordinary desktop product being tested.

### 5 — add isolated test workspaces and safe cleanup

Map existing `persistent`, `isolated` and `candidate` intents onto tested
Hyper-V mechanisms. Evaluate a stopped immutable base plus differencing VHDX
and a separately identified derivative; do not assume a checkpoint alone gives
isolation or safe discard. Report the actual mechanism. If the common mechanism
schema cannot describe it honestly, extend that contract with compatibility
tests rather than mislabeling it as another provider's format.

Bind private receipts to exact base/derivative VM and disk identities, claim,
requested intent and cleanup disposition. Protect the base and its backing
chain; check storage headroom, parent dependencies and concurrent acquisition.
Default to one development target, one stopped ready base and at most one
temporary workspace; do not make per-feature clones or full-copy fallbacks.

Prove isolated marker changes disappear after release while the base remains
unchanged. Candidate intent retains its explicitly owned result. Failed or
partial acquisition/release must retain enough private state for exact recovery;
unknown outcomes are not permission to delete by name or retry allocation.
Exercise missing/foreign receipts, wrong claims and last-ready-base protection.

### 6 — prove and document the host-to-guest iteration loop

From the Windows host, run a repeatable command-driven sequence: build a known
revision, acquire the guest/workspace, deploy the exact artifact, run native
tests with independent fixture effects, collect minimized evidence and release
in finally-style cleanup. Renew claims during long work. Guest UI tests must
leave host focus, pointer and keyboard alone without a VMConnect window open.

Run a second warm edit/build/deploy/test cycle to prove useful incremental
iteration, not just one successful installation. Exercise the separate appliance
UAC/lock routes with existing fixtures and qualify ordinary desktop grants,
indefinite arming, Pause/Resume and Stop without conflating the two profiles.
Use the existing signed candidate/public packages for any signing, replacement
or updater assertions; do not publish merely to validate this provider.

Update the owning topics, Windows host matrix, platform guide, provider research
and System Map as their facts change. Document supported edition/architecture,
toolchain bootstrap, daily build commands, guest selection, credential locator,
recovery, cleanup and measured cycle times. Public docs use placeholders only.

## Completion and validation gates

- Native host engine checks, `dotnet format --verify-no-changes`, contract
  tests, frontend checks and appropriate ARM64/x64 publishes pass. Full local
  Tauri packaging works; hosted CI remains the signed release authority.
- Portable coordinator/provider fixtures pass, including claim/identity,
  serialization, failed creation, capacity and receipt-bound cleanup cases.
- One new native Windows guest reaches read-only doctor readiness, verified
  credential handoff, reboot recovery and independent resident control effects.
- Persistent, isolated and retained-candidate outcomes are exercised. The
  isolated base is unchanged, owned derivatives are cleaned up or explicitly
  retained for diagnosis, and all completed-use claims are released.
- Host-native builds drive two successful guest test cycles without routine
  outer input. Record measured timings and supported recovery limits.
- Leave host/guest power and installation state documented, preserve unrelated
  host work, finish the provisioning journal, and provide a repeatable handoff.

## Subsequent Windows product work

After this infrastructure gate, scope separate implementation tacticals for
desktop integration of existing protected capabilities, same-session consent
restoration, polite activity-aware control, authenticated caller integration,
and browser upload/raw CDP gaps. Reuse the protected appliance and optional
unlock implementations; personal-desktop authority requires its own explicit
contract and acceptance. Reboot persistence remains a separate decision.

## Final result

### Initial Windows Home feasibility — 2026-10-04

Private inventory resolved the intended x64 development host. WSL Git worked;
the checkout was clean. Native .NET, Rust/MSVC, C++/Windows SDK, Node and Python
were present; package-manager alignment and actual builds remain untested.
The full Hyper-V role is unavailable on Home. No existing target was operated.

The operator authorized a bounded QEMU/WHPX experiment, retaining explicit
approval for any reboot. A private provisioning journal began before the
experiment. A digest-verified Windows QEMU distribution was extracted into
private experiment storage without system-wide installation. Direct-script
steps, including the initial stdio QMP harness failure, were recorded manually.

Measured results (single smoke samples, not OS boot or iteration benchmarks):

| Probe | Result | Elapsed |
| --- | --- | --- |
| Diskless guest instruction marker, WHPX only | Expected exit marker observed; no emulation fallback | 0.147 s |
| Headless QMP over loopback | Prelaunch/running/paused readback and clean exit | 0.145 s |
| Offline QCOW2 overlay | Marker verified; base digest unchanged; fresh overlay had no marker | Not timed |

The feature-enable request was cancelled after probes succeeded without it.
HypervisorPlatform still reported disabled, with an existing active hypervisor
and WSL2. No reboot or host feature change occurred. This is a bounded observed
configuration, not a recommendation to ignore upstream setup requirements.
The [provider dossier](../../research/providers/qemu-whpx.md) owns the capability
interpretation and open qualification gaps.

Cleanup: all probe processes were reaped and the two temporary probe disk files
were deleted. Private binaries, tiny test firmware, scripts and minimized logs
remain for reproducibility. No Windows installation, guest account, password,
accepted target, target claim or provider integration was created. Journal
closure records abandonment of full provisioning at this intentional smoke-test
boundary, rather than claiming appliance readiness.

The next gate is an actual Windows boot with supported firmware/TPM and guest
transport. Native builds, the common adapter, protected resident acceptance,
claimed workspaces and both measured build/deploy/test cycles remain pending.

### Windows guest preflight — 2026-10-04

The operator authorized the next experiment while retaining the no-reboot
boundary. A new private provisioning journal began before guest preflight.
The native QEMU binary rejected `-tpmdev` and reported `tpm-crb` and `tpm-tis`
absent. Upstream build/backend inspection confirmed a native Windows-host TPM
exclusion; merely installing another standard Windows package or running a
TPM server in WSL does not supply that missing backend. The
[provider dossier](../../research/providers/qemu-whpx.md) owns that finding.

Result: blocked before Windows boot. No installation media was downloaded,
guest disk created, credential assigned, accepted target/claim acquired, or
security check bypassed. All capability probes terminated; private source
snapshots and a reproducible preflight report remain for diagnosis. The journal
closed as blocked. No host feature, installation or reboot change occurred.

Windows boot/Secure Boot/TPM, unattended transport and resident effects remain
unproved. A supported native TPM route or another Home-capable VM provider is
needed before this Windows 11 experiment can continue. The earlier WHPX and
offline overlay results remain valid within their narrower scope.

### VirtualBox installer experiment — 2026-10-04

The operator selected a bounded VirtualBox experiment, retaining explicit
approval for any host reboot. A new private provisioning journal preceded
installation. The signed core application and support driver installed with
restart suppressed, exit status zero and no restart requested. Host boot time
remained unchanged. Optional networking/USB drivers and the Extension Pack
were not installed; the guest used NAT in an isolated private VM library.

Direct VBoxManage scripts bound each operation to a new exact UUID receipt.
The scratch VM used EFI, TPM 2.0, enrolled Secure Boot keys, four CPUs, 6 GiB
RAM and a 64 GiB dynamic disk. Official Windows 11 Enterprise evaluation media
matched Microsoft's published digest. The stock unattended template's hardware
check bypasses were removed and the rendered answer checked. The randomly
assigned password was stored atomically behind private Windows ACLs and passed
through password-file options. Its canonical stored value matches the prepared
answer; guest authentication has **not** been verified.

| Probe | Observed result | Elapsed |
| --- | --- | --- |
| Official evaluation ISO download | Full digest verified | 111.6 s |
| Headless start command | Provider accepted start; installer subsequently visible | 3.6 s |
| Unattended installation | Reached 77%, then blank console; no Guest Additions | Still incomplete after 21 min |
| Clean ACPI shutdown request | Request delivered; VM remained running | More than 2 min observation |

These are single experiment measurements, not build/deploy benchmarks. The
native Windows hypervisor backend reported slow execution mode. WSL remained
responsive, but coexistence performance is not qualified. After the blank
screen, the disk file timestamp stopped changing; a provider-native Shift tap
had no visible effect. Read-only debugger probes identified a Windows kernel
and reported no bugcheck. The cause remains unknown. Console capture/input was limited to this
explicit bootstrap diagnosis and did not use the host desktop.

At the initial check-in, cleanup was incomplete pending an operator decision
on forced guest recovery. The unaccepted scratch VM and its private disk,
NVRAM/TPM state, installation media and credential store were retained. No
accepted target or claim was created. Direct-script operations were recorded
manually because no common VirtualBox adapter exists.

The operator then authorized forced recovery. Exact-UUID force-stop followed
by one headless cold boot resumed setup from the existing disk; the start
command took 3.15 s. Within about one minute, setup displayed its next stage,
then advanced to 42%. Read-only debugger inspection identified the installed
Windows kernel. Storage counters showed continued I/O through roughly seven
minutes, despite an unchanged VDI timestamp and blank console. This corrects
the earlier interpretation of file timestamps as evidence of stopped writes.
The counters subsequently remained unchanged for several minutes and Guest
Additions never became available. No bugcheck was reported. A second clean
ACPI shutdown request did not stop the guest during 108 s of observation.

Cleanup: the same scratch VM was force-stopped under the recovery authorization
after approximately 12.2 min of this cold-boot attempt. Power-off readback was
verified and no further recovery boot attempted. Headless VM processes exited;
the disk, firmware/TPM state, media and private credentials remain for diagnosis.
The canonical secret was rechecked against the prepared answer, and ordinary
diagnostic files contained no matches for that secret. Guest authentication
remains unverified. Host boot time stayed unchanged; no host security/feature
changes occurred. The journal closed as blocked with the retained resource
state and credential limitation recorded.

Result: scriptable creation, headless installer boot and installed-kernel boot
are demonstrated. Completed Windows setup, effective Secure Boot/TPM,
credential authentication, guest command effects and recovery to guest readiness
remain unproved. The
[provider dossier](../../research/providers/virtualbox.md) owns the capability
assessment. Common-provider integration, isolated workspaces, resident
acceptance, native builds and both measured iteration cycles remain pending.

### Autonomous Windows and Linux provisioning — 2026-10-04

The operator expanded the experiment to end-to-end Windows and Linux setup,
retaining the explicit host-reboot approval boundary. Separate private journals
covered the two candidates. Direct Git commands used WSL and builds/VirtualBox
management stayed native; an internal package-helper exception was discovered
and fixed below. No host reboot or security/feature change occurred.

An opt-in native Windows adapter now binds exact VM/configuration/disk pins,
exclusive claims and serialized operations. Pinned loopback SSH carries the
existing guest residents and credential verifiers. Ordinary tests use only
guest-native routes. Explicit disruptive recovery covers console capture,
ACPI delivery, forced stop and bounded stopped-candidate hardware experiments.
Creation and initial console bootstrap remain private direct-script steps,
recorded manually in the journals.

| Measurement | Result | Elapsed |
| --- | --- | --- |
| Native Windows static checks | Build, formatting and contract suites passed | 28.344 s |
| Native x64 runtime package | Existing runtime and desktop companion built | 3.186 s |
| Medium/elevated fixture publishes | Both self-contained publishes passed | 1.446 / 1.457 s |
| Linux resident deployment | Existing resident, broker and fixtures installed | 19.7 s |
| Linux resident conformance | Independent semantic/Unicode effects and capture hash; local/remote parity | 17.427 s |
| Linux warm reboot | New boot/resident identities and ready doctor observed | Within 50.909 s |
| Linux post-recovery conformance | One-CPU recovery, then two four-CPU cold boots passed | 15.461 / 14.693 / 16.482 s |

Linux used a digest-verified official Ubuntu 24.04 cloud image, EFI Secure Boot,
pre-pinned SSH host keys and a canonical password established and independently
verified through the existing verifier. GNOME Wayland and the existing resident
were installed. Four-vCPU cold boot initially stalled during initramfs driver
loading. One CPU restored access; guest arguments
`nox2apic rcupdate.rcu_normal=1` then enabled repeated four-vCPU cold boots.
The [provider dossier](../../research/providers/virtualbox.md) owns the upstream
comparison and cause uncertainty. Both final cold boots had seed media detached.

Linux cleanup: final doctor and password verification passed, guest-native
shutdown reached confirmed power-off, and the exclusive claim was released.
The private disk, firmware, keys, canonical credential, detached seed and
diagnostic evidence are retained. The journal closed ready for the experimental
candidate scope. Immutable-base promotion and isolated workspaces remain blocked.

Windows reached a responding login screen with three vCPUs, ordinary APIC
enabled, x2APIC disabled and guest paravirtualization `none`. Its stored
password authenticated and Guest Additions became available after first-logon
setup and a clean guest shutdown/cold boot. UAC remained active: a non-elevated
security probe was denied, and SSH bootstrap required the observed guest UAC
consent. Native OpenSSH capability installation took roughly 30 minutes before
the existing bootstrap completed with PowerShell 7 and key-only SSH. Its host
key was independently pinned before the first connection. Guest checks then
verified effective Secure Boot, ready TPM 2.0, no hardware-check bypasses and
UAC consent on the secure desktop.

Native build follow-up found two host-specific frictions. Package source-state
inspection originally invoked native Git internally; `--git-via-wsl` now routes
that inspection through WSL without adding a WSL prerequisite to hosted CI.
The native unlock bootstrap's generated batch command now uses an explicit
relative path, so it works with `NoDefaultCurrentDirectoryInExePath` enabled.
A complete unsigned development component build then passed in 12.750 s;
publisher signing remains exclusively in CI.

The existing transactional appliance installer and resident conformance suites
completed two measured iterations. Toolchains and build caches stayed on the
host; ordinary tests used pinned SSH and guest-native control with no host
desktop interference. Unchanged conformance fixtures were reused in cycle two.

| Windows measurement | Cycle one | Cycle two |
| --- | --- | --- |
| Native x64 runtime package build | 3.186 s | 8.328 s |
| Package transfer | 16.379 s via bootstrap Guest Additions | 5.138 s via pinned SFTP |
| Hash verification, extraction and transactional replacement | Completed; not separately timed | 15.365 s |
| Full resident desktop conformance | 67.583 s, passed | 59.729 s, passed |
| Protected UAC cancellation/approval conformance | 26.513 s, passed | 33.254 s, passed |

The first full test attempts exposed interference from the task's elevated
bootstrap terminal and a fixture startup exceeding the original timeout.
Minimizing that guest window and allowing an explicit 60-second transition
budget produced passing tests. The checked-in UAC harness retains its original
timeouts unless the caller requests that bounded override.

The existing optional unlock component installed unarmed in 22.418 s. Its
account, transport identity, controller fingerprint and bounded expiry were
observed in the native approval dialog. Ordinary semantic invocation failed;
the existing guest-local consent fixture completed approval and removed its
temporary task. An independently observed lock then passed the existing
signed-challenge, one-shot credential unlock and returned to the ordinary
desktop. Appliance authority remains separate from the desktop application.

Two transport fixes were required: SFTP replaced binary PowerShell stdin copying
that could stall, and absolute native OpenSSH paths prevent an OpenSSL PATH
addition from selecting Git's SSH. The latter failure refused before reading
the credential. Canonical password verification also passed with PowerShell 7.

Windows lifecycle acceptance failed after those successful iterations.
Automatic login, the registry's cached setup password and cached Panther answer
files were removed. Guest-native shutdown remained running beyond five minutes;
explicit recovery capture first showed shutdown and then a black screen. A
claimed force-stop was required. With installation media detached, a three-vCPU
cold boot reached pinned SSH and the resident's protected Winlogon snapshot,
with no interactive user. The following curtain-reveal call timed out and SSH
became unavailable. A four-vCPU recovery accepted the reveal input, but its next
observation timed out; both SSH doctor and authenticated Guest Additions
diagnosis then failed. No password was read or submitted for either cold-login
attempt. These failures do not establish a root cause or invalidate the earlier
existing-session unlock result.

The candidate remains useful as retained diagnostic evidence, but it is not a
reliably provisioned Windows base. Cold login, repeated clean lifecycle,
common-factory creation/promotion, and isolated workspaces remain unqualified.
No host reboot, host security change or WSL shutdown was performed. The private
journal records direct bootstrap/recovery actions and exact evidence; this
tactical is not complete.

Final Windows cleanup: a last boot restored the three-vCPU experiment setting
for an attempted authorization cleanup, but reached Automatic Repair before SSH
became available. The exact candidate was force-stopped and its power-off state
verified. Installation media remains detached; the disk, firmware/TPM state,
private keys, canonical password and evidence are retained for diagnosis. The
stored password's fingerprint is unchanged from its successful guest
verification, effective private ACLs were checked, and ordinary evidence files
contained no password matches. The temporary consent fixture had already
removed its task. Explicit unlock-grant revocation could not run on the final
boot; that test grant retains its bounded expiry and its controller key stays
private. No guest VM process remains, and the Windows claim was released.
The Windows journal closes **blocked**; the Linux journal remains **ready**.

Validation: twelve adapter regressions pass on native Windows and WSL, seven
unlock-controller tests pass, and package tests pass with the Windows symlink
case skipped. The modified UAC harness parses and passed both live iterations.
Host boot time remained unchanged. No public release or local signing occurred.

### Stability follow-up — qualified compatibility profile

The operator requested a stable retained Windows base and questioned whether
short shutdown waits had been mistaken for hangs. A fresh private journal and
disruptive claim cover this attempt. Before recovery, a stopped copy of the
complete candidate directory, including firmware/TPM state, was verified file
by file with SHA-256 in 188 seconds. It is a diagnostic backup, not a ready base.

The next boot reached Windows without recovery input. Administration observed
no CBS or Windows Update reboot marker, no pending file rename, and no active
servicing worker. Guest Pacific time and host-local virtual RTC produced a
nine-hour boot correction. The guest time zone and stopped virtual RTC were
aligned to UTC; the following boot's timestamp matched the controller.

Cold login passed using the existing appliance login pipe and canonical stored
password, after fresh account/field discovery. Ready doctor and live credential
verification followed. Guest shutdown then completed in 278.154 seconds with
no force-stop. Windows adapter shutdown now allows fifteen minutes, rechecks
its claim, and never automatically force-stops. The common adapter also gains
guarded cold login and bounded recovery keys. Seventeen adapter regressions
cover identity, claims, credential refusal, secret transport and slow shutdown.

A subsequent UTC boot still stalled during guest control. One recovery Escape
was followed by responsive SSH, but the result did not repeat reliably. This
does not establish an input-wake root cause. At that point, repeated lifecycle, promotion and
cleanup acceptance remained unqualified.


The guest-facing Hyper-V paravirtualization interface (with the host backend
unchanged) reached administration in 35.081 seconds and passed full resident
conformance in 71.580 seconds and protected UAC conformance in 31.206 seconds.
The optional unlock grant was explicitly revoked and no consent-fixture task
remained. An unassisted shutdown still exceeded fifteen minutes; one explicit
pause/resume was followed by power-off in 5.149 seconds. A privately enabled,
bounded shutdown scheduling assist subsequently completed one cycle in 37.940
seconds. It is reported as an outer lifecycle compatibility experiment and
requires disruptive authority before shutdown; it is not an ordinary desktop
control route or proof of an unassisted lifecycle.

Idle transport remained unreliable. Five-, fifteen- and thirty-second SSH
handshake budgets all failed in separate attempts, including a banner timeout.
Authenticated Guest Additions diagnosis found Windows and sshd running, the
local SSH banner responsive, and guest networking configured. Disabling guest
Intel virtual-NIC interrupt moderation became the next focused experiment;
these incomplete observations alone did not justify promotion.


The final private profile retains three virtual CPUs, ordinary APIC with
x2APIC disabled, guest-facing Hyper-V paravirtualization, UTC guest/RTC time,
and disabled guest Intel NIC interrupt moderation. SSH allows a bounded
fifteen-second handshake without automatically replaying commands. Native
shutdown includes the explicitly enabled single pause/resume after thirty
seconds. This combination is qualified on the tested controller; individual
causality and broader host compatibility are not established.

Three distinct source boots passed guarded cold login, idle readiness, live
canonical-password verification, Secure Boot/TPM/UAC checks, no pending restart
or servicing, absent automatic-login/cached-password state, and observed OS
power-off. Their shutdowns took 37.882, 37.893 and 69.193 seconds. Two reached
administration in approximately 58 seconds. The last included five untouched
idle minutes. An earlier 221.533-second shutdown had supplemental hypervisor
register queries and was conservatively excluded from the acceptance set.

The five-minute-idle run's first resident suite failed at the Start-menu stage;
its exact stderr was not retained. An unchanged diagnostic rerun passed in
54.439 seconds without VM recovery or restart, followed by protected UAC
conformance in 30.481 seconds. This test friction remains recorded rather than
being reported as a clean first-pass run.

A native full clone completed within 164 seconds, retaining firmware/TPM and
guest hardware identity while allocating fresh VM/disk/MAC identities and a
separate pinned loopback transport. An incorrect forwarding-rule-name
assertion stopped post-copy configuration before boot; exact inspection and a
corrected private step completed it without creating another clone. Its own
journal, exact claims and canonical stored password covered acceptance.
The derivative passed cold login, configuration readback, full resident
conformance on its first attempt in 76.849 seconds, protected UAC conformance
in 28.376 seconds, idle readiness and live security/password verification.
Its native shutdown completed in 37.975 seconds with the declared assist.

The stopped original was then promoted in place through the common CLI.
Promotion and independent verification hashed its disk, VM configuration and
firmware/TPM state; the three qualified lifecycle receipts and canonical
credential stamp remain private. A public start attempt was refused, and an
independent observation confirmed the protected source stayed off. The
accepted full-copy derivative is retained as the development target. These
are same-controller private appliance results, not generalized export or
isolated-workspace qualification.


Final cleanup retained the protected base, accepted development VM, canonical
credentials, private journals, ownership receipts and diagnostic logs. Only the
superseded diagnostic backup disk was deleted after receipt/path/hash checks
and verification of both retained replacements, reclaiming approximately
22.1 GiB. Both VMs ended stopped, both claims were released, and both follow-up
journals closed ready with zero unpaired commands. Host boot time was unchanged;
no host reboot, WSL shutdown, host security disable, local signing or public
release occurred. The optional unlock grant was revoked before derivation.
Private text evidence was scanned without credential matches; effective secret
ACLs were checked. A private retained-target registry and handoff document
preserve base/development selection without replacing other inventories.

Implementation commits: `7f3d605` adds guarded cold login and the longer
shutdown observation window; `3d6620d` adds qualification/protected-base guards
and the explicit compatibility controls. Twenty-nine adapter/image regressions
pass on native Windows and WSL. Live evidence establishes this bounded
compatibility profile and retained appliance milestone. Complete common-factory
creation/derivation, isolated workspaces, unassisted lifecycle reliability,
remote hosting and Windows ARM support remain open; this tactical as a whole
is not complete.

### Unassisted shutdown trace — 2026-10-05

The user requested a clean committed tree followed by shutdown tracing, to
investigate the pause/resume dependency rather than assume a guest power
setting would fix it. Research and the proposed experiment sequence were
committed before the live run (current history: `cb630e7`).

Read-only doctor, an exclusive disruptive claim, private journals, canonical
credential verification and guarded cold login covered the retained development
VM. The protected base remained off. A private configuration copy disabled
only the shutdown assist while retaining exact target identity; the normal
configuration was verified unchanged. No password submission occurred during
recording. Built-in WPR profiles failed with `0x80070032`, including a CPU-only
probe without shutdown persistence. Partial files and recorder state were
inspected; the successful custom probe was cancelled before the actual run.
A minimal custom shutdown-persistent profile succeeded
with scheduler, loader, disk, interrupt, power, service and logon coverage,
without sampled CPU stacks.

The native full shutdown failed its unassisted observation after 902.129
seconds. No console input, debugger probes or pause/resume occurred during
that interval. One explicitly claimed pause/resume recovery was followed by
independently observed power-off in 4.373 seconds. After restart, WPR merged
the private trace and was verified stopped; pinned transfer and matching
guest/controller hashes verified the retained approximately 16 MB ETL.

The trace contains 230,885 events with zero reported event or buffer loss.
After approximately eight seconds, only seven events appear over roughly
895 seconds; activity returns around recovery. The controller decoder emitted
inconsistent timezone suffixes, so relative timing was calibrated to the ETL
header and displayed wall clock rather than mixing those offsets. Some guest
schemas remain undecoded. Interpretation, Fast Startup availability and the
next diagnostic comparison live in the
[VirtualBox dossier](../../research/providers/virtualbox.md#unassisted-shutdown-investigation).
This is useful instrumented reproduction evidence, not unassisted lifecycle
acceptance or a confirmed root cause.

Private journals record recorder failures, a refused claim-release invocation
that incorrectly supplied the global claim argument, its corrected release,
and direct recovery/transfer steps outside automatic CLI coverage. Final
canonical credential verification passed. Cleanup using the normal assisted
profile completed in 37.969 seconds; the development VM ended off, its claim
was released, and the protected base remained off. Normal configuration and
host boot time were unchanged. No force-stop, host reboot, host security/WSL
change, or guest power-setting change occurred. Raw traces, decoded events,
provider logs, scripts and exact journal references remain private.
