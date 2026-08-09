# Tactical 003: Windows Credential Login

Status: completed 2026-08-09.

Topics: `windows-resident-control`, `architecture`, and
`capabilities-and-results`.

Parent tactical:
[`002-windows-full-target-native-control.md`](002-windows-full-target-native-control.md).

## Objective

Prove that an authorized outside operator can use the target-resident Windows
runtime before interactive login to select the stock Windows Hello PIN or
password Credential Provider, submit one secret without exposing it to an
agent transcript or ordinary JSON contract, and independently confirm a real
login and Medium-helper attachment.

PIN and password are separate acceptance cases. Software Secure Attention
Sequence generation is a conditional follow-up when target policy actually
requires `Ctrl+Alt+Delete`; it is not a prerequisite manufactured for this
test.

## Completion conditions

- The automatic service and authenticated administration carrier remain
  reachable with no interactive user.
- A dedicated interactive CLI reads a PIN or password without echo. The secret
  is absent from command arguments, environment variables, shell history,
  ordinary JSON requests/results, logs, screenshots, evidence, and Git.
- The service accepts only one bounded credential submission for the current
  target/session generation and never retries an unknown or failed outcome.
- The protected route confirms `Winlogon`, reveals the sign-in surface, selects
  the requested stock PIN or password provider, focuses its credential field,
  submits once, and reports all semantic or target-local input fallbacks.
- PIN login and password login each begin from a real no-user state and end in
  an independently observed interactive session on `Default` with a Medium
  user helper.
- Failed field/provider discovery refuses before secret submission. Incorrect
  credential behavior is not deliberately tested because it can consume
  lockout budget.
- Credential buffers are minimized and cleared on a best-effort basis after
  use. Results reveal only credential kind, delivery, effect, route, elapsed
  time, and redacted state evidence.
- Existing UAC, secure-desktop, Windows Hello, password, lockout, and sign-in
  policy remains unchanged.

## Architecture under test

```text
human terminal -- authenticated SSH transport --> target-local login CLI
        hidden prompt                         - no argument/env secret
                 |                            - one submission
                 +---- dedicated secret IPC --+
                                                |
                                      LocalSystem service
                                                |
                                      Winlogon desktop worker
                                        - reveal sign-in UI
                                        - choose PIN/password tile
                                        - focus credential field
                                        - target-local secret input
                                        - submit once
                                                |
                                      WTS + Default + Medium helper
                                      independent effect oracle
```

The agent coordinates state and observes redacted results but does not receive
the credential. The human runs the prompting command directly. A future secret
broker may replace the human without changing the protected login operation.

## Boundaries

- Do not place a PIN or password in chat, tool arguments, JSON, command-line
  options, environment variables, files, screenshots, logs, or evidence.
- Do not store credentials, enable autologon, weaken Windows Hello or lockout,
  disable the secure desktop, or change sign-in policy to manufacture a pass.
- Do not implement or register a custom Credential Provider in this tactical.
  Drive the stock Windows providers unless evidence proves that insufficient.
- Do not test a deliberately wrong PIN or password.
- Do not add `SendSAS` or change its enabling policy unless the real target
  requires SAS before exposing Credential Providers. Record that as a separate
  conditional result.
- Do not claim login from successful input delivery. WTS session/user state,
  the input desktop, and the Medium helper are the effect oracle.

## Implementation steps

### 1 — inspect the no-user credential surface

Log out through the typed lifecycle operation, keep SSH/service reachability,
and inspect only minimized sign-in semantics and state. Determine the exact
stock provider labels, field names, and required non-secret actions without
capturing credential contents.

### 2 — add secret-specific IPC and CLI prompting

Add a login command that reads characters without echo and never accepts the
secret as an option. Carry the credential over a dedicated one-shot local IPC
exchange rather than the ordinary JSON request. Bind it to credential kind,
session, generation, expiry, and one-use state; clear mutable buffers after
dispatch.

### 3 — drive the selected stock provider

Implement the smallest deterministic protected workflow needed to reveal the
sign-in UI, open sign-in options, select PIN or password, focus the correct
field, type the secret from a mutable buffer, and submit once. Report semantic
selection versus target-local keyboard/pointer fallback explicitly.

### 4 — prove PIN login

From no-user `Winlogon`, have the human run the hidden prompt in a separate
terminal and enter the correct PIN. Confirm the interactive user, `Default`,
Medium helper, session/generation rebinding, and absence of secret artifacts.

### 5 — prove password login

Log out again with advance warning. Repeat through the password provider and
the hidden prompt, with one submission and the same independent effect checks.

### 6 — evaluate SAS only if required

If policy blocks access behind `Ctrl+Alt+Delete`, record the real refusal and
open a narrow `SendSAS` follow-up using Windows' service and policy boundary.
Otherwise record SAS as unnecessary for this target rather than expanding the
runtime preemptively.

### 7 — verify cleanup and update current truth

Delete all generated sign-in observations and test IPC state, confirm policy
and lockout settings are unchanged, and record only redacted conformance
evidence. Update the Windows topic and parent tactical with the proven login
surface and remaining portability gaps.

## Validation record

The physical Windows x64 target passed both one-submission cases from a real
no-user `Winlogon` state. The human entered each secret through
`scripts/login-windows.sh`; neither credential entered chat, JSON, command
arguments, environment variables, a file, a screenshot, public evidence, or
Git.

The pre-secret path used native UI Automation. PIN was already the selected
stock provider and exposed a semantic `PIN` edit control. Password required an
invokable `Sign-in options` hyperlink followed by the semantic stock
`Password` button and `Password` edit control. A discovery check caught an
important ambiguity before live submission: the PIN edit's internal automation
ID contained the word `Password`. Provider selection therefore requires the
expected button name or stable built-in provider automation ID. Credential
fields match their visible semantic name, or—only after positive provider
selection—a unique visible edit geometry. Ambiguous discovery refuses before
the one-shot secret pipe is opened.

After positive field discovery, the disposable LocalSystem Winlogon worker
read the secret over a SYSTEM-only one-shot pipe and delivered Unicode
characters plus Enter through target-local `SendInput`. It took no screenshot
and cleared mutable secret buffers on a best-effort basis. The result reported
only credential kind, semantic/input route, delivery, effect, and redacted
state.

PIN and password each independently ended with an interactive unlocked user on
`Default` and a newly attached ordinary helper at Medium integrity RID 8192.
The automatic service and authenticated SSH carrier remained available across
both logouts. Ordinary JSON login, login while a user was already present, and
non-Winlogon routing were separately refused before UI input.

`Ctrl+Alt+Delete` was not required by this target's real policy, so no
`SendSAS` policy or implementation was added. Temporary deployment staging was
removed, existing UAC/secure-desktop/sign-in policy was not weakened, and the
runtime remains installed for continued appliance testing.
