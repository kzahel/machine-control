# Android local workspace and document access

Experimental Java boundary, exercised by the sibling Yep Anywhere disposable
`packages/android-host/workspace-spike` app and experimental host. Include
`src/main/java` and retain this repository's MIT notice when packaging it. It has no third-party runtime
dependencies and requires Android API 30+.

`LocalWorkspace.resolve` accepts only a persisted read/write tree grant from
Android's built-in external-storage provider on the primary shared volume.
It separately checks actual all-files access, obtains the volume through
StorageManager, rejects traversal and Android app-specific storage, and checks
the selected document's identity/type/name against an accessible canonical local
directory. Document IDs are interpreted only for this explicitly qualified
provider, never as a general SAF path contract.

The caller must independently prove byte identity on an owned fixture, recheck
before starting new work, and propagate subsequent filesystem errors. There is
no filesystem mount, synchronization, write cache, permission request or private
fallback. This resolver does not constrain an all-files-authorized app UID to the
returned directory. Holding a path or open descriptor is not a revocable grant.

Direct mapping of removable volumes and arbitrary document providers is
unsupported. File recovery after reset requires a new user selection and permissions, not a marker
written into the selected project. YA owns product onboarding and runtime mapping.

## Explicit SAF operations

`SafDocuments` supplies persisted read/write tree-grant operations without broad
storage access: stat/list, mkdir, same-parent rename, delete and bounded stream
read/write. Paths are relative, reject traversal and ambiguous duplicate names,
and do not imply POSIX semantics. Deleting a directory requires explicit
recursive intent. Existing documents require explicit replacement; creation and
rename reject provider-altered names rather than reporting the requested name
as success. Failures after provider mutation can leave partial/renamed documents.

Limits are 32 path components, 4096 path characters, 2048 directory children and
64 MiB per transfer. Owned descriptors/cursors close per operation; queries and
opens receive cancellation. No native handles are cached. Callers must bound
concurrency, supply complete upload bytes before invoking write, enforce caller
authority and report provider-specific failures. A successful close/write is not
a promise of cloud upload, crash safety, fsync, general rename atomicity or
rollback. Provider mutation APIs do not all accept CancellationSignal; a blocked
provider is not made preemptible by this wrapper.

YA's installed `ya saf` CLI consumes this boundary over a same-app-UID native
bridge, against the same named registrations as optional direct PRoot mappings.
YA owns UI, transport deadlines, upload spooling, names and mapping restarts.
No JSTorrent or Web Server Chrome source was copied; retain MC's MIT notice.

## Evidence

Built and live-tested through YA's separate disposable Android fixture on Pixel
7a/API 37 (2026-10-18): actual picker and all-files Settings consent, independent
SAF/raw identity witness, both real CLIs, externally checked hashes, process
restart, separate grant/authority repair, data-clear and reinstall recovery.
[YA acceptance](../../../../yepanywhere/packages/android-host/workspace-spike/README.md#evidence)
owns the measured filesystem limits and commands. Later multi-root host
acceptance is documented in
[YA workspaces](../../../../yepanywhere/packages/android-host/docs/workspaces.md).
That host run passed two selected roots, SAF CRUD/transfers without broad
permission, real Codex/Claude YA sessions writing across both direct mappings,
independent checks of 10 external files, per-root/broad permission repair,
controlled restart and fixture data-clear/reinstall recovery. An incomplete
transport upload preserved its destination before native mutation. Fixture,
owned trees and temporary authorization/transports were removed. Cloud/removable
providers and store-policy approval remain unqualified. The fixture packaged this
repository's MIT notice; no third-party reference code was imported.
