# Desktop releases

One desktop version, required changelog, annotated `desktop-vX.Y.Z` tag, and
release script cover every currently packaged platform: Mac Apple silicon and
Intel, Windows x64 and ARM64, and from 0.5.0 Linux x64 and ARM64.
Workstation components remain independent. Public desktop 0.6.9 includes all
six architectures; the acceptance matrix distinguishes packaging from GUI execution.
The [0.6.9 release record](../docs/tactical/137-desktop-0.6.9-release.md)
owns exact source, workflow identities, public authentication and delivery.

## Release

1. Add meaningful versioned notes to [the changelog](../desktop/CHANGELOG.md).
2. Commit and push main. Run source checks and native acceptance appropriate to
   the change; keep architecture and physical-hardware execution gaps explicit.
3. From a clean main checkout matching origin, run:

   ```bash
   desktop/scripts/release.sh VERSION CANDIDATE_RUN_ID /private/path/acceptance.json
   ```

From 0.6.9, first complete the packaged candidate acceptance below. Earlier
versions retain the historical one-argument flow. The script validates
increasing versions, required notes and the acceptance envelope, pushes an immutable
annotated tag, and dispatches `desktop-release.yml`. Its reusable Mac, Windows and Linux
jobs build all six targets at the same source, version, and workflow attempt.
Protected signing runs only on main. Mac packages are signed, notarized, and
stapled; Windows app, uninstaller, installer, provider, and runtime catalog are
signed. All families authenticate updater signatures and signed versions.

