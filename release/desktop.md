# Desktop releases

One desktop version, required changelog, annotated `desktop-vX.Y.Z` tag, and
release script cover every currently packaged platform: Mac Apple silicon and
Intel, and Windows x64 and ARM64. Linux joins this same release matrix when its
standalone product is implemented. Workstation components remain independent.

## Release

1. Add meaningful versioned notes to [the changelog](../desktop/CHANGELOG.md).
2. Commit and push main. Run source checks and native acceptance appropriate to
   the change; keep architecture and physical-hardware execution gaps explicit.
3. From a clean main checkout matching origin, run:

   ```bash
   desktop/scripts/release.sh 0.4.8
   ```

The script validates increasing versions and required notes, pushes an immutable
annotated tag, and dispatches `desktop-release.yml`. Its reusable Mac and Windows
jobs build all four targets at the same source, version, and workflow attempt.
Protected signing runs only on main. Mac packages are signed, notarized, and
stapled; Windows app, uninstaller, installer, provider, and runtime catalog are
signed. Both families authenticate updater signatures and signed versions.

Publication revalidates every package, receipt, source, version and workflow
identity. It stages all four installers, Mac update archives, signatures, build
receipts, Windows installed payload inventories, and one Tauri `latest.json`.
A draft becomes public only after its complete uploaded asset set and GitHub
SHA-256 digests match. Missing targets fail publication; tags, drafts and
published assets are never overwritten. It preserves the repository-wide latest
pointer and the existing product update endpoint.

## Accept a candidate before publication

Build the entire release matrix without creating a tag or public release:

```bash
gh workflow run desktop-release.yml --ref main -f version=0.4.8
```

Download exact workflow artifacts and run native acceptance through claimed
Machine Control targets. To publish those same bytes without another build:

```bash
desktop/scripts/release.sh 0.4.8 CANDIDATE_RUN_ID
```

The optional run must be a successful unified dispatch on main at the exact
release source. The original workflow attempt is bound by every package receipt.
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

## Downloads and updates

The website selects the highest published numeric desktop release, excluding
drafts, prereleases and other package families. Unified releases require the
complete Mac and Windows set; historical Mac-only releases remain readable.
Stable download paths are:

- `/download/macos/arm64` and `/download/macos/x86_64`;
- `/download/windows/x64` and `/download/windows/arm64`.

The shared update server consumes the same `latest.json` and product registration
for `darwin-aarch64`, `darwin-x86_64`, `windows-aarch64`, and `windows-x86_64`.
The website proxies supported target/architecture requests to the existing
product route. Installation remains explicit and refuses active access or
pending approvals. Website deployment and installed production-feed acceptance
are verified separately from package publication.

Public ARM64 Windows availability does not imply native execution acceptance.
The [acceptance matrix](../docs/desktop-acceptance.md) records that distinction.
