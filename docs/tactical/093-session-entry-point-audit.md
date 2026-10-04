# Session entry-point and authority audit

Status: complete for the bounded source inventory; runtime migration not begun.
Owning topics: [unified desktop client](../../topics/unified-desktop-client.md),
[caller authorization](../../topics/caller-authorization.md),
[admission](../../topics/access-admission-and-pause.md) and
[target-use claims](../../topics/target-use-claims.md).

## Objective and completion conditions

The user requested the first migration step before choosing a stateful Python
or JavaScript facade: inventory existing entry points, claims, authorization
and concurrency so desktop app, CLI and agent tools can converge without
discarding mature native providers. Include ChromeOS and device-hosted iOS.

Complete this slice with a source-linked matrix, explicit coverage gaps and
profile distinctions, operation/conflict classifications, and a bounded next
implementation gate. Do not treat a claim selector as caller authentication.

## Boundaries and ordered work

### 1 — inventory command and native ingress

Read common CLI/SDK dispatch, host/VM adapters, native desktop grants and
admission, direct resident and browser routes, protected/operator/recovery
paths, and ChromeOS/iOS/Android/Quest entry points. Record Steam Deck's common
profile but defer its detailed platform dispatch audit explicitly.

### 2 — separate authority and concurrency guarantees

Distinguish target reservation, caller grant, active connection ownership,
claim-record locking, individual effect serialization and workflow lifetime.
Classify direct routes, profile exceptions, bootstrap exemptions and alternate
controllers without inferring containment from same-user interfaces.

### 3 — qualify the next implementation slice

Retain existing providers and operation envelopes. Select ordinary desktop
owner enforcement and CLI compatibility before model-runtime ergonomics.
Specify cross-platform/device placement constraints and negative acceptance
cases. Run existing deterministic claim/channel fixtures only; no target
connections, UI actions, provisioning, credentials or service restarts.

## Validation and final result

**Current:** the [source audit](../session-entry-point-audit.md) records the
reviewed revision, matrix, source anchors, gaps and proposed next slice.
All 28 selected tests pass: 9 common control-session tests, 5 claim transport
guardian tests and 14 claim-store tests. Local Markdown links and whitespace
checks pass. This is source/fixture evidence, not a native runtime security or
concurrency qualification. No runtime changes were made.

The result is a concrete starting boundary: existing Mac/Windows workstation
owner channels and compatible CLI entry, with authoritative exact-claim
binding still requiring an explicit design. Linux/device/admission differences,
direct resident bypasses, raw browser access and protected routes are recorded
rather than hidden behind a generic claim of unified session support.
