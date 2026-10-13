# 115 — Mac covered startup observation ordering

Status: complete bounded diagnosis, source repair and authorized signed local
installation with one physical completion cell; wider qualification open.
Owning topics: [macOS locked use](../../topics/macos-locked-use.md) and
[runtime and presentation](../../topics/runtime-and-presentation.md).

## Objective and completion conditions

Explain the observed covered-startup failure in desktop 0.6.0, reproduce the
relevant observation race deterministically, and repair it without changing
the installed controller or issuing further live lock/unlock operations.
Require failing-before/passing-after regressions, safety-boundary coverage,
the full Swift suite and both Mac architecture builds.

## Boundaries

The initial diagnosis excludes installation, helper repair, policy change,
new approval, credential access, release publication and live lock/unlock
operations. A later explicit user request authorizes signed local installation,
recorded separately below. Synthetic session dictionaries
exercise state ordering without manipulating an OS desktop. Existing root
watchdog, cover, physical takeover, expiry and console-identity requirements
remain authoritative. Exact host details and diagnostic evidence remain private.

## Ordered work

### 1 — correlate the failed transition

Read installed version identity, the earlier resident audit, and the relevant
0.6.0 and current source. Distinguish request acceptance from observed unlock
and correlate cancellation reasons. The platform report owns bounded live
failure evidence; it does not infer an unobserved screen transition.

### 2 — reproduce observation rollback

Seed the production background observer with a locked console, then deliver a
newer unlocked observation and poll again. Separately hold a pre-transition
read until after the newer observation. Both tests must reject rollback.

### 3 — preserve ordering through covered activation

New direct observations replace the cache and fence older read completions
without freeing an occupied worker. Cache projections do not renew evidence
lifetime. The trusted guardian's active reply carries the native observation
already established after helper unlock. The parent validates unlocked state
and the original console before adopting that observation and becoming active.

### 4 — validate safety and build both architectures

Check expiry, stopped-observer refusal, retained worker capacity, missing or
foreign console identity, unknown/locked readiness, and unlocked-origin refusal.
Run the full Swift suite, macOS static smoke, and isolated ARM64/Intel native
app assembly with signature verification. Do not launch or install those apps.

## Validation and final result

**Current:** both new rollback tests fail against the original implementation,
reporting `locked` where the newer observation is `unlocked`. They pass after
the ordering repair. Five added regressions cover the two races, observation
lifetime, physical worker capacity/Stop, and exact-console activation validation.
All 175 Swift tests and macOS static smoke pass. Both optimized native app
architectures assemble and pass the build script's ad-hoc signature
verification. These are development builds, not notarized or published product
packages.

### Authorized signed local installation

**Current:** the user subsequently requested a signed installation for testing.
The existing 0.6.0 Tauri desktop and bundled CLI are copied into private staging;
the repaired ARM64 Swift framework is built with the product bridge. Sealed
metadata marks the bundle as a local covered-observation candidate and binds
the exact patch digest. All nested native code and the final app are signed
using the installed publisher's Developer ID identity. Deep strict integrity,
the original designated publisher requirement and the bundled CLI inventory
verify before installation.

The candidate loads on an isolated endpoint with native permissions retained.
The supported per-user installer replaces the canonical app only on an unlocked,
idle console under an exclusive host claim. The original notarized bundle and
LaunchAgent are privately backed up for rollback. Installed framework and patch
digests match the signed candidate; the existing approved helper maintains
itself and reports healthy/idle without setup errors. The operator's disabled
locked-use choice is preserved. Final state is unlocked with no covered session;
the isolated candidate is stopped and the claim released.

This local test build retains version 0.6.0 with explicit candidate metadata;
it is not a new public release and has not been newly notarized. No live
lock/unlock operation occurs during installation. Exact signing selection,
digests, installation evidence and rollback files remain private.

### Authorized physical completion test

**Current:** after the user enables the setting and all ordinary scopes, the
test waits for normal manual lock. Its initial waiting attempt expires without
performing unlock and releases its claim. After the user confirms lock, a fresh
doctor and claim precede the bounded 120-second owner connection. The native
probe independently observes the locked origin and subsequent unlocked console,
while resident status reports one covered display and active control.

An exact owned AppKit fixture and private file oracle prove AX button press,
pointer click and keyboard effects beneath coverage. Filtered native display
capture has `coversExcluded=true`, produces PNG bytes through the common artifact
interface, and visual inspection shows the independent counter/text results.
The exact session is explicitly ended. Independent native readback verifies
relock; status verifies zero remaining covers/session, clean `completed`
termination, no manual-unlock pause and the original unchanged approval.

All 16 checks pass. The owner exits, fixture stops, resident source artifact is
removed and the exclusive host claim is released. Final OS state is locked.
Physical cover appearance is not independently observed; no hardware takeover
or fault injection occurs. Personal capture and exact private identifiers remain
outside Git. This is one bounded physical completion cell for the local signed
patch, not a public-release or wider protected-session qualification.

**Open:** successive tasks, expiry, takeover and multiple-display acceptance
require separate explicitly authorized tests of the signed candidate. The
passing completion cell supports the source diagnosis without establishing
that all protected-provider failures have the same cause. Covered startup
still contains the synchronous guardian readiness
wait documented by Tactical 109; this bounded repair does not recertify that
broader lifecycle or the privileged helper.
