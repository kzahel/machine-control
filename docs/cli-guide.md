# Command-line guide

Machine Control can run from an installed desktop bundle or a source checkout.
The desktop app includes the CLI and its Python runtime; see
[installed agent CLI](../topics/installed-agent-cli.md) for discovery. Headless
residents and appliance profiles also work independently of the desktop app.
The examples below use a checkout and configured logical targets.

## Set up a controller

The common client requires Python 3.10 or later and uses only the standard
library.

```bash
git clone https://github.com/kzahel/machine-control.git
cd machine-control

bin/machine-control targets
python3 bin/check --portable
```

On Windows, use `py -3 bin/machine-control targets` and
`py -3 bin/check --portable`. Portable checks do not contact a VM or physical
device.

To connect a real target:

1. Choose its guide from the [platform index](../platforms/README.md).
2. Install that platform's prerequisites and target-resident components.
3. Put concrete selectors, endpoints, paths, policy, and locators for any
   host-held credentials in ignored local configuration or an optional private
   inventory provider, following the
   [target-registry guide](target-registry.md). Keep credential values in
   its declared local secret store, not in this repository or the target
   registry.
4. Always inspect `inventory credentials TARGET` before VM login/unlock or
   asking for human password entry. In registry-only setups, resolve the
   adapter's declared secret-file locator. Use stored appliance credentials
   through the supported secret transport. A missing locator/file or unsupported
   delivery route is a specific handoff/capability gap; do not assume a locked
   disposable VM requires manual entry. Then run the read-only doctor, repair
   private identity if necessary, and claim the target before meaningful use.

On a controller with a private inventory provider:

```bash
set -e

bin/machine-control inventory status
bin/machine-control inventory credentials winvm
bin/machine-control --target windows target doctor
claim="$(bin/machine-control --target windows claim acquire \
  --duration 30m --reason 'validate the Windows appliance' \
  --claimant-authority example-agent --claimant-id session-42)"
claim_id="$(jq -er 'select(.accepted == true) | .data.claim.claimId' <<<"$claim")" || exit 1
trap 'bin/machine-control --target windows claim release "$claim_id"' EXIT
bin/machine-control --target windows --claim "$claim_id" target ensure-ready
bin/machine-control --target windows claim release "$claim_id"
trap - EXIT
```

`doctor` is read-only. `ensure-ready` is the explicit mutating composition: it
records the initial doctor result, performs only an adapter-declared ordinary
start when appropriate, and observes readiness again. It does not guess a
repair for a running unhealthy target.

Local target registries use the
[`machine-control-targets/v0`](../contracts/targets-v0.schema.json) schema. Logical
target names are selectors, not credentials or bearer authority. The
[target-registry guide](target-registry.md) documents standalone
`config.local`, ignored registry files, the per-user controller configuration,
provider setup, resolution precedence, and the provider command contract.

## Common workflows

### Run a bounded task under a claim

```bash
bin/machine-control --target windows run \
  --reason 'inspect the application desktop' \
  --claimant-authority example-agent --claimant-id task-42 \
  -- bin/machine-control desktop applications
```

The runner performs read-only doctor and exact-identity preflight, acquires and
renews the claim, passes selection to nested common-client commands, and
releases after task cleanup. Add `--intent isolated` to own a workspace and
its claim together. Supply a script for a sequence of operations. The program
runs locally; use `machine-control os -- …` inside it for guest commands.
Plain scopes do not stop the VM; tasks still own any required lifecycle
cleanup. See [scoped tasks](scoped-runs.md) for signals, audit output,
workspace retention, and unresolved-release recovery.

### Claim a VM for exclusive use

Use the lower-level commands when ownership must span independent processes:

