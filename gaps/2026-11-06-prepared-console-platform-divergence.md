# Locked-console route differs by platform and misled an agent

Topic: `access-admission-and-pause`

Status: **Repaired in source (Tactical 159); Windows enrolled unlock awaits
live qualification.** The table below records the state before repair.

## Observations

On 2026-11-06 an agent on a locked physical workstation Mac followed the
installed `agent instructions`. They said covered tasks require
`control --prepared-console`, and that agents must never replace that
lifecycle with `session.unlock`. The agent tried the flag, was refused, and
stopped. It treated every other route as forbidden. When the operator told it
to try anyway, an ordinary Desktop `control stream` worked. It unlocked the
console behind covers, completed the task, and relocked on close, and doctor
independently confirmed `locked`.

The controller reproduced the refusals on a workstation Mac (preset
`workstation`, `protectedAdministration: false`):

| Route from a plain CLI/SDK caller | macOS result | Windows result |
| --- | --- | --- |
| Desktop owner while locked, no flag | covered unlock and relock | `prepared_console_required` |
| Desktop owner with `preparedConsole: true` | `invalid_prepared_console_request` | covered prepared owner |
| `session.unlock` | `operation_not_permitted_by_policy` (appliance only) | only inside a prepared owner |
| legacy `desktop session control` | `control_session_required` | operation absent |

## Mechanism

- **macOS:** `AdmissionChannel.open` accepts `preparedConsole` only together
  with a natively delegated channel (`desktopDelegation`, Tactical 087).
  `control.accept` enters covered activation for every non-delegated Desktop
  owner (`delegation == nil || preparedConsole`). Covered unlock is therefore
  implicit for plain callers and explicit only for delegated ones.
- **Windows:** `AdmissionChannel.cs` requires an explicit `preparedConsole`
  owner whenever the console is not ordinarily ready, and refuses
  `session.unlock` outside such an owner.

Nothing in the topics records this inversion as a decision. Tactical 087 added
the Mac flag for delegated composition; the Windows flag came from Tactical
101. The shared instruction text described the Windows rule as universal.

## Consequences

- One agent prompt cannot be correct on both platforms without branching on
  the platform.
- An agent that follows the documented rule on a Mac refuses a task the
  operator already enabled.
- Help also advertised a legacy Mac command that the shared-policy resident
  now refuses.

## Repairs

- **Done (d73fea5):** instructions, CLI help and Mac guides now describe each
  platform's actual route and mark legacy/appliance commands.
- **Proposed:** let the macOS resident accept `preparedConsole: true` from a
  plain caller as an explicit request for the same covered owner it already
  grants implicitly. This adds no authority. Then document one rule: request
  `--prepared-console` for locked Desktop work on every desktop platform.
  Decide separately whether macOS should eventually require the flag the way
  Windows does. That would break older clients, so it needs capability
  negotiation.
- **Proposed:** add a cross-platform conformance case for the same four
  requests above, so the table becomes test-enforced rather than
  documentation-only.

## Outcome

[Tactical 159](../docs/tactical/159-platform-contract-alignment.md#result) made
`--prepared-console` the one route for locked Desktop work.

- **macOS (`a49a4b2`):** accepts the flag from plain callers. Covered
  unlock/effect/relock passed live for both flagless and prepared owners.
- **Windows (`6e35697`):** unlocks at `control.accept`; `session.unlock` is a
  no-op afterwards. Its live cell awaits protected-helper enrollment on the VM.
- **Linux (`934632b`):** refuses with `locked_use_unsupported`.
- **Guidance (`303af1c`):** the instructions and help state the single rule.

