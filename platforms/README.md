# Platform implementations

These directories are the canonical public sources for target lifecycle,
bootstrap, resident/device-native control, recovery, doctors, fixtures, and
platform operating guidance.

| Platform | Implementation | Agent-facing interface |
| --- | --- | --- |
| Windows | [`windows/`](windows/README.md) | common desktop plus WinVM commands |
| macOS | [`macos/`](macos/README.md) | common desktop plus MacVM commands |
| Linux | [`linux/`](linux/README.md) | common desktop plus LinuxVM commands |
| ChromeOS | [`chromeos/`](chromeos/README.md) | native ChromeOS device commands |
| iOS | [`ios/`](ios/README.md) | CoreDevice/XCTest device commands |
| Android | [`android/`](android/README.md) | guarded ADB handheld commands |
| Quest | [`quest/`](quest/README.md) | guarded ADB device commands |
| Steam Deck | [`steamdeck/`](steamdeck/README.md) | SteamOS Devkit commands |

Use [`../bin/machine-control`](../bin/machine-control) as the normal front
door. `machine-control targets` lists configured logical targets without
private commands or environment. `machine-control inventory ...` delegates
discovery and availability to an optional private inventory provider; it is
not required for ignored `config.local` or `targets.local.json` setups. See the
[target-registry guide](../docs/target-registry.md) for all three modes. Native
platform commands remain explicit through:

```text
machine-control --target <logical-target> testbed -- <platform-command>
```

Concrete machine selectors, endpoints, controller availability, local paths,
and signing values do not belong in tracked public configuration. Supply them
through ignored platform configuration, an ignored local target registry, or
an explicitly selected private inventory provider.

Former standalone `*-testbed` repositories are legacy after their cutover.
They may later be regenerated as focused, discoverable distributions, but
changes originate in these platform directories.

The private, nonfunctional hardware-KVM spike is not imported. Incorporating
an explicitly reviewed portable implementation remains future work.
