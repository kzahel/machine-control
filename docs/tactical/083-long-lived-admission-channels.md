# Long-lived admission channels

Status: complete for the cooperative Mac and Windows channel implementations.
Owning topic: [access admission and pause](../../topics/access-admission-and-pause.md).

## Objective and completion conditions

Keep a four-hour bounded desktop wait live without exhausting the former
request-ID budget after roughly fourteen minutes of normal SDK polling.
Negotiate compatibility, reject replay/downgrade and retain bounded memory.
Prove native handoff and prompt connection cleanup without renewing authority.

## Boundaries and ordered work

### 1 — negotiate ordered frames

Advertise strict ordering in live native intent replies. New clients switch
only after receiving that capability; old providers retain existing framing.
Accept exact positive, next Int64 sequences. Reject replay, gaps, overflow,
wrong numeric types and downgrade by closing the owning connection. Legacy
clients retain a 4,096 unique-ID budget, including their opening frame.

### 2 — prove duration, compatibility and cleanup

Exercise 72,000 ordered frames in each native ordering fixture, plus replay,
gap, downgrade and numeric refusals. Test a real socket replay closing its
owner without dispatch and admitting a successor. Exercise 4,200 SDK status
requests with an ordered peer, alongside legacy provider tests.

Deploy the source-native Mac resident through an exact VM claim and verify
readiness. Keep a native owner active through 4,200 real status requests, then
close it. This trial took 108 seconds; it exceeds the old request budget but
is not a four-hour wall-clock soak. Independent duration/deadline behavior
continues to be tested with the admission fake clock.

## Validation and final result

**Current:** 118 Swift tests, Windows desktop contract fixtures and 171 common
client tests pass. Linked Windows formatting and full-project whitespace
verification pass; the latter reports the existing non-Windows workspace-load
warning. ARM64 and x64 Windows publishes pass. Source-native Mac deployment
and doctor pass; native ordered ownership closes promptly after the trial.

This fixes the connection budget without changing grant duration, protected
watchdogs, queue deadlines, caller assurance or restart behavior. Full native
Windows formatting and acceptance remain platform gates; exact Windows target
identity is unavailable in the current private inventory.
