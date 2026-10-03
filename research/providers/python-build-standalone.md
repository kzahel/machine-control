# python-build-standalone

Upstream: [astral-sh/python-build-standalone](https://github.com/astral-sh/python-build-standalone).

**Current:** The build project's declared top-level license is
[MPL-2.0](https://github.com/astral-sh/python-build-standalone/blob/63249f9a31f23542d5a58754aed0b93cc432e761/LICENSE).
Its generated distributions contain CPython under the PSF/Python license stack
and native dependencies under their own narrower terms, including OpenSSL,
SQLite, libffi, compression and optional Tk libraries. The top-level build-tool
license is not a license assertion for every generated binary. Preserve
CPython's shipped `LICENSE.txt` and upstream component notices under
[`desktop/python-licenses`](../../desktop/python-licenses); the CLI ships no pip
site-packages. Exact archive pins live in the desktop runtime lockfile because
they are adopted package inputs, not disposable experiments.

## Fit and evidence

**Decision:** Use digest-pinned relocatable `install_only_stripped` distributions
to preserve a Python CLI without requiring users to install Python. This is a
packaging dependency, not a desktop control provider or resident replacement.
Native semantics and OS permissions remain with the existing adapters.

**Current:** All six adopted runtimes are **built** and have deterministic
relocated offline CLI execution evidence in public desktop 0.5.3 CI. Linux
x64/ARM64 and Windows x64/ARM64 use native runners; the Mac Intel target's hosted
execution does not establish physical Intel hardware acceptance. Final Mac code
signatures/notarization, Windows installed catalogs, and Linux final-container
signatures authenticate their exact inventories. Package and offline CLI
acceptance are distinct from desktop control.
[Tactical 063](../../docs/tactical/063-six-platform-desktop-release.md) records
exact source, workflow and public bytes.

Earlier Mac ARM64, Linux ARM64 and Windows x64 isolated-runtime evidence,
including appliance/container relocation, retains its bounded scope in
[Tactical 062](../../docs/tactical/062-installed-agent-cli.md). Source review
covers archive filtering, internal link flattening, runtime isolation and
whole-payload inventory. The
[installed CLI topic](../../topics/installed-agent-cli.md) owns adoption and
remaining acceptance direction.

## Packaging compatibility

**Current:** A Linux native ARM64 container reproduction with the AppImage
deployer confirms that placing this runtime under `usr/lib` changes its ELF
bytes and breaks its complete inventory. Placement under `usr/share` preserves
the same pinned payload and passes relocated offline execution. The first
six-platform candidate also observes Windows SIP catalog hashing refuse the
upstream stripped `zlib1.dll`; raw SHA-256 hashing remains available.
The [installed CLI topic](../../topics/installed-agent-cli.md) owns placement
and publisher-authenticated inventory decisions, and
[Tactical 063](../../docs/tactical/063-six-platform-desktop-release.md) owns
release validation.
