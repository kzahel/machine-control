# Machine Control Project Guide

This is the unified public repository for cross-platform machine-control
architecture, research, implementation, fixtures, and conformance. The
Windows resident runtime under `src/` is the first implementation vertical
slice; the documentation describes the cross-platform destination and governs
that code. Do not split reusable runtime code into a sibling repository merely
because the project began as documentation.

## North Star (highest priority)

The project's North Star is powerful **target-native control** across desktop,
mobile, headset, and other device classes. macOS, Windows, Linux, and ChromeOS
virtual or physical targets should be able to control their own running OS
from inside that OS: administration, semantic UI, screen capture, keyboard and
pointer input, application/session management, and an explicitly authorized
path for protected desktop operations.

For a platform such as stock iOS that cannot host a general agent or complete
resident service, use the richest platform-native runner on the device and an
authorized controller-host provider. XCTest/CoreDevice on iOS and ADB plus
UIAutomator/accessibility on Android are first-class implementations of the
same target-selection and control experience, not afterthoughts. Do not build
a replacement for a mature platform facility merely to make every provider's
process placement identical.

The same agent-facing control experience must work from either placement:

- an agent on the target calls the resident controller locally; and
- an agent elsewhere reaches that same resident controller through an
  authenticated tunnel or transport; or, for a constrained attached device,
  reaches its native runner through the authoritative device-host provider.

Local versus remote use should differ mainly by target selection and command
transport. It should not require a different UI vocabulary, different skills,
or host-side manipulation of a VM window. Remote use of a target-resident
provider is still an inner route; it is not outer VM/KVM control.

Hypervisor consoles, host input, hardware KVM, and similar outer routes exist
for unattended installation, initial bootstrap, independent diagnosis, and
recovery. They are not the ordinary application-testing path. After the
resident controller is healthy, a VM window should not need to be visible,
focused, or manipulated on the controller user's desktop.

The project should own a stable ergonomic contract even when implementations
use Cua, WinApp/UIA, AX, AT-SPI, Computer Use, Chrome accessibility/CDP,
XCTest, ADB/UIAutomator, or another provider.
Proprietary agent-coupled tools may be excellent optional routes and quality
benchmarks, but they are not the only foundation for the target-native
interface.

The provisional implementation architecture is an owned facade,
resident-session boundary, provider adapter interface, and conformance corpus
over replaceable upstream and native providers. Begin with the functional
hybrid: pinned Cua for common-runtime behavior and deep platform adapters such
as WinApp/Win32 for measured gaps. Route per operation and report the actual
provider, fidelity, delivery, and independently observed effect. Do not fork
Cua or start an all-platform rewrite for neatness alone; require repeated
evidence that wrapping or upstreaming cannot meet the needed reliability,
fidelity, packaging, security, or maintenance boundary. Provider agreement is
differential evidence, not a correctness oracle; deterministic fixture and OS
effects are the oracle.

Treat the existing ChromeOS testbed as the closest current reference for the
desired desktop architecture. An agent outside the Chromebook reaches it over
SSH, while administration, `chrome.automation` desktop semantics, per-page
CDP, DRM/EGL capture, and evdev/uinput actions all execute on the target. This
is remote ergonomic access to target-native control, not external pixel/HID
control. Preserve that shape when designing the common facade and the Windows,
macOS, and Linux implementations.

An outside agent must remain capable of rich ordinary control without first
spawning another agent on the target. In-target YA workers are an optional
placement for work that benefits from local filesystem/build/debug context or
from agent-coupled capabilities such as Computer Use. Treat placement as an
optimization or additional capability, not as a prerequisite for driving the
machine.

Focus the first complete vertical slice on Windows: build a clean, reproducible
Windows test appliance; bring its resident control stack up without routine
manual console work; exercise the same interface locally and remotely; and let
an agent provision, validate, shut down, and seal or snapshot the resulting
image. Do not spread implementation effort across all platforms until that
slice proves the contract. Cross-platform design work should directly support
or be validated by this slice. Windows-first is sequencing, not a narrowing of
the destination: preserve and reuse the already strong ChromeOS and iOS
testbeds, treat ChromeOS as its own platform rather than generic Linux, and use
Android's established ADB foundation instead of starting over.

Treat this North Star as the highest-priority decision when other documents,
older spikes, or implementation conveniences pull in a different direction.

Start with the North Star in `README.md`. Use `research/README.md` as the entry
point for provider/platform options and evidence, then read `GLOSSARY.md`,
`topics/README.md`, and `topics/inner-first-routing.md`. Read `SYSTEM-MAP.md`
before changing ownership boundaries among YepAnywhere, dotfiles, a testbed, a
guest-resident provider, or an outer provider.

Preserve these rules:

- YepAnywhere owns agent-session coordination and cross-host delegation.
- Dotfiles owns private concrete testbed inventory, discovery, and availability
  declarations only.
