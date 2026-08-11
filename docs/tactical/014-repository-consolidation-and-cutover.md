# Tactical 014: Repository Consolidation and Cutover

Status: complete.

Topic: `repository-consolidation-and-publication`.

## Objective

Make `machine-control` the single canonical public source for the existing
Windows, macOS, Linux, ChromeOS, iOS, Quest, and Steam Deck testbed/control
implementations while retaining dotfiles as the private concrete inventory.
Preserve useful public Git history, switch agents and local inventory to the
new paths, and leave each external repository as an explicit legacy source
that may later become a generated focused distribution.

## Completion conditions

- The seven public testbed histories are reviewed proportionately and imported
  below stable `platforms/<platform>/` prefixes, with original and rewritten
  tips recorded.
- The imported commands run from the monorepo and the common client resolves
  its portable defaults there.
- Dotfiles continues to own concrete target/controller inventory but delegates
  public behavior to `machine-control` paths.
- Durable agent guidance starts with the common inventory/client rather than
  requiring agents to learn sibling repository ownership.
- Each imported platform passes its existing dependency-light smoke tests or a
  focused equivalent plus basic command/orchestration checks from its new
  location.
- The three accepted desktop adapters pass common unit tests and minimized
  status/doctor orchestration; repeating the full historical control corpus is
  not required.
- Each external repository is marked legacy only after its monorepo path is
  validated and selected by the private inventory.
- No concrete inventory, credentials, private paths, endpoints, identifiers,
  or captures enter `machine-control` history.
- The root architecture, system map, topics, and this tactical describe the
  resulting ownership and any deviations.

## Boundaries

- Do not implement generated `*-testbed` publication yet. Preserve the option
  and the external forge repositories for later focused exports.
- Do not import dotfiles history or concrete inventory. Only its adapter paths
  and handoff documentation change.
- Do not import `hardware-kvm-testbed`. It is a nonfunctional private spike;
  record sanitized incorporation as future work.
- Do not redesign platform semantics or refactor every imported tree during
  history import.
- Do not repeat exhaustive semantic, capture, input, protected-session, image
  factory, or physical-device acceptance already recorded by the platform
  repositories. Use smoke checks sufficient to detect path, import,
  dispatch, packaging, and basic functionality regressions.
- Do not start, resume, modify, or recover an inactive target merely to prove
  repository placement. Prefer read-only status and available-target doctors.

## Implementation steps

### 1 — establish the consolidation policy

Add the living repository-consolidation topic, reconcile root ownership
language, register the commit topic, and retain the existing external-source
authority until each atomic cutover.

### 2 — prepare repeatable history imports

For each public source, verify visibility and licensing, freeze the remote tip,
run a lightweight complete-history safety and artifact review, and rewrite a
temporary clone below its destination prefix with `git filter-repo`. Merge the
rewritten history without squashing, record provenance, and make integration
changes in later commits.

Resolve ChromeOS licensing before treating its contents as the canonical MIT
implementation. If any public history contains questionable deployment or
third-party material, sanitize the rewrite or fall back to an audited snapshot
instead of importing it for aesthetic continuity.

### 3 — make the monorepo the executable front door

Update portable target defaults, command discovery, tests, and documentation
to resolve platform CLIs below `platforms/`. Define a stable private-inventory
overlay consumed by the public common client without exposing inventory values
in portable output.

### 4 — migrate the accepted desktop testbeds

Import and integrate Linux as the process rehearsal, followed by macOS and
Windows. Run each imported smoke suite from its new prefix, exercise the common
client tests, and perform minimized status/doctor checks against available
targets. Keep the existing Windows resident runtime and shared contracts in
their current root locations unless a separate refactor is justified.

### 5 — migrate ChromeOS and device testbeds

Import ChromeOS after resolving its license, then iOS, Quest, and Steam Deck.
Preserve their device-native and controller-host boundaries. Run their
dependency-light tests and read-only status/doctor checks only where the target
is already available and the check does not mutate it.

### 6 — switch private inventory and agent handoff

Update dotfiles registry command paths and documentation to treat
`machine-control` as the public source while retaining all concrete inventory
there. Update the canonical portable global agent guidance, deploy it through
the documented dotfiles process, and verify the deployed files.

### 7 — retire editable external authorities

After each platform's new path and inventory selection work, replace its
external README entry guidance with a prominent legacy notice linking the
canonical directory and source commit. Preserve original history and forge
metadata. Do not archive or generate repositories in this slice.

### 8 — validate and publish the resulting map

