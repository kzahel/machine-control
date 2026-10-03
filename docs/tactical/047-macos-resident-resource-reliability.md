# macOS resident resource reliability

Topics: `macos-resident-control`

Status: complete — reproduced, fixed, regressed, and validated in the claimed guest.

## Objective and completion conditions

Investigate the two resident readiness failures reported by RSTorrent Tactical
232 (incident summary through `7ade2df9`), starting from the clean Machine
Control revision `12c363f`. Identify resource ownership, preserve unknown/locked
input refusal, add a regression, and exercise the fix and supported recovery in
an exclusively claimed guest. Keep product code and private infrastructure out
of this change. Finish with owned fixtures/artifacts removed, inherited power
state restored, and the claim released. Do not push or publish.

## Boundaries and hypotheses

The incident's 10,563 `lsof` entries are not a descriptor count: `cwd`, `txt`,
and other mapping records must be excluded. Historical raw logs were removed;
the second incident has no descriptor-type sample. Neither a shared cause for
both incidents nor capture as the originating leak can be assumed.

The running resident can answer status while its child session probe fails.
That differs from a missing socket/transport, a denied TCC grant, a locked
console, and a stale cached session. The original maintenance check named
`semantic_authorization` actually consumed combined semantic *readiness*,
which includes the session state. Its failure did not establish revoked
Accessibility consent.

### 1 — inspect ownership and reproduce without application operations

**Current, source-reviewed:** `runResidentServer` called `refreshSession` before
its 250 ms socket poll, outside the autorelease pool wrapping accepted
requests. Every refresh spawned `mc-session-probe` with a Foundation `Pipe`.
The parent read handle remained autoreleased outside any draining pool. A
request pool does not drain objects enqueued before that pool was created.
The observer suppressed all launch/parse errors into `desktopState: unknown`.

The independent command transport does not execute in the resident. Native AX
references have bounded retention; capture subprocesses execute inside the
request pool; captures retain at most 16 cache entries; accepted client and
unlock-broker sockets have explicit closes. Optional Cua subprocesses also run
inside the request pool. These paths were inspected, not presumed innocent
from a successful API response. Idle reproduction makes them unnecessary for
the demonstrated leak.

**Current, reproduced:** Extracting the unchanged observer into a synthetic
bundle with a deterministic unlocked probe produced 3 → 1,003 open FDs after
1,000 calls. Wrapping those calls in a draining pool held 3 FDs throughout.
With a 256-FD process limit, call index 251 returned unknown. Instrumenting
only the formerly empty catch recorded `NSPOSIXErrorDomain`, code 9 (`EBADF`).
A capture-like `/usr/bin/true` spawn without the output pipe still succeeded
in that reduced-limit experiment. This demonstrates low-limit exhaustion, but
does not alone explain the historical capture failure. The separate high-FD experiment below identifies
the applicable spawn ceiling before the much larger process limit.

The checked-in no-UI replay uses the same no-argument observer and a 128-FD
limit; the original fails at probe 124 with 127 descriptors, while a caller
pool or the fixed observer holds 3 descriptors for 500 probes:

```bash
scratch=$(mktemp -d)
git show 12c363f:platforms/macos/guests/macos/ui/macui.swift > "$scratch/original.swift"
# Expected nonzero: increasing FDs followed by unknown session.
python3 tests/macos/session-probe-resources.py \
  --source "$scratch/original.swift" --idle-only
python3 tests/macos/session-probe-resources.py \
  --source "$scratch/original.swift" --idle-only --caller-pool
python3 tests/macos/session-probe-resources.py --idle-only
rm -rf "$scratch"
```

#### Darwin spawn ceiling, independently of RLIMIT exhaustion

**Current, source-reviewed and live-tested on the same guest:** launchd and
the guest transport reported a 65,536 soft FD limit (524,288 hard limit), and
`kern.maxfilesperproc` was 65,536. A 10,563-line historical lsof report therefore
must not be called ordinary `RLIMIT_NOFILE` exhaustion without further evidence.

An isolated process retained at most 12,000 pipe read ends, closing each writer
immediately. This brought descriptor numbers near the incident without waiting
for thousands of slow Foundation launches or exhausting the running resident.
Direct `posix_spawn_file_actions_adddup2` succeeded below 10,240 and returned
9 (`EBADF`) above it. Both the original observer and a plain Foundation
`Process` launching `/usr/bin/true` failed at the same boundary. The latter
matches capture's subprocess setup without capturing any desktop. The fixed
observer correctly also refuses under this externally imposed pressure; it
prevents its own accumulation rather than bypassing OS limits.

