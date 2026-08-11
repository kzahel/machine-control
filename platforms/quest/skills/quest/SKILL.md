---
name: quest
description: Diagnose and safely control a physical Meta Quest headset over ADB, including authorization and device selection, recoverable wake/proximity leases, sleep and recovery, APK install and launch, screenshots, logcat, file transfer, reverse ports, and explicit shell commands. Use when Codex is asked to deploy, test, inspect, recover, or operate Quest or Horizon OS hardware from a development project.
---

# Quest Testbed

Use the public testbed CLI for headset transport and lifecycle. Keep compiling,
assets, app-specific startup policy, host XR runtimes, performance criteria,
and acceptance assertions in the consuming project.

Tool path: `~/code/quest-testbed/bin/quest`

## Start safely

1. Run `quest doctor` before mutating the headset.
2. Use `quest status` to distinguish disconnected, unauthorized, booting,
   awake/asleep, low-battery, proximity-override, and stale-lease states.
3. Pass `--serial` when more than one Quest could be attached. Never operate
   the first arbitrary Android device or an emulator.
4. Do not bypass ADB RSA authorization, use root, change device policy, perform
   a factory reset, or fully shut down the headset.

## Run a project test

Prefer one transactional command:

```bash
quest session \
  --stop-package com.example.game \
  --reverse tcp:9757=tcp:9757 \
  -- ./project-owned-test.sh
```

The testbed wakes the Quest, keeps it awake with proximity disabled, and
guarantees normal cleanup. The child owns the APK build/install, assets,
launch arguments, host XR processes, log assertions, and pass/fail policy.

If building should happen before wake, use `quest begin --owner-pid` after the
build and arrange `quest end` in the project's trap/finally block. Do not use a
bare `wake` plus ad hoc settings for automated validation.

## Recover safely

If `doctor` reports a journal, first decide whether its owner is still active.
The same controller automatically repairs a dead-PID transactional/external
lease on the next begin. Otherwise use `quest recover`; a journal from another
controller requires `recover --force` only after confirming no test is active.

Cleanup must restore saved Android settings, clear the Meta proximity debug
override, broadcast proximity-open, remove owned reverse ports, stop only
explicit packages, and send Android `KEYCODE_SLEEP`. Sleep is standby, not a
full power-off.

## Generic operations

```bash
quest install path/to/app.apk
quest launch com.example.game --component com.example.game/.MainActivity --wait
quest screenshot /tmp/quest.png
quest logcat /tmp/quest.log --package com.example.game
quest push LOCAL REMOTE
quest pull REMOTE [LOCAL]
quest shell -- COMMAND ARG...
```

Read `README.md` before changing lifecycle flags, recovery semantics,
controller setup, or the public command contract.
