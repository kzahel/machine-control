# 063 — Six-platform desktop 0.5.3 release

Status: in progress.

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

The initial 0.5.1 attempt at `fc10c83` caught a strict Rust lint in the
new Mac sudo helper: a function item was cast directly to the integer signal
handler type. Cast through a function pointer without changing delivery or
authentication behavior. Cancel the doomed workflow; preserve its annotated
`desktop-v0.5.1` tag and do not publish partial packages. Restart every build
at one repaired source as 0.5.3. Source review of the second attempt found that the ARM64 Windows installed
CLI smoke would execute ARM64 Python on an x64 runner. Cancel 0.5.2 before
publication and preserve its tag too. Build that architecture on GitHub's
native `windows-11-arm` runner, keeping every catalog, publisher, inventory,
relocation and execution check required. Build the full 0.5.3 matrix as a
candidate before creating its release tag. Public verification remains pending.

The first 0.5.3 candidate builds both Linux containers but refuses their CLI
payload hashes. Upstream linuxdeploy rewrites every ELF beneath `usr/lib`,
including bundled Python resources. Use its supported custom-file mappings to
put the CLI under `usr/share/machine-control/mc-cli` in both Debian and AppImage.
Keep staged hashes, require the installed CLI for this version, and run the
relocation smoke from each extracted final container before signing evidence.
Mac and Windows resource locations remain the same.

Windows x64 reaches CLI catalog creation, where Windows SIP hashing cannot
catalog the upstream stripped `zlib1.dll`. Catalog and publisher-sign the
complete full-byte SHA-256 inventory instead. Final installed acceptance must
authenticate that catalog first, verify every inventoried file and refuse
unexpected files, then execute relocated CLI smoke. This preserves publisher
trust without changing pinned runtime bytes or excluding native dependencies.

The native Windows ARM64 runner also needs the x64 .NET 8 runtime used by
Microsoft's x64 signing DLL. Install its official SHA-512-verified runtime
installer, verify the registered x64 host/runtime, and set only DOTNET_ROOT_X64;
the native ARM64 build SDK and interpreter remain unchanged. Both Mac signed
candidates from the first 0.5.3 run pass notarization and CLI relocation.
A repaired unified candidate must still rebuild every platform at one source.
