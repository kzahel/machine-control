# Coordinating YA agent sessions

**Current (source-reviewed, offline-tested; bounded live lifecycle checks):**
[`scripts/ya-sessions.py`](../scripts/ya-sessions.py) provides a small Python
standard-library wrapper over existing YepAnywhere REST routes. It creates no
session until explicitly invoked with `create`. Its tests use synthetic API
responses. Coordinator checks additionally created a Sol 6.1 high/Fast review
session, observed matching selected and applied settings, and verified shutdown
of an owned completed worker. Queue correlation and resume remain separate
acceptance cases. A first mutation refused for a missing `X-Yep-Anywhere`
header; the helper now supplies the normal YA CSRF header and tests it.

[Delegation and placement](../topics/delegation-and-agent-placement.md) owns the
coordination decision. YA owns agent processes and supervision; Machine Control
owns target selection and target-use claims. Worker host, project checkout and
system under test remain independent selections. This helper addresses one YA
server and its target-local project. It neither discovers deployments nor
implements peer grants, SSH execution, or proposed `ya-agent` cross-session
commands.

## Before launching

The coordinator must already have the user's authorization for the work.
Delegation records that authority; agent-authored instructions cannot expand
it. Select an existing authenticated YA endpoint and the exact absolute project
path on its execution host. Do not guess a deployment endpoint, switch off auth,
create credentials, answer approvals, or change standing permissions to make a
launch succeed. An auth failure requires repair through the existing owner.

Give each worker a bounded objective, exact owned files, relevant instructions,
required deterministic checks, explicit exclusions, private report destination,
and a completion condition. Default to no nested delegation. Use disjoint files
for concurrent workers and one coordinator as committer; workers must not stage,
commit, revert other workers, create branches, or create worktrees unless the
coordinator explicitly assigns that work. Shared files go through the coordinator.

Set a small explicit concurrency bound before dispatch, based on available
capacity and scope. Queued requests count as outstanding work. Keep one writer
per receipt; the helper does not coordinate simultaneous receipt writers or
acquire Machine Control claims. Any later target operation still needs its own
read-only doctor, exact identity, claim and cleanup under the target's policy.

## Invocation

Supply all endpoint, project and receipt values at runtime from private
configuration. The following shell variables are placeholders, not deployment
defaults. `YA_URL` is the server root without `/api`; `YA_PROJECT` is the path on
the execution host. Create the private receipt directory beforehand, outside the
public checkout. Keep prompt and report files private too.

```sh
python3 scripts/ya-sessions.py \
  --base-url "$YA_URL" --project-path "$YA_PROJECT" \
  --receipt "$YA_RECEIPT" --auth-headers-file "$YA_AUTH_HEADERS" \
  create --message-file "$YA_PROMPT" --effort low --speed normal
```

The optional auth file is an **existing mode-0600 JSON object** containing only
`Authorization` and/or `Cookie` string headers accepted by that deployment.
Never pass credential values in command arguments. The helper reads that file
without modifying it, logging in, or persisting auth to its receipt. Omit the
option only when the established route already supports the request. Use the
existing protected transport for remote HTTP; the helper does not construct a
tunnel. It refuses URL userinfo, query strings and fragments, and refuses HTTP
redirects so auth cannot be forwarded to another endpoint.

`create` fixes the provider to `codex` and model to `gpt-6.1-sol`. Effort defaults
to `low`; only `low`, `medium`, and `high` are accepted, with `high` the ceiling.
The exact model's advertised reasoning efforts must include the choice. Normal
speed explicitly sends `serviceTier: "default"`, normalized by YA to standard
provider behavior. Fast selects the tier ID whose advertised name is `Fast`
(current Codex mapping: `priority`); it does not send the string `fast` or
assume every model supports it. Missing or ambiguous catalog evidence refuses
the launch. Only the selected model's catalog row is used; no catalog is printed.

Use the same global arguments for subsequent commands:

```sh
python3 scripts/ya-sessions.py \
  --base-url "$YA_URL" --project-path "$YA_PROJECT" \
  --receipt "$YA_RECEIPT" --auth-headers-file "$YA_AUTH_HEADERS" status
```

Replace `status` with `message --message-file "$YA_FOLLOWUP"` for a live process,
`resume --message-file "$YA_FOLLOWUP"` for a cold session, or `abort` for cleanup.
Message files may be `-` to read stdin. Resume and message retain the receipt's
bounded model, effort and tier request; they send no permission or approval
fields. They deliver an actual user turn, so they require authorization for that
instruction. A follow-up accepted into YA's queue is not proof the worker read
or finished it. Use the worker's private report for task completion evidence.

## Observe, reconcile, then continue

The receipt is reserved with mode `0600` before create dispatch. An existing
receipt refuses another create, preventing a routine rerun from making a second
worker. Updates use a mode-0600 temporary file and atomic replacement. Read paths
reject symlinks and non-private files on platforms supporting `O_NOFOLLOW`.
Receipts are private operational state, not bearer credentials or authorization.

