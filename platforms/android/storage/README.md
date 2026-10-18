# Local Android workspace qualification

Experimental Java boundary, exercised by the sibling Yep Anywhere disposable
`packages/android-host/workspace-spike` app. Include `src/main/java` and retain
this repository's MIT notice when packaging it. It has no third-party runtime
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

Removable volumes and arbitrary document providers are unsupported. File
recovery after reset requires a new user selection and permissions, not a marker
written into the selected project. YA owns product onboarding and runtime mapping.

## Evidence

Built and live-tested through YA's separate disposable Android fixture on Pixel
7a/API 37 (2026-10-18): actual picker and all-files Settings consent, independent
SAF/raw identity witness, both real CLIs, externally checked hashes, process
restart, separate grant/authority repair, data-clear and reinstall recovery.
[YA acceptance](../../../../yepanywhere/packages/android-host/workspace-spike/README.md#evidence)
owns the measured filesystem limits and commands. This is not adoption into YA's
production host or general SAF-provider support. The fixture packaged this
repository's MIT notice; no third-party reference code was imported.