```bash
set -e
mc=bin/machine-control

$mc --target windows target doctor
$mc --target windows claim capabilities
$mc --target windows claim status
claim="$($mc --target windows claim acquire --duration 30m \
  --reason 'test the save workflow' \
  --claimant-authority example-agent --claimant-id session-42 \
  --session-id task-7 --metadata purpose=acceptance)"
claim_id="$(jq -er 'select(.accepted == true) | .data.claim.claimId' <<<"$claim")" || exit 1

trap '$mc --target windows claim release "$claim_id"' EXIT
$mc --target windows --claim "$claim_id" target ensure-ready
$mc --target windows --claim "$claim_id" desktop applications
$mc --target windows claim renew "$claim_id" --duration 30m
$mc --target windows claim release "$claim_id"
trap - EXIT
```

The authority and identifiers are caller-chosen, bounded, and self-asserted;
they do not need to come from a particular agent system. Use values your
current environment can truthfully expose, plus a useful reason. Do not put
credentials, private endpoints, or provider identities in claim metadata.

Claims are exclusive and expire after a reported interval, so an abandoned
session cannot block a VM forever. Release promptly in a `finally` block or
shell trap; renew only while work remains active. The opaque claim ID selects
the current lease but is not a credential or authorization grant.

### Inspect and control a desktop

Use a live claim acquired for this task and retain it through the operations:

```bash
mc=bin/machine-control

$mc --target windows --claim "$claim_id" desktop status
$mc --target windows --claim "$claim_id" desktop capabilities
$mc --target windows --claim "$claim_id" desktop applications
$mc --target windows --claim "$claim_id" desktop windows
$mc --target windows --claim "$claim_id" desktop snapshot \
  --target org.example.Application --query Save
$mc --target windows --claim "$claim_id" desktop capture \
  --scope window --target active_window
```

A semantic snapshot returns ephemeral, generation-scoped element references.
Use those references for actions and rediscover them after navigation, process
restart, or window recreation.

### Use a physical iOS target

Follow the [iOS guide](../platforms/ios/README.md) for Mac-host setup, exact
device selection, signing, and lease requirements. On a configured controller:

```bash
mc=bin/machine-control

$mc --target ios target doctor
$mc --target ios ios runner prepare
$mc --target ios ios application launch Settings --relaunch
$mc --target ios ios snapshot --interactive
```

iOS has a device-shaped operation family rather than pretending to be a
desktop. Android, Quest, ChromeOS, and Steam Deck likewise retain explicit
native operations where a common projection would hide important semantics.

### Request a VM workspace

```bash
set -e
mc=bin/machine-control

workspace="$($mc --target macos workspace acquire --intent isolated \
  --reason 'run an isolated application test' \
  --claimant-authority example-agent --claimant-id session-42)"
handle="$(jq -er 'select(.accepted == true) | .data.handle' <<<"$workspace")" || exit 1
claim_id="$(jq -er '.data.claim.claimId' <<<"$workspace")" || exit 1
trap '$mc --target macos --claim "$claim_id" workspace release "$handle"' EXIT
$mc --target macos --workspace "$handle" --claim "$claim_id" desktop status
$mc --target macos --claim "$claim_id" workspace release "$handle"
trap - EXIT
```

Callers request intent—`persistent`, `isolated`, or `candidate`—while the
platform adapter chooses the safe provider mechanism. Workspace handles are
opaque selectors backed by private exact-identity receipts. Acquisition also
returns the workspace's live exclusive-use claim. Release requires that claim,
performs receipt-bound retain/discard cleanup, and then relinquishes it.

### Reach a platform-specific operation

```bash
$mc --target windows testbed -- help
$mc --target chromeos maintenance capabilities
$mc --target chromeos maintenance audit --profile runtime
```

`testbed --` keeps platform lifecycle, bootstrap, recovery, and specialized
operations available without flattening them into a misleading universal
interface. `os --` provides an explicit guest-administration escape on
supported desktops.

Read [SECURITY.md](../SECURITY.md) before arming protected operations.
Platform guides own setup and operating policy; claims coordinate VM use,
while native grants authorize desktop access.
