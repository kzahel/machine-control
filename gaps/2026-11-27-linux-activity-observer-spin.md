# Linux resident spins when the activity observer is unavailable

**Open.** Observed on 2026-11-27 with Machine Control 0.7.5 installed from
the amd64 `.deb` on Ubuntu 26.04.1 with GNOME Wayland.

Owning topics are [Linux desktop](../topics/linux-desktop.md) and
[Linux locked use](../topics/linux-locked-use.md).

## Observations

The resident sustained roughly 110% CPU (1.1 logical cores) while the GNOME
console was locked and there was no active control claim. The CPU sensor read
82°C and the CPU and GPU fans were running at roughly 7,000 and 7,400 RPM.
Process I/O counters showed about 5,000 pipe writes per second in each
direction between the resident and its notification helper, and comparable
traffic with the policy process. The physical activity observer's socket was
absent, and systemd had no loaded observer unit in either the system or user
manager.

## Mechanism and reproduction

[`Activity.refresh()`](../desktop/native/linux/activity.py) limits the worker
to one in-flight sample. When the socket is absent, the sample fails
immediately. `Activity.completed()` clears the in-flight flag and reports the
failure to [`Desktop.activity_changed()`](../desktop/native/linux/desktop.py),
which calls `refresh_availability()` and queues another sample. The retry has
no delay, even when observer state is unchanged.

The callback also schedules a status publication. The
[notification helper](../desktop/native/linux/notice.py) sends an `alive`
reply on each update, even when the task list is empty. The resident handles
that reply by checking availability again. Each publication also queries the
policy process.

A bounded harness using the matching checkout's activity worker and resident
callbacks reproduced 250 status publications from one availability refresh
with a missing socket. The harness stopped at 250 and supplied no notification
heartbeats or external requests.

## Proposed repair and verification

- Pace ordinary observer sampling independently of completion callbacks.
  Bound retries while the observer is missing or unavailable. Keep immediate
  readiness invalidation on explicit observer loss, expiry on silence, and
  the fresh post-offer sample required for admission.
- Publish status on changes and a bounded refresh cadence. Keep notification
  liveness checks and visibility changes responsive when updates are frequent.
- Add a regression test for the missing-socket case and observer recovery.
  Verify idle CPU and bounded message rates on an installed GNOME build with
  the observer absent, then verify that an available observer still detects
  takeover and supplies the post-offer sample.

This and the [covered-access setup gap](2026-11-27-linux-covered-access-setup-feedback.md)
can share installed GNOME verification in a focused Linux fix pass.
