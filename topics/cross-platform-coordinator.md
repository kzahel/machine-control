# Cross-Platform Coordinator

Topic: `cross-platform-coordinator`

Status: portable coordinator, native CI, and live Windows/Linux appliance
execution implemented.

## Scope

This topic owns portability of the target-selecting `machine-control` client
across macOS, Linux, and Windows controller hosts. It also owns the boundary
between a target's operating system, the controller host that can execute a
particular adapter route, and optional worker placement.

It does not make Tart available on Linux or Windows, make UTM a Linux provider,
or imply that every target is controllable from every controller. Platform
lifecycle and resident implementations remain target-owned.

## Decision

**Decision:** the common coordinator must run on macOS, Linux, and Windows even
when no configured target is currently controllable. Inventory and target
listing are portable operations. Adapter execution is conditional on an
explicit controller-platform declaration and executable launcher.

The three identities remain independent:

```text
controller platform    executes a selected adapter route
target platform        identifies the system under test
worker placement       optionally hosts an agent session
```

A Windows target may be reached through a macOS UTM adapter, a direct Windows
resident route, or an authenticated remote carrier. Those are different
controller routes to one target class, not different Windows contracts.

## Controller eligibility

Every resolved target entry declares `controllerPlatforms`, using `darwin`,
`linux`, and `windows`. The common client reports the current controller
platform, whether the route supports it, and whether its launcher is available.

Selecting an unsupported route returns a typed
`controller_platform_unsupported` refusal before examining or executing the
adapter. A missing launcher or command returns `adapter_unavailable`. Neither
condition is evidence that the target itself is powered off or unhealthy.

The private inventory provider selects concrete routes and environment for the
current controller. Public defaults remain sanitized examples and declare
their real controller reach honestly.

## Portable launchers

**Decision:** target entries may select `auto`, `direct`, `python`,
`powershell`, or `bash` launch behavior. `auto` recognizes Python and
PowerShell scripts and otherwise uses direct execution. Launcher resolution is
part of adapter availability and is shared by target, desktop, testbed, and OS
escape operations.

The public coordinator never interprets private route arguments as authority.
It only launches the resolved adapter after target selection and controller
eligibility succeed.

## Validation model

Routine validation has two independent axes:

1. **Coordinator portability:** fixture-backed common-client and registry
   tests execute natively on macOS, Linux, and Windows without private
   inventory or live targets.
2. **Target-native implementation:** dependency-light Windows builds and
   PowerShell parsing execute on Windows, macOS Swift/plist checks execute on
   macOS, and Linux resident Python/shell checks execute on Linux.

The existing testbeds may carry a committed source revision into their guests
and run these checks there. That validates the target OS without requiring a
separate interactive agent session. Routine hosted CI performs the same
non-mutating checks. It does not boot VMs, contact physical devices, use
private inventory, or replay guarded live application-control corpora.

## Current evidence

**Current (2026-08-11):** The root portable and native checks pass on the
macOS controller. The exact committed source archive was transferred through
the guarded Linux UTM adapter, matched by SHA-256 inside the guest, and passed
the portable corpus, the Linux-native static/compile checks, and a direct
coordinator invocation reporting a Linux controller. The guest was cleaned
and shut down afterward.

**Current (2026-08-11):** Tactical 018 reused a retained Windows candidate
without cloning it, restored key-only administration and automatic services,
and proved full common readiness after a changed OS boot epoch. An exact
committed archive matched by SHA-256 inside Windows and passed the portable
corpus plus all Windows-native .NET 8 builds. The dedicated stateful appliance
now contains Python and .NET 8 as reproducible public development tooling; the
check runner supplies a per-process PowerShell execution policy rather than
changing the appliance's machine or user policy.

**Current (2026-08-11):** Hosted run `31481111956` passed all six public jobs
at commit `5ed134a`: portable coordinator checks and matching native checks on
macOS, Linux, and Windows. The Windows native job parsed the PowerShell corpus
and built all three .NET projects with .NET 8. Five ChromeOS post-update tests
use a POSIX fake-SSH fixture and are explicitly skipped only on Windows; both
Unix coordinator jobs execute them. Private-inventory run `31480390146` passed
its macOS/Linux/Windows registry matrix and portable agent-config job at
dotfiles commit `4ef3ded`.

## Current direction

- Provide one portable root check command that owns correct suite working
  directories and records intentional skips.
- Keep the root command green on hosted macOS, Linux, and Windows.
- Keep live target rehearsals deliberate and controller-owned.
- Keep the retained Windows and Linux development appliances reproducible and
  re-run exact-archive checks after material coordinator or toolchain changes.
- Add direct local/remote resident routes only when their transport and
  authorization are explicit; do not disguise a macOS VM-lifecycle wrapper as
  a Windows-local adapter.
