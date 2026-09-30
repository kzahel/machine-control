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
3. Ask once for every scope the task can need, for the time it needs:

   ```bash
   bin/machine-control --target host --claim "$CLAIM" grant request \
       --scope observe --scope control --duration 15m \
       --reason "Reproduce the settings crash in the running app"
   ```

   The call waits while the person decides. Write the reason for them: it is
   shown verbatim in the prompt. Each extra request is another interruption,
   so plan scopes up front: `observe` to see the screen or windows, `control`
   for keyboard, pointer, and apps, `browser` for Chrome tabs, and `devtools`
   for raw DevTools protocol access. A browser
   task that may show a native dialog needs all three.
4. Use the ordinary `desktop` commands. A result with
   `errorCode: approval_required` names the missing scope in
   `data.requiredScope`; request it once, with a reason.
5. When finished, run `grant revoke` and release the claim.

## Browser work

- Prefer `browser` commands over desktop input in Chrome: `snapshot` gives
  references, then `click`, `type`, `key --key Enter`, and `navigate`.
- Attach files with `browser upload --reference R --file /absolute/path`,
  where `R` is a file input or the page's upload/attach button. It never opens
  the macOS file dialog. Do not click upload buttons and then drive the
  native Open dialog with keystrokes.
- For anything the typed commands do not cover, request the `devtools` scope.
  For a few calls, use `browser cdp --method Domain.method --params JSON` or
  `browser eval --expression JS`. For a live session or to watch events, run
  `browser endpoint` and connect a raw CDP WebSocket client to the returned
  `ws://127.0.0.1:PORT/devtools/page/<tabId>?token=…` (substitute a real tab
  id from `browser tabs`). Do not send an Origin header. The endpoint stops
  working when the grant ends. Say in the reason why raw DevTools access is
  needed; it lets the agent act on every signed-in site.
- Files in hidden folders or `~/Library` are refused. If Chrome reports
  `file_access_not_allowed`, ask the person to turn on "Allow access to file
  URLs" for Machine Control in `chrome://extensions`.

## Desktop input

- Key chords join modifiers and one key with `-` or `+`: `cmd+shift+g`,
  `ctrl-option-cmd-.`, `return`, `escape`.
- Pass `--target APP` when you know which application should receive keys.
  Some system sheets only accept untargeted input; then check
  `data.keyboardReceiver` in the result to confirm where the keys went, and
  stop if it is not the application you meant.

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
