# Package the Python CLI for desktop consumers

Owning topics: [Installed agent CLI](../../topics/installed-agent-cli.md),
[Native distribution](../../topics/native-distribution.md).

Status: in progress, 2026-10-02.

## Objective

The maintainer requested end-to-end implementation of YA's desktop-consumer
migration while retaining Python for fast command iteration. Ship the common
client, its local adapters and its runtime with the desktop product; expose
offline identity and agent instructions. YA's
[Tactical 142](../../../yepanywhere/docs/tactical/142-machine-control-desktop-consumer.md)
owns consumer migration and legacy retirement gates.

## Completion conditions and boundaries

Source-independent installed CLI use, authenticated package closure, real
desktop/browser effects and actual YA advertisement must pass before claiming
consumer acceptance. Keep writable state external, local/remote targets honest,
claims separate from access and native sudo separate from desktop arming.
Preserve direct Python development and existing appliance providers. No native
provider rewrite or GUI focus for ordinary CLI commands.

## Ordered work

### 1 — package the Python client and local dependencies

Pin six standalone runtime archives, include local adapters/claim helpers,
stage a relocatable command directory and authenticate complete product bytes.

### 2 — publish identity and agent instructions

Define a versioned offline identity and owned instructions. Test calls without
a checkout, system Python or ambient Python configuration. Expose only installed
default adapters and preserve explicit controller configuration.

### 3 — prove installed control through YA

Build the product, validate in a claimed dedicated appliance, and prove local
semantics, browser operations, artifacts and refusal. Integrate YA discovery
through the same installation. Verify publisher trust before executing probes.

## Validation and result

Mac ARM64 staging, CLI identity, portable packaging negatives, common client
tests, desktop frontend build and Rust tests pass locally. Signed product and
Windows/Linux installed execution remain separate gates. Update this record
with exact source-independent and consumer evidence as validation completes.