The default is fire-and-forget: the script returns after dispatch, and CI
publishes automatically when every required check succeeds. Report the release
as queued and provide the [workflow link](https://github.com/kzahel/machine-control/actions/workflows/desktop-release.yml).
Waiting for publication, repairing failed builds, and independent public-download
or installation checks remain opt-in. A failed build
or verification prevents publication. Pushing a tag alone does not start this
workflow; use the script, which also dispatches the protected main-only workflow.

Publication revalidates every package, receipt, source, version and workflow
identity. It stages every installer, Linux Debian/AppImage package, Mac update archive,
signature, build receipt, installed payload inventory, and one Tauri
`latest.json`.
A draft becomes public only after its complete uploaded asset set and GitHub
SHA-256 digests match. Missing targets fail publication; tags, drafts and
published assets are never overwritten. It preserves the repository-wide latest
pointer and the existing product update endpoint.

## Accept a candidate before publication

This is required from 0.6.9 for the Mac ARM64 packaged browser/crash slice.
Other platform GUI acceptance remains distinct from package verification.

Build the entire release matrix without creating a tag or public release:

```bash
gh workflow run desktop-release.yml --ref main -f version=VERSION
```

Download the successful unified run's `macos-desktop-aarch64-apple-darwin`
artifact to a private directory. At that exact clean source, run the controller
harness against a prepared dedicated VM with Chrome for Testing, an unlocked
session, an existing healthy standing resident, and normal Developer ID TCC
consent. It verifies updater signatures, notarization and bundle identity before
installation, temporarily selects the stricter workstation policy, and restores
the original app/policy/LaunchAgent/operator state and original power state.

```bash
bin/machine-control --target macos run \
  --reason 'Accept exact packaged desktop candidate' \
  --claimant-authority release-maintainer --claimant-id packaged-acceptance \
  --duration 30m -- python3 tests/macos/packaged-acceptance.py \
  --package-directory /private/path/candidate --team-id EXPECTED_TEAM \
  --output /private/path/new-evidence --repeat 5 --seed 3407 \
  --soak-seconds 300 --faults
```

Use real controller-private paths and the expected publisher identity; these
examples do not identify infrastructure. Evidence stays outside the checkout.
The harness exercises downloads/uploads, native dialogs, Settings recreation,
native-host loss, Stop during a blocked provider, forced app-exit recovery,
stale-reference refusal and actual operator crash-report preview/export. A
passing complete run emits minimized `acceptance.json`; `--app --development`
supports local builds but cannot emit a qualifying release receipt. Failed or
uncertain restoration retains guest backups and fails acceptance.

No CI runner currently reaches the prepared VM. This is maintainer/controller
attestation of execution, not a claim that hosted CI ran the GUI or independently
attested the machine. The receipt contains only closed coverage, source/version,
workflow attempt, archive hash, seed/counts and cleanup status. No target names,
endpoints, raw logs, screenshots or crash reports are accepted. Hosted CI verifies
that receipt against the exact authenticated Mac archive before publication.

To publish those same bytes without another build:

```bash
desktop/scripts/release.sh VERSION CANDIDATE_RUN_ID /private/path/new-evidence/acceptance.json
```

The run must be a successful unified dispatch on main at the exact
release source. The original workflow attempt is bound by every package receipt.
Candidates also authenticate all final packages and stage the complete public
asset set before passing; an empty release tag skips publication only.
Public Windows installer names omit spaces to avoid GitHub filename rewriting;
build receipts retain original candidate names and hashes. Verify downloaded
release assets with `windows-package.py verify --published --target TARGET`
and the expected version, source, and original workflow identity.

Expired/missing artifacts fail closed. A newer main commit requires a new
candidate; never move a release tag to work around source validation.

Mac signed builds retain separate `macos-symbols-TARGET` CI artifacts for ninety
days. Each archive contains source/version, executable/framework UUIDs, dwarf
hashes and both nonempty dSYMs. The build collects Swift symbols before temporary
objects disappear, strips product debug maps, then verifies UUIDs again after
signing. Symbol artifacts are excluded from published installer assets.

For a failed dispatch after the tag was pushed, rerun the printed workflow
command at its original source. For a publication failure after draft creation,
authenticate the original packages and verify that draft by ID before completing
publication. Do not recreate it, replace its assets, or move its tag.

If final staging stops before draft creation because of a release-tooling
defect, repair the tooling and reauthenticate the original annotated tag,
source, successful candidate run, required notes, and all original packages.
Stage those exact bytes, check that no release/draft exists for the tag, upload
one draft, verify the complete asset set and GitHub digests, then publish it
by ID. A public filename mapping may change; original receipts and signed
payloads must stay intact. Record the repair and recovery in the tactical.

## Downloads and updates

The website selects the highest published numeric desktop release, excluding
drafts, prereleases and other package families. Unified releases from 0.5.0 require the
complete Mac, Windows and Linux set; historical Mac-only releases remain readable.
Stable download paths are:

- `/download/macos/arm64` and `/download/macos/x86_64`;
- `/download/windows/x64` and `/download/windows/arm64`.
- `/download/linux/amd64/appimage` and `/download/linux/arm64/appimage`, with
  corresponding `/deb` paths for Debian packages.

The shared update server consumes the same `latest.json` and product registration
for `darwin-aarch64`, `darwin-x86_64`, `windows-aarch64`, `windows-x86_64`,
`linux-aarch64`, and `linux-x86_64`.
The website proxies supported target/architecture requests to the existing
product route. Installation remains explicit and refuses active access or
pending approvals. Website deployment and installed production-feed acceptance
are verified separately from package publication.

Public 0.5.4 has focused ARM64 Windows installed grant and production-update
acceptance. The [acceptance matrix](../docs/desktop-acceptance.md) distinguishes
that slice from broader lifecycle, browser, and physical-hardware coverage.

Linux native Ubuntu 24.04 runners build Debian and AppImage packages, sign both
final containers with the product updater key and authenticated version, and
inventory the extracted product payloads. Publication requires both architectures
with the same source/workflow as Mac and Windows. AppImage is the Linux in-place
updater format; Debian installation follows the system package manager.
The unified manifest adds `linux-x86_64` and `linux-aarch64`. Historical releases
before 0.5.0 retain their original Mac/Windows requirements.
