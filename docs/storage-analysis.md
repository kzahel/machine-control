# Disk image and prune analysis

`bin/machine-control storage analyze` inspects known controller VM libraries,
application-managed disks, emulator images, current platform factory storage,
and sibling legacy factory storage. It works offline, including after a target
has disappeared from the registry. Installed CLI packages include the analyzer.

```bash
bin/machine-control storage analyze
bin/machine-control storage analyze --root /private/image-library
bin/machine-control storage analyze --root /private/image-library --root /private/exports
```

Explicit roots replace the defaults. Select a parent directory to inspect
arbitrary locations. The scanner includes hidden directories, skips symlinks
and secret-store directories, deduplicates hardlinks and overlapping roots,
and never opens image contents or launches a provider. Paths and sizes are
private operator output; do not commit it. JSON reports coverage, permission
failures, bounds, allocation and volume free space. `--minimum-bytes`,
`--max-files`, and `--max-results` bound the scan.

Logical capacity differs from allocated storage. POSIX allocation is
`st_blocks * 512`; where unavailable it is null. APFS clones and snapshots can
share extents, so summed allocation does not promise that many newly free
bytes after deletion. Exclusive and reclaimable bytes remain unknown.

`factory_artifact_review` identifies factory staging for review; it does not
establish orphan status. Other categories distinguish provider disks,
application-managed disks, development images and remaining images. The
analyzer never deletes or changes registration, claims, credentials or
receipts. Workspace pruning stays with `workspace gc --dry-run`.

Before deleting, establish exact identity, live-use and backing-image
dependencies, retained-source role, private inventory references, and explicit
operator intent. Stop an owned running VM through its claimed lifecycle first.
A filename, age or absence from one provider library is insufficient deletion
authority. Remove only the selected artifact and matching manifest; preserve
canonical credentials for retained VMs. Remeasure volume free space afterward.