Apple's [spawn file-action implementation](https://github.com/apple-oss-distributions/xnu/blob/main/libsyscall/wrappers/spawn/posix_spawn.c)
checks descriptor numbers against `OPEN_MAX`, and the
[Darwin header](https://github.com/apple-oss-distributions/xnu/blob/main/bsd/sys/syslimits.h)
defines that constant as 10,240. The installed SDK header agreed. These are
reference links, not copied code or a claim to an exact guest OS source build.
The independent guest API experiment establishes the behavior on build 25G83.
Raising an already larger process limit would not fix this file-action ceiling.

The checked-in diagnostic on the fixed observer reported:

| Retained pipe readers | Highest retained FD | Total numeric FDs | adddup2 | Foundation spawn | Observer |
| ---: | ---: | ---: | --- | --- | --- |
| 10,000 | 10,002 | 10,003 | success | success | unlocked |
| 10,230 | 10,232 | 10,233 | success | success | unlocked |
| 10,240 | 10,242 | 10,243 | EBADF | EBADF | unknown |
| 10,600 | 10,602 | 10,603 | EBADF | EBADF | unknown |
| 12,000 | 12,002 | 12,003 | EBADF | EBADF | unknown |

Replay only in an explicitly claimed dedicated guest with sufficient existing
limits; it neither raises limits nor queries a desktop:

```bash
$mc os -- /usr/bin/python3 -c "$(cat tests/macos/session-probe-resources.py)" \
  --spawn-boundary
# --source FILE can select an exported original macui.swift instead.
```

The original-source variant retained its additional leaked read ends (12,011
FDs at the last point); the fixed variant returned to its prefilled count
after each call. All artificially retained descriptors were process-owned and
closed at exit. No resident restart was necessary for this experiment.

### 2 — measure the unchanged claimed appliance

Environment: Apple-hosted ARM64 macOS 26.6.2, build 25G83, Tart 2.30.5;
ordinary Aqua resident reached through the common CLI and guest transport.
`MACVM_FORBID_OUTER_UI=true` for all claimed guest work. Common discovery and read-only doctor
found the exact target suspended, with host resume available. A scoped common
run acquired and renewed the exclusive claim; `target ensure-ready` resumed
it through ordinary `up` and reached ready. No outer input/capture or browser
was used.

Read-only measurements used resident status for the PID, `lsof -nP -p PID
-Fft` (and `-Ffat` for the extended workload) with **numeric** `f` records only, `ps -o rss= -p PID`, `ps -M -p PID`,
`pgrep -P PID`, and the separate native session probe. Only aggregate counts,
latencies, and readiness were retained. No arbitrary AX content or screenshots
were recorded. The resident is serial; the workload has at most one request
in flight and samples at zero outstanding test requests. There is no internal
queue/task telemetry, so this is not a measurement of every OS/framework task.

| Relative time | Numeric FDs | Pipes | Non-FD entries | RSS KiB | Threads | Children | Status ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 s | 1,553 | 1,549 | 9 | 24,448 | 3 | 0 | 113 |
| 31 s | 1,644 | 1,640 | 9 | 24,704 | 3 | 0 | 147 |
| 61 s | 1,734 | 1,730 | 9 | 24,896 | 3 | 0 | 107 |
| 91 s | 1,825 | 1,821 | 9 | 25,152 | 3 | 0 | 93 |
| 256 s | 2,318 | 2,314 | 9 | 26,576 | 3 | 0 | 115 |

The other descriptors were one character device, two regular files, and one
Unix socket. This is approximately three leaked pipe FDs per second **while
idle**, with no captures or AX workload. All samples still reported unlocked
and ready; this inherited resident was repaired before driving it to
exhaustion. The isolated reduced-limit process supplies exhaustion evidence
without exhausting the appliance.

### 3 — fix lifetime and diagnostic reporting

**Decision:** Drain an autorelease pool around every idle refresh and make the
observer independently own its pool and handles. Explicitly close both pipe
ends and the private stderr handle. Bound probe output to 16 KiB and execution
to two seconds; kill and reap the known child on timeout, cancellation, or
output refusal. This helper has no descendant processes. Never substitute a
previous successful observation after failure.

Status now includes minimized `sessionProbe.failure` and numeric error code,
with no raw stderr, paths, or session identifiers. Failures distinguish launch,
read, nonzero exit, malformed response, output bound, timeout, and cancellation.
`semanticAuthorizationState` and `captureAuthorizationState` are independent
of session/display readiness. Maintenance consumes these fields, retaining a
legacy readiness fallback for older residents; `target_native` still requires
actual semantic/capture readiness. No TCC, unlock, or lock-safety policy changes.

`desktop_not_unlocked`, session-generation invalidation, and the fresh probe
before ordinary mutation remain intact. Unknown means refuse, not unlock.

### 4 — regress and challenge the fixed guest

Deterministic native tests:

```bash
python3 tests/macos/session-probe-resources.py
python3 tests/macos/session-probe-resources.py --idle-only
python3 tests/macos/maintenance-projection.py
python3 bin/check --portable
python3 bin/check --native
```

The observer regression compiles the actual production function. It checks
normal completion, missing executable, nonzero exit, invalid JSON/state,
excessive output, hung child, closed-stdout-but-running child, cancellation
before and during execution, subsequent recovery, real FD counts, and child
reaping. Its Swift checks use `precondition`, which stays active under `-O`.
An early test draft used `assert`; that optimized-away run was discarded and
is **not** endurance or cancellation evidence.

Live deployment used common `maintenance repair --profile development` and
preserved consent without reboot. Source redeployment had already started
the new resident before the maintenance report; its repair field correctly
said `not_needed`, rather than proving that the repair branch kickstarted it.

Run the following inside a common claimed task, after doctor/ensure-ready and
with outer UI forbidden. The fixture workload requires a previously absent,
task-owned AppKit fixture. Always remove it in `finally`/trap cleanup.

```bash
mc=bin/machine-control
export MACVM_FORBID_OUTER_UI=true
$mc maintenance repair --profile development
# Inside the guest, the source defaults to the installed deployed macui.swift.
$mc os -- /usr/bin/python3 -c "$(cat tests/macos/session-probe-resources.py)" \
  --iterations 30000
$mc testbed -- deploy-fixture
$mc desktop raw \
  '{"operation":"application.launch","applicationId":"org.machine-control.fixture"}'
$mc os -- /usr/bin/python3 -c "$(cat tests/macos/resident-resources.py)" \
  --rounds 1000 --idle-seconds 120
$mc testbed -- remove-fixture
python3 tests/macos/resident-recovery.py --evidence-dir "$private_evidence_dir"
```

The actual run first performed 30 common `os -- /usr/bin/true` calls (75.0 s).
The workload isolates 200 status requests, 100 AX observations, 100 AX actions,
100 activations, 100 targeted keys, and 30 exact-fixture captures. It then
combines 1,000 rounds of fresh snapshot/action, activation, targeted key, and
one capture per ten rounds, followed by two minutes idle. Fixture file oracles
must observe every counter/key effect. It rejects a resident-generation
change and descriptor growth beyond the small transient allowance. Each
capture is checked as PNG and deleted immediately.

The recovery runner separately performs 20 common capture/artifact round trips,
then temporarily removes the probe's execute bits on the dedicated guest.
It restores the original mode in `finally`. A separate copied probe supplies
independent OS observation. It checks unknown-session input refusal, distinct
consent/readiness reporting, automatic observation recovery with a fresh
desktop generation, and supported resident stop/audit/maintenance restart.
Old references must fail after restart; a fresh AX action must change the
fixture oracle. The caller retains power-state and claim cleanup ownership.

## Results and limits

The fixed resident completed 4,863 operations in 2,295.1 seconds (38.3
minutes), including two minutes idle, without a generation change. All 32
samples had six FDs (two character, two regular, one Unix socket, one
transient probe pipe), three threads, and zero children. Non-FD entries rose
from 8 to 12 as UI frameworks warmed. RSS rose from 18,432 to 22,336 KiB at
its sampled maximum and ended at 22,336 KiB; this is a measured range, not a
strict heap bound. Each sample had zero outstanding test requests.

| Operation | Count | Median ms | P95 ms | Maximum ms |
| --- | ---: | ---: | ---: | ---: |
| Status | 233 | 164.9 | 175.4 | 193.0 |
| AX snapshot | 1,200 | 200.4 | 235.7 | 260.2 |
| AX action | 1,100 | 477.3 | 499.3 | 556.4 |
| Activation | 1,100 | 323.2 | 340.0 | 442.6 |
| Targeted key | 1,100 | 895.2 | 921.9 | 1,012.7 |
| Exact-window capture | 130 | 225.8 | 292.5 | 363.1 |

The [minimized interval evidence](../evidence/macos-resident-resources.json)
retains all samples and latency/count summaries. The independent accelerated
probe test ran concurrently for part of the workload, adding guest CPU load.
An earlier optimized-away test's apparent pass is excluded.

The recovery runner passed 20 additional common capture/artifact round trips
and removed every artifact. With probe execution temporarily denied, status
reported `sessionProbe.failure: launch_failed` (numeric error 4), unknown
desktop, ready semantic authorization, and unavailable semantic readiness.
The independent probe remained unlocked and input returned
`desktop_not_unlocked`. Restoring the original executable mode recovered
readiness in the same resident and changed the desktop generation.

Supported resident stop produced an unhealthy read-only maintenance audit.
Common maintenance repair returned healthy without reboot; its deployment
startup path restarted the stopped resident before its report, so the reported
resident repair action was `not_needed`. The resident generation changed,
a stale reference was refused with no fixture counter effect, and a fresh AX
action changed the independent counter. The runner then removed its fixture.

After recovery and fixture removal, 31 samples over 1,808.0 seconds held six
FDs, three threads, zero children, and six non-descriptor entries. RSS stayed
between 15,056 and 15,184 KiB. Every sample remained unlocked/ready with the
same resident generation. The private idle harness reused the checked-in
sampler without launching a fixture:

```bash
python3 - <<'PYIDLE'
from pathlib import Path
source = Path('tests/macos/resident-resources.py').read_text()
prefix = source.split("initial = call('status')", 1)[0]
Path('/tmp/mc-idle-sample.py').write_text(prefix + """
generation = call('status')['generation']
for index in range(31):
    sample('post-recovery-idle-' + str(index * 60))
    if index < 30: time.sleep(60)
""")
PYIDLE
$mc os -- /usr/bin/python3 -c "$(cat /tmp/mc-idle-sample.py)"
rm /tmp/mc-idle-sample.py
```

The corrected, always-on observer regression completed 30,000 successful
probes plus its error, output-limit, timeout, cancellation, recovery, and child
reaping cases. It held three FDs at all 30 checkpoints and at completion under
a 128-FD limit. Controller wall time was 5,517.8 seconds (92.0 minutes),
including transport and compilation. Unlike the discarded draft, every
observation and assertion executed in the optimized Swift build.

Final guest checks found six resident FDs, three threads, zero children,
15,296 KiB RSS, and unlocked/ready state in both resident and independent
observations. The probe was executable, fixture paths were absent, and no
test processes or test temporary directories remained. Source-digest and
signature verification passed for the deployed ARM64 app. The portable and
native repository check suites passed; this change does not touch the Windows
runtime and did not require Windows publishes.

Final common doctor reported ready before cleanup. The scoped task suspended
the guest successfully, released its claim, and exited zero. A subsequent
read-only doctor confirmed `power: suspended` with outer UI prohibited;
claim status returned `available`. This restores the inherited power state.
No credentials were changed, and no RSTorrent code was modified. The fix and
evidence were committed locally; nothing was pushed or published.

```bash
# Scope cleanup, using its still-held claim:
$mc target suspend
# After the scoped runner has released the claim:
$mc --target macos target doctor   # expected unavailable while suspended
$mc --target macos claim status   # available
```

**Current:** The accumulating resource has a reproduced cause in the owned
session-probe lifetime, independent of RSTorrent and capture. Its eventual
failure mechanism is the Darwin spawn file-action descriptor-number ceiling,
not necessarily exhaustion of the configured process FD limit. Both historical
incidents are consistent with this same continuously recurring leak and the
fact that restarting temporarily restored readiness. Their identity of cause
cannot be established retrospectively without the removed per-incident logs.
There is no evidence here of revoked TCC consent or a genuinely locked guest.
The second incident's resource counts and the exact historical capture call
remain unavailable; the shared subprocess EBADF mechanism is reproduced.

**Open:** This does not qualify a physical Mac, other macOS versions, Cua
endurance, or a new protected-session path. Socket partial-request deadlines,
disconnect cancellation of an already executing UI operation, concurrent Cua
stdout/stderr drainage, and deadlines for capture/application subprocesses
remain separate hardening work. They are not required to trigger this leak
and were not silently changed in this bounded fix. Do not interpret the probe's
internal cancellation hook as a new public cancellation API.
