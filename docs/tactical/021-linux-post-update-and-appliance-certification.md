# Tactical 021: Linux Post-update and Appliance Certification

Status: complete.

Topics: `linux-resident-control` and `target-lifecycle-and-readiness`.

## Objective

Give the retained Ubuntu GNOME Wayland development appliance the same bounded
maintenance lifecycle proven on Windows, while keeping the implementation and
evidence Linux-native. Add a minimized read-only post-update audit, narrowly
enumerated systemd repair, explicit reboot certification, reproducible runtime
and development profiles, and exact-source in-appliance checks without making a
clone or workspace.

## Completion conditions

- `linuxvm post-update audit` never starts a stopped target, changes guest
  state, installs packages, or invokes an outer route.
- The guest audit reports minimized, stable checks for package-manager
  consistency, pending reboot state, QEMU guest-agent, GNOME Wayland session,
  SPICE session support, resident user service, root input broker, target-native
  status, and declared profile tooling without exposing concrete account,
  endpoint, path, package-source, or target identity.
- `linuxvm post-update repair` is restricted to the exact retained candidate
  and may only start or enable the enumerated installed system and user units.
  It never installs a missing component, changes login policy, clears a pending
  reboot marker, handles credentials, or uses host input.
- A missing QEMU guest-agent remains an explicit administration/recovery
  boundary. The route does not claim to repair the transport through itself.
- Reboot remains opt-in and is accepted only after the provider observes a
  changed Linux boot ID and the post-update audit plus common doctor return
  healthy.
- `linuxvm bootstrap --profile development|runtime` idempotently installs the
  declared Ubuntu package profile through guest-agent root administration,
  deploys the checked-in resident stack and post-update support, and proves
  readiness. Initial installation of a missing guest agent remains the
  documented visible-console bootstrap.
- `linuxvm appliance-certify` requires a clean committed tree and the exact
  retained candidate, audits without repair, reboots, transfers a digest-bound
  archive of the exact commit, runs portable and Linux-native checks inside the
  guest with bounded timeouts, removes staging, and cleanly shuts down only
  after all acceptance checks pass.
- One minimal live rehearsal reuses the retained Linux candidate, creates no VM
  or workspace, leaves no named staging, and leaves the candidate stopped.

## Boundaries

- Do not add libvirt/KVM, unattended Ubuntu installation, image sealing,
  generated focused repositories, or a generic cross-platform repair engine.
- Do not create, clone, snapshot, derive, compact, rename, or delete a VM.
- Do not upgrade the distribution or change update policy as part of audit,
  repair, bootstrap, or certification. Normal update installation remains an
  explicit operator action documented by the platform guide.
- Do not make ordinary doctor or candidate assertions mutating. Post-update
  audit must inspect provider power before calling any guest-agent operation,
  because the existing provider transport starts an exact stopped target when
  asked to execute.
- Do not enable Ubuntu's static, device-activated `qemu-guest-agent.service`.
  Starting it when the device exists is valid; enabling it is not.
- Do not treat active systemd units as application readiness. The final host
  result still requires the common semantic, resident, capture, and input
  doctor.
- Do not expose apt output, package versions, desktop account names, boot IDs,
  or remote staging paths in public certification results.
- Do not shut down a failed certification target; leave it running for bounded
  diagnosis after removing staging.

## Ordered work

### 1 — define minimized guest evidence

Implement a root-only Ubuntu support script with read-only `audit` and bounded
`repair` modes. Give each check a stable identifier, required status, observed
state, and repair disposition. Bind each result to a caller nonce and profile,
and omit private or machine-identifying values.

### 2 — orchestrate audit and repair

Expose `linuxvm post-update audit|repair [--reboot]`. Refuse a stopped audit
before any provider execution, require the exact candidate for repair, validate
the nonce-bound guest result, then require a ready common doctor. Keep reboot
explicit and use the provider's changed-boot-ID observation.

### 3 — make package profiles reproducible

Extend the guest bootstrap with explicit `runtime` and `development` profiles.
Add a host command that stages the exact bootstrap, deploys the resident and
support script, and finishes with the minimized audit plus full doctor. Keep
apt acquisition target-native and initial guest-agent recovery separate.

