# Desktop 0.6.10 release

Owning topics: [native distribution](../../topics/native-distribution.md),
[browser control](../../topics/browser-control.md),
[Mac locked use](../../topics/macos-locked-use.md).

Status: active; source prepared for candidate acceptance and publication.

## Objective and completion conditions

The operator requested a new version after the remote-arming repair and small
Windows/Linux smoke checks. Publish one version for all six packaged desktop
architectures, contingent on a successful unified candidate and acceptance of
its exact signed Mac ARM64 package. Promote those bytes through the release
script, then report publication queued; CI owns automatic publication.

## Boundaries

No controller-workstation installation, extra Windows/Linux GUI campaign,
release overwrite or post-publication monitoring. Source-native development
and smoke evidence does not replace the packaged Mac receipt. Keep concrete
targets, raw evidence, credential locators and reviewer metadata private.

## Ordered work

1. Freeze meaningful 0.6.10 changelog notes on clean main and push the source.
2. Build the unified candidate and authenticate its final Mac ARM64 artifact.
3. Run the common CLI's claimed packaged Mac acceptance at that exact source,
   with three seeded browser cycles, a two-minute soak and all required fault
   cells. Verify restoration and original power; release the claim.
4. Pass the minimized exact-package receipt and candidate run to
   `desktop/scripts/release.sh` once. Report the queued workflow without
   waiting for public delivery.

## Validation and result

[Tactical 138](138-remote-arming-recovery.md) owns the signed Mac development
fault campaign and ten-check source-native Windows/Linux smoke results. Those
checks found and repaired Windows' missing typed-dialog scope mapping before
this release freeze. Windows format/contracts and both architecture publishes
pass. Exact signed-package acceptance and publication are separate gates under
[the release guide](../../release/desktop.md); this prepared source does not
claim they have already passed. The private controller receipt and workflow
records establish subsequent outcomes without putting raw VM evidence here.
