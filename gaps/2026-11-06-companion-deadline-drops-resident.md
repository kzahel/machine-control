# Companion reply deadline drops the resident under load

Topic: `runtime-and-presentation`

Status: **Open — reproduced on Linux and Windows ARM64 VMs; not repaired.**

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

## Proposed repairs

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
