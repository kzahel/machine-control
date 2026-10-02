# Desktop releases

One desktop version, required changelog, annotated `desktop-vX.Y.Z` tag, and
release script cover every currently packaged platform: Mac Apple silicon and
Intel, Windows x64 and ARM64, and from 0.5.0 Linux x64 and ARM64.
Workstation components remain independent. Public desktop 0.5.0 includes all
six architectures; the acceptance matrix distinguishes packaging from GUI execution.

## Release

1. Add meaningful versioned notes to [the changelog](../desktop/CHANGELOG.md).
2. Commit and push main. Run source checks and native acceptance appropriate to
   the change; keep architecture and physical-hardware execution gaps explicit.
3. From a clean main checkout matching origin, run:

   ```bash
   desktop/scripts/release.sh 0.5.0
   ```

The script validates increasing versions and required notes, pushes an immutable
annotated tag, and dispatches `desktop-release.yml`. Its reusable Mac, Windows and Linux
jobs build all six targets at the same source, version, and workflow attempt.
Protected signing runs only on main. Mac packages are signed, notarized, and
stapled; Windows app, uninstaller, installer, provider, and runtime catalog are
signed. All families authenticate updater signatures and signed versions.

Publication revalidates every package, receipt, source, version and workflow
identity. It stages every installer, Linux Debian/AppImage package, Mac update archive,
signature, build receipt, installed payload inventory, and one Tauri
`latest.json`.
A draft becomes public only after its complete uploaded asset set and GitHub
SHA-256 digests match. Missing targets fail publication; tags, drafts and
published assets are never overwritten. It preserves the repository-wide latest
pointer and the existing product update endpoint.

## Accept a candidate before publication

Build the entire release matrix without creating a tag or public release:

```bash
gh workflow run desktop-release.yml --ref main -f version=0.5.0
```

Download exact workflow artifacts and run native acceptance through claimed
Machine Control targets. To publish those same bytes without another build:

```bash
desktop/scripts/release.sh 0.5.0 CANDIDATE_RUN_ID
```

The optional run must be a successful unified dispatch on main at the exact
release source. The original workflow attempt is bound by every package receipt.
Candidates also authenticate all final packages and stage the complete public
asset set before passing; an empty release tag skips publication only.
Public Windows installer names omit spaces to avoid GitHub filename rewriting;
build receipts retain original candidate names and hashes. Verify downloaded
release assets with `windows-package.py verify --published --target TARGET`
and the expected version, source, and original workflow identity.

Expired/missing artifacts fail closed. A newer main commit requires a new
candidate; never move a release tag to work around source validation.

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

Public ARM64 Windows availability does not imply native execution acceptance.
The [acceptance matrix](../docs/desktop-acceptance.md) records that distinction.

Linux native Ubuntu 24.04 runners build Debian and AppImage packages, sign both
final containers with the product updater key and authenticated version, and
inventory the extracted product payloads. Publication requires both architectures
with the same source/workflow as Mac and Windows. AppImage is the Linux in-place
updater format; Debian installation follows the system package manager.
The unified manifest adds `linux-x86_64` and `linux-aarch64`. Historical releases
before 0.5.0 retain their original Mac/Windows requirements.
