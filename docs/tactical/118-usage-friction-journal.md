# 118 — Usage friction journal

Status: active. Source implementation and fixture tests are complete; live
comparison runs are in progress.
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

Pending step 4.
