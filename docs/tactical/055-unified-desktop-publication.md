# Unified desktop publication

Topic: native-distribution
Owning topics: [native distribution](../../topics/native-distribution.md),
[Windows desktop](../../topics/windows-desktop.md)
Status: complete; public 0.4.8 and available native production updates accepted

## Objective

Publish Windows x64 and ARM64 alongside Mac using one release script, version,
required changelog, tag, and updater manifest. Preserve existing Mac updates.

## Completion conditions

- One entry point builds or promotes exact signed packages for all four targets.
- A complete verified draft publishes once; missing or mixed-source targets fail.
- Public downloads expose both Windows architectures and retain both Mac routes.
- Production update metadata serves all four architectures and current clients.
- Available Mac ARM64 and Windows x64 VM tests exercise exact signed packages
  and production replacement; ARM64 Windows execution remains an honest gap.
- Claims, testbed power, original applications, and temporary staging are restored.

## Boundaries

No Linux implementation, privileged-service installation, or new hardware claim.
The user explicitly requests Windows ARM64 publication despite its native
execution gap. Signing and byte verification remain required for every target.
Concrete infrastructure, claims, credentials and raw evidence remain private.

## Ordered work

### 1 — unify package publication

Reuse platform build jobs under one main-only workflow. Authenticate all package
identities and bytes, stage a four-platform manifest, and verify the complete
draft. Allow exact successful unified candidates to be promoted without rebuilding.

### 2 — expose platform downloads and updates

Extend the existing website selector and proxy. Preserve historical Mac releases
and the shared server's product registration. Require versioned release notes.

### 3 — accept and publish the release

Run local release/site/source checks, build signed 0.4.8, and accept available
native VMs. Publish through the single script, verify public assets/routes, and
exercise installed production updates before restoring testbeds.

## Validation and result

Public [desktop-v0.4.8](https://github.com/kzahel/machine-control/releases/tag/desktop-v0.4.8)
is bound to source `b008d95190e1d768985cdf8e3820d043e9d60d81`.
The [unified candidate run](https://github.com/kzahel/machine-control/actions/runs/36956108893)
passed all source checks, both Mac signing/notarization jobs, both Windows
signing/install jobs, and independent updater authentication. The
[publication run](https://github.com/kzahel/machine-control/actions/runs/36958691848)
promoted those exact attempt-1 bytes without rebuilding. Every candidate receipt
retains `36956108893.1`; publication also binds the immutable annotated tag,
required changelog and complete uploaded asset hashes.

All 17 public assets are verified. Re-downloaded installers and update packages
match accepted candidates byte for byte and pass updater signed-version/tamper
checks; both Mac families also pass publisher, Gatekeeper and stapling checks.
Public Windows names omit spaces to avoid GitHub asset rewriting, while original
receipts and signatures remain unchanged. Four stable download redirects select
0.4.8. Both shared-service and website update routing serve exact signed metadata
for older Mac/Windows clients and 204 for current clients on all architectures.

Local validation passed 48 release tests, eight website tests, the website build,
portable checks, workflow lint and shell syntax. No runtime code was changed in
this release workstream. The first candidate was cancelled before acceptance
when public asset naming was corrected; no tag or public bytes were replaced.

Available native acceptance:

- ARM64 Tart accepted installed 0.3.5 to candidate 0.4.8 replacement, permission
  retention, revoked access, new generation and stale references; native UI
  approvals/narrowing/denial, independent fixture effects, prompt-time input
  pause, self/protected refusal, tray commands, emergency Stop and Quit passed.
- Windows x64 accepted 128 installed UI checks, 65 browser checks, 78 held-image
  uninstall-refusal checks and 11 ordinary uninstall checks with Chrome and an
  independent application alive. A first UI run omitted launching the silently
  installed operator; the corrected setup passed all 128 checks on the same
  exact signed candidate without a product change.
- Production Windows 0.4.7 to public 0.4.8 passed 122 browser/update checks with
  Chrome open: active-access exclusion, automatic relaunch, exact new payload,
  startup/registration/manifest retention, browser survival/reconnect, revoked
  access, stale-reference refusal and independent post-update effects. The final
  public install also passed the 11-check ordinary uninstall again.
- Production Mac 0.3.5 to public 0.4.8 automatically relaunched with retained
  permissions, access off, new generation and stale references rejected. Native
  Permissions Restart, operator/tray/approval/fixture/Stop/Quit checks passed.

Windows ARM64 signing, payload bytes and updater authentication pass; native
ARM64 Windows execution remains untested. Intel Mac and physical product
execution remain separate gaps. Linux packaging is not implemented.

Original Mac application, appliance policy, LaunchAgent and suspended power
state were restored, and claims released. Windows owned installs, registrations,
startup, browser profiles, fixture staging and clipboard text were removed;
its original appliance doctor passed, stored login credential was verified,
and original off state and released claim were restored. Raw evidence remains
private. [The acceptance matrix](../desktop-acceptance.md) retains older-version
execution evidence separately rather than silently relabelling it as 0.4.8.
