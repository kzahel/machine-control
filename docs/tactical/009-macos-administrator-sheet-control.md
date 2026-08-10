# Tactical 009: macOS Administrator-Sheet Control

Status: active.

Topics: `macos-resident-control`, `architecture`, and
`capabilities-and-results`.

Research:
[`macOS platform report`](../../research/platforms/macos.md).

Authoritative testbed:
[`macvm-testbed`](../../../macvm-testbed/README.md).

## Objective

Prove that the Tart guest's target-resident macOS controller can operate a
normal administrator authorization sheet from inside the logged-in Aqua
session. Use a deterministic harmless privileged request, identify the exact
sheet before accepting a credential, deliver that credential through a
one-shot non-echoing channel, and verify success or failure independently of
input acknowledgement. Ordinary acceptance must not use Tart-window capture or
input.

Begin with the existing ordinary resident and its granted Accessibility,
Screen Recording, and target-local input routes. Add a more privileged broker
only if live evidence proves that the normal user-session controller cannot
deliver to the authorization sheet.

## Completion conditions

- Every mutation uses the guarded copy-on-write Tart candidate; the prepared
  source remains protected.
- A deterministic fixture requests a harmless privileged operation and records
  requested, cancelled, denied, authorized, and completed states through an
  independent file oracle without changing durable system configuration.
- The resident observes and identifies the exact authorization sheet, owning
  process, secure text field or bounded input target, and available buttons.
  A merely visible password-like window is not sufficient identity.
- The resident can cancel the sheet and independently observe cancellation
  without outer input.
- Credentials never appear in request JSON, command arguments, environment
  variables, files, logs, captures, shell history, repository content, or
  result envelopes.
- A guest-local helper reads one credential without echo and transmits it over
  a user-owned, mode-`0600`, one-shot channel bound to the current resident
  generation, exact sheet identity, short expiry, and single submission.
- Correct and incorrect credential cases produce independently observed,
  bounded results. Delivery, sheet dismissal, authorization, privileged
  command completion, and uncertainty remain separate.
- Missing, expired, reused, wrong-generation, wrong-sheet, cancelled, and
  unavailable-channel cases fail closed without provider or outer-route
  fallback.
- Resident restart invalidates pending authorization leases. Full guest reboot
  restores ordinary readiness and permits a new authorization attempt without
  Tart-window input.
- Fixture applications, oracle state, credential sockets, captures, logs, and
  temporary files are removed. The accepted candidate is stopped, the source
  remains unchanged, and all repositories are clean.

## Boundaries

- This tactical covers a normal Aqua administrator authorization sheet in the
  prepared Tart appliance. It does not cover loginwindow, FileVault/preboot,
  firmware, Recovery, or another user's session.
- Do not weaken TCC, SIP, secure input, code-signing, or Authorization Services.
  Do not edit or transplant TCC or authorization databases.
- Do not add a password field to `machine-control/v0`, an MCP tool, or any
  ordinary agent-visible request. A public bootstrap credential still uses the
  secret-safe path so the contract remains suitable for real credentials.
- Never infer authority from a window title, coordinates, or the presence of a
  secure text field alone. Bind the one-shot channel to observed process,
  window, resident generation, and fixture request identity.
- A failed or uncertain mutating submission is observed and reconciled before
  any retry. Do not create repeated authentication attempts that could trigger
  account lockout.
- Outer Tart input remains available for explicit recovery, but any use during
  this tactical invalidates the corresponding inner-control acceptance case.
- Do not generalize a successful password sheet into unrestricted root control.
  The fixture proves one authorization interaction; future product operations
  still need bounded intent and policy.

## Implementation steps

### 1 — create a harmless authorization fixture

Package a small guest application that requests authorization for a read-only
privileged command and records its lifecycle in an independent oracle. Give
each request an opaque identity so a resident lease cannot accidentally bind
to a stale or unrelated sheet.

### 2 — observe and cancel from the resident

Trigger the sheet through the fixture, inventory the real owning process and
window, inspect the Accessibility surface and exact-window capture where macOS
permits, and define a strict sheet fingerprint. Implement and prove Cancel
without focusing Tart or using host input.

### 3 — add the one-shot credential channel

Add an authorization-begin operation that creates a short-lived lease only
after the fingerprint matches. Install a guest-local non-echoing helper that
streams one credential through a dedicated private socket or equivalent
descriptor channel. Keep the secret out of JSON and all durable state, erase
transient buffers where practical, close the channel after one attempt, and
return only minimized outcome metadata.

### 4 — submit and verify effects

Focus the sheet's secure input target, deliver the credential target-locally,
submit once, and observe sheet dismissal plus the fixture's authorization and
command-completion oracle. Exercise a correct credential, one controlled
incorrect attempt, explicit cancellation, and timeout without automatic retry.

### 5 — prove failure and lifecycle behavior

Exercise missing, expired, reused, stale-generation, wrong-sheet, and resident
restart cases. Shut down and restart the guest without outer input, re-establish
ordinary readiness, and complete one fresh bounded authorization workflow.

### 6 — clean and record the result

Remove fixture and authorization artifacts, stop the candidate normally, and
record the measured sheet reach, secret boundary, routes, effects, limitations,
and whether a privileged broker was necessary. Update the macOS topic,
platform report, capability vocabulary, testbed runbook, root entry point, and
this execution record.

## Validation record

Pending live execution.