- Until a platform completes an explicit repository-consolidation cutover, its
  existing `*-testbed` repository remains authoritative for lifecycle,
  transport, bootstrap, recovery, and safe operating policy. After cutover,
  the platform directory here owns that public implementation; an external
  repository is legacy or a generated one-way distribution.
- Agent placement and control-target selection are independent. An authorized
  outside agent must have the full ordinary resident or device-native control
  surface. Spawn a worker on the target when substantial local development or
  an in-target-only capability makes that placement useful.
- Guest-local administration and semantic desktop control are the normal
  routes. Guest-local capture and input are the ordinary fallbacks.
  Host/hypervisor/KVM input is for initial bootstrap and recovery.
- A worker agent must not silently fall back to an outer route. If an outer
  route could interrupt the controller user's desktop, it should normally be
  absent from the worker's tools and require an explicit recovery request.
- Dedicated test appliances may explicitly authorize a stronger resident
  service or protected provider than a personal workstation, including full
  target-native semantics, capture, keyboard, and pointer control across
  elevated, UAC, lock/login, and session transitions. Describe that privilege
  honestly; keep its API and arming typed rather than weakening its control or
  exposing arbitrary SYSTEM command execution. Do not weaken the
  target-resident goal merely because a normal user process cannot cross a
  session, integrity, or secure-desktop boundary.
- Treat local IPC, SSH, tunnels, CLI/SDK calls, and MCP as transports or facades
  over the contract, not as the contract or its security boundary. A public
  target name or agent session ID is not private bearer authority.
- Do not claim same-user containment when the agent also has a shell. Stronger
  separation requires a different OS identity, sandbox, isolated appliance, or
  authorization component outside the agent's authority.
- ChromeOS, iOS, Android, Quest, and other physical devices are in scope for the
  North Star. Preserve their existing authoritative testbeds and native routes;
  do not make desktop VM architecture a prerequisite for device support.
- Unify the desktop experience across macOS, Windows, Linux, and ChromeOS as far
  as capabilities permit. Give mobile/device providers the same inventory,
  authorization, target selection, capability, and result vocabulary without
  forcing iOS and Android into a misleading desktop-control abstraction.
- A successful input API call is not proof of an application effect. Keep
  delivery, observed effect, and uncertainty separate.
- Capability descriptions must report real route, fidelity, omissions,
  privilege, session requirements, and host-interference risk.
- Do not collapse a YA peer, an agent execution host, a system under test, a
  testbed provider, or a delegation handle into one identity.

## Implementation workflow

The Windows runtime owns the reusable target-resident facade, provider adapter
boundary, normalized contract, protected session broker, and conformance
fixtures. Preserve these rules:

- Expose typed desktop/session capabilities, not arbitrary SYSTEM shell,
  filesystem, registry, or provider dispatch.
- A dedicated-test-appliance profile may arm full protected-desktop semantics,
  capture, keyboard, pointer, and credential-provider control. Do not weaken
  UAC, secure desktop, Windows Hello, password, or lockout policy.
- Keep secrets out of ordinary JSON, arguments, environment variables, logs,
  captures, evidence, and Git. A credential operation must use its dedicated
  one-shot secret transport and refuse before reading the secret if provider or
  field discovery is uncertain.
- Bind observations and actions to runtime, session, desktop, and provider
  generations. Reject stale references rather than retargeting them.
- Keep request acceptance, delivery, effect, evidence, and uncertainty
  separate. Report the actual provider route, capture fidelity, coordinate
  space, privilege, and foreground/cursor consequences.
- RustDesk is an AGPL-3.0 architecture reference, not a code donor.

Use `dotnet format --verify-no-changes`, the contract tests, and appropriate
Windows ARM64/x64 publishes before committing runtime changes.

## Documentation workflow

Use a research/topic/tactical convention:

- Root architecture and reference documents own durable system shape,
  vocabulary, ownership boundaries, and the North Star.
- The two-axis corpus under `research/` owns provider dossiers and platform
  reports. Provider dossiers record cross-platform architecture, declared
  license scope, claimed reach, implementation depth, evidence, gaps, and fit.
  Platform reports compare all plausible routes for one OS or device family
  and record how deeply each has actually been investigated.
- Focused, living topic documents under `topics/` own current truth, decisions,
  gaps, and direction derived from the research corpus.
- Numbered tactical documents under `docs/tactical/` own bounded implementation
  slices and execution records.
- Disposable third-party experiments and exact upstream source pins remain in
  `machine-control-spike`; adopted reusable runtime code and its conformance
  suites live here. Target lifecycle/bootstrap/recovery evidence stays with its
  authoritative platform/testbed implementation: in the external repository
  before consolidation cutover and in the platform directory here afterward.

