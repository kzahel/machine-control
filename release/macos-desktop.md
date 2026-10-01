# Mac desktop publication

The desktop release entry point follows lid-awake's clean-checkout and changelog
pattern. Tags use `desktop-vX.Y.Z`, independently of `workstation-vX.Y.Z`
Windows component releases. Both Mac architectures publish together.

## Release

1. Add a version section to [the desktop changelog](../desktop/CHANGELOG.md).
   Validate the intended signed candidate in the dedicated Tart testbed through
   the common CLI, with doctor, a claim, and cleanup. The CI packaging checks do
   not replace native application acceptance.
2. Commit and push the source and notes to `main`. The local checkout must be
   clean and match `origin/main`.
3. From the repository root, run:

   ```bash
   desktop/scripts/release.sh 0.3.3
   ```

Every publication requires exactly one `## [X.Y.Z]` changelog section with
at least one nonempty change bullet. Missing, duplicate, empty, and placeholder
notes are refused locally and in CI. The checked-in section becomes both the
GitHub release body and the updater metadata notes.

The script validates a strictly increasing version and release notes, creates
and pushes an annotated tag, then dispatches `macos-desktop.yml` from `main`
with that tag and version. CI requires the tag to point to the exact workflow
source commit. A concurrent main push can make dispatch fail this identity
check; rerun the original workflow rather than moving the tag. The release
signing environment retains its existing main-only policy. For a retry, rerun
all jobs so both architecture receipts share the same workflow attempt.

CI runs source checks, builds Apple silicon and Intel, signs/notarizes/staples
both apps and DMGs, and authenticates the final updater archives. Publication
reverifies both candidates, their source/version/run identity, and the complete
asset set. It rechecks the remote tag and creates a draft. GitHub's uploaded
asset hashes and sizes must match before that draft becomes public. Existing
drafts/releases are refused; published bytes and tags are never replaced.
A publication failure leaves its draft for diagnosis, not automatic clobbering.
Draft verification and publication use the release ID; GitHub's by-tag endpoint
resolves published releases. Recovery must authenticate the original CI
packages and verify the existing draft's source, notes and complete asset hashes
before publishing it. Do not recreate the draft or move the tag.

The release includes:

- versioned Apple silicon and Intel DMGs;
- both authenticated `.app.tar.gz` archives and updater signatures;
- separate architecture build receipts; and
- standard Tauri `latest.json` with version-pinned URLs and signatures.

The publication has a numeric version and is a normal GitHub release so the
Stable update contract can select it. The app remains explicitly labelled a
developer preview. It does not change GitHub's repository-wide latest pointer,
which is also used by the independently released Windows component.

An empty `release_tag` retains signed **CI candidate only** behavior:

```bash
gh workflow run macos-desktop.yml --ref main -f version=0.3.3
```

## Website downloads

[The download page](https://machinecontrol.dev/downloads/) resolves published
`desktop-v` releases independently of other release families. It exposes:

- `/download/macos/arm64` — Apple silicon DMG;
- `/download/macos/x86_64` — Intel DMG.

These paths redirect to exact versioned GitHub assets and cache for five
minutes. Drafts and prereleases are excluded; numeric version ordering picks
the newest desktop release. Both installers, updater archives/signatures, and
`latest.json` must be present. An incomplete newest release fails closed rather
than silently selecting an older one. Before first publication the page shows
no public Mac release; upstream failures show temporary unavailability.
The website needs no rebuild for a new release.

## Updates

The public `latest.json` follows Desktop Release Kit's Tauri metadata contract.
The existing simple-app-update-server owns production update routing. Register
the product there using `githubRepo: kzahel/machine-control`,
`tagPrefix: desktop-v`, and `tauriUpdates: true`. Optional installer patterns are
`MachineControl_*_arm64.dmg` and `MachineControl_*_x86_64.dmg`.
Concrete host/path configuration and proxy deployment belong in private
infrastructure configuration.

The product configuration is [update-server/machine-control.json](../update-server/machine-control.json).
Deploy it through the shared server's product-config directory. The website
proxies `machinecontrol.dev/updates/tauri/...` to the product's public shared
server route. The proxy accepts only supported Mac targets and numeric versions,
forwards optional anonymous check metadata, and does not forward website
credentials. Publication alone does not deploy the server or website.
The first installed production-feed update is tracked in tactical 052. Native code requires
access and pending approvals to be off before bundle replacement, and verifies
the updater signature and its trusted version.

## Verify completion

Check the successful workflow, public tag, downloaded package authenticity,
website redirects for both architectures, and the published updater metadata
before calling package publication accepted. Production in-app updates require
separate feed deployment and installed-update acceptance.

The first public preview is
[`desktop-v0.3.3`](https://github.com/kzahel/machine-control/releases/tag/desktop-v0.3.3),
from source `15dbb63471dda2938cc9d2de905d28c33a8a2ef3`. The exact signed
[candidate](https://github.com/kzahel/machine-control/actions/runs/36817620234)
passed ARM64 Tart native UI and signed-upgrade acceptance. The
[publication run](https://github.com/kzahel/machine-control/actions/runs/36820029330)
passed both final package builds and staging, then left a complete draft when
its by-tag lookup returned 404. Verified recovery published that same draft by
ID after checking all nine uploaded assets, source identity, changelog and
updater metadata. The workflow now uses IDs for draft verification/publication.
Public package and website download verification is recorded in the
[native distribution topic](../topics/native-distribution.md).
The production route is deployed and returns signed metadata for older clients
and 204 for current clients on both Mac architectures. Installed 0.3.3 to
0.3.4 production acceptance remains in progress.

[Tactical 052](../docs/tactical/052-macos-production-updates.md) owns deployment
and the first production-feed update acceptance.

## 0.3.4 publication gate

The signed candidate passed both architecture authentication and claimed
ARM64 Tart operator/tray acceptance. The immutable `desktop-v0.3.4` tag exists,
but [tagged CI](https://github.com/kzahel/machine-control/actions/runs/36830572285)
stopped before publication: Apple returned HTTP 403 for a missing or expired
agreement on both notarization requests. The Account Holder must resolve that
account gate. Verify read-only notarization access, then rerun **all jobs** of
that existing run with `gh run rerun 36830572285`; do not recreate or move the
tag. Both receipts must have the same new workflow attempt. Public package and
installed-update acceptance follow. 0.3.3 remains the latest public release.
