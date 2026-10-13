# 118 — Usage friction journal

Status: complete. Source implementation, fixture tests and live comparison
runs on a personal Mac host are complete; follow-ups are listed below.
Owning topics: [operational workflow automation](../../topics/operational-workflow-automation.md),
[target operation audit](../../topics/target-operation-audit.md).

## Objective and completion conditions

The operator observed an agent struggling to load an unpacked Chrome extension
through Machine Control on a personal Mac: omnibox typing landed in History,
the Open panel's Go-to sheet was hard to find, and the agent fell back to
Computer Use before the person took over. Nothing recorded those difficulties
for later review. The request: have agents record difficulties privately, tie
them to the agent session so a reviewer can read the transcript, and compare
routes with Computer Use on the same task.

Complete when:

- agents can write private, bounded friction notes through the common CLI;
- notes and audit commands carry the agent host's session ID without a
  coordinator dependency;
- unattributed claims default to that session inside a publishing host;
- skills and installed-agent instructions say when to record a note; and
- live runs show notes and their audit trail retrievable for a real task, with
  a sanitized comparison against Computer Use.

## Boundaries

Notes are agent-authored and self-asserted; they authenticate nothing and do
not replace audit history or provider diagnostics. Audit commands still omit
arguments, typed text and payloads. Recording friction does not authorize
fixing it within the task. Live run evidence, transcripts and screenshots stay
private; only sanitized findings enter this repository.

## Ordered work

### 1 — record usage notes and session attribution

Add offline `usage note|show`, private SQLite storage beside the audit
journal, a self-asserted `sessionRef` from `AGENTCTL_SESSION_ID`,
`CLAUDE_CODE_SESSION_ID` or `CODEX_THREAD_ID`, and `audit history
--session-ref`. Attach retained audit results per note's claim or session.

### 2 — retain enough command grammar to review

Keep browser verbs (`navigate`, `tabs`, `wait`, `upload`, `cdp`, `eval`,
`endpoint`) and desktop input kinds (`text`, `key`, `click`, …) in audit
command descriptions while stopping before their operands.

### 3 — tell agents when to write

Default the claimant to the detected session. Update the root guide, the
installed-agent instructions and the macOS host, macOS VM, Linux VM and
Windows VM skills.

### 4 — prove it with live comparison runs

Launch independent agents on the extension-loading task through Machine
Control and through Computer Use. Confirm their notes, session references and
audit trails are retrievable, and compare the routes.

## Validation

Focused fixture tests cover session precedence and validation, claim and
session audit correlation, pagination, the note bound, private permissions,
CLI input bounds, payload omission and the claimant default (explicit pair
wins, partial pair refused). The full client and release-package suites pass.

## Final result

Step 1–3 landed as planned. The live step used Codex sessions launched
through YepAnywhere on a personal Mac, each loading and then removing a
throwaway probe extension in the everyday Chrome profile. Four Machine
Control attempts and two Computer Use attempts ran; the original failed
session was backfilled as notes with an explicit session reference.

**Current:** The journal works end to end. Notes recorded the Codex thread
ID automatically, claims defaulted to it as claimant, and `usage show
--commands` attached each note's claim or session audit trail without
arguments or typed text. Later runs wrote notes before reporting back.

Live runs exposed and fixed four problems:

- a source checkout lost the built-in `host` target when the sibling
  private inventory provider was present; inventory registries now keep it;
- a malformed claim ID produced an opaque refusal, and an agent that had
  dropped one character could not tell; the refusal now states the expected
  shape and what differs;
- the first agent stopped on a blocker without a note; guidance now covers
  blocking errors and states that notes work offline; and
- an agent revoked a standing grant it had not requested because the host
  skill said to revoke unconditionally; it now revokes only its own.

Comparison (sanitized):

| Route | Attempts | Loaded, verified, removed | Time on success |
| --- | --- | --- | --- |
| Machine Control | 1 after setup fixes (plus the original) | 1 | about 5 minutes |
| Computer Use | 2 | 0 | — |

Both routes reached `chrome://extensions` quickly; every failure and most of
the time was in the macOS Open panel. Computer Use could not open Go to
Folder and gave up within one to three minutes. Machine Control opened it
with cmd+shift+g; an absolute path returned to the volume root, while the
same path without its leading slash produced a selectable suggestion. The
successful run was coordinate-driven and verified with window captures,
because `chrome://` pages are outside the browser route.

**Open:** follow-ups, in priority order:

1. `--help` for desktop and browser subcommands; nine of 45 audited commands
   in the successful run were usage refusals while learning grammar.
2. A typed native Open-panel path or folder choice for the Mac host; `browser
   upload` covers only file inputs, and the native panel is the root of the
   task's difficulty on every route.
3. Document that `chrome://` pages refuse `browser navigate` and snapshot,
   and that `about:blank`, cmd+l, `desktop input text` and Return works.
4. Accept application names or `--target` consistently on `desktop snapshot`
   and `desktop input click`.
5. Consider binding `grant revoke` to the requesting caller.
