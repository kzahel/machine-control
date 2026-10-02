# Unified desktop publication

Topic: native-distribution
Owning topics: [native distribution](../../topics/native-distribution.md),
[Windows desktop](../../topics/windows-desktop.md)
Status: active

## Objective

Publish Windows x64 and ARM64 alongside Mac using one release script, version,
required changelog, tag, and updater manifest. Preserve existing Mac updates.

## Completion conditions

- One entry point builds or promotes exact signed packages for all four targets.
- A complete verified draft publishes once; missing or mixed-source targets fail.
- Public downloads expose both Windows architectures and retain both Mac routes.
- Production update metadata serves all four architectures and current clients.
- Available Mac ARM64 and Windows x64 VM tests exercise exact signed packages
  and production replacement; ARM64 Windows execution remains an honest gap.
- Claims, testbed power, original applications, and temporary staging are restored.

## Boundaries

No Linux implementation, privileged-service installation, or new hardware claim.
The user explicitly requests Windows ARM64 publication despite its native
execution gap. Signing and byte verification remain required for every target.
Concrete infrastructure, claims, credentials and raw evidence remain private.

## Ordered work

### 1 — unify package publication

Reuse platform build jobs under one main-only workflow. Authenticate all package
identities and bytes, stage a four-platform manifest, and verify the complete
draft. Allow exact successful unified candidates to be promoted without rebuilding.

### 2 — expose platform downloads and updates

Extend the existing website selector and proxy. Preserve historical Mac releases
and the shared server's product registration. Require versioned release notes.

### 3 — accept and publish the release

Run local release/site/source checks, build signed 0.4.8, and accept available
native VMs. Publish through the single script, verify public assets/routes, and
exercise installed production updates before restoring testbeds.

## Validation and result

In progress. Local release tests, website tests/build, shell syntax and workflow
lint pass. Final signed build, native acceptance and publication remain.
