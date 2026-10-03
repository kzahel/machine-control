# Resident pause enforcement

Status: active; Windows and Mac pause source/contract integration passed;
native acceptance and automatic physical resumption remain in progress.

Owning topic: [access admission and pause](../../topics/access-admission-and-pause.md).
Parent: [Tactical 074](074-access-admission-and-pause.md), step 2.

## Objective and boundaries

Expose operator Pause and Resume separately from Stop, preserve valid access
through ordinary availability interruptions, and fence stale observations and
actions. Pause must gate governed browser and desktop routes alike. This slice
does not make public IDs into credentials or advertise an agent queue yet.

## Ordered work and completion conditions

1. Wire the common arbiter into Windows resident grant dispatch and generation
   checks. Preserve timed authorization while unavailable; expire it normally.
2. Expose Pause/Resume only on the inherited operator channel, leaving public
   grant status/revocation and read-only diagnosis available.
3. Add duration controls and truthful paused state to the shared desktop UI.
4. Wire equivalent Mac broker, browser and covered-session fencing, preserving
   watchdog relock and distinguishing expected pauses from safety failure.
5. Validate alternate routes, composed reasons, timed expiry, old references
   and the operator-only resume boundary through fixtures and native trials.

## Validation and current result

**Current:** Windows grant contracts verify pause of observation/action,
preserved authorization, changed reference generations, independent safety
blocks, timed pause expiry and grant expiry while paused. Existing browser
dispatch and permission updates use the same authorization gate. UI type checks
pass. Windows ARM64/x64 publishes and formatting checks pass; native Windows
execution and established browser-session acceptance remain future gates.

**Current:** the Mac arbiter port passes three deterministic suites for composed
pauses, complete resource sets, fresh sessions, deadlines and notice interruption.
It is not yet wired into production admission in this record.

**Current:** Mac operator Pause/Resume now gates every ordinary scope, retains
valid access, closes DevTools authority and invalidates resident references.
Expected manual/physical interruption preserves access while covered control
still relocks. The 99-test Swift suite passes, relevant socket/browser suites
pass after the final coordinator edit, and the Intel resident builds. Root
physical quiet/resumption and new signed physical acceptance remain later work.

The existing covered-use foundation passes all 95 Swift tests in an isolated
scratch build. Further Mac behavior changes require new acceptance evidence;
earlier physical results are not promoted to the new pause semantics.
