# Tactical 014: Repository Consolidation and Cutover

Status: active.

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

Active. The ownership decision and migration method are accepted; imports and
cutovers remain to be executed.
