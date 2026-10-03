# Mac helper maintenance after signed updates

Owning topic: [macOS locked use](../../topics/macos-locked-use.md).

Status: complete within the existing approved physical installation; distribution
and additional OS versions remain unqualified.

## Objective

The person repeatedly needed Repair during signed physical test iterations.
Ordinary launches should require no repair. A signed update should refresh an
already approved helper binding through native lifecycle maintenance, and Repair
should preserve the person's existing locked-use checkbox choice.

## Completion conditions

- Refresh an existing approved managed installation after a signed update.
- Preserve the stored checkbox choice without granting ordinary access.
- Relaunch the same build without restarting or repairing a healthy helper.
- Keep initial installation, revoked OS approval and real failures visible.
- Never restart a covered or paused helper, or maintain a locked/unknown console.
- Preserve exact code-hash checks and fixed root-private payload staging.

## Boundaries

No agent-facing setup API, new privilege grant, arbitrary root command, automatic
initial installation, password transport or saved ordinary access grant.
Maintenance requires existing macOS service approval, existing capture
preparation and native grants, a healthy enabled locked-use installation and a
trusted root-owned public receipt identifying service-managed ownership.
The current user's unlocked console must be complete and no task may be covered
or paused. Only a changed caller binding is eligible. Attempt once per process;
surface failures instead of entering a registration loop or opening consent UI.

## Ordered work

### 1 — preserve the existing local choice

Preparation leaves the persistent preference untouched. Initial setup remains
default off. Helper readiness is false during registration, installation and
capture preparation, so an existing opt-in cannot activate an incomplete helper.
Explicit removal and disabling still persist revocation.

### 2 — maintain an approved updated installation

Native permission polling detects the constrained update condition, uses the
existing asynchronous unregister/register lifecycle and fixed root preparation,
and reuses already prepared capture consent without another capture request.
macOS continues to validate and own daemon approval; the new daemon pins the
updated code generation before staging fixed payloads. Unexpected approval
requirements remain visible in Permissions and require person-initiated Settings.

### 3 — prove update and ordinary relaunch behavior

Replace the claimed, unlocked test candidate with the signed revision. Observe
automatic maintenance restoring helper health and caller eligibility without a
native Repair click. Relaunch those exact signed bytes and require the helper
generation to remain unchanged. Then complete Tactical 070's retained-access
and hardware-takeover cells. Keep private captures and identities outside Git.

## Validation and current result

**Current:** all 82 Swift tests pass. New tests cover update eligibility, ordinary
relaunch refusal to repair, absent approval/preparation, legacy and appliance
ownership, active/paused/unhealthy/unknown helper state, locked or other-user
console, and preservation of initial-off versus existing-on preference choices.
ARM64 and Intel framework builds passed; the staged Developer ID candidate
passed deep strict signature verification.

**Current:** replacing the signed test candidate while the physical console was
unlocked triggered native maintenance without a Repair click. The helper moved
through installing to idle/ready, restored caller eligibility, changed its
generation, and preserved the stored checkbox value. No ordinary access grant
was created. Relaunching those exact signed bytes returned ready with the same
helper generation, preserved preference, and no setup error or Repair click.
That first live preference was off because the previous Repair had cleared it.
A subsequent signed display-wake update also refreshed automatically and
preserved the person's enabled checkbox, proving live preservation of both
choices. Source tests cover initial default-off preparation as well.

**Current:** a later physical test found the running app in mutable build output
had lost a valid resource seal. Strict verification failed while the saved
signed candidate still passed; macOS reported a code-signing plist-load failure
(`SMAppServiceErrorDomain 3`, `-67056`). The already installed root helper was
healthy but rejected that caller. Restoring the verified candidate and launching
an isolated test copy returned ready using existing OS approval, preserved the
enabled preference and cleared the error without another native Repair click.
Use separately staged, verified test installations rather than running product
tests from build output that another build can replace. This trial does not prove
automatic recovery from arbitrary bundle corruption or a release updater.

**Open:** Tactical 070's successive-task and takeover acceptance, additional OS
versions, and notarized distribution. This bounded maintenance result does not
establish those capabilities or require another initial OS permission grant.
