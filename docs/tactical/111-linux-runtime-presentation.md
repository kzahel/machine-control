# 111 — Linux runtime and presentation

Status: implementation and bounded x64 candidate qualification complete;
ARM64 and production release qualification remain open.
Owning topic: [runtime and presentation](../../topics/runtime-and-presentation.md).
Parent: [107](107-runtime-and-presentation.md).
Handoff: [110](110-windows-runtime-presentation.md).

## Objective and completion conditions

Reuse the Python/AT-SPI resident and its ordinary-user authorization. Bound
background provider and companion work; keep Stop and recovery independent.
Support Personal, Minimal and Appliance, disposable Settings, native approvals
and safety notices, atomic preferences, local configuration and launch overrides
that expire on Restart. Prove native effects, cancellation, faults and restart
on the supported Ubuntu/GNOME Wayland profile.

## Boundaries

No publication or installed-app replacement. Presentation grants no authority
and never selects the root virtual-HID appliance route. Use isolated candidates
and claimed dedicated targets, target-native control and separately identified
browsers. Keep raw evidence, signing material and infrastructure private. Restore
installation, policy and initial power; release claims in cleanup.

## Ordered work

### 1 — bound resident work and retain native safety

Use one physical provider slot with deadlines and cancellation fences. Retain
capacity for late work, reject stale completion, preserve uncertain dispatched
effects and move session/portal waits away from GLib. Keep native approval and
safety processes separate from provider work.

### 2 — integrate profiles and operator recovery

Add owner-only atomic preferences and a separate bounded local configuration
socket. Make Settings lazy, isolate candidate instances, expire temporary
profiles on Restart and keep native Stop independent of companion IPC.

### 3 — qualify exact candidates and document limits

Run fault, configuration, frontend, Rust, client and Linux appliance checks.
Exercise every profile, independent GTK/portal/browser effects, ownership loss,
Pause/Stop, generation refusal, lifecycle exclusion and restart. Distinguish
source, build, signature authentication, native execution and installed
acceptance; record architecture gaps honestly.

## Validation and final result

### Implementation

The ordinary-user companion retains the existing AT-SPI, compositor portal,
native approval, audit, grants and provider boundary. One persistent physical
provider slot admits work; a 20-second logical deadline never frees a still
running native call. Generation, expiry and cancellation fences prevent late
preflight from dispatching under replacement authority. Already dispatched
effects stay uncertain and unsafe to retry. Paired portal input release remains
permitted during cancellation and retains the actual route in the result.