Run documentation and unit/smoke validation, confirm all affected worktrees
are clean after commits, update this tactical with exact import provenance and
validation results, and leave hardware KVM plus generated publications as
explicit future work.

## Validation plan

- `git diff --check` and repository status checks at every commit boundary.
- Complete-history secret/personal-infrastructure pattern scan plus license,
  non-text blob, symlink, submodule, and large-object inventory before import.
- Imported-tree equivalence check before integration changes.
- Existing lightweight test scripts from each imported repository when they
  are host-compatible.
- Root client/contract tests after changing target defaults.
- Read-only common inventory/status and selected doctor checks against already
  available targets; no exhaustive replay of accepted control corpora.
- Dotfiles testbed and agent-config tests, apply/check deployment, and a final
  scan that public diffs contain no concrete private inventory.

## Result

Completed 2026-08-11.

The seven public implementations are canonical below `platforms/`. Their
logical histories were rewritten below stable prefixes and merged without
squashing:

| Platform | Original tip | Rewritten tip | Import commit |
| --- | --- | --- | --- |
| Linux | `1e227ed591b46a19abf1595aa25aa3d05177b081` | `c71ea1e1b7ddf0b5df3049e100db6c69190b153b` | `90568f6` |
| macOS | `e7c95c3829f7d7451a2cc1fc7596a8319457ae24` | `f675546d1b3e3fff8b6462a34e6b66b99b7ea822` | `1e62709` |
| Windows | `9f86f0a1548c128d7c8adc821bf5c368bda04c74` | `64e3e7cce19c9824ef0082197ed3c3c4e8ec903b` | `b25ad56` |
| ChromeOS | `552a4f81e288e2c00fc9d7bf8d3b19af2343710b` | `94f39b491fc2934d20d9ae6151dfa95270c2ed11` | `30f0a83` |
| Steam Deck | `0a836ee60102c5b45d912131df5f624129a3c31c` | `910408737658d5e95a43e89e0010afd841204aaa` | `8e7ba40` |
| Quest | `13b04a3cefcb87a443fc8e8e7b72d8dccf2ebf02` | `bd0a65cac1e9b26c4a475f660585e9b6b3f8fe89` | `43401a3` |
| iOS | `18330d39b421c17f0822e2172ec1573b3c82cfcf` | `4c6d98b7d5b76d56d6679b73c3bd5848d3aee516` | `72377ce` |

The public client now resolves all seven platform commands in-repository. Its
three accepted desktop targets retain the common lifecycle/resident interface;
the four device targets expose honest `native` interfaces through the explicit
testbed escape. A private dotfiles provider supplies concrete selectors,
configuration paths, and environment internally while `targets` omits those
values. Durable agent guidance was deployed from the canonical dotfiles source.

Every former source repository has a committed legacy/read-only notice linking
its canonical platform directory. No generated distribution was added.

## Validation record

- Initial imports matched source path sets and blob identities. Before
  publication, a final identity scan found a Linux example username and an
  embedded ChromeOS controller public key; both were generalized throughout
  the unpushed migration range. ChromeOS also omitted the documented obsolete
  intent-test paths and deployment selector. The current legacy source tips
  were cleaned without rewriting their already-public histories.
- Complete local committed histories had no private-key/token signatures,
  suspicious credential/artifact paths, submodules, symlinks, or large blobs.
  Generic example and loopback matches were manually reviewed.
- The common client passed 15 dependency-free unit tests, including native
  target refusal, explicit escape routing, and private-environment omission.
- Windows passed focused shell/static doctor checks. macOS and Linux passed
  shell/Python checks and read-only status parity with their legacy paths.
- ChromeOS passed 16 unit tests; Steam Deck passed 11; Quest passed 12; and iOS
  passed its 17-test `pnpm check` corpus.
- Read-only orchestration reached the already available ChromeOS, Steam Deck,
  iOS, and macOS targets through the new paths. Unavailable or non-ready target
  details were kept local and did not trigger boot, login, repair, or recovery.
- Dotfiles passed eight inventory tests. The portable agent-config test,
  deployment apply, and post-deployment check passed.
- Public target listing reported all seven configured logical targets without
  commands, environment, concrete selectors, or private paths.

The user explicitly requested focused confidence rather than replaying every
accepted semantic, capture, input, protected-session, image-factory, or
physical-device corpus. Those existing acceptance records were not repeated.

## Remaining work

- Consider a deterministic focused `*-testbed` exporter when discoverability
  justifies maintaining a generated distribution.
- Review the private, nonfunctional hardware-KVM spike only if it develops a
  portable implementation worth publishing.