A successful launch response records acceptance and identifiers. Status looks up
the exact session process, then falls back to its stable process ID in the active
and recently terminated process list. It checks project/provider identity and
retains prior session IDs when YA replaces a provisional ID with its canonical
provider ID. Never infer identity from a title, prompt, model, recent timestamp,
or “the newest process.” A later process for the same known session can be
observed and its previous process ID retained.

Configuration evidence remains separate:

- `selected` comes from the process's requested model, selected effort and
  service tier. `reportedModel` is the model reported by that process's provider.
- `lastApplied` comes from YA's persisted `effectiveLaunchSettings` snapshot,
  recorded by its process activation coordinator using applied effort. It is
  the last applied snapshot, not an atomic observation of the current turn.
- `selectionMatchesRequest` and `appliedMatchesRequest` compare those observations
  with the request. Missing snapshots and differences stay visible. A matching
  request alone never establishes either match. Inspect `reportedModel` too;
  aliases and provider-reported names can differ.

The live process effort getter can expose a pending next-turn change, so selected
and last-applied effort may disagree. Missing process evidence, missing applied
snapshots, mismatches or a still-provisional identity require further observation
before claiming the intended configuration ran. The helper does not change
configuration to hide a mismatch. Status reports `waiting-input` without reading
or answering the permission/approval request.

An HTTP `202` launch response supplies a queue ID and position, **not** a session
or process ID. Status checks the exact queue entry; abort can cancel that entry.
When it departs, a known resumed session can be reconciled through its process.
For a queued **new** session there is no safe polling correlation in these REST
responses: status reports `queue-departed-unresolved`. The coordinator must
reconcile the original queue-start event in YA privately before proceeding.
The helper deliberately has no “pick newest” or arbitrary attach command. Do not
repeat create to resolve this gap. If cancellation races with launch, inspect YA
and reconcile identity; a missing queue entry does not prove cancellation.

Transport failures after dispatch have unknown outcomes. The receipt preserves
`dispatch-pending` before dispatch and status reports `dispatch-outcome-unknown`
when no identity can resolve it. An accepted launch receipt is saved before its
follow-up observation, so an observation failure does not erase launch IDs.
Inspect the receipt and YA state privately; never automatically retry a mutating
request. HTTP diagnostics omit server bodies and transport exception text because
these can contain secrets or prompts. No transcripts, message content, titles,
raw unrelated catalog rows, or credentials are written to receipts or stdout.

## Finish and close

First collect the worker's concise private report: changed files, checks,
limitations, unresolved questions and integration steps. Review the actual diff
and tests before committing. An idle process is not proof of completed work;
a terminated process is not proof of success. Bounded status polling belongs to
the coordinator; stop polling after the report and cleanup settle.

`abort` calls YA's verified process shutdown with `blockResume: true`, requesting
exemption from YA-owned heartbeat and auto-resume after shutdown. Check both the
`stopped` outcome and returned exemption booleans; missing/false values remain
unverified. Killing a worker is distinct from deleting or archiving its durable
session, committing its changes, releasing a target-use claim, or stopping an
independent Machine Control resident. The helper does not perform those actions.
Release any coordinator-owned target claims separately in finally-style cleanup.

Maintain a private campaign ledger with exact endpoint/project/session/process/
queue IDs, receipt/report locations, owned files, authority scope, bounded
concurrency, states, unknown outcomes and cleanup result. Keep credentials in
their existing secret store, never in the ledger. Public tactical tracking records
sanitized objectives, decisions, test results, integration state and remaining
work. It must not copy private paths, deployment names, session IDs, prompts,
transcripts or ledger entries. A session receipt complements that ledger; it is
not a complete history or proof of authenticated agent identity.

## REST implementation references and checks

The source-reviewed contract lives in the sibling YA checkout:

| Operation | REST route | Implementation |
| --- | --- | --- |
| Model/tier preflight | `GET /api/providers/codex` | `packages/server/src/routes/providers.ts` |
| Create with initial turn | `POST /api/projects/:projectId/sessions` | `packages/server/src/routes/sessions.ts` |
| Process observation | `GET /api/sessions/:sessionId/process` | same |
| Applied snapshot | `GET /api/projects/:projectId/sessions/:sessionId/metadata` | same; `supervisor/SessionActivationCoordinator.ts` |
| Resume with turn | `POST /api/projects/:projectId/sessions/:sessionId/resume` | same routes file |
| Live message | `POST /api/sessions/:sessionId/messages` | same |
| Exact process fallback | `GET /api/processes?includeTerminated=true` | `packages/server/src/routes/processes.ts` |
| Verified stop | `POST /api/processes/:processId/abort` | same |
| Queue status/cancel | `GET/DELETE /api/queue/:queueId` | `packages/server/src/routes/supervisor-queue.ts` |

Project IDs are unpadded base64url of UTF-8 target-local absolute paths, per
YA's `packages/shared/src/projectId.ts`. Thinking effort is sent as `thinking`,
per `routes/session-thinking-options.ts`. Re-review these contracts when YA
changes; the helper is an operator convenience, not a second coordination API.

```sh
python3 -m unittest discover -s tests/experiments -p test_ya_sessions.py -v
```
