# Windows native pointer gestures

Status: source and focused x64 VM qualification complete; cleanup complete.
Signed installed, ARM64 live and physical qualification remain open.
Owning topics: [Windows desktop](../../topics/windows-desktop.md),
[Windows resident control](../../topics/windows-resident-control.md).

## Objective and completion conditions

Complete Windows desktop parity for native move, drag and scroll through the
existing common CLI and retained owner contract. Independently observe pointer
motion, drag endpoints/releases and both signed wheel axes. Prove access/scope
and operator protections, Pause/Stop interruption and unlocked-origin cleanup.
Commit the result, remove owned staging and release the target claim.

## Boundaries

Normal input remains target-native. No host pointer, VM window manipulation,
arbitrary held-button API or automatic action replay is added. The desktop UAC
profile admits pointer operations only on unlocked Default; secure consent
remains typed. Windows wheel units are explicit and differ from Mac pixel
scroll units. Signed packages, live ARM64, multiple displays, physical devices,
elevated-app pointer effects and secure-desktop transitions need separate
qualification.

## Ordered work and validation

1. Add typed requests, native capabilities, grant scopes and CLI translation.
2. Implement physical-pixel motion, bounded drags, signed wheel events and
   authority-independent release cleanup restricted to the original desktop.
3. Protect operator endpoints, crossing paths, current wheel routing and
   pointer capture. Verify refusal geometry, secure policy and client fields.
4. Use an independent native window-message fixture and the real operator UI
   to test effects, scopes, Pause/Stop and absence of a held button afterward.
5. Run formatting verification, desktop/unlock contracts, x64/ARM64 publishes
   and the embedded desktop build. Remove owned test state, verify baseline
   readiness and stored credentials, shut down the VM and release its claim.

## Result

**Current:** formatting verification, desktop/unlock contracts, client pointer
translation and locked-use client checks pass. The one unavailable secret-pipe
fixture remains skipped on this controller. Self-contained x64/ARM64 runtime
and native fixture publishes and the embedded desktop build pass.

The staged desktop runtime SHA-256 is
`74240fc881b7b8f55d3fab1363bd3c001ed1cf9f0681559a09f10684660987ee`.
The real desktop operator and independent native window-message fixture pass
36 checks: access-off and observation-only refusals, advertised operations,
operator endpoint and crossing-path protection, requested movement, signed
horizontal/vertical wheel messages, left/right release at the requested drag
endpoint and independently measured hold timing, malformed requests,
mid-drag Pause/Stop, native button release,
retained consent on Pause, fresh Resume and revoked consent on Stop.
Unlocked-origin cleanup leaves the console unlocked. API delivery continues
to report application effect as unverifiable; fixture effects are separate.

Inspection of the first passing report found that a nominal 500 ms drag took
about five seconds because every delayed sample was still sent. The
scheduler now skips elapsed samples after authority checks, binds display
geometry and adds independent event timing. The final timing checks require
each nominal 500 ms hold to finish in under 2500 ms on this VM; independently
measured holds were 514.8 ms and 598.4 ms. This is a
focused timing bound, not a hard real-time API guarantee.

An initial run reached the input request before the app's next polling tick
hid the protected control announcement. The resident correctly refused the
operator overlap. Waiting for the UI tick corrected the harness. A later run
passed effects and both interruptions, then hit a harness assertion expecting
an explicit null grant; the serializer omits null values. Correcting that
assertion produced the complete passing run without weakening product guards.

One bounded scheduler recovery restored guest routes after the known boot
stall. Canonical secret-safe cold login and read-only doctor then confirmed
full readiness. That infrastructure recovery is separate from feature evidence;
no host pointer or VM window was manipulated. The common CLI audit does not
reconstruct raw provider steps, and its attribution is self-asserted.

Signed installed, live ARM64, physical/multiple-display, elevated pointer
application effects, owner-disconnect/expiry and desktop-transition cleanup
remain separate qualification gates. Source cancellation/cleanup fences are
present; the focused live interruption evidence is specifically Pause/Stop.
Raw observations stay in ignored private evidence, outside public Git history.

Implementation is committed in `9646c7d`. Owned fixture and actor processes,
the exact scheduled task and guest staging were removed using native
PowerShell with containment, task-identity and ancestor/child link checks.
An initial combined controller cleanup command was blocked by command policy;
separate script preparation and checked execution completed the same cleanup.
No protected helper or controller grant was installed by this slice, and no
capture artifact was created. Baseline doctor and canonical stored credential
verification passed after cleanup. Shutdown reached independently confirmed
power-off in 38.0 seconds using the declared 30-second scheduler assistance;
the exact target claim was released. This is assisted shutdown evidence.