Provider-first and platform-first research are complementary. A provider may
be the best common architectural spine without being the deepest route on
every platform; a platform-specific provider may sit behind the common
contract. Do not force one library everywhere, and do not discard useful
cross-platform architecture merely because one OS has a deeper specialist.

Use the evidence levels defined in `research/README.md` and attach them to a
specific provider, platform, capability, and route. Keep upstream claims,
source review, builds, live tests, conformance evidence, and adoption distinct.
Record the repository's declared top-level license and any relevant narrower
terms in every provider dossier, while keeping third-party revision audits in
the spike and target-specific lifecycle audits in the owning platform/testbed
source.

Before working on a continuing concern, read its topic and relevant provider
dossier/platform report. Update the corpus when work changes a provider fact,
license, comparison, evidence level, or investigation gap. Update the topic
when that evidence changes current status, contract, decision, or next
direction. Keep topics as current truth rather than append-only diaries; Git
and commit bodies retain the history. Create a sibling topic when two concerns
can evolve independently, and do not create a topic for every small standalone
change.

New topics should normally include a `Topic: <slug>` line and honest status.
Implementation tacticals use zero-padded filenames such as `000-topic.md` and
`001-next-topic.md`. Each tactical names its owning topics, objective,
completion conditions, boundaries, ordered work, validation, and final result.
Name steps for the product surface or work they cover, for example
`### 3 — prove remote direct control`; do not invent opaque letter-and-number
lane codes.

Completed tacticals remain execution records. Continuing guidance comes from
the current topic and architecture documents. Add every tactical to
`docs/tactical/README.md` and every topic to `topics/README.md`.

Avoid duplicate truth: a provider dossier owns provider-wide facts, a platform
report owns platform comparison, a topic owns the resulting decision, and a
tactical owns execution. Summaries should link downward rather than copying
evidence details into every layer.

Label claims as one of:

- **Current**: observed in the checked-in testbeds or research spike.
- **Decision**: the present architectural direction.
- **Proposal**: a candidate contract or implementation approach.
- **Open**: a question that still needs evidence or a product decision.

When a decision changes, update the affected topic and `README.md` when the
North Star or repository-level synthesis also changes. When a new program or
repository enters the system, update `SYSTEM-MAP.md`. Keep exact experiment
evidence and third-party source pins in `machine-control-spike`; link to those
findings rather than copying detailed audit logs here.

## Public repository safety

Treat this repository and its complete Git history as public. Portable
architecture, contracts, schemas, generic examples, conformance expectations,
and reusable implementation plans belong here. Private infrastructure and
deployment state do not.

Never commit:

- real machine, VM, host, device, Wi-Fi, network, relay, account, or friendly
  names that identify the controller user's infrastructure;
- IP or MAC addresses, DNS names, ports tied to a private deployment, usernames,
  home-directory paths, peer IDs, device serials/UDIDs, VM IDs, or cloud resource
  identifiers;
- credentials, passwords, API keys, tokens, private keys, certificates,
  pairing material, signing identities, recovery codes, or authorization
  grants and leases;
- private network topology, access routes, firewall rules, remote-management
  endpoints, or enough combined detail to reconstruct them;
- personal screenshots, recordings, logs, clipboard contents, support bundles,
  crash artifacts, or golden-image identifiers; or
- machine-specific configuration, even when it appears harmless or temporary.

Use generic placeholders and logical examples instead. Labels such as `winvm`
or `ios` are acceptable only as non-authoritative examples that reveal no real
endpoint or access path. Store actual inventory and deployment configuration in
ignored local files or a deliberately private infrastructure store owned by the
relevant testbed. Before committing captured evidence, redact and minimize it;
when uncertain, keep it out of this repository. Deleting a secret in a later
commit does not remove it from Git history.

## Commit message guidance

Aim for a <=65 character subject and strictly enforce a 72-column line wrap for
the body. Prefer bullets when items are numerous or complex and prose when the
content is short and simple.

For non-trivial commits, include a concise excerpt or synthesis of the
originating instruction—or the motivating observation when the change was not
user-prompted. Summarize the request and key direction well enough that a future
maintainer could re-derive something close to the intended result. Prune
digressions, secrets, and low-signal chat detail rather than reproducing the
conversation verbatim.

Keep the subject as the scannable result for `git log --oneline`; put the
motivation synthesis in the body. A one-line message is sufficient for a small,
mechanical, self-evident change.

When a commit belongs to a related series, append one or more exact
`Topic: <string>` trailers. Later commits copy the topic string verbatim so
`git log --grep "Topic: ..."` finds the chain. Use multiple trailers when one
commit spans multiple topics. Standalone commits with no expected follow-up do
not need a trailer.

Register each new series string in root [`topics.md`](topics.md) when its first
commit is created, and scan that registry before choosing a new one. When a
series implements a documented topic, normally reuse the topic filename's slug.
