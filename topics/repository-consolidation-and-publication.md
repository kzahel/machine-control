# Repository Consolidation and Focused Publications

Topic: `repository-consolidation-and-publication`

Status: accepted direction; platform migrations have not started.

## Scope

This topic owns the repository boundary for public machine-control and testbed
implementation, private deployment inventory, migration from the existing
`*-testbed` repositories, and optional focused public distributions.

It does not change target-native routing, privilege, recovery, or result
semantics. Those remain governed by their existing architecture and platform
topics.

## Decision

**Decision:** [`machine-control`](../README.md) is the canonical public source
for portable machine-control and testbed implementation across every supported
machine type. This includes common contracts and clients as well as public
platform lifecycle, bootstrap, resident control, recovery, doctors, fixtures,
tests, and operating guidance.

**Decision:** the private dotfiles repository remains authoritative for the
controller user's concrete deployment inventory: actual target aliases,
controller availability, machine-specific paths and endpoints, and references
to locally held access material. None of that inventory is imported into this
public repository or a generated public distribution.

**Decision:** an external `*-testbed` repository may remain useful as a
focused, discoverable public distribution. Such a repository is generated
one-way from committed `machine-control` content. It is not a second editable
source of truth.

The intended mental model is:

```text
machine-control                  canonical public source and agent CLI
    + private dotfiles overlay   concrete local target inventory
    |
    +-- optional export -------> focused public *-testbed distribution
```

An agent should normally start with the common `machine-control` command. The
command may consume the private inventory overlay without requiring the agent
to navigate dotfiles or understand repository placement.

## Ownership boundary

| Concern | Canonical owner |
| --- | --- |
| Common capability, request, result, and doctor contracts | `machine-control` |
| Public platform lifecycle, bootstrap, control, recovery, and tests | `machine-control` after that platform's cutover |
| Actual machines, aliases, endpoints, availability, and local paths | private dotfiles inventory |
| Credentials and secret material | an appropriate local secret store; never this repository or an export |
| Agent-session coordination and cross-host delegation | YepAnywhere |
| Focused public packaging and discoverability | generated `*-testbed` distribution when justified |

Public examples use generic logical targets and placeholders. The common CLI
must keep portable results free of private inventory even when its local
adapter has access to that inventory.

## Transition rule

There is no period in which two repositories are editable authorities for one
platform. Each platform moves through these states:

| State | Canonical implementation | External repository |
| --- | --- | --- |
| Current | existing `*-testbed` repository | active and authoritative |
| Frozen migration | frozen external tip | no unrelated implementation changes |
| Subsumed | `machine-control` platform directory | legacy/read-only notice |
| Published, if later justified | `machine-control` platform directory | generated distribution stamped with its source commit |

Before cutover, a necessary fix still belongs in the external source
repository; the migration then restarts from its new tip. After cutover, all
implementation changes belong here. The external repository is not marked
legacy until the imported implementation and its new entry paths have passed
the platform's completion conditions.

## Initial source classification

**Current:** remote inspection during planning found these repositories public,
unarchived, and using one simple `main` history without tags or merge commits:

- `winvm-testbed`, `macvm-testbed`, `linuxvm-testbed`, `steamdeck-testbed`,
  `quest-testbed`, and `ios-device-testbed`, each with an MIT license; and
- `chromeos-testbed`, which currently has no top-level license and therefore
  requires a licensing decision before import or generated redistribution.

`hardware-kvm-testbed` is currently private and has no top-level license. It
must not receive the abbreviated public-source review described below. Its
portable implementation, if adopted here, requires an intentional sanitized
publication review; preserving its private history is not a goal.

Visibility and licensing must be rechecked at each freeze point. Public
visibility shows that material has already been disclosed; it does not prove
that the history is free of deployment data, that every bundled artifact may
be republished, or that it is suitable for permanent inclusion in another
public history.

## Destination layout

**Decision:** import each repository below a stable platform prefix rather than
keeping it as a submodule or sibling dependency:

```text
platforms/
  windows/
  macos/
  linux/
  chromeos/
  ios/
  quest/
  steamdeck/
  hardware-kvm/
```

The initial import should reproduce the source tree under its prefix without
also redesigning it. Follow-up commits may move adopted reusable resident code
into shared `src/`, `providers/`, `contracts/`, or conformance locations when
the ownership boundary is understood. Separating import from refactoring keeps
tree equivalence, review, and rollback straightforward.

Submodules are rejected because they retain separate version and authority
decisions. A long-lived Git subtree workflow is also rejected because it
invites bidirectional synchronization. The migration may use Git history
filtering as a one-time import mechanism; that does not make the old repository
an ongoing upstream.

## History-preserving import

**Decision:** preserve the useful public repositories' logical history rather
than squashing them to snapshots, unless review finds a reason not to import a
particular history.

For each public source:

1. Freeze and fetch the exact remote `main` tip. Record the source URL and tip
   commit in the platform tactical.
2. Run the pre-import review against the complete source history.
3. In a temporary clone, rewrite every tree below
   `platforms/<platform>/`, preferably with `git filter-repo` and its
   `--to-subdirectory-filter` option.
4. Fetch the rewritten branch into `machine-control` and merge it without
   squashing. Do not rewrite either published source repository in place.
5. Record the original tip and rewritten import tip. Preserve original authors,
   author dates, commit messages, and file evolution. Commit IDs necessarily
   change because every historical tree path changes; the external repository
   remains the exact original-commit reference.
