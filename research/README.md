# Machine-Control Research Corpus

This is the entry point for evidence about machine-control providers and
platform options. Read the [North Star](../README.md#north-star) first.

The corpus deliberately preserves two views of the same field:

```text
provider-first research                   platform-first research
"Could this be a common spine?"           "What is best on this OS?"
              \                              /
               +---- evidence and gaps -----+
                             |
                             v
                  topics: current decisions
                             |
                             v
                  tacticals: bounded work
```

A library that spans several platforms can reduce adapter and agent-skill
fragmentation without being the strongest implementation on every platform.
Conversely, selecting the best platform-specific component must not force the
whole system into unrelated vocabularies. One library everywhere is an
optimization, not a requirement.

## Documentation ownership

- [`providers/`](providers/README.md) owns one dossier per reusable library or
  provider: license, architecture, claimed platforms, implementation depth,
  test model, evidence, gaps, and North Star fit.
- [`platforms/`](platforms/README.md) compares every plausible route for one
  operating system or device family and records how deeply each has actually
  been investigated.
- [`topics/`](../topics/README.md) owns current decisions and recommended
  direction. A topic links to corpus evidence instead of copying the dossier.
- [`docs/tactical/`](../docs/tactical/README.md) owns the bounded work selected
  from those decisions.
- [`machine-control-spike`](../../machine-control-spike/README.md) and the
  authoritative testbeds own exact revisions, commands, environments, private
  execution details, and experiment artifacts.

The corpus is current, public, portable synthesis. It is not an append-only
lab notebook and must not contain private infrastructure.

## Evidence levels

Evidence attaches to a specific provider, platform, capability, and route. A
provider can be conformance-tested for normal macOS windows and merely
upstream-claimed for Linux Wayland.

| Level | Meaning |
| --- | --- |
| `discovered` | The project has been identified; no material claim has been checked. |
| `upstream-claimed` | Upstream documentation makes the claim; implementation and behavior have not been independently checked. |
| `source-reviewed` | Relevant implementation and tests were inspected. Exact source pins belong in the spike when the conclusion affects a decision. |
| `built` | The referenced source was built in a recorded environment. |
| `live-tested` | The capability was exercised on a real configured target. |
| `conformance-tested` | Independent effect and non-interference oracles verified the declared behavior and refusals. |
| `adopted` | An authoritative testbed currently depends on the route for ordinary operation. |

Higher levels do not automatically apply to every claim in the same project.
Record the strongest justified level and link the evidence. Never promote an
API success to `conformance-tested` without observing its effect.

## License records

Every provider dossier records the repository's declared top-level license and
links to its source. Also record narrower or different terms for bundled
components, generated bindings, skills, assets, models, or hosted services
when they affect the contemplated use.

A license field is evidence, not legal advice. Before distributing a provider
or derivative, repeat the license review at the exact revision, inspect
dependency and asset obligations, and put that pin and audit in the owning
implementation or spike repository. Private API fragility, signing,
entitlements, and app-store policy are technical/distribution risks separate
from copyright license.

## Dossier fields

A provider dossier should answer:

1. What is it, who maintains it, and under what declared license?
2. Which platforms and surfaces are claimed, source-reviewed, built, tested,
   conformance-tested, or adopted?
3. How are process, application, window, element, snapshot, and session
   identities represented?
4. What semantic, visual, input, browser, shell, administration, and protected
   routes exist?
5. Can the same implementation be called locally and remotely without
   manipulating a VM or remote-desktop window?
6. What foreground, cursor, z-order, session, integrity, permission, and
   protected-desktop effects can occur?
7. What fixtures and independent oracles support its claims?
8. Which North Star responsibilities fit directly, require a facade or
   platform component, conflict, or remain unknown?
9. What is the smallest experiment that could change the current disposition?

A platform report should then compare dossiers using the platform's real
acceptance cases rather than a lowest-common-denominator feature count.

## Current indexes

- [Provider index](providers/README.md)
- [Platform index](platforms/README.md)
- [Adjacent projects and benchmarks](adjacent-projects.md)
- [Windows options and evidence](platforms/windows.md)
- [Cross-provider decision topic](../topics/provider-landscape.md)
- [Windows decision topic](../topics/windows-resident-control.md)

## Update rules

- Add a provider dossier when a project receives more than search-result
  triage or becomes a serious comparison candidate.
- Add or update a platform report when evidence changes the depth, limits, or
  disposition of a route on that platform.
- Link exact pins and experiment reports; do not duplicate their command logs.
- Distinguish upstream claims, source findings, local observations, and
  decisions in every summary.
- Update the affected topic when corpus evidence changes the current direction.
- Update [`SYSTEM-MAP.md`](../SYSTEM-MAP.md) when a provider enters or leaves
  the actual system boundary, not merely because it was discovered.
