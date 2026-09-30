---
name: drive-macos-host
description: Control the Mac this agent runs on through the local Machine Control resident, with a person approving access from the menu bar. Use when an agent needs to see or operate the controller user's own macOS desktop or Chrome rather than a VM.
---

# Drive the macOS Host

The `host` target is the Mac running the common client. Its Machine Control
resident reads a root-owned deployment policy. On a personal Mac there is no
policy file, so the resident is a `workstation`: every capture and action is
refused until the person at the computer approves a grant.

## Workflow

1. Run `bin/machine-control --target host target doctor`. A failed
   `resident` check means Machine Control is not installed or not running;
   ask the person to install it rather than starting it yourself.
2. Acquire a target-use claim as for any other target and pass `--claim`
   on every call. The claim coordinates agents; it grants no access.
3. Ask for the least access and time the task needs:

   ```bash
   bin/machine-control --target host --claim "$CLAIM" grant request \
       --scope observe --scope control --duration 15m \
       --reason "Reproduce the settings crash in the running app"
   ```

   The call waits while the person decides. Write the reason for them: it is
   shown verbatim in the prompt.
4. Use the ordinary `desktop` commands. A result with
   `errorCode: approval_required` names the missing scope in
   `data.requiredScope`; request it once, with a reason.
5. When finished, run `grant revoke` and release the claim.

## Rules

- Treat `approval_denied` and `approval_timeout` as final for the task. Do
  not retry in a loop or narrow the reason to get past a person's decision.
- Never try to operate the Machine Control menu, prompt, or its settings;
  the resident refuses it and the attempt is recorded.
- A grant ends when the screen locks, when it expires, or when the person
  presses Stop (⌃⌥⌘.). Expect `approval_required` afterwards and ask again
  only if the task still needs it.
- The prompt labels your process chain as unverified. Do not claim to be a
  different program in the reason.
- Controlling the person's own desktop can move their pointer and change
  focus. Prefer semantic actions over coordinates, and say what you changed.