6. Make path integration, documentation, and refactoring changes only after
   the mechanically equivalent import merge.

This approach makes `git log -- platforms/<platform>` and file blame useful in
the monorepo. A plain unrelated-history merge can retain the old object IDs,
but leaves every old tree rooted at `/` and makes path-local history difficult
to follow. For this small corpus, useful monorepo history is the better
tradeoff as long as provenance is recorded.

Issues, pull requests, discussions, releases, and other forge metadata are not
Git history. They remain available in the legacy repository and should be
linked from the migration record when relevant.

## Proportionate pre-import review

The already-public repositories receive a lightweight but complete-history
review. The review is deliberately narrower than a forensic audit but is not
limited to the checked-out tree:

1. Confirm the remote visibility, license, exact tip, clean worktree, and lack
   of unpushed intended changes.
2. Run a secret scanner over all revisions and inspect any findings without
   copying sensitive matches into logs or committed evidence.
3. Search all tracked paths and historical blobs for private infrastructure
   categories prohibited by this repository: credentials and keys, real
   endpoints and addresses, usernames and home paths, serials and device IDs,
   machine-specific configuration, personal captures, logs, and archives.
4. Inventory non-text and unusually large blobs, submodules, symlinks, vendored
   code, generated artifacts, and third-party license or notice requirements.
5. Review the source README, configuration examples, ignore rules, automation,
   and the commits most likely to contain bootstrap or troubleshooting data.
6. Scan the rewritten import range again before it is pushed publicly from
   `machine-control`.

If a finding is isolated and removal is legally and operationally sound,
sanitize it in the temporary rewrite and record the omission without recording
the sensitive value. If the history is mixed with private or uncertain
material, import a reviewed current snapshot as new commits and retain only a
link to the source repository. Do not import questionable history merely for
aesthetic continuity.

Private sources require a stronger presumption: extract only explicitly
reviewed portable files into new public commits. Dotfiles history and concrete
inventory are never candidates for import.

## Per-platform cutover

Each migration gets a numbered tactical document and independently satisfies
these completion conditions:

1. Freeze, classify, review, and import the source at a recorded commit.
2. Make its commands and internal paths operate from the new platform prefix.
3. Route the common client to the in-repository implementation while reading
   concrete target selection from the private inventory interface.
4. Run the imported repository's tests, relevant root contract tests, doctor,
   lifecycle checks, and guarded live conformance appropriate to that target.
5. Update public architecture, platform topics, runbooks, and examples without
   copying private deployment facts.
6. Update the private dotfiles inventory to select the new command location.
7. Verify that ordinary operation no longer depends on the external checkout.
8. Declare cutover in both repositories, then mark the external repository
   legacy/read-only. Do not delete its history or forge metadata.

A platform migration should be independently reversible before the legacy
notice is published. Several histories may be prepared in parallel later, but
authority changes one platform at a time.

## Migration sequence

**Proposal:** proceed in these stages:

1. **Foundation:** finalize the inventory interface between the public common
   client and private dotfiles overlay; add platform-directory conventions and
   reusable import/audit tooling.
2. **Desktop rehearsal:** migrate Linux first as a meaningful but relatively
   small accepted common-client target. Use the result to correct the process.
3. **Active desktops:** migrate macOS and Windows separately, including their
   resident and image/lifecycle relationships, without disrupting the existing
   Windows-first runtime.
4. **ChromeOS:** resolve licensing, import ChromeOS, validate its update and
   recovery workflows, and mark the existing repository legacy. Treat a
   generated focused distribution as a later publication task, not part of the
   authority cutover.
5. **Attached and physical devices:** migrate iOS, Quest, and Steam Deck with
   their native device-host boundaries intact.
6. **Private candidate:** separately review whether any portable
   hardware-KVM implementation should be published here from a sanitized
   snapshot.
7. **Agent handoff:** once the common CLI covers the full current inventory,
   update durable agent instructions to start there and reduce
   `dotfiles/testbeds` to private inventory/deployment and compatibility roles.

The exact platform order may change when a tactical discovers a dependency,
but a smaller pilot should precede the repositories with the most active image
and recovery machinery.

## Optional focused publications

Generated `*-testbed` repositories are deferred until a platform has completed
cutover and there is a concrete discoverability or standalone-use need.

When introduced, an export must:

- be reproducible from a clean committed `machine-control` revision;
- contain only public source and sanitized examples, never the private
  inventory overlay;
- assemble the platform directory and an explicit allowlist of required common
  files rather than copying the whole monorepo;
- include a generated notice, canonical source link, source commit identifier,
  license, and contribution instructions;
- preserve the external repository's useful historical and forge metadata;
- reject or detect manual drift in continuous integration; and
- direct changes back to the canonical paths in `machine-control`.

An export is a distribution artifact. It may be independently cloneable and
pleasant to use without becoming an independently maintained implementation.

## Non-goals

- Do not move private inventory into `machine-control` merely to create one
  physical checkout.
- Do not copy dotfiles history, secret material, or actual deployment details
  into an import or generated repository.
- Do not require every platform to expose misleadingly identical lifecycle or
  desktop operations.
- Do not refactor all imported code during the history merge.
- Do not maintain reverse synchronization from generated or legacy testbed
  repositories.
- Do not mark an external repository legacy before its platform passes the
  cutover conditions.
