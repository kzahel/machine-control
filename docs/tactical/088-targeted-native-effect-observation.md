# Targeted native effect observation

Status: active; source correction under signed qualification.
Owning topics: [Mac resident control](../../topics/macos-resident-control.md),
[access admission](../../topics/access-admission-and-pause.md) and
[caller authorization](../../topics/caller-authorization.md).

## Objective and completion conditions

Keep native AX and input effect observations within the unchanged finite owner
watchdog. An actual signed GUI run exposed roughly five-second AX actions:
before/after fingerprints queried every application's windows, including the
resident's own GUI on its main thread. Subsequent keepalive correctly expired
ownership. Do not extend the watchdog or retry an uncertain action.

Complete after native source/static checks, deployment/doctor and an immutable
signed-app regression prove independent AX/pointer/key effects, real capture
bytes and Pause refusal with ownership retained between eligible operations.

## Boundaries and ordered work

1. Retain cheap process/focus observations; query AX windows only for the actual
   affected process. Never send AX window messages to the resident itself from
   its main thread. Obtain an AX action's process from its stored reference;
   targetless input uses the independently observed frontmost process.
2. Preserve delivery, effect uncertainty, native routes, control fencing and
   watchdog deadlines. Target observations are evidence, not a correctness
   oracle; use the separate AppKit counter and event records for acceptance.
3. Run Swift/static checks and deployed source doctor. Freeze/sign the exact
   committed candidate, then run the checked-in signed `routes` case with an
   independent fixture oracle and cleanup. Record performance and limitations.

## Validation and result

**Current, source correction:** effect fingerprints obtain the affected PID
from the stored AX reference or verified input target/frontmost process. AX
window sampling excludes every other process, including the resident itself;
cheap process/focus observations remain global. 141 Swift tests pass without
warnings, Mac static checks pass, and source deployment/fresh doctor are ready.
The signed regression remains pending.

The initial signed route trial expired immediately after an AX action
near the five-second lease boundary; the next request refused before its
provider effect. The ordinary signed path and its source fixtures remain
recorded in Tactical 086. This slice does not qualify physical hardware or
protected control.
