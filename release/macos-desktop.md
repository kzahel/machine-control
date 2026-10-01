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

The app's `machinecontrol.dev/updates/tauri/...` route remains reserved until
that routing is deployed. Publication alone does not deploy the update server.
Installed production-feed update acceptance remains open. Native code requires
access and pending approvals to be off before bundle replacement, and verifies
the updater signature and its trusted version.

## Verify completion

Check the successful workflow, public tag, downloaded package authenticity,
website redirects for both architectures, and the intended updater response
before calling a publication accepted. The first public publication has not
been executed by the infrastructure change alone.
