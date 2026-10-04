# Windows required owner session and CLI compatibility

Status: source slice complete with deterministic validation; installed
Windows desktop/browser acceptance pending.
Owning topics: [unified desktop client](../../topics/unified-desktop-client.md)
and [access admission](../../topics/access-admission-and-pause.md).

## Objective and completion conditions

The user requested a bounded first implementation of shared live ownership,
preserving mature providers and basic CLI usability before choosing a persistent
Python/JavaScript agent runtime. Require one connection-owned desktop session
in the Windows desktop product, and route compatible common CLI calls through
the same native checks. Complete the source slice with negative lifecycle
fixtures, CLI compatibility/stream fixtures, formatting and both Windows
architecture publishes. Keep installed-build qualification explicit.

## Boundaries

No all-platform rewrite, interpreter, new MCP server, automatic installation,
claim replacement/renewal, or new caller authentication. The existing adapter
claim guardian remains separate from resident ownership. Desktop operator,
grant/update/status, headless workstation, protected appliance, and outer
recovery policy remain as before. This slice is not a fix or reproduction of
the reported Mac application-registration/resource failure.

## Ordered work

### 1 — enforce owner context at Windows desktop dispatch

Require the trusted in-process `ControlOwnership` attached by the live
admission channel for native and browser operations. Preserve grant, readiness,
generation and pre-effect checks. Refuse caller-supplied JSON ownership, and
advertise the requirement in capabilities and a typed undispatched refusal.
Match browser admission to the existing devtools grant coverage.

### 2 — preserve simple CLI entry and retain multi-action ownership

Negotiate one short session only after an explicit, safely undispatched
requirement. Use the existing Python SDK and adapter channel. Preserve explicit
local-route parity probes. Add sequential JSON-lines `control stream` for
scripts to read a result and issue the next action under the same owner; EOF,
refusal and error close the connection. Do not replay, fall back, or reacquire
silently. Document reference generations and bounded session lifetime.

### 3 — prove lifecycle and compatibility without controlling a desktop

Use the real Windows admission channel over loopback streams with deterministic
effects: idle grant without owner, forged context, two competing connections,
Pause, stale offers, disconnect/replacement and heartbeat expiry. Use a Python
protocol peer to exercise negotiation, transport failure, uncertain outcomes,
stream reuse and cleanup. Retain existing claim-expiry/parent-death fixtures.

## Validation and final result

**Current:** Windows desktop grant/live-channel and common admission contracts
pass. All 229 common client tests and 35 claim-store/guardian tests pass, including
17 control-session tests covering negotiated handoff, uncertain delivery,
interactive stream replies before EOF and cleanup. Runtime and desktop-contract
`dotnet format --verify-no-changes` checks pass, as do self-contained Windows
ARM64 and x64 runtime publishes. On this Mac, format needs
`RuntimeIdentifier=win-x64` to load Windows references; runtime publishes use
the full .NET 10 SDK and portable contract execution uses .NET 8. The
Windows-only unlock contract executable is not runnable here and remains a
Windows CI check; the protected implementation is unchanged.

These fixtures exercise the real arbiter/channel and
client, but replace Windows UI providers with deterministic effects. Native
named-pipe ACLs, operator notices, UIA input and browser extension delivery need
an installed Windows acceptance pass before release. ChromeOS/iOS placement
proofs and remaining platform migration remain subsequent slices.
