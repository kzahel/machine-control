# Target Registry and Private Inventory

Machine Control keeps public control implementation separate from private
deployment inventory. The public repository contains platform adapters and
safe generic defaults. Each controller supplies the concrete VM, device,
endpoint, route, and local credential locators that exist in its environment.

This guide explains the three supported setup modes, how the common client
chooses among them, and the contract for an optional private inventory
provider.

## The two commands are different

`targets` shows the logical targets resolved by the common client:

```bash
bin/machine-control targets
```

It works with built-in defaults, a local registry file, or an inventory
provider. Its output deliberately omits adapter commands and environment.
`adapterAvailable: true` means the selected launcher and adapter command can
execute on this controller; it does not mean the concrete VM or device is
present, powered on, reachable, or ready. Doctor provides that observation.

`inventory` delegates to an optional private inventory provider:

```bash
bin/machine-control inventory status
```

It is an additional discovery and operator-diagnostics interface. A setup that
uses only `config.local` or `targets.local.json` need not provide it and will
receive `inventory_provider_unavailable` if it is invoked.

## Choose a setup mode

### 1. One standard target per platform

The dependency-free client has generic logical targets such as `windows`,
`macos`, `linux`, `chromeos`, `ios`, `android`, `quest`, and `steamdeck`.
Those entries select the public adapter under `platforms/`; they do not contain
a real machine identity or authorize mutation.

For a standard setup:

1. Follow the selected [platform guide](../platforms/README.md).
2. When that platform provides `config.example`, copy it to the ignored
   `config.local` beside the example.
3. Set the exact machine or device selector and any required safety pin.
4. Run `targets`, then the selected target's read-only doctor.

For example:

```bash
cp platforms/linux/config.example platforms/linux/config.local
# Edit config.local and bind the intended VM exactly.

bin/machine-control targets
bin/machine-control --target linux target doctor
```

This mode needs no root target-registry file and no inventory provider.

### 2. Custom aliases, routes, or multiple targets

Use an ignored local registry when one controller needs custom logical names,
more than one target for a platform, or target-specific environment values:

```bash
cp targets.example.json targets.local.json
# Edit targets.local.json with private deployment values.

bin/machine-control targets
bin/machine-control --target another-linux target doctor
```

`targets.local.json` is ignored by this repository. It uses the
[`machine-control-targets/v0`](../contracts/targets-v0.schema.json) schema.
The same document can be selected explicitly:

```bash
bin/machine-control --registry /absolute/path/to/targets.json targets
```

or through the controller environment:

```bash
export MACHINE_CONTROL_TARGETS_FILE=/absolute/path/to/targets.json
bin/machine-control targets
```

A command path in a registry file may be absolute, a command available on
`PATH`, or a relative path. Relative paths are resolved from the directory
containing that registry file.

### 3. Shared or multi-controller private inventory

Use an inventory provider when private configuration should detect the current
controller, filter its eligible targets, perform lightweight availability
probes, or manage credential locators outside this checkout.

Select the provider explicitly:

```bash
export MACHINE_CONTROL_INVENTORY_PROVIDER=/absolute/path/to/inventory-provider.py
bin/machine-control targets
bin/machine-control inventory status
```

or per invocation:

```bash
bin/machine-control \
  --inventory-provider /absolute/path/to/inventory-provider.py targets
```

The provider is private deployment code. Public lifecycle, bootstrap,
resident control, recovery, and platform assertions continue to live in this
repository.

## Registry resolution order

For operations that resolve a logical target, the common client uses the first
available source in this order:

1. `--registry PATH`;
2. `MACHINE_CONTROL_TARGETS_FILE`;
3. `targets.local.json` in the repository root;
4. an inventory provider selected by `--inventory-provider`,
   `MACHINE_CONTROL_INVENTORY_PROVIDER`, or the compatibility discovery below;
5. the built-in generic targets.

Global options must appear before the command. For example, use
`machine-control --registry PATH targets`, not
`machine-control targets --registry PATH`.

A registry file takes precedence over an inventory provider. In particular,
an existing `targets.local.json` is selected before even an explicit
`--inventory-provider` for target-resolving operations. The `inventory`
command itself always delegates to the selected provider and does not read a
registry file.

For compatibility with the project's original controller layout, the client
also discovers this provider when it exists:

```text
<checkout-parent>/dotfiles/testbeds/testbeds.py
```

That sibling layout is a convenience used by one deployment, not a required
part of Machine Control. Other deployments should normally select their
provider explicitly.

## Registry document

A minimal registry is:

```json
{
  "schema": "machine-control-targets/v0",
  "includeDefaults": false,
  "targets": {
    "example-linux": {
      "platform": "linux",
      "profile": "ubuntu-gnome-wayland",
      "interface": "machine-control-v0",
      "controllerPlatforms": ["linux"],
      "launcher": "direct",
      "claimPolicy": "required",
      "command": ["/opt/machine-control/platforms/linux/bin/linuxvm"],
      "environment": {
        "LINUXVM_PROVIDER": "libvirt-linux",
        "LINUXVM_LIBVIRT_DOMAIN_NAME": "example-development-vm"
      }
    }
  }
}
```

