# Connect the shared core to a real browser provider

Owning topics: [shared resident core](../../topics/shared-resident-core.md),
[browser profiles](../../topics/browser-profiles.md).

Status: **bounded Mac real-browser slice complete; native adoption pending**.

## Objective and completion conditions

The user requested proceeding with Tactical 150's next step: a real extension
and native-messaging adapter consuming the same TypeScript policy core. Prove
independent browser effects with two isolated profiles, Stop, a held late reply
and transport loss/reconnect. Keep the lightweight deterministic suite.

Complete when real tab/snapshot/click requests flow through the core and
unmodified extension, independent HTTP counters establish profile-specific
effects, authority changes reach both workers, stale replies/references cannot
retarget work, and owned browser/native-host processes and temporary profiles
are cleaned up. Record exact evidence and its limits, then commit the slice.

## Boundaries

Use the project's pinned Playwright package and its separately identified
Chrome for Testing executable. No primary installed browser, real sign-ins,
installed resident, registry/native-host registration outside scratch profiles,
VM provisioning, protected control, release or store publication.

The first real-browser fixture uses two independent persistent profiles in
two test-browser processes. It does not claim same-process Chrome multi-profile
or installed package acceptance. Private fixture sockets and configuration
assign profile identity; this does not implement durable extension naming,
production native peer authentication or same-user shell containment. Approval
remains an in-process fixture operator action, never an exposed wire method.

## Ordered work

### 1 — prove the browser-native transport in isolation

Use a fresh packaged unpacked extension, scratch native-host manifest and
headless full Chrome for Testing. Observe the worker's actual native hello,
then close/reap the browser and relay. Use no virtual display unless the exact
route requires one.

### 2 — implement typed observations and the extension adapter

Extend the existing core's typed browser boundary with tabs and snapshots;
preserve clicks, exact handles, deadlines and uncertainty. Add a bounded
adapter over the existing extension protocol, with unique per-connection wire
correlation, grant projection, cancellation and conservative malformed-reply
handling. Keep routing/approval in the core and transport/serialization outside.

### 3 — exercise two profiles and failures

Run the core with two real extension workers, owned fixture pages and HTTP
effect counters. Verify unapproved discovery/actions refuse, approval does not
expand, selected profile effects stay isolated, Stop fences queued/dispatched
work and revokes worker authority, and late responses cannot complete newer
requests. End an owned native-host transport, observe genuine reconnect and fresh
generation, then prove old references refuse and the other profile still works.
Use test-host response gates to order late delivery without modifying the
extension or pretending a timeout undoes a page effect.

### 4 — validate, record and commit

Run strict checking, existing/new deterministic contracts, real-browser
acceptance and portable checks. Wire the browser runner into a separate Linux
CI job with the pinned full test browser. Keep raw evidence private; commit
only portable source and sanitized findings. Preserve unrelated existing work.

## Validation and final result

The initial probe and composed acceptance pass on the development Mac ARM64
with the pinned Playwright 1.64.1, its full Chrome for Testing 156.0.8078.4 and
the unchanged unpacked extension 0.8.4. The worker is staged through the clean
unpacked packager and its bytes are checked against source. No framebuffer,
desktop VM, installed native resident or real browser profile is used.

The core now admits typed tabs/snapshots alongside clicks; observation requests
cannot bypass approval. The adapter projects core authority to existing worker
grant messages, bounds/normalizes responses, uses connection-local wire IDs and
preserves dispatch-time budgets and truthful unknown delivery. Node framing is
separate from the portable core; the fixture host has private profile endpoints
and in-process operator approval, with no public grant method.

Eight composed checks pass in approximately 3.1 seconds. Independent HTTP
counters observe four Work and three Personal trusted-click effects. Work-only
approval refuses Personal discovery without forwarding; both profiles remain
connected and cross-profile references refuse. Stop reaches both real extension
panels and clears controlled tabs while a withheld dispatched click reports
unknown delivery/effect. Its late response cannot complete a fresh Personal
request carrying the same public label. Native relay transport loss ends the
pending Work request with uncertainty and causes real worker/native-host
reconnection; old references refuse, Personal remains usable and fresh Work
effects pass. All held replies settle, core retained work reaches zero, both
browser contexts close, all observed native relay processes exit and scratch
profiles/manifests are removed.

The deterministic suite grows to 24 passing tests with strict portable and
Node-adapter TypeScript checks. A separate Linux CI job installs the full pinned
test browser and runs the composed fixture; no Linux live or remote CI result
is inferred from this Mac run. Windows fixture registration is intentionally
unsupported rather than writing to the user's registry.

The two profiles run in separate processes, with fixture-assigned identities
and operator authority. Chromium's sandbox is explicitly disabled for the
empty test profiles. This does not qualify same-process Chrome profiles,
production native peer authentication, saved consent, signed packaging,
installed integration, production-browser sandboxing or store delivery.
The installed singleton runtimes and the real extension are unchanged.

Both reference and extension providers use the same host dispatch helper for
the fresh core check, remaining budget and synchronous submission ordering.
Strict checking and all 24 deterministic tests pass under Node 24.22.2 and
26.7.0; composed real-browser acceptance passes on both Node hosts, with all
observed relay processes reaped. The temporary official Node 24 executable is
verified against its published archive checksum and removed after execution.
The full repository portable suite passes in 242 seconds. Frozen dependency,
whitespace, runtime JSON and local documentation-link checks pass.

Next remove fixture-assigned identity with persistent extension installation
IDs and a same-process, single-registration profile fixture before production
native integration and packaging. No public multi-profile release is claimed.
