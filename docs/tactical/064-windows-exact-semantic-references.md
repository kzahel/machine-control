# Windows Exact Semantic References

Status: complete, 2026-09-29.

Native UIA currently converts a snapshot reference back into a global label
query. Two controls named Start can therefore invoke the wrong application.
Fix reference resolution for invoke and set.value without changing query-only
search, provider composition, privilege or deployment policy.

Cache the observed opaque UIA runtime ID and process ID under a fresh reference;
resolve only that identity inside the bounded 10,000-node search. Never fall
back to a name, caller query or another control when the referenced element is
absent. Preserve generation fencing and the 10,000-entry cache bound. UIA IDs
are desktop-scoped and may be reused over time: this does not promise durable
identity across arbitrary provider reuse. Fresh references avoid overwriting
old observations when a new snapshot returns the same UIA identifier.

Source: [Microsoft GetRuntimeId documentation](https://learn.microsoft.com/en-us/dotnet/api/system.windows.automation.automationelement.getruntimeid).

Validate duplicate-label controls with independent fixture counters and text
readback, removed-element refusal, generation refusal, unchanged query behavior,
format, contract checks and x64/ARM64 publishes. Exercise an isolated user host
in the claimed Windows guest before updating its installed controller. Stop
when the regression and product Start action select their exact observations.

## Evidence

The isolated Windows x64 user host passed
`reference-fixture.ps1` plus `reference-conformance.ps1`: the right duplicate
text field changed independently, the second Start button alone incremented
its marker, that removed button's old reference refused, wrong generation
refused, and query-only lookup still affected the remaining button. A
contradictory caller query could not override an observed reference. The same
controller subsequently invoked the real application's Start button (empty
AutomationId) and its authenticated application snapshot confirmed resume;
the shell Start button was untouched.

Linux cross-publishes for win-x64 and win-arm64 pass. Plain Linux build/format
cannot load Windows desktop runtime references, so full Windows static checks
were run in the guest: four builds, format verification, PowerShell parsing,
and WindowsUnlock.Contracts all pass. The claimed common runtime bootstrap then refreshed the installed appliance.
The same duplicate-reference regression passes through its installed facade;
the owned fixture was closed and temporary user host stopped. No outer UI
was used.