The coordinator has a private GLib context; the persistent AT-SPI worker owns
initialization, native calls and process-default context pumping. GNOME session
observation and portal request setup use asynchronous D-Bus; media setup and
teardown use a separate retained worker. Native GTK safety and approval are
separate processes. Safety acknowledgement gates access; loss revokes it.
Approval reads have frame/deadline bounds and one physical child slot through
termination and kernel reaping. The [Linux report](../../research/platforms/linux.md#resident-responsiveness-and-presentation)
owns upstream context-affinity findings and their diagnostic limits.

Tauri companion waits, lifecycle and stdout reads run off its event thread.
Bounded permits, nonblocking stdin and a one-frame reader prevent unlimited
admission. Protocol loss/timeout reaps the owned companion. Native Stop uses
the separate same-user recovery socket rather than the companion mutex or
public agent slots. Browser writes have a bounded writer and generation fences.

Personal opens Settings; Minimal retains its idle tray; Appliance hides that
idle tray. Pending or active access preserves native approvals, safety and
tray recovery. Closing Settings destroys its WebView. Same-instance Settings
launches recover it without replacing the resident. Versioned owner-only
preferences use atomic replacement and a held resident lock; the CLI refuses
offline replay after uncertain delivery. Temporary launch overrides expire on
Restart. A pidfd-based restart helper waits for kernel process exit, including
an unreaped predecessor, before executing the exact candidate. Companion loss
can be recovered through retained GUI Settings and Restart.

Coherent source stages:

- `0b0d40c`: retained work capacity, fences, native safety and local preferences.
- `82c98d8`: profiles, disposable Settings, bounded companion and CLI recovery.
- `1fcac60`: restart handoff tied to kernel exit rather than PID existence.
- `43e618d`: one AT-SPI thread/default context and a private coordinator.
- `2b27ac1`: actual cancellation routes and expanded native recovery fixtures.
- `4f91ab8`: bounded approval lifetime, physical child capacity and real faults.
- `35ee5ec`: Settings Restart stays available after companion observation loss.

### Candidate identity and authentication

Native qualification exposed and fixed two product failures: PID-existence
restart waiting hung on an unreaped predecessor, and a fresh Settings WebView
hid Restart after companion loss because it had no platform observation.
Real regression fixtures cover both. Native actors also required fresh
AT-SPI portal windows and tolerance for departed tray registrations; failed
reports remain private rather than being discarded.

The exact implementation source is
`35ee5ecbd9471710a14cfd7eb46ffdd05b5b2882`. The x64 native debug Debian
candidate contains the complete GUI, hashed Python runtime and bundled CLI.
Its SHA-256 is
`b52fc0f305d0c9d32cb527ec0e2cb26d2d83c825be5001bb7e65752cff68f826`.
Transfer independently preserves that hash. A disposable local development
key authenticates the detached Tauri/minisign signature; changed bytes refuse.
The production updater public key is unchanged and deliberately does not match
this development signer. This proves development artifact authentication,
not publisher identity, installed package-manager acceptance, release-mode
packaging, AppImage replacement or production updater acceptance.

The package was extracted into private staging on a claimed accepted target.
It was never installed. Native execution uses the packaged runtime and app;
fault injection uses a test-only Provider subclass of those same runtime bytes.
No root input fallback or outer VM input was used by the ordinary candidate.

### Validation

Portable `bin/check`, frontend build, Linux desktop Python unit tests,
native grant checks, Rust tests, formatting and Clippy pass. Real Rust child
faults prove five-second protocol timeout/reaping and restart with an unreaped
predecessor. Python child fixtures prove silent, partial-frame and stopped,
TERM-ignoring approval cancellation. The existing appliance smoke passes
separately through resolved private inventory and the parent claim.

The supported target is Ubuntu 24.04/GNOME 46 Wayland, x64. Native candidate
qualification uses independent fixture files and HTTP effects as the oracle;
API success alone is insufficient.

| Exact candidate campaign | Result |
| --- | --- |
| Native companion, portal capture/input/Unicode and cancellation | 57 checks |
| All three GUI profiles, native safety, disposable Settings and restart | 92 checks |
| Chrome for Testing native messaging, browser effects and replacement | 29 checks |
| Injected native provider/session-owner/safety faults | 30 checks |
| Local bundled CLI and outside common CLI generation/effect parity | 6 checks |

The profile campaign proves native approvals and semantic effects with Settings
absent, idle/active tray behavior, Pause/Resume/stale-reference refusal, native
Stop, persistent settings, override expiry, Restart Off and companion-loss
repair. Holding all 16 public handshakes does not occupy the separate recovery
socket; profile mutation plus Settings recovery retains the resident PID and
passes a four-second end-to-end bound.

Fault injection proves 30 discovery replies progress while native observation
stalls (three-second batch bound), independent Stop below one second, retained
physical capacity through the 20-second deadline, and stale completion refusal
after replacement authority. Pause/Resume during preflight causes no fixture
effect; Stop after dispatch reports uncertainty and the oracle records exactly
one effect. Caller disconnect retains capacity, lifecycle exclusion refuses
arming, safety-process loss revokes access and refuses new arming, and inherited
owner EOF removes both sockets. Real portal drag cancellation independently
confirms button release while preserving unknown delivery and actual route.

The browser campaign uses separately identified Chrome for Testing and isolated
registration/data. It proves native messaging, AX observation, HTTP-observed
click and Unicode effects, capture hashes, separate script scope, stale
references, Stop and owned runtime replacement with the browser alive. It does
not exercise the user's primary browser or install an extension there. Local
and outside common CLI calls share one generation and the fixture records one
effect from each route; the local test claim is released by its runner.

GTK/WebKit/GStreamer diagnostics and AT-SPI cache warnings were observed in
private logs. Passing effect oracles do not prove warning-free native libraries
or accelerated GPU presentation. The concluding commit changes documentation,
JSX formatting and native-runner readiness/foreground fixtures only; the candidate identity above
remains the exact implementation artifact qualified here.

### Cleanup and handoff

All five final reports are retained and independently checked in ignored
private evidence. No owned candidate, test-browser or fixture processes remain;
both candidate sockets are absent. Browser registration/data are restored by
the runner. The temporary browser sandbox helper is disarmed and owned target
staging is removed. The disposable development private key and key-generation
log are removed; the public key, detached signature and exact package remain
available privately for authentication.

The installed-app presence is unchanged and the original appliance resident
passes its read-only doctor. Canonical password-file readiness and a pinned
SSH guest hash comparison pass without exposing or rotating the credential.
Missing private verifier SSH locators were restored in ignored controller
configuration using the existing retained key and pin. This changes no guest
password, SSH policy, desktop privilege or public inventory.

Initial power was off; shutdown restores it and the exclusive target-use claim
is promptly released. No application publication, installation, updater
replacement, protected-helper change or policy weakening occurred.

### Limits

**Open:** ARM64 build and execution of these changes: the available native host
has x64 GTK/WebKit, and no ARM64 GNU toolchain/sysroot or runnable ARM64 target.
Previous ARM64 desktop acceptance does not qualify these bytes. Production
publisher signing, release-mode/installer/AppImage/updater acceptance and
installed replacement are separate gates. No public release is requested.

**Open:** Other compositors/X11, physical hardware, multiple monitors/scaling,
suspend/resume, longer load/soak and fresh lock/login/protected-control
qualification. The ordinary profile still requires the supported unlocked
GNOME Wayland session and visible compositor consent. Arbitrary top-level
activation remains explicitly unsupported. No policy or privilege expansion
is inferred from a quiet presentation mode.

These trials bound admission, event-loop progress, logical cancellation,
protocol waits and child recovery. A stuck native provider retains its physical
slot; a kernel-uninterruptible child can delay reaping. They do not establish
hard latency for every filesystem, native library, kernel or lifecycle path.
Same-user recovery is operator convenience, not containment from a shell with
that OS identity. Raw captures, failures, reports, signing material and concrete
target identity remain private and ignored.
