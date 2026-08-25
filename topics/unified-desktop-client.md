# Unified Desktop Client

Topic: `unified-desktop-client`

Status: accepted first three-desktop client over the current resident
implementations.

## Goal

An agent should use the same ordinary desktop workflow on Windows, macOS, or
Linux by changing target selection rather than changing skills or command
vocabulary. The common client is a facade over the existing residents and
transports, not a fourth UI implementation.

```text
machine-control --target <logical-target> desktop status
machine-control --target <logical-target> desktop applications
machine-control --target <logical-target> desktop snapshot ...
machine-control --target <logical-target> desktop action ...
machine-control --target <logical-target> desktop capture ...
machine-control --target <logical-target> desktop input ...
```

## Common surface

**Current:** The first portable desktop subset covers:

- `status`, `capabilities`, application and window inventory;
- compact/full semantic snapshots with generation-bound references;
- semantic press/focus/value actions;
- display/window capture and bounded artifact retrieval;
- pointer, click, drag, scroll, key, and Unicode text input where declared;
- application launch, activation, termination, and window close where
  declared; and
- a raw request escape hatch for an operation already defined by a resident.

The client accepts the common request vocabulary and translates only known
historical naming differences, such as Windows `app.launch`, `screenshot`,
`invoke`, `set.value`, `click`, `key`, and `type`. It returns the resident's
actual operation and route alongside the requested common operation. It does
not fabricate capability parity.

## Transports and placement

**Decision:** `desktop call` reaches the resident through the selected
testbed's outside adapter. `desktop call-local` reaches the same resident
through its installed guest-local CLI when the testbed supports that proof.
Both use the same request and result vocabulary and should report one resident
generation.

The common client does not treat the transport as the contract. Windows SSH,
Tart guest execution, QEMU guest-agent execution, a future authenticated
tunnel, and direct local IPC may all carry the same request.

**Current:** the selected Windows adapter now hands ordinary administration
and resident calls directly to OpenSSH after one claim check and one exact UTM
target resolution. The connection uses the resolved guest address internally
while retaining the logical alias as its host-key identity. The generated
standalone alias still uses its self-guarding proxy for independent callers.
A live initially-off acceptance pass measured a 3.07-second median common OS
call and 3.60-second resident status call, down from the earlier 8.3–10.4
second common administration path. A fresh already-resolved SSH call was about
0.40 seconds and a shared connection about 0.23 seconds, so persistent SSH
reuse is deferred: it would not materially reduce the remaining adapter and
claim cost.

## Escape hatches

**Decision:** Unification stops where platform semantics become misleading.
The client therefore exposes explicit namespaces rather than arbitrary
pass-through hidden behind a generic operation:

```text
machine-control --target <logical-target> testbed -- <native arguments>
machine-control --target <logical-target> os -- <native arguments>
```

`testbed` invokes the authoritative platform/testbed CLI for lifecycle, image,
device, or recovery operations outside the portable subset. `os` invokes the
platform-owned guest administration route and reports its platform and
privilege. Before repository-consolidation cutover that implementation may be
in an external testbed; afterward it lives under the platform directory here.
PowerShell is not presented as Bash; UAC, TCC, Polkit, GDM, loginwindow, and
provider-specific operations remain explicit capabilities.

Outer screenshot or input commands are not reachable through ordinary
`desktop` fallback. They remain named testbed recovery operations and retain
the authoritative testbed's guard and authorization policy.

## Results and artifacts

**Decision:** The client validates the resident envelope before returning it
and adds a separate transport projection rather than rewriting provider truth.
Every result preserves operation, acceptance, route, generation, delivery,
effect, uncertainty, host interference, and typed error information.

The retained Windows seal predates the mandatory `hostInterference` result
field. Its adapter may add `none` only for that known target-native runtime and
must disclose `compatibilityProjection: ["hostInterference"]`. Newly published
Windows runtimes emit the field themselves. No other missing field or platform
receives this compatibility treatment.

Artifact retrieval is normalized around an opaque handle returned by the
adapter. A handle may project a Windows artifact identifier, a bounded macOS
guest path, or a Linux UUID, but callers do not receive a generic arbitrary
file-read primitive. The result reports the actual fetch route and local
output path.

## Conformance

The shared workflow runs through the same client on all three accepted
desktops:

1. inspect doctor and resident capabilities;
2. launch or reset a deterministic application fixture;
3. obtain a compact semantic snapshot and reference;
4. focus or enter Unicode text and press a semantic control;
5. confirm an independent application effect;
6. capture the relevant window and retrieve its artifact;
7. compare guest-local and outside status generations;
8. clean up the application and artifact; and
9. report request bytes, result bytes, latency, retries, and round trips.

Platform-specific setup and independent-effect readers remain testbed-owned
hooks. A provider acknowledgement is never the correctness oracle.

**Current:** The guarded live corpus passed on Windows, macOS, and Linux.
Every target reported outer UI prohibited, local and outside status agreed on
one resident generation, semantic presses produced independently observed
effects, and target-native captures were retrieved as valid PNG artifacts.
macOS and Linux also confirmed Unicode fixture effects. The Windows fixture
does not contain an editable field, so that shared cell reports the omission;
the deeper Windows corpus already covers Unicode input. See the
[minimized evidence](../docs/evidence/desktop-common-entry.md) and executable
[`live-desktop-conformance.sh`](../tests/client/live-desktop-conformance.sh).

## Remaining direction

- Add an authenticated remote carrier, SDK, or MCP projection only after the
  local contract stays stable under real application campaigns.
- Expand friendly normalization when repeated workflows demonstrate a common
  field or selector; retain `desktop raw` for honest provider-specific calls.
- Extend ChromeOS beyond its common readiness/maintenance projection only when
  measured desktop operations support honest shared capability and result
  semantics. Its complete native vocabulary remains available explicitly.
- Profile the remaining Windows provider/claim setup and the Linux
  administrative route when iteration latency justifies another bounded
  transport slice. Do not add persistent sessions merely to save the measured
  approximately 0.17-second Windows SSH handshake delta.

## Non-goals

- Do not collapse platform-specific VM/device bootstrap or lifecycle into one
  misleading generic implementation. Canonical source may live here while
  platform semantics remain separate. Never centralize private inventory here.
- Do not replace native resident providers or their security boundaries.
- Do not make a generic shell or arbitrary privileged command part of the
  desktop contract.
- Do not force unsupported operations to appear successful.
- Do not make the common client a prerequisite for direct testbed debugging.