### 4 — compose exact-source certification

Add a candidate-only command that audits without repair, reboots, re-audits,
transfers a `git archive` plus SHA-256, and runs `bin/check --portable` and
`bin/check --native` from the extracted archive inside Ubuntu. Supervise each
check with a configurable timeout, remove guest and host staging on all paths,
and shut down only after success.

### 5 — test policy and failure boundaries

Add dependency-light fixtures for parsing, stopped-audit refusal, exact
candidate policy, nonce/report validation, bounded repair, profile selection,
reboot observation, source-digest checks, timeout/failure behavior, cleanup,
and success-only shutdown. Prove no clone, workspace, or outer route is used.

### 6 — run one bounded live rehearsal

On the existing retained candidate, deploy the development profile, run a
read-only audit, run one healthy idempotent repair without reboot, then run
certification once. Record only minimized outcomes, verify unique staging is
absent, and leave the target stopped.

### 7 — close current guidance

Update Linux bootstrap and platform guidance plus the owning topics with the
proven contract and its recovery limits. Run portable, native, Linux platform,
and hosted CI validation; audit the public diff; commit in coherent stages;
and push.

## Validation

- `python3 bin/check --portable`
- `python3 bin/check --native`
- `platforms/linux/tests/smoke.sh`
- Linux shell and Python static checks
- fixture coverage for audit/repair/bootstrap/certification policy
- live minimized audit and healthy idempotent repair on the retained candidate
- one live changed-boot-ID certification with exact-source guest checks
- stopped candidate and absent named guest/host staging at handoff

## Result

Completed on 2026-08-11 using only the existing retained Linux candidate. No
VM, clone, snapshot, derived image, or workspace was created, renamed,
compacted, or deleted. Workspace inventory remained empty and the candidate
was left cleanly stopped.

The installed root-only `machine-control-linux-post-update/v0` support now
reports nonce-bound minimized checks for dpkg consistency, pending reboot,
runtime/development packages, QEMU guest-agent, system and interactive SPICE
support, GNOME Wayland, the root input broker, active-user resident, and the
target-native status operation. A stopped live audit failed before any
guest-agent execution and left the candidate stopped. The interactive SPICE
process remains an optional warning because it improves the outer console but
does not establish ordinary resident semantics, capture, or input.

The live development profile installed its declared Git, build toolchain, and
Python virtual-environment packages and deployed the exact resident plus
maintenance support. Its first attempt revealed that apt inherited the QEMU
guest-agent service cgroup: package configuration restarted the agent and
killed its own dpkg child. The interrupted package state was resumed once in
an independent transient root unit. Product bootstrap now always uses that
shape, polls a nonce-bound report after the agent returns, and has a validated
30-minute default completion bound. The corrected profile completed cleanly
and a repeated run was healthy and idempotent.

The live read-only audit and no-reboot repair both returned healthy with a
ready full doctor. Repair changed no unit, reported no required failure, did
not reboot, and invoked no outer route. Fixture evidence separately proves
candidate-only repair, explicit reboot, stopped-audit refusal, invalid nonce,
profile and timeout policy, cleanup, and success-only shutdown.

Certification failed closed twice while developing archive-mode acceptance,
removed staging each time, and left the target running for diagnosis. Those
runs exposed a recursive host-certification fixture that required absent Git
metadata and a guest-agent root environment with no `HOME`. The final runner
keeps host orchestration fixtures checkout-only and gives exact-source checks
an ephemeral private home inside unique staging.

The final certification accepted exact commit `afd9769`: the guest archive
matched SHA-256, the provider observed a changed boot ID, initial and final
post-update plus common doctor results were healthy, portable and Linux-native
checks passed inside Ubuntu, staging was removed, and the candidate cleanly
shut down. A final live resident smoke run after a stopped/start cycle passed
administration, GNOME Wayland, semantics, application lifecycle, capture,
input, and independent fixture effects with outer UI prohibited, then cleanly
stopped the appliance again.

Repository portable checks, macOS native checks, Linux dependency-light
static/unit fixtures, and public-diff whitespace checks passed. Public source
and results contain no concrete target identity, endpoint, account, private
inventory path, package source, boot ID, or captured UI.