Use placeholders in shared examples. A real local document may contain
private selectors and paths, but it must remain ignored and outside public
artifacts.

`includeDefaults` controls composition:

- `true` starts with the built-in targets, then adds or replaces entries from
  the document;
- `false` exposes only the entries in the document; and
- omission is equivalent to `false`.

Each target has these fields:

| Field | Required | Meaning |
| --- | --- | --- |
| `platform` | yes | Target OS or device family supported by the common client |
| `profile` | yes | Honest platform-specific capability and deployment profile |
| `controllerPlatforms` | yes | Controller operating systems eligible for this concrete route |
| `command` | yes | Adapter executable and any fixed leading arguments |
| `interface` | no | `machine-control-v0` by default, or `native` for a device-shaped adapter |
| `launcher` | no | `auto`, `direct`, `python`, `powershell`, or `bash`; default `auto` |
| `claimPolicy` | no | `required`, `optional`, or `unsupported`; inferred from platform/interface when omitted |
| `workspaceDefaultIntent` | no | `persistent`, `isolated`, or `candidate` |
| `environment` | no | Private non-secret adapter configuration injected only for that target |

`controllerPlatforms` describes the actual selected route, not merely the
target OS. For example, a Windows guest may have one entry for a macOS-hosted
UTM adapter and another for a Linux-hosted libvirt adapter.

## Inventory-provider contract

An inventory provider is an executable or a Python/PowerShell script that the
common client can launch. Target resolution invokes:

```text
PROVIDER machine-control-registry
```

The command must:

- exit successfully within 10 seconds;
- write exactly one JSON object to standard output;
- use schema `machine-control-targets/v0`;
- declare each concrete route's controller eligibility truthfully; and
- normally use absolute adapter paths or commands available on `PATH` because
  provider output has no registry-file directory against which to resolve a
  relative path. Nested relative paths are rejected; a bare working-directory
  command is allowed but fragile.

A typical provider projection is:

```json
{
  "schema": "machine-control-targets/v0",
  "includeDefaults": false,
  "targets": {
    "example-device": {
      "platform": "android",
      "profile": "android-handheld-adb",
      "interface": "native",
      "controllerPlatforms": ["linux"],
      "launcher": "python",
      "command": ["/opt/machine-control/platforms/android/android_device.py"],
      "environment": {
        "ANDROID_TESTBED_SERIAL": "example-device-selector"
      }
    }
  }
}
```

`machine-control inventory ARG...` passes `ARG...` directly to the provider.
Providers that support the complete operator experience should implement:

```text
list [TARGET...]
status [TARGET...] [--json]
guide [TARGET...]
credentials [TARGET...] [--json]
doctor [TARGET...]
machine-control-registry
```

Only `machine-control-registry` has a common machine-readable schema today.
The other commands are provider-defined operator and diagnostic surfaces; they
must remain read-only unless their own documentation says otherwise. In the
project's reference inventory, `status` is lightweight and read-only, while
`doctor` delegates deeper diagnostics without performing repair.

## Credentials and private data

A logical target name is a selector, not a credential, bearer token, claim, or
authorization grant. The target registry may contain private route metadata,
but it must not contain credential values.

When an adapter needs a controller-held credential:

1. Store the value in an appropriate untracked local secret store.
2. Put only a typed file locator in private inventory.
3. Pass only that path through the adapter's documented environment variable.
4. Let the platform's dedicated one-shot secret transport read and deliver the
   value without adding it to ordinary arguments, JSON, logs, captures, or
   evidence.

Do not commit real machine names, endpoints, addresses, device identifiers,
accounts, local paths, credential locators, or topology to this public
repository. `machine-control targets` intentionally projects only logical and
capability metadata; it does not print the selected command or environment.

## Validate a setup

Start with non-mutating checks:

```bash
bin/machine-control targets
bin/machine-control --target TARGET target doctor
```

If a provider is configured, also use:

```bash
bin/machine-control inventory list
bin/machine-control inventory status --json
bin/machine-control inventory credentials TARGET
```

Interpret common failures as configuration boundaries:

- `inventory_provider_unavailable`: no provider is configured; this is
  expected for registry-file-only setups unless `inventory` was required;
- `target_not_found`: the selected registry source does not expose that alias;
- `controller_platform_unsupported`: the target exists, but this concrete
  route is not eligible on the current controller OS;
- `adapter_unavailable`: the selected command or launcher cannot execute; and
- `invalid_registry`: the registry or provider projection violates the public
  schema enforced by the client.

Doctor is read-only. For an accepted VM, repair exact private identity when
doctor requests it, then acquire and carry a target-use claim before meaningful
or mutating work.
