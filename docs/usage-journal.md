# Record difficult control use

Agents should leave a private note whenever Machine Control makes an ordinary
task hard. A later reviewer opens the note, follows its session reference to
the agent transcript, and compares the route with another provider such as
Computer Use. The resulting fix might be a typed command, a skill correction,
a conformance fixture, or a provider bug. Recording friction does not authorize
fixing it during the task.

## When to write a note

Write one note per distinct difficulty, while the details are fresh, when:

- one goal took more than about three attempts or materially longer than a
  person would need;
- you had to read Machine Control source to learn a command's grammar;
- a request was accepted but had no observed effect, or the effect was wrong;
- you switched to another route, such as Computer Use, AppleScript or a
  provider escape hatch (`--kind fallback`);
- the person took over (`--kind handoff`);
- an error stopped the task, even a setup or configuration failure before any
  control happened; or
- the typed surface lacked an operation you needed (`--kind follow-up`).

Write the note before reporting back to the person, so a stopped task still
leaves a trace. `usage note` is offline and works when the target is
unreachable. Routine success needs no note. If a task produced friction notes, close it
with one `summary` stating whether the goal was finally achieved and how.

```bash
machine-control --target host --claim "$CLAIM" usage note --kind friction \
  --goal "load an unpacked extension from chrome://extensions" <<'NOTE'
After cmd+shift+g in Chrome's folder chooser, the Go-to sheet was absent from
desktop snapshot until --max-depth 18. set_value on its path field and return
had no observed effect; OKButton was then missing from the snapshot.
NOTE
```

Kinds are `friction`, `workaround`, `fallback`, `handoff`, `follow-up`, and
`summary`. Describe the goal, the commands or element references tried, the
observed result, and what finally worked. Distinguish observation from a
suspected cause. Notes accept at most 4096 UTF-8 bytes on stdin. Never include
secrets, typed passwords, page contents you would not otherwise retain, or
private screenshots.

## Session attribution

Each note and each common CLI audit command records a self-asserted session
reference. The first valid value wins:

1. `--session-ref ID`, for notes only;
2. `AGENTCTL_SESSION_ID`, published by YepAnywhere for every hosted agent;
3. `CLAUDE_CODE_SESSION_ID`; then
4. `CODEX_THREAD_ID`.

`AI_AGENT`, when present, is recorded as the agent label. A YepAnywhere
session ID is the provider transcript ID, so a reviewer can locate
`~/.claude/projects/*/ID.jsonl` or `~/.codex/sessions/**/*ID.jsonl` without the
journal storing a home-directory path.

`claim acquire` and attributed `workspace acquire` use the same detected
session as the claimant when neither `--claimant-authority` nor
`--claimant-id` is given: authority `yepanywhere`, `claude-code` or `codex`,
with matching `--session-id`. Explicit attribution always wins, and a partial
pair is refused rather than completed.

## Review

```bash
machine-control usage show --limit 20
machine-control usage show --kind fallback --commands --markdown
machine-control usage show --session-ref SESSION_ID --commands
machine-control audit history --session-ref SESSION_ID
```

`--commands` attaches the retained [audit](target-operation-audit.md) result
events for the note's claim, or for its session when it has no claim. These
contain command grammar such as `desktop input text` and outcomes, never
arguments, typed text or payloads; the transcript holds that detail. Audit
history expires after 30 days, while notes remain until the 10,000-note bound.
Global `--target` filters `show` by the logical target recorded on notes.

## Storage and coverage

- macOS/Linux: `${XDG_STATE_HOME:-~/.local/state}/machine-control/usage/`.
- Windows: `%LOCALAPPDATA%/MachineControl/usage/`.
- `MACHINE_CONTROL_USAGE_DIR` selects an absolute private override.

The directory is mode `0700` and `notes.sqlite3` mode `0600`; links and public
permissions are refused. No upload occurs. Notes are agent-authored and
selective, session references are self-asserted, and a same-user process can
edit the file. Missing notes do not mean a task was easy. Promote only
sanitized, minimized findings into public topics or tests.
