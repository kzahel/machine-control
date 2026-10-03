# 063 — Six-platform desktop 0.5.3 release

Status: complete.

Owning topics: [native distribution](../../topics/native-distribution.md),
[installed agent CLI](../../topics/installed-agent-cli.md), and
[native sudo](../../topics/native-sudo.md).

## Objective and completion conditions

Release a new version on every packaged platform, as requested. Publish desktop
0.5.3 for Mac Apple silicon/Intel, Windows x64/ARM64, and Linux x64/ARM64.
Include native update discovery, the bundled Python CLI, and Mac sudo helpers.

- Require meaningful notes and one exact main source across all six targets.
- Pass source checks and native CI tests, authenticate final packages and CLI
  payloads, and retain honest GUI execution and physical-hardware gaps.
- Publish one immutable annotated tag and complete verified asset set.
- Verify public receipts, all six updater entries, eight download redirects,
  and production metadata for older and current clients.

## Boundaries

No workstation-component release, appliance replacement, credential rotation,
permission expansion, or physical-host input. Preserve unrelated working edits.
Existing native acceptance belongs to tacticals 060–062; package verification
alone does not establish a new GUI execution result.

## Ordered work

### 1 — prepare the complete patch

Version the unreleased notes and add installed CLI and Mac sudo changes. Run
portable checks, release tests, the desktop build, and site release tests.
Commit and push main without including unrelated working edits.

### 2 — build and authenticate every platform

Dispatch the unified release workflow from the exact main source. Require both
Mac, Windows, and Linux targets, native tests, signatures, installed inventories,
relocated CLI smoke, provenance, and tamper rejection before publication.

### 3 — verify public delivery

Use the common release script and its verified-draft publication flow. Check
published assets and receipts, signed updater metadata, production update
responses, and every download route. Record exact source and workflow identity,
restore working edits, and keep execution gaps explicit.

## Validation and final result

**Current:** [Public desktop 0.5.3](https://github.com/kzahel/machine-control/releases/tag/desktop-v0.5.3)
contains Mac ARM64/Intel, Windows x64/ARM64, and Linux x64/ARM64 Debian/AppImage
packages. The exact source is `d5aa271ca93d890325a12b0906432b762a4aaec4`.
[Candidate run 37063349080](https://github.com/kzahel/machine-control/actions/runs/37063349080),
attempt 1, built and authenticated all six targets.
[Promotion run 37066468328](https://github.com/kzahel/machine-control/actions/runs/37066468328)
published those verified artifacts without rebuilding.

All 29 downloaded public assets match their GitHub SHA-256 digests and expected
sizes. All six build receipts bind version, source, candidate run and attempt.
Mac publisher signatures, notarization and staples authenticate; Windows
installer signatures and installed publisher catalogs authenticate; Linux
Debian/AppImage signatures and complete extracted inventories authenticate.
Package tamper rejection passes. Every CLI payload passes authenticated offline
relocation smoke in CI, including native Windows ARM64 execution. This remains
package/CLI evidence rather than new GUI control acceptance.

The public updater manifest contains exactly six signed platform entries.
All eight download redirects select the correct versioned assets. The public
download page selects 0.5.3. All 24 production update responses across the site
proxy and shared update service return matching signed metadata for 0.5.0
clients and HTTP 204 for current 0.5.3 clients.

Portable release regression tests pass (61 tests), alongside workflow lint and
source checks. CI passes required Windows contract tests, format verification,
x64/ARM64 publishes, strict Rust checks, native platform tests, signed-package
verification and installed CLI checks. Earlier GUI and physical-host coverage
retains its own versions in the
[desktop acceptance matrix](../desktop-acceptance.md). Unrelated working edits
were restored exactly after the clean-checkout promotion.

### Packaging failures resolved before publication

The initial 0.5.1 attempt caught a strict Rust signal-handler cast lint in the
Mac sudo helper. Cast through a function pointer without changing behavior.
The 0.5.2 attempt exposed ARM64 Python acceptance scheduled on an x64 Windows
runner; move that build and installed smoke to native `windows-11-arm`.
Both failed attempts remain immutable, unpublished tags. Build 0.5.3 as a
complete candidate before tagging.

Linux deployment rewrites ELF files beneath `usr/lib`, breaking pinned Python
inventory hashes. Supported custom-file mappings place the CLI beneath
`usr/share/machine-control/mc-cli` in Debian and AppImage; final extracted
payloads retain every byte and pass relocation. Exact CLI hashes allow valid
empty package files. The versioned resident allowlist requires the newly
shipped `updates.py`; authenticated acceptance and missing-module refusal have
regression coverage.

Windows SIP hashing refuses an upstream stripped Python DLL. Publisher-sign a
catalog over the full-byte SHA-256 inventory, then authenticate that catalog
and every listed file while refusing unexpected files. Tauri's bundle-only
hook preserves those catalog-authenticated PE resources; other native files,
the app, uninstaller and installer retain strict Authenticode signing. Install
the signing DLL's required x64 .NET runtime on ARM64 from its official
SHA-512-verified archive, without replacing the native build SDK.

Tauri's indirect child inherits PowerShell 7 module paths that prevent the
legacy Windows PowerShell host from loading its security module. Use CI's
absolute PowerShell 7 executable for the bundle hook. Preflight it through an
indirect child that preserves that environment, covering absolute, relative
and alternate-separator resource paths. Final installed acceptance independently
authenticates the publisher, timestamp, complete inventory and relocated CLI;
no trust check or pinned runtime byte was relaxed to obtain a passing build.
