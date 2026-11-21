# macOS policy reader retains decoded JSON between replies

Topic: `runtime-and-presentation`

Status **Fixed in source.** The policy reader now releases temporary JSON
objects after each frame. The trigger for the original menu and socket
outage remains open.

## Observed on installed macOS 0.7.2

- The menu bar was unresponsive when checked after about 12 days of app
  uptime. `target doctor` and a direct Unix-socket connect both returned
  connection refused. The resident socket had eight queued clients, matching
  its listen backlog. The app and its policy child were still running.
- Two pre-restart snapshots confirmed a 31.9 GB footprint, with roughly
  31.7 GB of small-allocation regions swapped or compressed. The default
  malloc zone reported 402,292,641 live blocks. A short thread sample placed
  AppKit in its event wait and the Swift policy reader in its pipe read.
  The hung launch had no allocation histories, so the allocation sites for
  its 31.9 GB were unverified.
- A normal termination request did not complete. Force quitting the original
  app and reopening it restored resident, semantic, capture and input status.
  Settings responded to navigation. The new process measured 33.6 MB and
  78,565 live default-zone allocations. With both access surfaces off, it
  reached 99,760 allocations and 35.8 MB 72 seconds later, about 294 new live
  allocations per second over that interval.

## Allocation source and comparison

On a second launch with `MallocStackLogging=lite`, live allocations with
`SharedResidentHost.readLoop()` on their stack grew from 944 to 6,491 in
about 30 seconds. The largest stacks went through `NSJSONSerialization`,
`_NSJSONReader`, and construction of Foundation strings and dictionaries.
The native transport starts `readLoop()` on a detached Foundation thread
and decodes frames in a loop that has no per-frame autorelease pool. An
isolated comparison used the 0.7.2 reader and the same reader with a pool
around each frame, with the same synthetic policy child and reply sequence.
Each measurement followed a six-second wait for pending timeout work to
settle. [Swift policy transport](../platforms/macos/resident/Sources/macui/SharedResidentHost.swift)

| Reader | Live blocks after 1,000 replies | After 5,000 replies | Growth |
| --- | ---: | ---: | ---: |
| Released | 11,321 | 43,384 | 32,063 |
| Per-frame pool | 3,315 | 3,362 | 47 |

This isolates the missing pool as the cause of the reader's sustained
JSON allocation growth. The experiment uses a standalone transport fixture.
The installed app was relaunched normally after profiling and passed
`target doctor` with a 32.1 MB footprint.

The Swift reader source is identical in 0.7.2 and 0.7.3. Live installed
measurements here cover 0.7.2. The Windows .NET and Linux Python transports
have no corresponding Objective-C autorelease boundary. Their retained heap
under a long-running policy stream was outside this investigation.
[Windows transport](../src/MachineControl.Windows/SharedBrowserHost.cs), [Linux transport](../desktop/native/linux/policy.py)

## Reproduce and profile

Use the normal app and leave Desktop and Browser access off for the idle
baseline. Quit the current app and confirm its process exited before using
the following launch option. It enables live allocation stack logging for
this launch. Take two samples of the same app PID about 30 seconds apart.

```bash
open -g --env MallocStackLogging=lite "$APP"
umask 077
vmmap -summary "$PID" > "$EVIDENCE/heap.txt"
malloc_history "$PID" -callTree -invert -ignoreThreads -noContent \
  | gzip > "$EVIDENCE/stacks.txt.gz"
```

Use distinct filenames for each sample and keep the captures private. Quit
the profiled app and reopen it normally to end logging. For an armed
comparison, use the normal surface controls and a fixture browser profile in
a claimed test workspace. The idle baseline already exercises the leak path.

## Repair and regression coverage

The detached reader wraps `receiveFrame()` in an autorelease pool on each
iteration. The pool drains after replies, queued events, ignored native reply
acknowledgements, and throwing decode or transport paths. The regression test
compares live allocation counts after two equal batches of nested JSON reply
frames while the reader is still running. Each batch sends ignored native
acknowledgements followed by a normal reply on the same pipe, exercising
decoding and the early return with one reply deadline and one write watchdog
per batch. The test reproduces the leak with the old reader and passes with
the fix.

### Installed package comparison

A disposable Apple silicon Mac VM ran the signed 0.7.2 app and then a
locally Developer ID signed build of the repair. Each install opened
Settings through the normal handoff. The resident kept the same PID through
each run and returned status with native semantics ready at every sample.

| Installed build | Allocation growth at about 60 seconds | At about 120 seconds |
| --- | ---: | ---: |
| 0.7.2 | 26,313 | |
| Repaired development build | 1,949 | 3,783 |

These counts cover the process as a whole. The repaired build's measured
footprint went from 26.5 MB to 24.1 MB during the two-minute interval.

## Remaining liveness gap

A separate liveness test should hold the public socket or UI poll unavailable
and check the supervisor response. In 0.7.2
the Mac status poll schedules work on the app's main thread and waits for a
reply without a deadline. The observed outage never recovered on its own.
The thread sample and heap evidence leave open what first prevented the
socket and the menu bar from responding.
