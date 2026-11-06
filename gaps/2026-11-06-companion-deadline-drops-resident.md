# Companion reply deadline drops the resident under load

Topic: `runtime-and-presentation`

Status: **Repaired in source — three reviewed commits on 2026-11-06; VM
acceptance under load pending.**

## Observations

During operator-update acceptance on 2026-11-06 (candidates 0.7.0 → 0.7.1 at
`3ba7b92`), the desktop supervisor repeatedly lost its resident companion
while the guests were CPU-starved. The controller host was at a load of about
28 on 14 cores from three concurrent VM campaigns.

- **Linux ARM64 (GNOME Wayland):** 5 of 8 real runs ended with
  `companion.timeout`, followed either by `companion.protocol_error` and
  `supervisor.stop`, or by "Resident did not respond; restart Machine
  Control" at startup. The app exited and left stale `desktop.sock` and
  `operator.sock` files. In one run a successful update installed 0.7.1 but
  the relaunched client never came up. Without a manual relaunch, its
  pending access restoration would have expired. The guest journal logged
  rtkit "canary thread is apparently starving" just before one timeout.
- **Windows ARM64:** `companion.state_timeout` killed the resident job and
  left Settings showing "Resident unavailable" until restart. It happened
  soon after start with covered desktop enabled, 1–2 minutes after turning
  on Desktop Ask with nothing else running (reproduced without UI
  automation), 20–30 seconds after a Desktop or Browser agent task
  activated, and during Chrome for Testing startup. The guest runs x64
  Chrome under emulation on 4 vCPUs. This blocked the Browser update and
  running-task confirmation cases on Windows.

Exact diagnostics are retained in private acceptance evidence and usage notes
482 and 485.

## Mechanism

`desktop/src-tauri/src/linux.rs` `Runtime::call` waits 5 seconds for each
operator reply. On timeout the caller drops the runtime (`owner.take()`),
which kills the companion. `desktop/src-tauri/src/windows.rs` uses the same
5-second deadline (30 seconds only for `hello`). A watchdog terminates the
private job one second later, so a late reply can never be reused. Neither
platform restarts the companion afterwards. The 1-second `state` poll in
`main.rs` makes a single slow reply fatal.

The deadline is a deliberate fence against stale replies. The gap is that
missing it is treated as permanent failure, with no recovery or backoff.

## Repair

The repair landed as three commits (`git log --grep "Topic:
runtime-and-presentation"`):

1. **Status polls no longer wait for the policy process.** Linux answers
   `state` on its stdin reader from a reply the coordinator pre-encodes
   about once a second and after each command. Windows reads a snapshot
   its monitor builds. macOS presents a cached full projection that is
   refreshed in the background. Each cached reply carries `stateAgeMs`,
   and the supervisor treats a snapshot older than 30 seconds as a lost
   resident. `fresh` state keeps the synchronous path for the update flow.
2. **Deadlines outlast inner calls.** Ordinary companion calls get 15
   seconds and `hello` 30 seconds on both platforms, so a policy call that
   is slow but within its own 5-second limit no longer ends the resident.
   A policy reply later than that still ends the policy process, which now
   leads to the restart below. Linux status polls return `busy` rather than
   queueing behind a command.
3. **Supervised restart.** A lost Linux or Windows resident is restarted
   with backoff (1, 2, 5, 15, then 60 seconds; escalating while losses
   recur within five minutes). A resident whose policy process fails ends
   itself so it restarts with a fresh one (not for unavailable audit
   storage, which would recur); macOS restarts the app instead, never in
   its first minute and at most once per ten minutes across launches. The
   supervisor remembers the last live status poll (at most 3 seconds old)
   that no person's action overtook, and replays its surface choices after
   the restart through the same restore path as an update. Operator
   commands (before and after they run), app Stop, and a live count of
   stops each resident reports, including its hotkey, native notices and
   safety revocations, cancel the restoration. Linux no longer quits when
   its resident fails to start.

Not changed: stale Linux sockets were already handled at startup (a
refused `desktop.sock` is removed and `operator.sock` is always rebound);
a graceful close before the kill now usually removes them anyway. The
slow operations themselves were not measured.

## Original proposals

- Restart the companion under supervision after a timeout, bounded and with
  backoff. Increase the runtime generation so stale references are still
  refused. Then surface "Resident restarted" rather than staying dead.
- Give read-only `state` polls a longer deadline, or skip a poll while one is
  outstanding, instead of killing on the first slow reply.
- Remove stale sockets on Linux exit, and have startup treat a dead socket as
  absent.
- Measure companion main-thread stalls under load (Linux AT-SPI and portal
  calls; Windows UIA/STA work during task activation) to find the actual slow
  operation.
