# Windows desktop bounded unlock and relock

Owning topics: `windows-desktop`, `windows-protected-unlock`,
`access-admission-and-pause`.

Status: implementation in progress; no installed or live acceptance yet.

## Objective

Following the request to finish Windows desktop qualification and locked use,
integrate the existing guarded unlock protocol with native desktop consent,
connection-owned tasks and an independent privileged relock watchdog.

## Completion conditions

- Exact installed-candidate qualification for the accumulated Windows changes.
- Initially disabled operator preparation and explicit controller approval.
- One-shot password transport after exact provider/field discovery, without
  caching passwords or changing Windows security policy.
- Same account and logon session after unlock, independently observed task
  effects, and relock after completion, Pause, Stop, expiry or failure.
- Unprepared, stale, foreign, paused and observe-only requests refuse before
  credential use; interrupted effects are never automatically replayed.
- Owned processes, services and staging are cleaned up; runtime format,
  contracts and both Windows architecture publishes pass before commits.

## Boundaries

The first Windows profile temporarily exposes the console while a task runs.
The operator must see this before enabling it. Opaque covered control is a
separate presentation/capture qualification; this slice claims no Mac cover
privacy. Local console accounts and password fields inherit the existing
unlock broker's exact discovery limits. No cold login, account switching,
appliance authority, persistent password, arbitrary privileged dispatch or
automatic retry is added.

## Ordered work

### 1 — qualify the installed Windows candidate

Resolve authenticated release tooling and build a signed CI candidate. Exercise
native and browser workflows, install/update with the test browser open,
optional helper setup/removal and uninstall against its exact bytes.

### 2 — bind unlock to desktop consent and task ownership

Reuse protected controller grants and one-shot credential transport. Expose
operator-only setup and opt-in, explicitly prepared owner admission, and an
exact owner-bound unlock preparation. Keep ordinary dispatch unavailable until
independent unlock evidence, and rotate stale observation generations.

### 3 — own relock independently of the desktop process

Start a privileged guardian before possible credential submission. Bound it to
the exact account/logon session, task authority and finite deadline. Observe
physical takeover, service/resident failure and authority loss; confirm relock
before admitting another task.

### 4 — validate and document the product contract

Use the existing deterministic contracts and a command-driven interactive VM
actor with independent OS and fixture evidence. Record exact candidate identity,
architecture limits, cleanup and remaining signed/physical qualification gaps.

## Final result

Pending.
