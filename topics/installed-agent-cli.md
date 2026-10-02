# Installed agent CLI

Topic: `installed-agent-cli`

Status: implemented in source; Mac ARM64 standalone packaging passes local
smoke, including physical payload relocation and isolated Python configuration.
A locally assembled Developer ID app passes YA publisher, closure and identity
verification. Linux ARM64 also passes relocated offline CLI execution in an isolated native
container, and Windows x64 passes the same smoke in a claimed appliance.
Notarization, publication and signed Windows/Linux desktop acceptance remain
separate.

## Contract

**Decision:** Python remains the common CLI implementation. Developers run
`bin/machine-control` directly; command changes require no Rust toolchain or
desktop rebuild. Desktop packages bundle the same modules, local host adapters,
claim helpers and a pinned CPython runtime. YA consumes this interface rather
than maintaining a second resident installation for the migrated route.

**Current:** Tauri builds stage `mc-cli` resources using
[`prepare-cli.py`](../desktop/scripts/prepare-cli.py). The terminal entry is
`mc-cli/commands/machine-control` on macOS/Linux and
`mc-cli/commands/machine-control.cmd` on Windows. These names are separate from
the Windows/Linux GUI binary. Mac resources live inside the app bundle;
Windows resources live under the product root. The launcher uses isolated
Python, suppresses bytecode writes and propagates its runtime to host/claim
subprocesses. No system Python is needed for the CLI; Linux's native GTK/AT-SPI
resident retains its documented system dependencies.

**Current:** `agent identity` returns
[`machine-control-client-identity/v1`](../contracts/client-identity-v1.schema.json)
without contacting a resident. `agent instructions` returns the owned workflow
for doctor, claims, scoped access, semantics, browser control and bounded
artifacts. Reading either grants no authority. Installed defaults expose only
`host`; explicit per-user registries/providers can add other installed adapters.
There is no implicit sibling checkout/private-inventory lookup in a package.

**Decision:** CPython archives are SHA-256 pinned for six desktop targets in
[`python-runtime.lock.json`](../desktop/python-runtime.lock.json). Retain upstream
component license notices. Mac signs nested native libraries before sealing
the script/runtime inventory in the app signature. Windows authenticates the
whole CLI directory with its publisher-signed catalog. Linux final packages
use the existing authenticated package signatures. An unsigned hash receipt is
integrity evidence only, not publisher authority. The packaging
[dossier](../research/providers/python-build-standalone.md) owns licensing.

## Consumer ownership and acceptance

**Decision:** MC owns installed commands, native access/arming, claims,
resident lifecycle and updates. YA owns launch eligibility and advertisement,
optional tool adaptation and media presentation. A session ID is attribution,
not authority; suppressing advertisement cannot contain same-user shell access.
Native sudo remains a separate feature with OS authentication.

**Current:** The CLI does not start a replacement resident when the app is
unavailable. The caller receives the existing typed failure and can ask the
operator to open MC. Mutations and captures retain the shared resident's route,
generation, delivery, effect and uncertainty reporting.

[`cli-installed.py`](../tests/desktop/cli-installed.py) tests offline discovery,
isolated runtime use and bundled claim dependencies from an unrelated directory.
Archive traversal, external links, unused terminal-data aliases,
modified/missing files and unexpected files have portable negative tests.
Linux ARM64 passes the same relocation smoke in an isolated native container.
The Mac and Linux workflows execute this smoke after staging; Windows executes
it against the actual signed installer payload before recording provenance. The signed Mac ARM64 assembly passes bounded
workstation approval/refusal/revocation, an independent AppKit counter effect,
exact-window capture and artifact retrieval through the installed CLI. This is
claimed-appliance evidence, not physical-workstation acceptance. Chrome for Testing browser acceptance also passes 21 checks through the
installed CLI with independent page/Chrome effects, browser PNG retrieval,
release, worker restart and reconnect. A real YA local Codex provider launch
reads installed instructions/identity and observes the retained browser fixture
PNG through its native image viewer. YA also passes full-app HTTP media and
real desktop/phone image-viewer acceptance: live output serves exact native PNG
bytes, and a fresh app/media store reconstructs them from the actual transcript
after provider shutdown. Preservation stays off and the fixture source remains
available until cleanup. Provider-driven control remains separate. Signed
installed replacement and per-platform evidence remain required before
retiring any legacy YA component. [Tactical 062](../docs/tactical/062-installed-agent-cli.md)
records implementation; [YA's migration plan](../../yepanywhere/docs/tactical/142-machine-control-desktop-consumer.md)
owns consumer cutover.

**Current:** Windows x64 passes physically relocated offline execution through
its bundled interpreter in a claimed Windows 11 appliance. The Windows desktop
harness accepts the installed command as an alternative to a checkout and uses
it for control and artifact retrieval. Native PowerShell syntax passes; the selection-refusal run was blocked by the
guest's script execution policy and is not counted as passing. Full signed installed desktop/browser and YA acceptance
still need the new candidate; this staging smoke does not establish them.
